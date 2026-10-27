import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from jira_archiver.dashboard import Archive, make_handler

ISSUE = {
    "issue": {"key": "PROJ-2", "self": "https://jira.example.local/rest/api/2/issue/1",
              "fields": {"summary": "Hello", "issuetype": {"name": "Bug"},
                         "status": {"name": "Done", "statusCategory": {"key": "done"}},
                         "created": "2026-01-02T10:00:00.000+0100", "labels": ["x"],
                         "components": [{"name": "GUI"}], "issuelinks": [], "subtasks": []},
              "changelog": {"histories": []}},
    "comments": [{"author": {"displayName": "Ann"}, "created": "2026-01-03T10:00:00.000+0100", "body": "hi"}],
    "worklogs": [],
}


@pytest.fixture
def served(tmp_path):
    tdir = tmp_path / "PROJ" / "PROJ-2"
    tdir.mkdir(parents=True)
    (tdir / "issue.json").write_text(json.dumps(ISSUE), "utf-8")
    (tmp_path / "PROJ" / ".PROJ-3-tmp").mkdir()  # unfinished ticket, must be ignored
    (tmp_path / "secret.txt").write_text("no", "utf-8")
    (tmp_path / "PROJ" / "ok.txt").write_text("yes", "utf-8")
    archive = Archive(tmp_path / "PROJ" / "..")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(archive))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def get(url):
    with urlopen(url) as r:
        return r.read()


def test_lists_only_finished_tickets(served):
    data = json.loads(get(served + "/api/issues"))
    assert [r["key"] for r in data["issues"]] == ["PROJ-2"]
    assert data["issues"][0]["components"] == ["GUI"]
    assert data["base"] == "https://jira.example.local"


def test_detail_has_comments(served):
    d = json.loads(get(served + "/api/issue/PROJ-2"))
    assert d["comments"][0]["author"] == "Ann"


def test_files_cannot_escape_archive(served):
    assert get(served + "/files/PROJ/ok.txt") == b"yes"
    with pytest.raises(HTTPError) as e:
        get(served + "/files/../../etc/passwd")
    assert e.value.code == 404
