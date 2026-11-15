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


class ChatOut(BaseModel):
    answer: str
    suggestions: list[Suggestion]
    unverified_numbers: list[str]
    model: str
    disclaimer: str = DISCLAIMER


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
            raw = await m().reply(system_instruction(grd, rid, vid), turns)
        except Exception:  # noqa: BLE001 - never leak provider errors to the browser
            log.exception("model call failed")
            raise HTTPException(
                502, "The assistant is not available right now. The rest of the app works as usual."
            ) from None

        answer = raw.get("answer") or "Sorry, I could not answer that. Try asking about the result on screen."
        suggestions = build_suggestions(grd, raw.get("suggestions", []))
        flagged = unverified_numbers(
            answer + " " + " ".join(s.why for s in suggestions), grd.facts_text(rid, vid)
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
                    "est_usd": round(estimated_usd(usage), 6) if usage else None,
                    "suggestions": len(suggestions),
                    "unverified_numbers": flagged,
                }
            ),
            flush=True,
        )
        return ChatOut(answer=answer, suggestions=suggestions, unverified_numbers=flagged, model=m().name)

    return app


app = create_app()
