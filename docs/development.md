# Development

## Setup

```
uv sync
```

## Everyday commands

```
uv run pytest               # tests (offline)
uv run ruff check           # lint
uv run ruff format          # format
uv run jira-archiver --help
```

## Tests

Tests live in `tests/` and never touch the network. `test_archiver.py` builds an `Archiver`
with a `JiraClient` whose `download` is replaced by a fake. To test `collect`/`archive`
end to end, fake `JiraClient.get`, `get_optional` and `paged` the same way.

## Versioning and releases (Chronver)

[Chronver](https://chronver.org) uses the release date: `YYYY.MM.DD`, with an optional
`.N` changeset for further releases on the same day (`2026.09.29`, `2026.09.29.1`).
The version lives only in `pyproject.toml`.

```
uv run python scripts/bump_version.py   # sets today's date or increments the changeset
uv build                                # optional: sdist + wheel in dist/
```

Commit the bump and tag it, e.g. `git tag v2026.09.29`.

## Conventions

See [CLAUDE.md](../CLAUDE.md): token stays on the Jira host, ticket folders are atomic,
`issue.json` stays complete, attachments are stored once.
