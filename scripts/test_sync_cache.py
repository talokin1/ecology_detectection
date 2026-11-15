"""Offline tests of scripts/sync_cache.py (fake HTTP; no bucket, no gcloud)."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_cache as sc  # noqa: E402

GRID = b"netcdf bytes " * 1000
SERIES = b"month,value\n2000-01,1\n"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture
def cache(tmp_path):
    (tmp_path / "grids").mkdir()
    (tmp_path / "power_zarr").mkdir()
    files = [
        {"path": "grids/a_2deg.nc", "sha256": sha(GRID), "bytes": len(GRID), "kind": "grid"},
        {"path": "power_zarr/s.csv", "sha256": sha(SERIES), "bytes": len(SERIES), "kind": "series"},
    ]
    (tmp_path / "MANIFEST.json").write_text(json.dumps({"files": files}))
    return tmp_path


class FakeResp:
    def __init__(self, status, body=b""):
        self.status_code, self._body = status, body

    def iter_content(self, n):
        for i in range(0, len(self._body), n):
            yield self._body[i : i + n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeSession:
    def __init__(self, blobs):
        self.blobs = blobs  # sha -> bytes

    def _sha(self, u):
        return u.rsplit("/", 1)[-1]

    def head(self, u, timeout):
        return FakeResp(200 if self._sha(u) in self.blobs else 404)

    def get(self, u, stream, timeout):
        b = self.blobs.get(self._sha(u))
        return FakeResp(200, b) if b is not None else FakeResp(404)


def test_only_large_files_are_remote(cache):
    assert [e.path for e in sc.remote_entries(cache)] == ["grids/a_2deg.nc"]


def test_pull_downloads_and_verifies(cache):
    e = sc.remote_entries(cache)[0]
    assert sc.local_state(cache, e) == "missing"
    sc.download("b", e, cache / e.path, session=FakeSession({e.sha256: GRID}))
    assert sc.local_state(cache, e) == "ok"
    assert not list(cache.glob("grids/*.part"))


def test_pull_rejects_wrong_bytes_and_leaves_nothing(cache):
    e = sc.remote_entries(cache)[0]
    with pytest.raises(RuntimeError, match="do not match MANIFEST"):
        sc.download("b", e, cache / e.path, session=FakeSession({e.sha256: GRID + b"tampered"}))
    assert not (cache / e.path).exists() and not list(cache.glob("grids/*.part"))


def test_missing_blob_is_an_error(cache):
    e = sc.remote_entries(cache)[0]
    assert sc.remote_has("b", e, session=FakeSession({})) is False
    with pytest.raises(RuntimeError, match="HTTP 404"):
        sc.download("b", e, cache / e.path, session=FakeSession({}))


def test_local_state_detects_changed_file(cache):
    e = sc.remote_entries(cache)[0]
    (cache / e.path).write_bytes(GRID[:-1] + b"X")
    assert sc.local_state(cache, e) == "differs"


def test_urls_are_content_addressed():
    assert sc.url("bkt", "ab" * 32) == f"https://storage.googleapis.com/bkt/sha256/{'ab' * 32}"
