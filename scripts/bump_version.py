"""Set the Chronver version in pyproject.toml to today's date (YYYY.MM.DD).

If the version already starts with today's date, a numeric changeset is appended/incremented
(2026.09.29 -> 2026.09.29.1 -> 2026.09.29.2). Run: uv run python scripts/bump_version.py
"""
import re
from datetime import date
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
VERSION_RE = re.compile(r'^version = "([^"]+)"', re.MULTILINE)


def next_version(current, today):
    base = f"{today:%Y.%m.%d}"
    if current == base:
        return f"{base}.1"
    if current.startswith(base + "."):
        return f"{base}.{int(current.rsplit('.', 1)[1]) + 1}"
    return base


def main():
    text = PYPROJECT.read_text("utf-8")
    current = VERSION_RE.search(text).group(1)
    new = next_version(current, date.today())
    PYPROJECT.write_text(VERSION_RE.sub(f'version = "{new}"', text, count=1), "utf-8")
    print(f"{current} -> {new}")


if __name__ == "__main__":
    main()
