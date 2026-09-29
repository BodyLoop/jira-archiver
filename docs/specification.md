# Specification

## Goal

Archive the complete contents of selected Jira Server / Data Center projects into a plain
file tree that can be read, searched and versioned without Jira. Each ticket is one folder
holding *all* information the ticket carries.

## Scope

- Target: on-premise Jira Server / Data Center, REST API v2, Personal Access Token
  (Bearer) authentication (Jira 8.14+).
- Unit of archive: a ticket. Projects are archived as sets of tickets plus project metadata.
- Out of scope: Jira Cloud, boards, sprint reports, dashboards, filters, comment edit
  history, attachments that were deleted (only visible in the changelog).

## Functional requirements

| ID | Requirement |
|---|---|
| F1 | Accept one or more project keys and archive every ticket of each project. |
| F2 | An optional extra JQL filter narrows the ticket set (e.g. a single-ticket test run). |
| F3 | Each ticket becomes a folder `<out>/<PROJ>/<KEY>/` with `index.md`, `issue.json`, `_attachments/`, `_figures/`. |
| F4 | `issue.json` contains every field (custom fields with names and schema), rendered fields, changelog, comments, worklogs, remote links, watchers, votes and issue properties. It is the completeness guarantee. |
| F5 | `index.md` is a readable rendering: header table, description and other rich-text fields, details, sub-tasks, links, attachments, comments, work log, watchers/votes, properties, history. |
| F6 | Every attachment is stored exactly once: in `_figures/` if embedded as an image in any rich-text field or comment, otherwise in `_attachments/`. Thumbnails resolve to the full-size file. |
| F7 | Other inline images served by the Jira host (emoticons, icons) are saved to `_figures/` so `index.md` renders offline. External images are fetched only with `--fetch-external-images`. |
| F8 | Links to tickets of projects archived in the same run become relative links; other ticket links point to the Jira URL. User mentions become plain names. Attachment links point to the local copy. |
| F9 | Per project: `project.json` (project metadata, versions) and an `index.md` listing all tickets. Globally: `fields.json` (field definitions). |
| F10 | Optional `--dev-status` stores Bitbucket development info (repositories, branches, pull requests) via Jira's dev-status API. |

| F11 | Every option can be supplied as a `JIRA_*` environment variable, optionally from a `.env` file (`--env-file` / `JIRA_ENV_FILE` for another location). Precedence: command line > environment > `.env` > default. Missing url/token/projects or an invalid boolean is a usage error. |

## Non-functional requirements

| ID | Requirement |
|---|---|
| N1 | **Resumable.** A ticket is written to a temporary directory inside the project folder and renamed only when complete. Presence of `issue.json` marks a finished ticket; finished tickets are skipped unless `--force`. |
| N2 | **Failure isolation.** A failing ticket is logged and collected; other tickets continue. Exit code is 1 if any ticket failed, and a re-run retries only those. |
| N3 | **Retries.** GET requests are retried (up to 6 times, exponential backoff, honouring `Retry-After`) on HTTP 429, 500, 502, 503, 504. |
| N4 | **Token confinement.** The token is sent only to the Jira host. Images from other hosts are downloaded without the Jira session. |
| N5 | **TLS.** Verification is on by default; `--ca-bundle` supports internal CAs; `--insecure` disables it explicitly. |
| N6 | **Portable file names.** Attachment names are sanitised for Windows/macOS and de-duplicated case-insensitively; names are limited to 150 characters. |
| N7 | **Optional endpoints degrade gracefully.** Remote links, watchers, votes, properties and dev-status returning 400/403/404 are stored as empty. |

## Known limitations

- Anything the token's user cannot see (issue security levels, role/group-restricted comments) is silently missing. Use an admin or dedicated archive account.
- Wiki-to-Markdown conversion (via Jira's rendered HTML) is not perfectly lossless; `issue.json` retains the raw wiki markup.
- Sprints and other agile data appear only as raw field values.
- `--dev-status` relies on an undocumented API that may change between versions.
- Interrupted runs may leave `.<KEY>-*` temporary folders behind; they can be deleted safely.
- Re-running without `--force` does not refresh changed tickets.

## Open decisions

- Whether `_attachments/` should be a complete 1:1 copy of Jira's attachment list (duplicating figures).
- Automatic clean-up of leftover temporary folders.
- Incremental refresh (re-archive only tickets whose `updated` changed).
