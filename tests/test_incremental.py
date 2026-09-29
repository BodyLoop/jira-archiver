import json

from jira_archiver.cli import archived_row


def write(path, updated="2026-01-01T10:00:00.000+0000", **extra):
    issue = {"key": "P-1", "fields": {"summary": "S", "updated": updated,
                                       "issuetype": {"name": "Bug"}, "status": {"name": "Done"}}}
    path.write_text(json.dumps({"issue": issue, **extra}), "utf-8")
    return path


def test_unchanged_ticket_is_skipped(tmp_path):
    p = write(tmp_path / "issue.json")
    row = archived_row(p, "2026-01-01T10:00:00.000+0000", False)
    assert row == {"key": "P-1", "summary": "S", "type": "Bug", "status": "Done"}


def test_changed_missing_or_corrupt_is_refetched(tmp_path):
    p = write(tmp_path / "issue.json")
    assert archived_row(p, "2026-02-02T10:00:00.000+0000", False) is None   # updated in Jira
    assert archived_row(p, None, False) is None                             # no timestamp known
    assert archived_row(tmp_path / "nope.json", "x", False) is None         # not archived yet
    p.write_text("{not json", "utf-8")
    assert archived_row(p, "x", False) is None                              # corrupt


def test_dev_status_requested_later_refetches(tmp_path):
    p = write(tmp_path / "issue.json")
    ts = "2026-01-01T10:00:00.000+0000"
    assert archived_row(p, ts, True) is None
    write(p, devStatus={})
    assert archived_row(p, ts, True) is not None
