"""Earthdata Login for offline precompute scripts (never used by the deployed app).

The token is read from the ``EARTHDATA_TOKEN`` environment variable or, failing that, from the
repo's ``.env`` file. It is only ever placed in an HTTP ``Authorization`` header sent to NASA
hosts; it is never printed, logged, or written to cache or provenance files.

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import os
import time
from functools import cache
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
TOKEN_VAR = "EARTHDATA_TOKEN"


class NotCachedError(LookupError):
    """A login-only series was requested offline and is not in the cache."""


def _read_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


@cache
def token() -> str:
    """The Earthdata bearer token, or a clear error if it is not configured."""
    value = os.environ.get(TOKEN_VAR) or _read_dotenv(REPO_ROOT / ".env").get(TOKEN_VAR, "")
    if not value:
        raise RuntimeError(
            f"{TOKEN_VAR} is not set. Create a token at https://urs.earthdata.nasa.gov "
            "(Generate Token) and put it in .env; see .env.example."
        )
    return value


def _is_nasa_host(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host == "nasa.gov" or host.endswith(".nasa.gov")


RETRY_STATUS = {429, 500, 502, 503, 504}


def get(
    url: str, *, params: dict | None = None, timeout: float = 300, retries: int = 4, stream: bool = False
) -> requests.Response:
    """GET with the bearer token; retries connection errors and HTTP 429/5xx with backoff."""
    return _with_retries(lambda: _get_once(url, params=params, timeout=timeout, stream=stream), retries)


def get_public(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 60,
    retries: int = 4,
) -> requests.Response:
    """GET without credentials (CMR and other public endpoints), with the same retries."""
    return _with_retries(lambda: requests.get(url, params=params, headers=headers, timeout=timeout), retries)


def _with_retries(call, retries: int) -> requests.Response:
    for attempt in range(retries + 1):
        try:
            r = call()
        except (requests.ConnectionError, requests.Timeout):
            if attempt == retries:
                raise
        else:
            if r.status_code not in RETRY_STATUS or attempt == retries:
                r.raise_for_status()
                return r
        time.sleep(2**attempt)
    raise AssertionError("unreachable")


def _get_once(
    url: str, *, params: dict | None, timeout: float, stream: bool, max_hops: int = 8
) -> requests.Response:
    """One GET with the bearer token, following redirects by hand.

    The token is sent only to ``*.nasa.gov`` hosts, never to the signed storage URLs
    (CloudFront / S3) that the DAACs redirect to.
    """
    session = requests.Session()
    for _ in range(max_hops):
        headers = {"Authorization": f"Bearer {token()}"} if _is_nasa_host(url) else {}
        r = session.get(
            url, params=params, headers=headers, timeout=timeout, allow_redirects=False, stream=stream
        )
        if r.status_code in (301, 302, 303, 307, 308):
            url = urljoin(url, r.headers["Location"])
            params = None  # already encoded in the redirect target
            continue
        if r.status_code in (401, 403):
            raise PermissionError(
                f"HTTP {r.status_code} from {urlsplit(url).hostname}: token rejected or the "
                "data centre's application is not approved in your Earthdata profile"
            )
        return r
    raise RuntimeError(f"too many redirects for {url}")


CMR_GRANULES = "https://cmr.earthdata.nasa.gov/search/granules.json"


def cmr_granules(short_name: str, version: str | None = None, page_size: int = 2000) -> list[dict]:
    """All granule records of a collection from NASA CMR (public, no token), oldest first."""
    params = {"short_name": short_name, "page_size": page_size, "sort_key": "start_date"}
    if version:
        params["version"] = version
    out: list[dict] = []
    search_after = None
    while True:
        headers = {"CMR-Search-After": search_after} if search_after else {}
        r = get_public(CMR_GRANULES, params=params, headers=headers)
        entries = r.json()["feed"]["entry"]
        out.extend(entries)
        search_after = r.headers.get("CMR-Search-After")
        if not entries or not search_after or len(entries) < page_size:
            return out


def data_url(granule: dict, prefix: str = "https://") -> str:
    """The granule's main download link (``rel`` ending in ``data#``)."""
    for link in granule.get("links", []):
        if link.get("rel", "").endswith("/data#") and link["href"].startswith(prefix):
            return link["href"]
    raise KeyError(f"no data link starting with {prefix!r} in granule {granule.get('title')}")


def download(url: str, dest: Path, *, chunk: int = 1 << 20) -> Path:
    """Download ``url`` to ``dest`` (skipped if it already exists). Returns ``dest``."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    with get(url, stream=True) as r, tmp.open("wb") as fh:
        for block in r.iter_content(chunk):
            fh.write(block)
    tmp.replace(dest)
    return dest
