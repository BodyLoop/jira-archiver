import pytest

from jira_archiver import cli

ENV_VARS = ["JIRA_URL", "JIRA_TOKEN", "JIRA_PROJECTS", "JIRA_OUT", "JIRA_JQL", "JIRA_CA_BUNDLE",
            "JIRA_INSECURE", "JIRA_FORCE", "JIRA_DEV_STATUS", "JIRA_FETCH_EXTERNAL_IMAGES",
            "JIRA_ENV_FILE"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)  # no stray .env from the repo is picked up


def test_settings_from_dotenv_file(tmp_path):
    (tmp_path / ".env").write_text(
        "JIRA_URL=https://j.example\nJIRA_TOKEN=abc\nJIRA_PROJECTS=A, B C\n"
        "JIRA_FORCE=true\nJIRA_OUT=arch\n", "utf-8")
    opts = cli.parse_args([])
    assert (opts.url, opts.token, opts.out) == ("https://j.example", "abc", "arch")
    assert opts.projects == ["A", "B", "C"]
    assert opts.force is True and opts.dev_status is False


def test_cli_beats_env_beats_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("JIRA_URL=https://file\nJIRA_TOKEN=file\nJIRA_PROJECTS=A\n", "utf-8")
    monkeypatch.setenv("JIRA_TOKEN", "env")
    opts = cli.parse_args(["--url", "https://cli", "X"])
    assert opts.url == "https://cli"      # command line
    assert opts.token == "env"            # real env over .env
    assert opts.projects == ["X"]         # command line over JIRA_PROJECTS


def test_explicit_env_file(tmp_path):
    f = tmp_path / "other.env"
    f.write_text("JIRA_URL=https://o\nJIRA_TOKEN=t\nJIRA_PROJECTS=P\n", "utf-8")
    assert cli.parse_args(["--env-file", str(f)]).url == "https://o"


def test_missing_env_file_is_an_error():
    with pytest.raises(SystemExit):
        cli.parse_args(["--env-file", "nope.env"])


@pytest.mark.parametrize("env", [
    {"JIRA_TOKEN": "t", "JIRA_PROJECTS": "P"},                      # no url
    {"JIRA_URL": "u", "JIRA_PROJECTS": "P"},                        # no token
    {"JIRA_URL": "u", "JIRA_TOKEN": "t"},                           # no projects
    {"JIRA_URL": "u", "JIRA_TOKEN": "t", "JIRA_PROJECTS": "P", "JIRA_FORCE": "maybe"},
])
def test_missing_or_invalid_settings_exit(monkeypatch, env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(SystemExit):
        cli.parse_args([])
