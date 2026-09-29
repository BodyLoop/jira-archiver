"""Command line entry point.

Every option can also be set through an environment variable (JIRA_*), optionally read from
a .env file. Precedence: command line > environment > .env file > built-in default.
"""
import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
from pathlib import Path

import urllib3
from dotenv import find_dotenv, load_dotenv

from . import __version__
from .archiver import Archiver
from .client import JiraClient
from .util import cell, fmt, log, parse_tickets, tickets_jql

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"", "0", "false", "no", "off"}


def env_flag(name):
    """Boolean from environment variable `name`; unset means False."""
    value = os.environ.get(name, "").strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise SystemExit(f"error: {name}={os.environ[name]!r} is not a boolean (use true/false)")


def env_int(name, default):
    """Integer from environment variable `name`; unset or empty means `default`."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"error: {name}={os.environ[name]!r} is not an integer") from None


def env_list(name):
    """Whitespace- and/or comma-separated list from environment variable `name`."""
    return [x for x in re.split(r"[\s,]+", os.environ.get(name, "")) if x]


def load_env_file(argv):
    """Load the .env file (--env-file, else .env from the working directory upwards)."""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--env-file")
    known, _ = pre.parse_known_args(argv)
    path = known.env_file or os.environ.get("JIRA_ENV_FILE") or find_dotenv(usecwd=True)
    if known.env_file and not Path(known.env_file).is_file():
        raise SystemExit(f"error: env file not found: {known.env_file}")
    if path:
        load_dotenv(path, override=False)  # real environment variables win over the file
    return path


def build_parser():
    ap = argparse.ArgumentParser(
        prog="jira-archiver",
        description="Archive Jira Server/Data Center projects to Markdown folders. "
                    "Options can also be given as JIRA_* environment variables or in a .env file.")
    ap.add_argument("projects", nargs="*", metavar="project",
                    help="project keys, e.g. PROJ OPS (env: JIRA_PROJECTS, space/comma separated)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("--env-file", help="read settings from this file (env: JIRA_ENV_FILE; default: .env)")
    ap.add_argument("--url", default=os.environ.get("JIRA_URL"),
                    help="Jira base URL, e.g. https://jira.example.local (env: JIRA_URL)")
    ap.add_argument("--token", default=os.environ.get("JIRA_TOKEN"),
                    help="Personal Access Token (env: JIRA_TOKEN)")
    ap.add_argument("--out", default=os.environ.get("JIRA_OUT") or "jira-archive",
                    help="output directory (env: JIRA_OUT; default: jira-archive)")
    ap.add_argument("--jql", default=os.environ.get("JIRA_JQL") or None,
                    help="extra JQL filter, e.g. \"key = PROJ-123\" for a test run (env: JIRA_JQL)")
    ap.add_argument("--tickets", default=os.environ.get("JIRA_TICKETS") or None,
                    help="only these ticket numbers/ranges of each project, e.g. \"5 10-20 100-\" "
                         "(env: JIRA_TICKETS)")
    ap.add_argument("--ca-bundle", default=os.environ.get("JIRA_CA_BUNDLE") or None,
                    help="CA bundle for an internal certificate authority (env: JIRA_CA_BUNDLE)")
    ap.add_argument("--insecure", action="store_true", default=env_flag("JIRA_INSECURE"),
                    help="disable TLS verification, not recommended (env: JIRA_INSECURE)")
    ap.add_argument("--force", action="store_true", default=env_flag("JIRA_FORCE"),
                    help="re-archive tickets that already exist (env: JIRA_FORCE)")
    ap.add_argument("--dev-status", action="store_true", default=env_flag("JIRA_DEV_STATUS"),
                    help="also store Bitbucket development info: commits/branches/PRs (env: JIRA_DEV_STATUS)")
    ap.add_argument("--fetch-external-images", action="store_true",
                    default=env_flag("JIRA_FETCH_EXTERNAL_IMAGES"),
                    help="also download inline images hosted outside Jira (env: JIRA_FETCH_EXTERNAL_IMAGES)")
    ap.add_argument("--workers", type=int, default=env_int("JIRA_WORKERS", 4),
                    help="tickets to archive in parallel (env: JIRA_WORKERS; default: 4)")
    return ap


def parse_args(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    load_env_file(argv)
    ap = build_parser()
    opts = ap.parse_args(argv)
    if not opts.projects:
        opts.projects = env_list("JIRA_PROJECTS")
    if not opts.projects:
        ap.error("no projects given (pass project keys or set JIRA_PROJECTS)")
    if not opts.url:
        ap.error("no Jira URL given (use --url or set JIRA_URL)")
    if not opts.token:
        ap.error("no token given (use --token or set JIRA_TOKEN)")
    if opts.workers < 1:
        ap.error("--workers / JIRA_WORKERS must be at least 1")
    try:
        opts.ticket_ranges = parse_tickets(opts.tickets)
    except ValueError as e:
        ap.error(f"--tickets / JIRA_TICKETS: {e}")
    return opts


def archived_row(path, updated, want_dev_status):
    """Index row of an already archived ticket if it is still current, else None.

    Current means: issue.json exists and holds the same `updated` timestamp Jira reports now
    (and dev-status data, if requested now, was stored). Unreadable files count as not current.
    """
    if not updated or not path.exists():
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
        f = data["issue"]["fields"]
    except (OSError, ValueError, KeyError):
        return None
    if f.get("updated") != updated or (want_dev_status and "devStatus" not in data):
        return None
    return {"key": data["issue"]["key"], "summary": f.get("summary", ""),
            "type": fmt(f.get("issuetype")), "status": fmt(f.get("status"))}


def main(argv=None):
    opts = parse_args(argv)

    if opts.insecure:
        # The user chose this explicitly: warn once instead of once per request.
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        log("warning: TLS verification is disabled (--insecure / JIRA_INSECURE)")
    verify = False if opts.insecure else (opts.ca_bundle or True)
    client = JiraClient(opts.url, opts.token, verify=verify)
    arch = Archiver(client, opts.projects, opts)
    out = Path(opts.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "fields.json").write_text(
        json.dumps(client.get("/rest/api/2/field"), indent=2, ensure_ascii=False), "utf-8")

    failures = []
    for project in opts.projects:
        pdir = out / project
        pdir.mkdir(exist_ok=True)
        meta = {"project": client.get(f"/rest/api/2/project/{project}"),
                "versions": client.get(f"/rest/api/2/project/{project}/versions")}
        (pdir / "project.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), "utf-8")

        jql = f'project = "{project}"'
        if opts.ticket_ranges:
            jql += f" AND ({tickets_jql(project, opts.ticket_ranges)})"
        if opts.jql:
            jql += f" AND ({opts.jql})"
        jql += " ORDER BY key ASC"
        found = [(it["key"], (it.get("fields") or {}).get("updated"))
                 for it in client.paged("/rest/api/2/search", "issues", jql=jql, fields="key,updated")]
        keys = [k for k, _ in found]
        log(f"{project}: {len(keys)} tickets")

        def process(pdir, progress, key, updated):
            if not opts.force:
                row = archived_row(pdir / key / "issue.json", updated, opts.dev_status)
                if row:
                    return row
            log(f"  [{progress}] {key}")
            try:
                return arch.archive(key, pdir)
            except Exception as e:
                log(f"  ! {key} failed: {e}")
                failures.append(key)
                return None

        with ThreadPoolExecutor(max_workers=opts.workers) as pool:
            progress = [f"{i}/{len(keys)}" for i in range(1, len(keys) + 1)]
            results = pool.map(process, repeat(pdir), progress, keys,
                               [u for _, u in found])  # keeps ticket order
            rows = [r for r in results if r]

        L = [f"# {meta['project'].get('name', project)} ({project})", "",
             f"Archived from <{client.base}/browse/{project}>", "",
             "| Key | Type | Status | Summary |", "|---|---|---|---|"]
        L += [f"| [{r['key']}]({r['key']}/index.md) | {cell(r['type'])} | {cell(r['status'])} | "
              f"{cell(r['summary'])} |" for r in rows]
        (pdir / "index.md").write_text("\n".join(L) + "\n", "utf-8")

    if failures:
        log(f"\n{len(failures)} ticket(s) failed: {' '.join(failures)}  (re-run to retry)")
        sys.exit(1)
    log("done")
