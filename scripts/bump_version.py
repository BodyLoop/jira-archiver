"""Set the version in pyproject.toml to today's date plus the next release counter (YYYY.MM.DD.N).

N counts releases across all days and never resets: 2026.09.29 -> 2026.09.29.1 -> 2026.10.02.2.
A version without a counter counts as release 0. Run: uv run python scripts/bump_version.py
"""
import re
from datetime import date
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
VERSION_RE = re.compile(r'^version = "([^"]+)"', re.MULTILINE)
CURRENT_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}(?:\.(\d+))?$")


def next_version(current, today):
    m = CURRENT_RE.match(current)
    if not m:
        raise ValueError(f"Unexpected version format: {current!r}")
    counter = int(m.group(1) or 0) + 1
    return f"{today:%Y.%m.%d}.{counter}"


def main():
    text = PYPROJECT.read_text("utf-8")
    current = VERSION_RE.search(text).group(1)
    new = next_version(current, date.today())
    PYPROJECT.write_text(VERSION_RE.sub(f'version = "{new}"', text, count=1), "utf-8")
    print(f"{current} -> {new}")


if __name__ == "__main__":
    main()
