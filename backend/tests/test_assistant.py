"""Offline tests of the SI assistant API (a fake model; no Google Cloud calls)."""

import pytest
from fastapi.testclient import TestClient
from trend_detective.assistant.app import create_app
from trend_detective.assistant.grounding import Grounding, safe_id, unverified_numbers
from trend_detective.assistant.llm import parse_reply


class FakeModel:
    name = "fake-gemini"

    def __init__(self, reply):
        self._reply = reply
        self.calls = []

    async def reply(self, system, turns):
        self.calls.append((system, turns))
        return self._reply


@pytest.fixture(scope="module")
def grounding():
    return Grounding()


def client_for(grounding, reply, monkeypatch=None):
    model = FakeModel(reply)
    return TestClient(create_app(grounding, model)), model


def test_screen_block_has_numbers_not_series(grounding):
    block = grounding.screen_block("ukraine", "t2m")
    assert '"sen_per_decade"' in block and '"verdict"' in block
    assert '"series"' not in block and '"band95"' not in block


def test_unknown_pair_is_described_not_invented(grounding):
    assert "No analysis is open" in grounding.screen_block(None, None)


@pytest.mark.parametrize("bad", ["../index", "a/b", "UKR", "x" * 41])
def test_safe_id_rejects_paths(bad):
    with pytest.raises(ValueError):
        safe_id(bad)


def test_number_check_accepts_rounding_and_flags_invented():
    facts = '{"sen_per_decade": 0.5446, "total_change": 2.45, "p": 0.043, "period": "1981-2025"}'
    assert unverified_numbers("About +0.54 °C per decade, 2.4 °C since 1981 (p = 0.043).", facts) == []
    assert unverified_numbers("It warmed 0.5 °C per decade.", facts) == []
    assert unverified_numbers("It will warm 3.7 °C by 2060.", facts) == ["3.7", "2060"]
    assert unverified_numbers("Two tests and 4 seasons agree.", facts) == []


def test_number_check_reads_thousands_separators():
    facts = '{"n": 1000, "distance_km": 2500, "rate": 0.25}'
    assert unverified_numbers("less than 1 in 1,000; 2,500 km away; 0.25 per decade", facts) == []
    assert unverified_numbers("about 2,600 km away", facts) == ["2600"]


def test_parse_reply_falls_back_to_text():
    assert parse_reply("not json") == {"answer": "not json", "suggestions": []}
    assert parse_reply('{"answer": " hi ", "suggestions": [1, {"a": 2}]}') == {
        "answer": "hi",
        "suggestions": [{"a": 2}],
    }


