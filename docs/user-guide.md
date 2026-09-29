# User guide

## Prerequisites

- [uv](https://docs.astral.sh/uv/) and network access to your Jira.
- A Jira Personal Access Token (Profile → Personal Access Tokens). The token's user must be
  able to see all tickets, security levels and restricted comments you want archived.

## Install

### As a uv tool (recommended for users)

Install straight from the git repository; no clone is needed:

```
uv tool install git+https://github.com/BodyLoop/jira-archiver
jira-archiver --help
```

This puts `jira-archiver` on your `PATH` (run `uv tool update-shell` once if uv says the tool
directory is not on `PATH`). Use it like the `uv run jira-archiver` examples below, just without
the `uv run` prefix. A `.env` file is read from the current working directory.

- Run once without installing:
  `uvx --from git+https://github.com/BodyLoop/jira-archiver jira-archiver PROJ --url https://jira.example.local`
- Update: `uv tool upgrade jira-archiver` (or `uv tool install --force git+https://github.com/BodyLoop/jira-archiver`
  to re-fetch the latest commit).
- Pin a branch, tag or commit: `uv tool install git+https://github.com/BodyLoop/jira-archiver@<ref>`.
- Remove: `uv tool uninstall jira-archiver`.

### From a clone (for development)

```
git clone https://github.com/BodyLoop/jira-archiver jira-archiver
cd jira-archiver
uv sync
```

## First run (single ticket)

PowerShell:

```
$env:JIRA_TOKEN = "<token>"
uv run jira-archiver PROJ --url https://jira.example.local --tickets 123
```

bash:

```
export JIRA_TOKEN=<token>
uv run jira-archiver PROJ --url https://jira.example.local --tickets 123
```

Open `jira-archive/PROJ/PROJ-123/index.md` and check it against Jira before archiving a
whole project.

## Full run

```
uv run jira-archiver PROJ OPS --url https://jira.example.local --ca-bundle ca.pem --dev-status
```

## Configuration: options, environment variables, `.env`

Every option has a `JIRA_*` environment variable. Precedence, highest first:
command line, real environment variables, `.env` file, built-in default.

| Option | Environment variable | Meaning |
|---|---|---|
| `projects` | `JIRA_PROJECTS` | Project keys (space or comma separated). Links between tickets of these projects become relative. |
| `--url` | `JIRA_URL` | Jira base URL (required). Include the context path if Jira has one. |
| `--token` | `JIRA_TOKEN` | Personal Access Token (required). Prefer the variable or `.env` over the option (command lines are visible to other users). |
| `--out` | `JIRA_OUT` | Output directory, default `jira-archive`. |
| `--jql` | `JIRA_JQL` | Extra JQL, combined as `project = "X" AND (<jql>)`. |
| `--tickets` | `JIRA_TICKETS` | Only these ticket numbers (the part after `PROJ-`) in each project: single numbers and ranges, space or comma separated, e.g. `5 10-20 100-` (`100-` = 100 and up, `-20` = up to 20). Combined with `--jql` by AND. |
| `--ca-bundle` | `JIRA_CA_BUNDLE` | PEM file of your internal CA. |
| `--insecure` | `JIRA_INSECURE` | Disable TLS verification. Not recommended. |
| `--force` | `JIRA_FORCE` | Re-archive all tickets, even if unchanged in Jira. |
| `--dev-status` | `JIRA_DEV_STATUS` | Also store linked Bitbucket repositories, branches and pull requests. |
| `--fetch-external-images` | `JIRA_FETCH_EXTERNAL_IMAGES` | Download inline images hosted outside Jira (without sending the token). |
| `--workers` | `JIRA_WORKERS` | Number of tickets archived in parallel (threads), default 4. Use 1 for sequential runs; lower it if Jira throttles (HTTP 429). |
| `--env-file` | `JIRA_ENV_FILE` | Read settings from this file instead of the `.env` found in the working directory (or a parent). |
| `--version` | | Print the version. |

Boolean variables accept `true/false`, `1/0`, `yes/no`, `on/off`; an unset variable means false.
A flag on the command line always switches the option on.

### `.env` file

Copy [`.env.example`](../.env.example) to `.env` and fill it in:

```
JIRA_URL=https://jira.example.local
JIRA_TOKEN=<token>
JIRA_PROJECTS=PROJ OPS
```

Then simply run `uv run jira-archiver`. `.env` is git-ignored; never commit a token. Real environment
variables override values in the file, so `JIRA_TOKEN` set by a CI system wins.

## Re-running

- Runs are incremental: the ticket listing includes each ticket's `updated` timestamp, and a ticket
  is fetched again only if it is missing, failed earlier, or its `updated` differs from the one in
  its stored `issue.json`. Unchanged tickets cost no per-ticket requests.
- `--dev-status` given on a later run also fetches tickets that were archived without it.
- `updated` does not change for everything (watchers, votes, or a linked ticket's renamed title
  shown in links). Use `--force` for a full refresh, optionally narrowed with `--jql`.
- Ticket listings (`<PROJ>/index.md`) are always regenerated.

## Reading the archive

Start at `<out>/<PROJ>/index.md`. Each ticket's `index.md` is the readable view;
`issue.json` has the full raw data. See [output-format.md](output-format.md).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `no token given` / `no Jira URL given` / `no projects given` | Set `JIRA_TOKEN` / `JIRA_URL` / `JIRA_PROJECTS` (environment or `.env`) or pass the option. |
| Settings in `.env` are ignored | The file is searched from the working directory upwards; use `--env-file` for another location. |
| `is not a boolean` | Use `true/false` for `JIRA_*` flags. |
| `401 Unauthorized` | Token invalid or expired; PATs need Jira 8.14+. |
| `403` / `404` on a project | The token's user lacks Browse permission or the key is wrong. |
| SSL certificate errors | Pass `--ca-bundle ca.pem` (preferred). `--insecure` works too; it prints one warning at start and silences urllib3's per-request `InsecureRequestWarning`. |
| Fewer tickets than expected | Permissions or issue security levels hide them; use an admin/archive account. |
| `! <KEY> failed` | See the message, fix, and re-run; only failed tickets are retried. Exit code is 1. |
| `size mismatch for attachment` | Download was truncated or Jira reports a different size; re-run with `--force`. |
| `could not fetch image` | The original URL is kept in `index.md`; the image is missing locally. |
| Leftover `.<KEY>-xxxx` folders | From an interrupted run; delete them. |
| Dev-status sections empty | No Bitbucket integration, or the API differs in your version. |
