"""HTTP API of the SI (AI) assistant (requirement R-13; ADR-009).

Run locally (PowerShell or bash, from the repo root):
    gcloud auth application-default login
    $env:GOOGLE_CLOUD_PROJECT = "<project>"        # bash: export GOOGLE_CLOUD_PROJECT=<project>
    .venv/Scripts/python -m uvicorn trend_detective.assistant.app:app --app-dir backend --port 8080

POST /v1/chat   {"message": str, "region_id"?: str, "variable_id"?: str, "history"?: [...]}
GET  /health
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .grounding import Grounding, safe_id, unverified_numbers
from .llm import GeminiModel, Model, estimated_usd
from .prompt import system_instruction
from .tools import Tools

log = logging.getLogger("assistant")

MAX_MESSAGE = 600
MAX_TURN = 2000
MAX_HISTORY = 8
DISCLAIMER = (
    "AI-generated (Google Gemini). Numbers come from the app's own analysis; check them on the verdict card."
)


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(max_length=MAX_TURN)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE)
    region_id: str | None = Field(default=None, max_length=40)
    variable_id: str | None = Field(default=None, max_length=40)
    history: list[Turn] = Field(default_factory=list, max_length=MAX_HISTORY)


class Suggestion(BaseModel):
    variable_id: str
    region_id: str
    variable_name: str
    region_name: str
    why: str
    verdict: str | None
    href: str


class LookedUp(BaseModel):
    """One lookup the assistant made in our precomputed data (shown under the answer)."""

    tool: str
    label: str
    href: str | None = None


class WebSource(BaseModel):
    """A web page Google Search grounding cited (URI kept exactly as Google returns it)."""

    title: str
    uri: str
    domain: str | None = None


class ChatOut(BaseModel):
    answer: str
    suggestions: list[Suggestion]
    looked_up: list[LookedUp] = Field(default_factory=list)
    web_sources: list[WebSource] = Field(default_factory=list)
    # Google's Search Suggestions HTML, to be displayed unmodified next to a grounded answer
    search_suggestions_html: str | None = None
    unverified_numbers: list[str]
    model: str
    disclaimer: str = DISCLAIMER


class SearchBudget:
    """Per-instance daily cap on Google Search queries (each query is billed); when it is used up,
    the assistant answers from the app's data only."""

    def __init__(self, per_day: int):
        self.per_day = per_day
        self.day, self.used = time.strftime("%Y-%m-%d"), 0

    def available(self) -> bool:
        today = time.strftime("%Y-%m-%d")
        if today != self.day:
            self.day, self.used = today, 0
        return self.used < self.per_day

    def spend(self, n: int) -> None:
        self.used += n


def web_search_enabled() -> bool:
    return os.environ.get("ASSISTANT_WEB_SEARCH", "1").strip().lower() not in ("0", "false", "no", "off")


class RateLimiter:
    """Per-client sliding window plus a per-instance daily cap (cost guard for a public demo)."""

    def __init__(self, per_window: int, window_s: int, per_day: int):
        self.per_window, self.window_s, self.per_day = per_window, window_s, per_day
        self.hits: dict[str, deque] = defaultdict(deque)
        self.day, self.day_count = time.strftime("%Y-%m-%d"), 0

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        today = time.strftime("%Y-%m-%d")
        if today != self.day:
            self.day, self.day_count = today, 0
        if self.day_count >= self.per_day:
            return False
        q = self.hits[key]
        while q and now - q[0] > self.window_s:
            q.popleft()
        if len(q) >= self.per_window:
            return False
        q.append(now)
        self.day_count += 1
        return True


def build_suggestions(g: Grounding, raw: list[dict]) -> list[Suggestion]:
    """Keep only suggestions whose ids exist and have a precomputed analysis; fill in the rest
    from the data, so names, verdicts and links never come from the model."""
    out: list[Suggestion] = []
    seen = set()
    for s in raw:
        vid, rid = str(s.get("variable_id", "")), str(s.get("region_id", ""))
        if (
            (rid, vid) in seen
            or vid not in g.variables
            or rid not in g.regions
            or not g.has_analysis(rid, vid)
        ):
            continue
        seen.add((rid, vid))
        v = g.verdict(rid, vid) or {}
        verdict = " · ".join(x for x in (v.get("headline"), v.get("rate")) if x) or None
        out.append(
            Suggestion(
                variable_id=vid,
                region_id=rid,
                variable_name=g.variables[vid]["name"],
                region_name=g.regions[rid]["name"],
                why=str(s.get("why", ""))[:300],
                verdict=verdict,
                href=f"#/region/{rid}?var={vid}",
            )
        )
    return out[:4]


def describe_lookups(g: Grounding, calls: list[dict]) -> list[LookedUp]:
    """Human-readable list of successful tool calls; names come from the data, not the model."""
    out: list[LookedUp] = []
    seen = set()
    for c in calls:
        if "error" in c:
            continue
        a, name = c.get("args", {}), c["name"]
        var = g.variables.get(str(a.get("variable_id")), {}).get("name", "")
        reg = lambda k: g.regions.get(str(a.get(k)), {}).get("name", "")  # noqa: E731
        if name in ("get_analysis", "get_series"):
            what = "Result" if name == "get_analysis" else "Yearly values"
            item = LookedUp(
                tool=name,
                label=f"{what}: {var} · {reg('region_id')}",
                href=f"#/region/{a.get('region_id')}?var={a.get('variable_id')}",
            )
        elif name == "rank_regions":
            word = (g.variables.get(str(a.get("variable_id")), {}).get("words") or {}).get(
                "pos" if a.get("direction") == "up" else "neg", a.get("direction", "")
            )
            item = LookedUp(tool=name, label=f"Ranking of places: {var}, {word}")
        elif name == "compare_regions":
            item = LookedUp(
                tool=name,
                label=f"Comparison: {var} · {reg('region_a')} vs {reg('region_b')}",
                href=f"#/compare/{a.get('region_a')}/{a.get('region_b')}?var={a.get('variable_id')}",
            )
        elif name == "map_cell":
            item = LookedUp(tool=name, label=f"Map square near {a.get('lat')}, {a.get('lon')}: {var}")
        else:
            continue
        if item.label not in seen:
            seen.add(item.label)
            out.append(item)
    return out


