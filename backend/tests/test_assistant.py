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

    async def reply(self, system, turns, run_tool=None, web_search=False):
        self.calls.append((system, turns))
        self.web_flags = getattr(self, "web_flags", []) + [web_search]
        reply = dict(self._reply)
        # A scripted reply may ask for lookups, like Gemini would; run them through the real tools.
        reply["tool_calls"] = []
        for name, args in reply.pop("lookups", []):
            try:
                reply["tool_calls"].append({"name": name, "args": args, "result": run_tool(name, args)})
            except ValueError as e:
                reply["tool_calls"].append({"name": name, "args": args, "error": str(e)})
        return reply


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


def test_number_check_reads_decimal_commas():
    facts = '{"sen_per_decade": 0.5446, "total_change": 2.45, "p": 0.043}'
    assert (
        unverified_numbers("Україна теплішає на +0,54 °C за десятиліття, разом 2,4 °C (p = 0,043).", facts)
        == []
    )
    assert unverified_numbers("Прогноз: 3,7 °C до 2060 року.", facts) == ["3.7", "2060"]


def test_number_check_reads_thousands_separators():
    facts = '{"n": 1000, "distance_km": 2500, "rate": 0.25}'
    assert unverified_numbers("less than 1 in 1,000; 2,500 km away; 0.25 per decade", facts) == []
    assert unverified_numbers("about 2,600 km away", facts) == ["2600"]


