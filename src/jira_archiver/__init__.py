"""Archive Jira Server / Data Center projects as a folder-per-ticket Markdown tree."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("jira-archiver")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "unknown"
