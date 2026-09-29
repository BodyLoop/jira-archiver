# jira-archiver

Archive Jira Server / Data Center projects as a folder-per-ticket Markdown tree.

```
<out>/
  fields.json                 field definitions (id -> name, schema)
  <PROJ>/
    index.md                  list of all archived tickets
    project.json              project metadata and versions
    <PROJ-123>/
      index.md                human-readable rendering of the ticket
      issue.json              complete raw data (the completeness guarantee)
      _attachments/           attachments not shown inline
      _figures/               images shown inline (attachments, emoticons, icons)
```

## Usage

### As an installed tool (no clone needed)

```
uv tool install git+https://github.com/BodyLoop/jira-archiver
jira-archiver PROJ --url https://jira.example.local

# or run once without installing
uvx --from git+https://github.com/BodyLoop/jira-archiver jira-archiver PROJ --url https://jira.example.local
```

Update with `uv tool upgrade jira-archiver` (or reinstall with `--force` to pick up the latest commit);
remove with `uv tool uninstall jira-archiver`.

### From a clone

```
uv sync
$env:JIRA_TOKEN = "..."          # Personal Access Token (Jira 8.14+)
uv run jira-archiver PROJ --url https://jira.example.local --jql "key = PROJ-123"   # test run
uv run jira-archiver PROJ OPS --url https://jira.example.local --ca-bundle ca.pem --dev-status
```

All options can also be set as `JIRA_*` environment variables or in a `.env` file
(see [.env.example](.env.example)); command line beats environment beats `.env`.
With a filled-in `.env`, just run `uv run jira-archiver`.

Options: `--out`, `--jql`, `--tickets` (e.g. `5 10-20 100-`), `--ca-bundle`, `--insecure`, `--force`, `--dev-status`,
`--fetch-external-images`. Re-runs are incremental: tickets whose `updated` timestamp is unchanged are skipped; changed and failed ones are fetched again (`--force` refreshes everything).

## Notes

- `issue.json` is the lossless record; `index.md` is a readable rendering of it.
- The token's user must be able to see everything (security levels, restricted comments).
- `--dev-status` uses Jira's undocumented dev-status API and may break across versions.
- Boards, sprint reports and comment edit history are not archived.

## Documentation

See [docs/](docs/README.md): user guide, specification, output format, architecture, development.

## Development

```
uv run pytest
uv run ruff check
```

Versioning follows [Chronver](https://chronver.org): `YYYY.MM.DD`, with `.N` for further releases
on the same day. Run `uv run python scripts/bump_version.py` to bump.