def create_app(grounding: Grounding | None = None, model: Model | None = None) -> FastAPI:
    app = FastAPI(title="Trend Detective assistant", docs_url=None, redoc_url=None, openapi_url=None)
    origins = [
        o.strip()
        for o in os.environ.get(
            "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"
        ).split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["POST", "GET"],
        allow_headers=["content-type"],
        max_age=600,
    )
    state = {"g": grounding, "model": model}
    limiter = RateLimiter(
        int(os.environ.get("ASSISTANT_PER_MINUTE", "6")), 60, int(os.environ.get("ASSISTANT_PER_DAY", "300"))
    )
    searches = SearchBudget(int(os.environ.get("ASSISTANT_SEARCHES_PER_DAY", "500")))

    def g() -> Grounding:
        if state["g"] is None:
            state["g"] = Grounding(
                os.environ.get("ASSISTANT_DATA_DIR") or Grounding.data_dir,
                os.environ.get("ASSISTANT_METHODS") or Grounding.methods_path,
            )
        return state["g"]

    def m() -> Model:
        if state["model"] is None:
            state["model"] = GeminiModel()
        return state["model"]

    @app.get("/health")  # not /healthz: Cloud Run reserves paths ending in "z"
    def health():
        return {"ok": True}

    @app.post("/v1/chat", response_model=ChatOut)
    async def chat(body: ChatIn, request: Request):
        # Cloud Run's front end appends the real client address last; earlier entries can be spoofed.
        client = request.headers.get("x-forwarded-for", "").split(",")[-1].strip() or (
            request.client.host if request.client else "?"
        )
        if not limiter.allow(client):
            raise HTTPException(429, "Too many questions right now. Please wait a minute and try again.")
        try:
            rid, vid = safe_id(body.region_id), safe_id(body.variable_id)
        except ValueError:
            raise HTTPException(400, "Unknown region or variable.") from None
        grd = g()
        if (rid is not None and rid not in grd.regions) or (vid is not None and vid not in grd.variables):
            raise HTTPException(400, "Unknown region or variable.")

        turns = [{"role": "model" if t.role == "assistant" else "user", "text": t.text} for t in body.history]
        turns.append({"role": "user", "text": body.message})
        try:
            started = time.monotonic()
            tools = Tools(grd)
            use_web = web_search_enabled() and searches.available()
            raw = await m().reply(
                system_instruction(grd, rid, vid, web=use_web), turns, tools.call, web_search=use_web
            )
        except Exception:  # noqa: BLE001 - never leak provider errors to the browser
            log.exception("model call failed")
            raise HTTPException(
                502, "The assistant is not available right now. The rest of the app works as usual."
            ) from None

        answer = raw.get("answer") or "Sorry, I could not answer that. Try asking about the result on screen."
        suggestions = build_suggestions(grd, raw.get("suggestions", []))
        calls = raw.get("tool_calls") or []
        # Numbers from tool results (and the model's own lookup arguments, e.g. a latitude) count as
        # grounded; everything else in the answer is checked against the same facts as before.
        looked_up_facts = json.dumps(
            [{"args": c.get("args"), "result": c.get("result")} for c in calls], ensure_ascii=False
        )
        web = raw.get("web") or {}
        searches.spend(len(web.get("queries") or []))
        # Numbers inside answer segments that Google Search grounding cites to a web source are
        # attributed to that source (listed under the answer as web, not our data); everything else
        # must come from the app's own data and tools.
        flagged = unverified_numbers(
            answer + " " + " ".join(s.why for s in suggestions),
            grd.facts_text(rid, vid)
            + "\n"
            + looked_up_facts
            + "\n"
            + "\n".join(web.get("cited_segments") or []),
        )
        usage = raw.get("usage") or {}
        # One structured line per answer (Cloud Logging parses JSON on stdout): cost and quality.
        print(
            json.dumps(
                {
                    "severity": "WARNING" if flagged else "INFO",
                    "message": "assistant_reply",
                    "model": m().name,
                    "screen": f"{rid}__{vid}" if rid and vid else None,
                    "latency_ms": round((time.monotonic() - started) * 1000),
                    **usage,
                    "est_usd": round(estimated_usd(usage, len(web.get("queries") or [])), 6)
                    if usage
                    else None,
                    "web_queries": len(web.get("queries") or []),
                    "web_sources": len(web.get("sources") or []),
                    "suggestions": len(suggestions),
                    "tools": [c["name"] + ("!" if "error" in c else "") for c in calls],
                    "unverified_numbers": flagged,
                }
            ),
            flush=True,
        )
        return ChatOut(
            answer=answer,
            suggestions=suggestions,
            looked_up=describe_lookups(grd, calls),
            web_sources=[WebSource(**s) for s in (web.get("sources") or [])[:8]],
            search_suggestions_html=web.get("suggestions_html")
            if web.get("sources") or web.get("queries")
            else None,
            unverified_numbers=flagged,
            model=m().name,
        )

    return app


app = create_app()
