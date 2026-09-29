"""Turn Jira issues into ticket folders (index.md, issue.json, _attachments/, _figures/)."""
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as html2md

from .util import cell, download_plain, fmt, fmt_dt, log, mdpath, safe_name, unique

ATT_RE = re.compile(r"/secure/(?:attachment|thumbnail)/(\d+)/")
BROWSE_RE = re.compile(r"/browse/([A-Z][A-Z0-9_]*-\d+)/?$")
TAG_RE = re.compile(r"<[a-zA-Z][^>]*>")

HEADER_FIELDS = [
    "project", "issuetype", "status", "resolution", "priority",
    "reporter", "creator", "assignee",
    "created", "updated", "resolutiondate", "duedate",
    "components", "labels", "versions", "fixVersions", "parent",
]
SECTION_FIELDS = {"summary", "description", "comment", "worklog", "attachment",
                  "issuelinks", "subtasks", "lastViewed"}


class Archiver:
    def __init__(self, client, projects, opts):
        self.c = client
        self.base = client.base
        self.host = urlparse(client.base).netloc
        self.projects = set(projects)
        self.opts = opts

    # ---- links

    def same_host(self, url):
        return urlparse(url).netloc == self.host

    def issue_link(self, key):
        proj = key.rsplit("-", 1)[0]
        if proj in self.projects:
            return f"../../{proj}/{key}/index.md"
        return f"{self.base}/browse/{key}"

    def issue_ref(self, ref):
        key = ref["key"]
        f = ref.get("fields") or {}
        status = fmt(f.get("status"))
        s = f"[{key}]({self.issue_link(key)}) {f.get('summary', '')}".rstrip()
        return f"{s} *({status})*" if status else s

    # ---- HTML -> Markdown with local resources

    def fetch_figure(self, src, ctx):
        if src in ctx.fig_cache:
            return ctx.fig_cache[src]
        same = self.same_host(src)
        if not same and not self.opts.fetch_external_images:
            return None
        name = unique(safe_name(Path(urlparse(src).path).name or "image"), ctx.used["_figures"])
        rel = f"_figures/{name}"
        try:
            (self.c.download if same else download_plain)(src, ctx.tmp / rel)
        except Exception as e:  # keep the original URL if the image can't be fetched
            log(f"    ! could not fetch image {src}: {e}")
            ctx.used["_figures"].discard(name.lower())
            return None
        ctx.fig_cache[src] = rel
        return rel

    def html_to_md(self, html, ctx):
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = urljoin(self.base + "/", a["href"])
            if self.same_host(href):
                if "ViewProfile.jspa" in href:          # user mention -> plain name
                    a.unwrap()
                    continue
                m = ATT_RE.search(href)
                if m and m.group(1) in ctx.att_local:
                    a["href"] = mdpath(ctx.att_local[m.group(1)])
                    continue
                m = BROWSE_RE.search(urlparse(href).path)
                if m:
                    a["href"] = self.issue_link(m.group(1))
                    continue
            a["href"] = href
        for img in soup.find_all("img", src=True):
            src = img["src"]
            if src.startswith("data:"):
                continue
            src = urljoin(self.base + "/", src)
            m = ATT_RE.search(src) if self.same_host(src) else None
            if m and m.group(1) in ctx.att_local:        # thumbnails resolve to the full image
                img["src"] = mdpath(ctx.att_local[m.group(1)])
                continue
            local = self.fetch_figure(src, ctx)
            img["src"] = mdpath(local) if local else src
        md = html2md(str(soup), heading_style="ATX", bullets="-")
        return re.sub(r"\n{3,}", "\n\n", md).strip()

    # ---- data collection

    def collect(self, key):
        c = self.c
        issue = c.get(f"/rest/api/2/issue/{key}", expand="renderedFields,names,schema,changelog")
        key = issue["key"]
        data = {
            "issue": issue,
            "comments": list(c.paged(f"/rest/api/2/issue/{key}/comment", "comments",
                                     expand="renderedBody")),
            "worklogs": list(c.paged(f"/rest/api/2/issue/{key}/worklog", "worklogs")),
            "remotelinks": c.get_optional(f"/rest/api/2/issue/{key}/remotelink") or [],
            "watchers": c.get_optional(f"/rest/api/2/issue/{key}/watchers"),
            "votes": c.get_optional(f"/rest/api/2/issue/{key}/votes"),
            "properties": {},
        }
        for p in (c.get_optional(f"/rest/api/2/issue/{key}/properties") or {}).get("keys", []):
            val = c.get_optional(f"/rest/api/2/issue/{key}/properties/{p['key']}")
            data["properties"][p["key"]] = (val or {}).get("value")
        if self.opts.dev_status:
            iid = issue["id"]
            dev = {"summary": c.get_optional("/rest/dev-status/1.0/issue/summary", issueId=iid)}
            for dt in ("repository", "branch", "pullrequest"):
                dev[dt] = c.get_optional("/rest/dev-status/1.0/issue/detail", issueId=iid,
                                         applicationType="stash", dataType=dt)
            data["devStatus"] = dev
        return data

    # ---- one ticket

    def archive(self, key, pdir):
        data = self.collect(key)
        issue = data["issue"]
        key = issue["key"]
        dest = pdir / key
        tmp = Path(tempfile.mkdtemp(prefix=f".{key}-", dir=pdir))
        try:
            self._write(data, tmp)
            if dest.exists():
                shutil.rmtree(dest)
            tmp.rename(dest)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        f = issue["fields"]
        return {"key": key, "summary": f.get("summary", ""), "type": fmt(f.get("issuetype")),
                "status": fmt(f.get("status"))}

    def _write(self, data, tmp):
        issue, comments = data["issue"], data["comments"]
        key, f = issue["key"], issue["fields"]
        names = issue.get("names") or {}
        schema = issue.get("schema") or {}
        rendered = issue.get("renderedFields") or {}

        (tmp / "_attachments").mkdir()
        (tmp / "_figures").mkdir()
        (tmp / "issue.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")

        # rich-text fields = string fields whose rendered form is HTML
        rich = {fid: html for fid, html in rendered.items()
                if isinstance(html, str) and TAG_RE.search(html)
                and (schema.get(fid) or {}).get("type") == "string"}
        html_sources = list(rich.values()) + [cm.get("renderedBody") or "" for cm in comments]

        # which attachments are embedded inline as images?
        fig_ids = set()
        for h in html_sources:
            for img in BeautifulSoup(h, "html.parser").find_all("img", src=True):
                m = ATT_RE.search(img["src"])
                if m:
                    fig_ids.add(m.group(1))

        ctx = SimpleNamespace(tmp=tmp, att_local={}, fig_cache={},
                              used={"_attachments": set(), "_figures": set()})
        atts = f.get("attachment") or []
        for a in atts:
            folder = "_figures" if a["id"] in fig_ids else "_attachments"
            ctx.att_local[a["id"]] = f"{folder}/{unique(safe_name(a['filename']), ctx.used[folder])}"
        for a in atts:
            target = tmp / ctx.att_local[a["id"]]
            self.c.download(a["content"], target)
            if a.get("size") is not None and target.stat().st_size != a["size"]:
                log(f"    ! size mismatch for attachment {a['filename']}")

        L = [f"# {key}: {f.get('summary', '')}", "",
             f"Original: <{self.base}/browse/{key}>  ",
             f"Archived: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", "",
             "| Field | Value |", "|---|---|"]
        for fid in HEADER_FIELDS:
            v = f.get(fid)
            if fid == "parent" and v:
                val = self.issue_ref(v)
            elif (schema.get(fid) or {}).get("type") == "datetime":
                val = fmt_dt(v)
            else:
                val = fmt(v)
            if val:
                L.append(f"| {cell(names.get(fid, fid))} | {cell(val)} |")

        if "description" in rich:
            L += ["", "## Description", "", self.html_to_md(rich["description"], ctx)]
        for fid, html in sorted(rich.items(), key=lambda kv: names.get(kv[0], kv[0])):
            if fid != "description":
                L += ["", f"## {names.get(fid, fid)}", "", self.html_to_md(html, ctx)]

        skip = set(HEADER_FIELDS) | SECTION_FIELDS | set(rich)
        details = []
        for fid, v in f.items():
            if fid in skip:
                continue
            val = fmt_dt(v) if (schema.get(fid) or {}).get("type") == "datetime" else fmt(v)
            if val:
                details.append((names.get(fid, fid), fid, val))
        if details:
            L += ["", "## Details", "", "| Field | Id | Value |", "|---|---|---|"]
            L += [f"| {cell(n)} | {fid} | {cell(val)} |" for n, fid, val in sorted(details)]

        if f.get("subtasks"):
            L += ["", "## Sub-tasks", ""] + [f"- {self.issue_ref(s)}" for s in f["subtasks"]]

        if f.get("issuelinks"):
            L += ["", "## Linked issues", ""]
            for ln in f["issuelinks"]:
                if "outwardIssue" in ln:
                    L.append(f"- {ln['type']['outward']} {self.issue_ref(ln['outwardIssue'])}")
                else:
                    L.append(f"- {ln['type']['inward']} {self.issue_ref(ln['inwardIssue'])}")

        if data["remotelinks"]:
            L += ["", "## Web and remote links", ""]
            for r in data["remotelinks"]:
                o = r.get("object") or {}
                rel = f" ({r['relationship']})" if r.get("relationship") else ""
                L.append(f"- [{o.get('title') or o.get('url')}]({o.get('url')}){rel}")

        if atts:
            L += ["", "## Attachments", "", "| File | Size | Author | Created |", "|---|---|---|---|"]
            for a in atts:
                p = ctx.att_local[a["id"]]
                L.append(f"| [{cell(a['filename'])}]({mdpath(p)}) | {a.get('size', '')} | "
                         f"{cell(fmt(a.get('author')))} | {fmt_dt(a.get('created'))} |")

        if comments:
            L += ["", "## Comments"]
            for cm in comments:
                head = f"### {fmt(cm.get('author'))} — {fmt_dt(cm.get('created'))}"
                if cm.get("updated") and cm.get("updated") != cm.get("created"):
                    head += f" (edited {fmt_dt(cm['updated'])} by {fmt(cm.get('updateAuthor'))})"
                L += ["", head]
                if cm.get("visibility"):
                    L += ["", f"*Visible to {cm['visibility'].get('type')}: "
                              f"{cm['visibility'].get('value')}*"]
                L += ["", self.html_to_md(cm.get("renderedBody") or "", ctx) or cm.get("body", "")]

        if data["worklogs"]:
            L += ["", "## Work log", "", "| Author | Started | Time spent | Comment |", "|---|---|---|---|"]
            for w in data["worklogs"]:
                L.append(f"| {cell(fmt(w.get('author')))} | {fmt_dt(w.get('started'))} | "
                         f"{w.get('timeSpent', '')} | {cell(w.get('comment', ''))} |")

        watchers = (data.get("watchers") or {}).get("watchers") or []
        votes = (data.get("votes") or {}).get("voters") or []
        if watchers or votes:
            L += ["", "## Watchers and votes", ""]
            if watchers:
                L.append(f"- Watchers: {fmt(watchers)}")
            if votes:
                L.append(f"- Voters: {fmt(votes)}")

        if data["properties"]:
            L += ["", "## Issue properties", "", "```json",
                  json.dumps(data["properties"], indent=2, ensure_ascii=False), "```"]

        if data.get("devStatus"):
            L += ["", "## Development (Bitbucket)", "", "```json",
                  json.dumps(data["devStatus"], indent=2, ensure_ascii=False), "```"]

        histories = (issue.get("changelog") or {}).get("histories") or []
        if histories:
            L += ["", "## History", "", "| Date | Author | Field | From | To |", "|---|---|---|---|---|"]
            for h in histories:
                for it in h.get("items", []):
                    L.append(f"| {fmt_dt(h.get('created'))} | {cell(fmt(h.get('author')))} | "
                             f"{cell(it.get('field', ''))} | {cell(it.get('fromString') or it.get('from') or '')} | "
                             f"{cell(it.get('toString') or it.get('to') or '')} |")

        (tmp / "index.md").write_text("\n".join(L) + "\n", "utf-8")
