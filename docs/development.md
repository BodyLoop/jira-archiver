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

Versions are `YYYY.MM.DD.N`: the release date plus `N`, a release counter that runs across all
days and never resets (`2026.09.29.1`, `2026.09.29.2`, `2026.10.02.3`). The version lives only in
`pyproject.toml`.

```
uv run python scripts/bump_version.py   # sets today's date and increments the counter
uv build                                # optional: sdist + wheel in dist/
```

Commit the bump and tag it, e.g. `git tag v2026.09.29.1`.

## Conventions

See [CLAUDE.md](../CLAUDE.md): token stays on the Jira host, ticket folders are atomic,
`issue.json` stays complete, attachments are stored once.
