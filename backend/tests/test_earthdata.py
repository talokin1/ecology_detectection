import pytest
import requests
from trend_detective import earthdata


@pytest.fixture(autouse=True)
def _clear_token_cache():
    earthdata.token.cache_clear()
    yield
    earthdata.token.cache_clear()


def test_token_from_environment(monkeypatch):
    monkeypatch.setenv("EARTHDATA_TOKEN", "abc")
    assert earthdata.token() == "abc"


def test_token_from_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    (tmp_path / ".env").write_text('# comment\nOTHER=1\nEARTHDATA_TOKEN="xyz"\n', encoding="utf-8")
    monkeypatch.setattr(earthdata, "REPO_ROOT", tmp_path)
    assert earthdata.token() == "xyz"


def test_missing_token_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    monkeypatch.setattr(earthdata, "REPO_ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="EARTHDATA_TOKEN is not set"):
        earthdata.token()


@pytest.mark.parametrize("url,expected", [
    ("https://data.gesdisc.earthdata.nasa.gov/x", True),
    ("https://opendap.earthdata.nasa.gov/x", True),
    ("https://d2b3c3wh8s6en5.cloudfront.net/x", False),
    ("https://nasa.gov.evil.example/x", False),
    ("https://evilnasa.gov/x", False),
])
def test_token_only_for_nasa_hosts(url, expected):
    assert earthdata._is_nasa_host(url) is expected


class FakeResponse:
    def __init__(self, status, location=None):
        self.status_code = status
        self.headers = {"Location": location} if location else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def test_redirect_to_storage_drops_the_token(monkeypatch):
    monkeypatch.setenv("EARTHDATA_TOKEN", "secret")
    seen = []
    replies = iter([FakeResponse(303, "https://bucket.cloudfront.net/f?sig=1"), FakeResponse(206)])

    def fake_get(self, url, **kw):
        seen.append((url, kw["headers"]))
        return next(replies)

    monkeypatch.setattr(requests.Session, "get", fake_get)
    r = earthdata.get("https://data.gesdisc.earthdata.nasa.gov/file.h5")
    assert r.status_code == 206
    assert seen[0][1] == {"Authorization": "Bearer secret"}
    assert seen[1][0].startswith("https://bucket.cloudfront.net") and seen[1][1] == {}


def test_403_is_explained(monkeypatch):
    monkeypatch.setenv("EARTHDATA_TOKEN", "secret")
    monkeypatch.setattr(requests.Session, "get", lambda self, url, **kw: FakeResponse(403))
    with pytest.raises(PermissionError, match="not approved"):
        earthdata.get("https://data.gesdisc.earthdata.nasa.gov/file.h5")


def test_retries_connection_errors_then_succeeds(monkeypatch):
    monkeypatch.setattr(earthdata.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.ConnectionError("reset by peer")
        return FakeResponse(200)

    assert earthdata._with_retries(flaky, retries=4).status_code == 200
    assert calls["n"] == 3


def test_retries_give_up(monkeypatch):
    monkeypatch.setattr(earthdata.time, "sleep", lambda s: None)
    with pytest.raises(requests.HTTPError):
        earthdata._with_retries(lambda: FakeResponse(503), retries=2)


@pytest.mark.network
def test_live_cmr_lists_grace_granule():
    (g,) = earthdata.cmr_granules("TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4")
    assert earthdata.data_url(g).endswith(".nc")