def test_parse_reply_falls_back_to_text():
    assert parse_reply("not json") == {"answer": "not json", "suggestions": []}
    assert parse_reply('{"answer": " hi ", "suggestions": [1, {"a": 2}]}') == {
        "answer": "hi",
        "suggestions": [{"a": 2}],
        "chart": None,
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

        async def reply(self, system, turns, run_tool=None, web_search=False):
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


# ---------------------------------------------------------------------- tools
@pytest.fixture(scope="module")
def tools(grounding):
    from trend_detective.assistant.tools import Tools

    return Tools(grounding)


def test_get_analysis_any_place(tools, grounding):
    r = tools.call("get_analysis", {"region_id": "c_fra", "variable_id": "t2m"})
    assert r["available"] and r["on_screen"]["region"] == grounding.regions["c_fra"]["name"]
    assert "series" not in r["analysis"]
    missing = tools.call("get_analysis", {"region_id": "ukraine", "variable_id": "sea_ice"})
    assert missing["available"] is False


def test_rank_regions_filters_and_sorts(tools, grounding):
    from trend_detective.assistant.tools import LEVEL_RANK

    r = tools.call(
        "rank_regions",
        {
            "variable_id": "t2m",
            "direction": "up",
            "place_set": "countries",
            "min_level": "strong",
            "limit": 5,
        },
    )
    assert 0 < len(r["top"]) <= 5 and r["places_tested"] > 100 and "chance" in r["note"]
    rates = [abs(x["rate_value"]) for x in r["top"]]
    assert rates == sorted(rates, reverse=True)
    for x in r["top"]:
        v = grounding.verdict(x["region_id"], "t2m")
        assert x["region_id"].startswith("c_") and v["direction"] == "up" and LEVEL_RANK[v["level"]] == 3


def test_compare_uses_tested_file_or_refuses_to_rank(tools):
    tested = tools.call(
        "compare_regions", {"region_a": "north_europe", "region_b": "sahel", "variable_id": "t2m"}
    )
    assert tested["difference_tested"] is True and "p" in tested and "gap_series" not in tested
    untested = tools.call("compare_regions", {"region_a": "c_fra", "region_b": "c_esp", "variable_id": "t2m"})
    assert untested["difference_tested"] is False and "do not say" in untested["rule"]


def test_get_series_year_and_range(tools, grounding):
    one = tools.call("get_series", {"region_id": "ukraine", "variable_id": "t2m", "start_year": 2010})
    assert [y["year"] for y in one["yearly"]] == [2010] and len(one["monthly"]) == 12
    a = grounding.analysis("ukraine", "t2m")["series"]["annual"]
    assert one["yearly"][0]["anomaly"] == a["anomaly"][a["years"].index(2010)]
    rng = tools.call(
        "get_series", {"region_id": "ukraine", "variable_id": "t2m", "start_year": 2000, "end_year": 2004}
    )
    assert [y["year"] for y in rng["yearly"]] == [2000, 2001, 2002, 2003, 2004] and "monthly" not in rng


def test_map_cell_finds_the_right_square(tools):
    import json

    r = tools.call("map_cell", {"variable_id": "t2m", "lat": 50.45, "lon": 30.52})  # Kyiv
    assert r["square_centre"] == {"lat": 51.0, "lon": 31.0}
    m = json.loads((tools.g.data_dir / "map" / "t2m.json").read_text())
    assert r["trend_per_decade"] == m["slope_per_decade"][70 * 180 + 105]


@pytest.mark.parametrize(
    "name, args",
    [
        ("get_analysis", {"region_id": "../x", "variable_id": "t2m"}),
        ("get_analysis", {"region_id": "atlantis", "variable_id": "t2m"}),
        ("rank_regions", {"variable_id": "t2m", "direction": "sideways"}),
        ("map_cell", {"variable_id": "t2m", "lat": 95, "lon": 0}),
        ("get_analysis", {"region": "ukraine"}),
        ("delete_everything", {}),
    ],
)
def test_bad_tool_calls_are_reported_to_the_model(tools, name, args):
    from trend_detective.assistant.tools import ToolError

    with pytest.raises(ToolError):
        tools.call(name, args)


def test_chat_with_lookups_grounds_numbers_and_lists_sources(grounding):
    v = grounding.verdict("c_fra", "t2m")
    soil = [
        x for k, x in grounding.index["verdicts"].items() if k.endswith("__soil") and x["direction"] == "down"
    ]
    worst = max(soil, key=lambda x: abs(x["rate_value"]))  # appears only in the ranking result
    reply = {
        "answer": f"France: {v['rate']}. Fastest drying: {worst['range_text']}.",
        "suggestions": [],
        "lookups": [
            ("get_analysis", {"region_id": "c_fra", "variable_id": "t2m"}),
            ("rank_regions", {"variable_id": "soil", "direction": "down"}),
            ("get_analysis", {"region_id": "atlantis", "variable_id": "t2m"}),
        ],
    }
    c, _ = client_for(grounding, reply)
    body = c.post("/v1/chat", json={"message": "How is France doing?"}).json()
    assert body["unverified_numbers"] == []  # the rate came from a tool result
    labels = [x["label"] for x in body["looked_up"]]
    assert labels[0].startswith("Result: Air temperature") and labels[1].startswith("Ranking of places")
    assert len(labels) == 2  # the failed call is not listed
    assert body["looked_up"][0]["href"] == "#/region/c_fra?var=t2m"


# ---------------------------------------------------------------------- web search
WEB = {
    "queries": ["2010 Russian heatwave cause"],
    "sources": [
        {
            "title": "metoffice.gov.uk",
            "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/x",
            "domain": "metoffice.gov.uk",
        }
    ],
    "cited_segments": ["According to the Met Office, temperatures reached 38.2 °C in Moscow."],
    "suggestions_html": "<style>.x{}</style><div class='x'>2010 Russian heatwave cause</div>",
}


def test_web_sources_and_suggestions_are_returned(grounding):
    reply = {
        "answer": "According to the Met Office, temperatures reached 38.2 °C in Moscow.",
        "suggestions": [],
        "web": WEB,
    }
    c, model = client_for(grounding, reply)
    body = c.post("/v1/chat", json={"message": "What caused the 2010 heatwave?"}).json()
    assert body["web_sources"][0]["uri"] == WEB["sources"][0]["uri"]  # unmodified
    assert body["search_suggestions_html"] == WEB["suggestions_html"]
    assert body["unverified_numbers"] == []  # the number sits in a segment cited to a web source
    assert model.web_flags == [True]
    assert "Web search:" in model.calls[0][0]


def test_uncited_numbers_are_still_flagged_with_web_on(grounding):
    reply = {"answer": "Ukraine warmed 9.99 °C per decade.", "suggestions": [], "web": WEB}
    c, _ = client_for(grounding, reply)
    assert c.post("/v1/chat", json={"message": "hi"}).json()["unverified_numbers"] == ["9.99"]


def test_no_suggestions_html_without_a_search(grounding):
    c, _ = client_for(grounding, {"answer": "ok", "suggestions": []})
    body = c.post("/v1/chat", json={"message": "hi"}).json()
    assert body["search_suggestions_html"] is None and body["web_sources"] == []


def test_web_search_can_be_switched_off(grounding, monkeypatch):
    monkeypatch.setenv("ASSISTANT_WEB_SEARCH", "0")
    c, model = client_for(grounding, {"answer": "ok", "suggestions": []})
    c.post("/v1/chat", json={"message": "hi"})
    assert model.web_flags == [False] and "Web search is not available" in model.calls[0][0]


def test_search_budget_stops_web_search(grounding, monkeypatch):
    monkeypatch.setenv("ASSISTANT_SEARCHES_PER_DAY", "1")
    c, model = client_for(grounding, {"answer": "ok", "suggestions": [], "web": WEB})
    c.post("/v1/chat", json={"message": "one"})
    c.post("/v1/chat", json={"message": "two"})
    assert model.web_flags == [True, False]


def test_collect_grounding_merges_and_dedupes():
    from types import SimpleNamespace as NS

    from trend_detective.assistant.llm import collect_grounding, empty_web

    web_chunk = NS(web=NS(title="t", uri="https://u", domain="d"))
    gm = NS(
        web_search_queries=["q"],
        grounding_chunks=[web_chunk, web_chunk],
        grounding_supports=[NS(segment=NS(text="seg"))],
        search_entry_point=NS(rendered_content="<b>x</b>"),
    )
    resp = NS(candidates=[NS(grounding_metadata=gm)])
    web = empty_web()
    collect_grounding(resp, web)
    collect_grounding(resp, web)
    assert web["queries"] == ["q"] and len(web["sources"]) == 1 and web["suggestions_html"] == "<b>x</b>"
    collect_grounding(NS(candidates=[]), web)  # no metadata: no error


# ---------------------------------------------------------------------- language, charts, links
@pytest.mark.parametrize(
    "text, lang, other",
    [
        ("Чи висихає ґрунт на півдні України?", "uk", False),
        ("Де теплішає найшвидше?", "uk", False),
        ("Как меняется температура в Украине?", "en", True),
        ("How fast is Ukraine warming?", "en", False),
        ("Wie schnell erwärmt sich Deutschland eigentlich?", "en", True),
        ("hi", "en", False),
    ],
)
def test_reply_language(text, lang, other):
    from trend_detective.assistant.language import reply_language

    assert reply_language(text) == (lang, other)


def test_language_reaches_the_prompt_last(grounding):
    c, model = client_for(grounding, {"answer": "ok", "suggestions": []})
    body = c.post("/v1/chat", json={"message": "Чи теплішає в Україні?"}).json()
    assert body["language"] == "uk"
    assert model.calls[0][0].rstrip().splitlines()[-1].startswith("REPLY LANGUAGE: Ukrainian")
    c.post("/v1/chat", json={"message": "Как дела с почвой?"})
    assert "not in English or Ukrainian" in model.calls[1][0].rstrip().splitlines()[-1]


def test_rates_chart_is_built_from_data(grounding):
    reply = {
        "answer": "ok",
        "suggestions": [],
        "chart": {
            "kind": "rates",
            "variable_id": "t2m",
            "region_ids": ["ukraine", "c_fra", "atlantis", "../x"],
        },
    }
    c, _ = client_for(grounding, reply)
    ch = c.post("/v1/chat", json={"message": "compare"}).json()["chart"]
    assert ch["kind"] == "rates" and [b["region_id"] for b in ch["bars"]] == ["ukraine", "c_fra"]
    v = grounding.verdict("ukraine", "t2m")
    assert (
        ch["bars"][0]["value"] == v["rate_value"]
        and [ch["bars"][0]["low"], ch["bars"][0]["high"]] == v["ci95"]
    )


def test_yearly_chart_and_bad_requests(grounding):
    from trend_detective.assistant.charts import build_chart

    ch = build_chart(grounding, {"kind": "yearly", "variable_id": "t2m", "region_ids": ["ukraine"]})
    a = grounding.analysis("ukraine", "t2m")["series"]["annual"]
    assert ch["series"][0]["x"] == a["years"] and ch["series"][0]["y"] == a["anomaly"]
    assert build_chart(grounding, {"kind": "pie", "variable_id": "t2m", "region_ids": ["ukraine"]}) is None
    assert build_chart(grounding, {"kind": "rates", "variable_id": "t2m", "region_ids": ["ukraine"]}) is None
    assert (
        build_chart(grounding, {"kind": "yearly", "variable_id": "sea_ice", "region_ids": ["ukraine"]})
        is None
    )
    assert build_chart(grounding, None) is None


def test_links_are_filtered(grounding):
    from trend_detective.assistant.app import filter_links

    web = {"https://vertexaisearch.cloud.google.com/grounding-api-redirect/x"}
    text = (
        "See [Ukraine](#/region/ukraine?var=t2m), [bad](#/region/atlantis?var=t2m), "
        "[cmp](#/compare/ukraine/c_pol?var=t2m), [evil](javascript:alert(1)), [ext](https://evil.example), "
        "[src](https://vertexaisearch.cloud.google.com/grounding-api-redirect/x)."
    )
    out = filter_links(text, grounding, web)
    assert "[Ukraine](#/region/ukraine?var=t2m)" in out and "[cmp](#/compare/ukraine/c_pol?var=t2m)" in out
    assert "(#/region/atlantis" not in out and "javascript" not in out and "evil.example" not in out
    assert "[src](https://vertexaisearch" in out
