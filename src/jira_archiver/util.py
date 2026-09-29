"""Small pure helpers: naming, formatting, plain downloads."""
import os
import re
import sys
from datetime import datetime
from urllib.parse import quote, unquote

import requests


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def safe_name(name, maxlen=150):
    name = unquote(name or "")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "file"
    if len(name) > maxlen:
        stem, ext = os.path.splitext(name)
        name = stem[: maxlen - len(ext)] + ext
    return name


def unique(name, used):
    """Return a name not yet in `used` (case-insensitive, for Windows/macOS)."""
    stem, ext = os.path.splitext(name)
    candidate, i = name, 2
    while candidate.lower() in used:
        candidate = f"{stem}-{i}{ext}"
        i += 1
    used.add(candidate.lower())
    return candidate


def fmt_dt(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%Y-%m-%d %H:%M %z")
    except (TypeError, ValueError):
        return s or ""


def fmt(v):
    """Generic, lossless-enough text rendering of a Jira field value."""
    if v is None or v == "" or v == [] or v == {}:
        return ""
    if isinstance(v, list):
        return ", ".join(s for s in (fmt(x) for x in v) if s)
    if isinstance(v, dict):
        for k in ("displayName", "name", "value", "key"):
            if v.get(k):
                s = str(v[k])
                if v.get("child"):  # cascading select
                    s += " → " + fmt(v["child"])
                return s
        skip = {"self", "id", "iconUrl", "avatarUrls"}
        return "; ".join(f"{k}: {fmt(x)}" for k, x in v.items() if k not in skip and fmt(x))
    return str(v)


def cell(s):
    return str(s).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def mdpath(p):
    return quote(p, safe="/")


def download_plain(url, dest, timeout=60):
    """Download without the Jira session, so the token never leaves the Jira host."""
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(1 << 16):
                fh.write(chunk)
