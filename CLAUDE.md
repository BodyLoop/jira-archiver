# jira-archiver

CLI that archives Jira Server/Data Center projects into a folder-per-ticket Markdown tree
(see README.md for output layout and usage).

## Commands

- `uv sync` — install deps (dev group included)
- `uv run jira-archiver PROJ --url <jira> [--jql "key = PROJ-1"]` — run (token via `$JIRA_TOKEN`)
- `uv run pytest` — tests
- `uv run ruff check` / `uv run ruff format` — lint / format
- `uv run python scripts/bump_version.py` — set version to today (Chronver)

## Layout

- `src/jira_archiver/client.py` — REST client (Bearer PAT, retries on 429/5xx, paging)
- `src/jira_archiver/archiver.py` — collects a ticket, renders `index.md`, writes `issue.json`, attachments, figures
- `src/jira_archiver/cli.py` — argparse entry point and per-project loop
- `src/jira_archiver/util.py` — pure helpers (naming, formatting)
- `tests/` — pytest; no network, Jira is faked

- `docs/` — user guide, specification, output format, architecture, development. Update the
  relevant doc when behaviour, options or the output layout change.

## Conventions

- Versioning is Chronver: `YYYY.MM.DD`, `.N` suffix for additional same-day releases. The only
  place the version lives is `pyproject.toml`; bump it with the script when releasing.
- Every CLI option has a `JIRA_*` env var (also via `.env`, loaded with `override=False`).
  Adding an option means: argparse default from env, `.env.example`, user guide table.
  Never read or print the user's `.env` (contains the token).
- Use plain `requests` (no atlassian wrapper libs) for exact control over expand/paging/downloads.
- The Jira token must only be sent to the Jira host: external images use `download_plain`
  and only with `--fetch-external-images`.
- Ticket folders are written to a temp dir and renamed when complete; `issue.json` presence marks
  a finished ticket. Keep that invariant.
- `issue.json` is the completeness guarantee; anything new fetched per ticket must go in it.
- Every attachment is stored exactly once (`_figures/` if embedded inline, else `_attachments/`).
- Keep tests offline; fake `JiraClient.download` / `get`.
