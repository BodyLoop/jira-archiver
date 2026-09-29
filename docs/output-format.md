# Output format

## Tree

```
<out>/
  fields.json                 GET /rest/api/2/field
  <PROJ>/
    index.md                  table of all tickets (key, type, status, summary)
    project.json              {"project": ..., "versions": [...]}
    <PROJ-123>/
      index.md
      issue.json
      _attachments/
      _figures/
```

Both `_attachments/` and `_figures/` are always created, possibly empty.

## Ticket `index.md`

Sections appear only when they have content, in this order:

1. Title `# KEY: summary`, link to the original, archive timestamp (UTC).
2. Header table: project, issue type, status, resolution, priority, reporter, creator, assignee,
   created, updated, resolved, due date, components, labels, affects/fix versions, parent.
3. `## Description`, then one section per further rich-text (string, HTML-rendered) field, sorted by name.
4. `## Details`: all other non-empty fields as `name | id | value`.
5. `## Sub-tasks`, `## Linked issues`, `## Web and remote links`.
6. `## Attachments`: every attachment with link to its local copy, size, author, date.
7. `## Comments`: author, timestamp, edit info, visibility restriction, body.
8. `## Work log`, `## Watchers and votes`, `## Issue properties`.
9. `## Development (Bitbucket)` (only with `--dev-status`).
10. `## History`: one row per changelog item (date, author, field, from, to).

Link rules: ticket links to archived projects are relative (`../../PROJ/PROJ-2/index.md`),
other tickets point to `<jira>/browse/KEY`; attachment links and images point into
`_attachments/` / `_figures/`; user mentions are plain names.

## Attachment placement

Each attachment is stored once. If its id appears as an image (`/secure/attachment/<id>/`
or `/secure/thumbnail/<id>/`) in any rich-text field or comment it is in `_figures/`,
otherwise in `_attachments/`. Emoticons, icons and other Jira-hosted inline images are also in
`_figures/`. Name collisions get `-2`, `-3`, … suffixes.

## `issue.json`

```
{
  "issue":       GET issue?expand=renderedFields,names,schema,changelog,
  "comments":    all comments (expand=renderedBody),
  "worklogs":    all worklogs,
  "remotelinks": remote links ([] if unavailable),
  "watchers":    watchers response or null,
  "votes":       votes response or null,
  "properties":  {property key: value},
  "devStatus":   {summary, repository, branch, pullrequest}   // only with --dev-status
}
```

`issue.issue.fields` holds every field by id; `names` maps field id → display name;
`schema` maps field id → type; `renderedFields` holds the HTML renderings; raw wiki markup is
in the plain field values.
