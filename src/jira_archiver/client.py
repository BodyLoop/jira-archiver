"""Minimal Jira Server / Data Center REST client (Bearer PAT auth, retries)."""
import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class JiraClient:
    def __init__(self, base_url, token, verify=True, timeout=60):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self._token = token
        self._verify = verify
        self._local = threading.local()

    @property
    def s(self):
        """Session of the calling thread (requests.Session is not documented as thread-safe)."""
        s = getattr(self._local, "session", None)
        if s is None:
            s = self._local.session = requests.Session()
            s.headers.update({"Authorization": f"Bearer {self._token}", "Accept": "application/json"})
            s.verify = self._verify
            retry = Retry(total=6, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                          allowed_methods=frozenset(["GET"]), respect_retry_after_header=True)
            adapter = HTTPAdapter(max_retries=retry)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
        return s

    def url(self, path):
        return path if path.startswith("http") else f"{self.base}{path}"

    def get(self, path, **params):
        r = self.s.get(self.url(path), params=params or None, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get_optional(self, path, **params):
        """GET that returns None for endpoints that may be missing or forbidden."""
        try:
            return self.get(path, **params)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (400, 403, 404):
                return None
            raise

    def paged(self, path, key, **params):
        start = 0
        while True:
            data = self.get(path, startAt=start, maxResults=100, **params)
            items = data.get(key, [])
            yield from items
            start += len(items)
            if not items or start >= data.get("total", 0):
                break

    def download(self, url, dest):
        with self.s.get(self.url(url), stream=True, timeout=self.timeout,
                        headers={"Accept": "*/*"}) as r:
            r.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in r.iter_content(1 << 16):
                    fh.write(chunk)
