from pathlib import Path
from types import SimpleNamespace

from jira_archiver.archiver import Archiver
from jira_archiver.client import JiraClient


def make_archiver(tmp_path):
    client = JiraClient("https://jira.example.local", "tok")
    downloaded = []
    client.download = lambda url, dest: (downloaded.append(url), Path(dest).write_bytes(b"x"))
    opts = SimpleNamespace(fetch_external_images=False, dev_status=False)
    ctx = SimpleNamespace(tmp=tmp_path, att_local={"10": "_attachments/a.pdf"}, fig_cache={},
                          used={"_attachments": set(), "_figures": set()})
    (tmp_path / "_figures").mkdir()
    return Archiver(client, ["PROJ"], opts), ctx, downloaded


def test_ticket_links_become_relative_for_archived_projects(tmp_path):
    arch, ctx, _ = make_archiver(tmp_path)
    md = arch.html_to_md(
        '<a href="/browse/PROJ-2">one</a> <a href="/browse/OTHER-3">two</a>', ctx)
    assert "(../../PROJ/PROJ-2/index.md)" in md
    assert "(https://jira.example.local/browse/OTHER-3)" in md


def test_attachment_links_point_to_local_copy(tmp_path):
    arch, ctx, _ = make_archiver(tmp_path)
    md = arch.html_to_md('<a href="/secure/attachment/10/a.pdf">a.pdf</a>', ctx)
    assert "(_attachments/a.pdf)" in md


def test_inline_jira_image_is_downloaded_to_figures(tmp_path):
    arch, ctx, downloaded = make_archiver(tmp_path)
    md = arch.html_to_md('<img src="/images/icons/emoticons/smile.png">', ctx)
    assert "_figures/smile.png" in md
    assert downloaded == ["https://jira.example.local/images/icons/emoticons/smile.png"]


def test_external_image_kept_by_default(tmp_path):
    arch, ctx, downloaded = make_archiver(tmp_path)
    md = arch.html_to_md('<img src="https://elsewhere.example/x.png">', ctx)
    assert "https://elsewhere.example/x.png" in md
    assert downloaded == []
