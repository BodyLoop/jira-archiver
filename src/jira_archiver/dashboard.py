"""Local, read-only dashboard over an archive written by jira-archiver.

Serves a single-page app plus a small JSON API from 127.0.0.1. Everything is read from the
`issue.json` files of finished tickets; nothing is sent to Jira and no token is needed.
"""
import argparse
import json
import mimetypes
import os
import re
import sys
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import unquote, urlparse

from .cli import load_env_file
from .util import fmt, log

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$")


def names(value):
    """List of display names of a Jira multi-value field."""
    return [fmt(x) for x in value or [] if fmt(x)]


def summarize(data, project):
    """Compact row (what the list, filters and charts need) from a parsed issue.json."""
    issue = data["issue"]
    f = issue.get("fields") or {}
    cat = ((f.get("status") or {}).get("statusCategory") or {}).get("key", "")
    parent = f.get("parent") or {}
    return {
        "key": issue["key"], "project": project, "summary": f.get("summary") or "",
        "type": fmt(f.get("issuetype")), "status": fmt(f.get("status")), "category": cat,
        "priority": fmt(f.get("priority")), "resolution": fmt(f.get("resolution")),
        "assignee": fmt(f.get("assignee")), "reporter": fmt(f.get("reporter")),
        "created": f.get("created"), "updated": f.get("updated"), "resolved": f.get("resolutiondate"),
        "labels": f.get("labels") or [], "components": names(f.get("components")),
        "versions": names(f.get("fixVersions")), "parent": parent.get("key", ""),
        "comments": len(data.get("comments") or []), "links": len(f.get("issuelinks") or []),
        "attachments": len(f.get("attachment") or []),
    }


def load_summary(path, project):
    try:
        return summarize(json.loads(path.read_text("utf-8")), project)
    except (OSError, ValueError, KeyError):
        return None  # unreadable ticket: skipped, like an unfinished one


class Archive:
    """The archive directory plus an in-memory index of its tickets (rebuilt by `reload`)."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.lock = threading.Lock()
        self.rows = []
        self.base = ""
        self.reload()

    def reload(self):
        jobs = []
        for pdir in sorted(p for p in self.root.iterdir() if p.is_dir() and not p.name.startswith(".")):
            for tdir in pdir.iterdir():
                # Ticket folders hold issue.json only when finished (temp dirs start with a dot).
                if KEY_RE.match(tdir.name) and (tdir / "issue.json").is_file():
                    jobs.append((tdir / "issue.json", pdir.name))
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = [r for r in pool.map(lambda j: load_summary(*j), jobs) if r]
        rows.sort(key=lambda r: (r["project"], int(r["key"].rsplit("-", 1)[1])))
        base = ""
        if rows:
            m = re.match(r"(.*)/rest/api/", self.issue_json(rows[0]["key"], rows[0]["project"])["issue"]["self"])
            base = m.group(1) if m else ""
        with self.lock:
            self.rows, self.base = rows, base

    def issue_json(self, key, project=None):
        project = project or key.rsplit("-", 1)[0]
        return json.loads((self.root / project / key / "issue.json").read_text("utf-8"))

    def detail(self, key):
        """Everything the detail panel shows, plus links to the archived copies."""
        data = self.issue_json(key)
        issue = data["issue"]
        f = issue["fields"]
        project = key.rsplit("-", 1)[0]
        links = []
        for ln in f.get("issuelinks") or []:
            other, direction = (ln["outwardIssue"], ln["type"]["outward"]) if "outwardIssue" in ln \
                else (ln["inwardIssue"], ln["type"]["inward"])
            links.append({"relation": direction, "key": other["key"],
                          "summary": (other.get("fields") or {}).get("summary", "")})
        history = [{"date": h["created"], "author": fmt(h.get("author")),
                    "items": [{"field": i["field"], "from": i.get("fromString") or "",
                               "to": i.get("toString") or ""} for i in h["items"]]}
                   for h in issue.get("changelog", {}).get("histories", [])]
        return {
            "row": summarize(data, project), "description": f.get("description") or "",
            "comments": [{"author": fmt(c.get("author")), "created": c.get("created"), "body": c.get("body") or ""}
                         for c in data.get("comments") or []],
            "links": links, "history": history,
            "subtasks": [{"key": s["key"], "summary": s["fields"].get("summary", ""),
                          "status": fmt(s["fields"].get("status"))} for s in f.get("subtasks") or []],
            "attachments": [a.get("filename", "") for a in f.get("attachment") or []],
            "worklogs": len(data.get("worklogs") or []),
        }

    def file_path(self, rel):
        """Resolved path of an archive file, or None if it escapes the archive or is missing."""
        p = (self.root / rel).resolve()
        if self.root in p.parents and p.is_file():
            return p
        return None


def make_handler(archive):
    page = resources.files("jira_archiver").joinpath("dashboard.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the terminal quiet
            pass

        def send(self, status, body, ctype):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, obj, status=200):
            self.send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json")

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            if path == "/":
                return self.send(200, page, "text/html; charset=utf-8")
            if path == "/api/issues":
                with archive.lock:
                    return self.send_json({"base": archive.base, "issues": archive.rows})
            if path.startswith("/api/issue/"):
                key = path.rsplit("/", 1)[1]
                if not KEY_RE.match(key):
                    return self.send_json({"error": "bad key"}, 400)
                try:
                    return self.send_json(archive.detail(key))
                except (OSError, ValueError, KeyError):
                    return self.send_json({"error": "not found"}, 404)
            if path.startswith("/files/"):
                p = archive.file_path(path[len("/files/"):])
                if p:
                    # Served as download-ish plain types: archived HTML/SVG must not run as a page.
                    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
                    if ctype in ("text/html", "image/svg+xml") or p.suffix == ".md":
                        ctype = "text/plain; charset=utf-8"
                    return self.send(200, p.read_bytes(), ctype)
            self.send_json({"error": "not found"}, 404)

        def do_POST(self):
            if urlparse(self.path).path == "/api/reload":
                archive.reload()
                return self.send_json({"count": len(archive.rows)})
            self.send_json({"error": "not found"}, 404)

    return Handler


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    load_env_file(argv)  # before the env-based defaults below are read
    ap = argparse.ArgumentParser(
        prog="jira-archiver-dashboard",
        description="Open a local dashboard for a jira-archiver output directory (read-only, no network).")
    ap.add_argument("--out", default=os.environ.get("JIRA_OUT") or "jira-archive",
                    help="archive directory (env: JIRA_OUT; default: jira-archive)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("JIRA_DASHBOARD_PORT") or 8765),
                    help="port on 127.0.0.1 (env: JIRA_DASHBOARD_PORT; default: 8765)")
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    ap.add_argument("--env-file", help="read settings from this file (env: JIRA_ENV_FILE; default: .env)")
    opts = ap.parse_args(argv)

    if not Path(opts.out).is_dir():
        raise SystemExit(f"error: archive directory not found: {opts.out}")
    archive = Archive(opts.out)
    log(f"{len(archive.rows)} tickets in {archive.root}")
    server = ThreadingHTTPServer(("127.0.0.1", opts.port), make_handler(archive))
    url = f"http://127.0.0.1:{opts.port}/"
    log(f"dashboard at {url}  (Ctrl+C to stop)")
    if not opts.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
