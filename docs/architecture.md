# Architecture

## Modules (`src/jira_archiver/`)

| Module | Responsibility |
|---|---|
| `cli.py` | `.env`/environment loading (python-dotenv, `override=False`), argument parsing with env-var defaults, project loop, resume logic, project `index.md`, exit code. |
| `client.py` | `JiraClient`: requests session with Bearer auth, retry adapter, `get`, `get_optional`, `paged`, `download`. |
| `archiver.py` | `Archiver`: collects all data of a ticket, converts HTML to Markdown with local resources, writes the ticket folder atomically. |
| `util.py` | Pure helpers: `safe_name`, `unique`, `fmt`, `fmt_dt`, `cell`, `mdpath`, `download_plain`, `log`. |
| `__main__.py` | `python -m jira_archiver`. |

## Data flow

```
cli.main
 ├─ GET /rest/api/2/field                       -> fields.json
 └─ for each project
     ├─ GET project, project/versions           -> project.json
     ├─ GET search (JQL, fields=key, paged)     -> ticket keys
     └─ for each key not yet archived
         Archiver.archive
          ├─ collect()   REST calls (below)
          ├─ _write()    into temp dir: issue.json, attachments, figures, index.md
          └─ rename temp dir -> <PROJ>/<KEY>/
```

### REST endpoints used

- `issue/{key}?expand=renderedFields,names,schema,changelog`
- `issue/{key}/comment?expand=renderedBody` (paged), `issue/{key}/worklog` (paged)
- `issue/{key}/remotelink`, `/watchers`, `/votes`, `/properties[/{key}]` (optional)
- `dev-status/1.0/issue/summary` and `/detail` with `applicationType=stash` (optional, `--dev-status`)
- attachment `content` URLs, and Jira-hosted image URLs found in rendered HTML

## Design decisions

- **Plain `requests`, no wrapper library.** Precise control over `expand`, paging, binary
  downloads and where the token is sent.
- **`issue.json` as source of truth.** Markdown conversion is lossy by nature; the JSON keeps
  everything. `index.md` is derived from the same in-memory data.
- **Rendered HTML as Markdown input.** Jira renders wiki markup server-side (macros, user links,
  attachments); converting that HTML is more faithful than parsing wiki markup locally.
- **Atomic ticket folders.** Temp dir + rename gives crash safety and cheap resume (`issue.json` exists ⇒ done).
- **Token confinement.** Only same-host URLs use the authenticated session; external images use `download_plain`.
- **Attachments stored once.** Figures vs. attachments is decided by scanning rendered HTML for
  attachment/thumbnail URLs before downloading.
- **Optional endpoints via `get_optional`.** 400/403/404 → `None`, so plugins or permissions
  missing on a server don't fail the ticket.

## Extension points

- New per-ticket data: fetch in `Archiver.collect` (it lands in `issue.json` automatically), render in `Archiver._write`.
- Different attachment layout: `Archiver._write`, the `fig_ids` / `att_local` logic.
- Incremental mode: compare stored `issue.fields.updated` with a search on `updated` in `cli.main`.