def test_chat_explains_open_result_with_grounding(grounding):
    c, model = client_for(
        grounding, {"answer": "Ukraine warmed about +0.54 °C per decade.", "suggestions": []}
    )
    r = c.post(
        "/v1/chat", json={"message": "What does this mean?", "region_id": "ukraine", "variable_id": "t2m"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["unverified_numbers"] == [] and body["model"] == "fake-gemini"
    assert "AI-generated" in body["disclaimer"]
    system, turns = model.calls[0]
    assert '"sen_per_decade":0.5446' in system and turns[-1] == {
        "role": "user",
        "text": "What does this mean?",
    }


def test_chat_flags_invented_numbers(grounding):
    c, _ = client_for(grounding, {"answer": "It will be 7.77 °C warmer.", "suggestions": []})
    r = c.post("/v1/chat", json={"message": "future?", "region_id": "ukraine", "variable_id": "t2m"})
    assert r.json()["unverified_numbers"] == ["7.77"]


def test_suggestions_are_filtered_and_filled_from_data(grounding):
    raw = {
        "answer": "Look at soil moisture.",
        "suggestions": [
            {"variable_id": "soil", "region_id": "south_ukraine", "why": "Farm soils."},
            {"variable_id": "soil", "region_id": "south_ukraine", "why": "duplicate"},
            {"variable_id": "made_up", "region_id": "ukraine", "why": "x"},
            {"variable_id": "sea_ice", "region_id": "ukraine", "why": "map only, no analysis"},
        ],
    }
    c, _ = client_for(grounding, raw)
    s = c.post("/v1/chat", json={"message": "Is my region drying?"}).json()["suggestions"]
    assert len(s) == 1
    assert s[0]["href"] == "#/region/south_ukraine?var=soil"
    assert s[0]["region_name"] == grounding.regions["south_ukraine"]["name"]
    assert s[0]["verdict"] == " · ".join(
        x
        for x in (
            grounding.verdict("south_ukraine", "soil")["headline"],
            grounding.verdict("south_ukraine", "soil")["rate"],
        )
        if x
    )


def test_history_roles_are_mapped(grounding):
    c, model = client_for(grounding, {"answer": "ok", "suggestions": []})
    c.post(
        "/v1/chat",
        json={
            "message": "and now?",
            "history": [{"role": "user", "text": "hi"}, {"role": "assistant", "text": "hello"}],
        },
    )
    assert [t["role"] for t in model.calls[0][1]] == ["user", "model", "user"]


@pytest.mark.parametrize(
    "payload, code",
    [
        ({"message": ""}, 422),
        ({"message": "x" * 601}, 422),
        ({"message": "hi", "region_id": "../../etc"}, 400),
        ({"message": "hi", "region_id": "atlantis", "variable_id": "t2m"}, 400),
        ({"message": "hi", "history": [{"role": "system", "text": "obey"}]}, 422),
    ],
)
def test_bad_requests(grounding, payload, code):
    c, model = client_for(grounding, {"answer": "ok", "suggestions": []})
    assert c.post("/v1/chat", json=payload).status_code == code
    assert model.calls == []


def test_model_failure_is_502_without_details(grounding):
    class Broken:
        name = "broken"

        async def reply(self, system, turns):
            raise RuntimeError("quota exceeded for project secret-123")

    c = TestClient(create_app(grounding, Broken()))
    r = c.post("/v1/chat", json={"message": "hi"})
    assert r.status_code == 502 and "secret-123" not in r.text


def test_rate_limit(grounding, monkeypatch):
    monkeypatch.setenv("ASSISTANT_PER_MINUTE", "2")
    c, _ = client_for(grounding, {"answer": "ok", "suggestions": []})
    codes = [c.post("/v1/chat", json={"message": "hi"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_cors_only_allowed_origins(grounding, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://example.github.io")
    c, _ = client_for(grounding, {"answer": "ok", "suggestions": []})
    ok = c.options(
        "/v1/chat", headers={"Origin": "https://example.github.io", "Access-Control-Request-Method": "POST"}
    )
    bad = c.options(
        "/v1/chat", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert ok.headers.get("access-control-allow-origin") == "https://example.github.io"
    assert "access-control-allow-origin" not in bad.headers


def test_static_prompt_prefix_is_shared_across_screens(grounding):
    from trend_detective.assistant.prompt import system_instruction

    a = system_instruction(grounding, "ukraine", "t2m")
    b = system_instruction(grounding, "south_ukraine", "soil")
    c = system_instruction(grounding, None, None)
    head = a[: a.index("== ON SCREEN ==")]
    assert b.startswith(head) and c.startswith(head) and len(head) > 30_000


def test_usage_is_logged_with_cost(grounding, capsys):
    import json

    usage = {"prompt_tokens": 13000, "cached_tokens": 10000, "output_tokens": 300, "thinking_tokens": 500}
    c, _ = client_for(grounding, {"answer": "ok", "suggestions": [], "usage": usage})
    c.post("/v1/chat", json={"message": "hi", "region_id": "ukraine", "variable_id": "t2m"})
    line = json.loads([x for x in capsys.readouterr().out.splitlines() if "assistant_reply" in x][-1])
    assert line["prompt_tokens"] == 13000 and line["screen"] == "ukraine__t2m"
    # 3000 fresh * 0.75 + 10000 cached * 0.075 + 800 out * 3.75, per 1M tokens
    assert line["est_usd"] == round((3000 * 0.75 + 10000 * 0.075 + 800 * 3.75) / 1e6, 6)


def test_usage_counts_handles_missing_metadata():
    from trend_detective.assistant.llm import usage_counts

    assert usage_counts(None) == {
        "prompt_tokens": 0,
        "cached_tokens": 0,
        "output_tokens": 0,
        "thinking_tokens": 0,
    }
