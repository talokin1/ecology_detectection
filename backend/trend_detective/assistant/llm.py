"""Gemini on Google Cloud (Vertex AI / Gemini Enterprise Agent Platform) behind a tiny interface,
so tests can swap in a fake model and never touch the network.

Authentication is Application Default Credentials: on Cloud Run the service account, locally
`gcloud auth application-default login`. There is no API key anywhere (CLAUDE.md rule 5).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Protocol

# Structured reply: the answer text plus optional catalog suggestions (ids only; the server
# fills names, verdict headlines and links from the precomputed data).
REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "suggestions": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "variable_id": {"type": "string"},
                    "region_id": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["variable_id", "region_id", "why"],
            },
        },
    },
    "required": ["answer", "suggestions"],
}


ToolRunner = Callable[[str, dict], dict]


class Model(Protocol):
    name: str

    async def reply(
        self, system: str, turns: list[dict], run_tool: ToolRunner | None = None, web_search: bool = False
    ) -> dict:
        """turns: [{"role": "user"|"model", "text": str}, ...] -> REPLY_SCHEMA dict plus
        "usage" (summed over calls), "tool_calls" ([{"name", "args", "result"|"error"}]) and
        "web" (Google Search grounding: queries, sources, cited segments, suggestions HTML)."""
        ...


class GeminiModel:
    """google-genai client in enterprise (Vertex AI) mode."""

    def __init__(self, model: str | None = None, project: str | None = None, location: str | None = None):
        from google import genai  # imported lazily: tests and the static build do not need it

        self.name = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
        self._client = genai.Client(
            enterprise=True,
            project=project or os.environ.get("GOOGLE_CLOUD_PROJECT"),
            location=location or os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        )

    async def reply(
        self, system: str, turns: list[dict], run_tool: ToolRunner | None = None, web_search: bool = False
    ) -> dict:
        """Manual tool loop: Gemini may call our read-only lookup tools (tools.py) and, when
        ``web_search`` is on, Google Search (grounding) for up to ASSISTANT_MAX_TOOL_ROUNDS rounds,
        then must answer in REPLY_SCHEMA JSON."""
        from google.genai import types

        from .tools import DECLARATIONS

        contents = [types.Content(role=t["role"], parts=[types.Part(text=t["text"])]) for t in turns]
        tools = [types.Tool(function_declarations=[types.FunctionDeclaration(**d) for d in DECLARATIONS])]
        if web_search:
            tools.append(types.Tool(google_search=types.GoogleSearch()))

        def config(with_tools: bool):
            return types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.2,
                max_output_tokens=int(os.environ.get("ASSISTANT_MAX_OUTPUT_TOKENS", "2048")),
                response_mime_type="application/json",
                response_json_schema=REPLY_SCHEMA,
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                tools=tools if with_tools else None,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            )

        usage = {"prompt_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "thinking_tokens": 0}
        calls: list[dict] = []
        web = empty_web()
        max_rounds = int(os.environ.get("ASSISTANT_MAX_TOOL_ROUNDS", "4"))
        for round_no in range(max_rounds + 1):
            # The last round has no tools, so the model must answer with what it has.
            with_tools = run_tool is not None and round_no < max_rounds
            resp = await self._client.aio.models.generate_content(
                model=self.name, contents=contents, config=config(with_tools)
            )
            for k, v in usage_counts(getattr(resp, "usage_metadata", None)).items():
                usage[k] += v
            collect_grounding(resp, web)
            fcs = resp.function_calls or []
            if not fcs or not with_tools:
                break
            contents.append(resp.candidates[0].content)  # keeps the model's thought signatures
            parts = []
            for fc in fcs[:6]:
                args = dict(fc.args or {})
                try:
                    result = run_tool(fc.name, args)
                    calls.append({"name": fc.name, "args": args, "result": result})
                    parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
                except ValueError as e:  # ToolError: tell the model so it can fix the call
                    calls.append({"name": fc.name, "args": args, "error": str(e)})
                    parts.append(types.Part.from_function_response(name=fc.name, response={"error": str(e)}))
            contents.append(types.Content(role="user", parts=parts))
        out = parse_reply(resp.text or "")
        out["usage"] = usage
        out["tool_calls"] = calls
        out["web"] = web
        return out


def empty_web() -> dict:
    return {"queries": [], "sources": [], "cited_segments": [], "suggestions_html": None}


def collect_grounding(resp, web: dict) -> None:
    """Merge one response's Google Search grounding metadata into ``web`` (sources de-duplicated by
    URI; source URIs and the suggestions HTML are kept exactly as Google returns them)."""
    try:
        gm = resp.candidates[0].grounding_metadata
    except (AttributeError, IndexError, TypeError):
        return
    if gm is None:
        return
    for q in gm.web_search_queries or []:
        if q not in web["queries"]:
            web["queries"].append(q)
    for ch in gm.grounding_chunks or []:
        w = getattr(ch, "web", None)
        if w is not None and w.uri and all(s["uri"] != w.uri for s in web["sources"]):
            web["sources"].append(
                {"title": w.title or w.domain or "source", "uri": w.uri, "domain": w.domain}
            )
    for s in gm.grounding_supports or []:
        seg = getattr(s, "segment", None)
        if seg is not None and seg.text:
            web["cited_segments"].append(seg.text)
    ep = gm.search_entry_point
    if ep is not None and ep.rendered_content:
        web["suggestions_html"] = ep.rendered_content


def usage_counts(meta) -> dict:
    """Token counts Gemini reports for one call (thinking tokens are billed as output)."""
    get = (lambda k: int(getattr(meta, k, None) or 0)) if meta is not None else (lambda k: 0)
    return {
        "prompt_tokens": get("prompt_token_count"),
        "cached_tokens": get("cached_content_token_count"),
        "output_tokens": get("candidates_token_count"),
        "thinking_tokens": get("thoughts_token_count"),
    }


def estimated_usd(usage: dict, searches: int = 0) -> float:
    """Rough cost of one call from env prices in USD per 1M tokens (defaults: gemini-3.8-flash
    global endpoint, introductory 2026 rate; check the Vertex AI pricing page)."""
    p_in = float(os.environ.get("PRICE_INPUT_PER_M", "0.75"))
    p_cached = float(os.environ.get("PRICE_CACHED_PER_M", "0.075"))
    p_out = float(os.environ.get("PRICE_OUTPUT_PER_M", "3.75"))
    fresh = max(usage.get("prompt_tokens", 0) - usage.get("cached_tokens", 0), 0)
    out = usage.get("output_tokens", 0) + usage.get("thinking_tokens", 0)
    p_search = float(os.environ.get("PRICE_SEARCH_PER_1K", "14"))  # Gemini 3: billed per search query
    tokens = (fresh * p_in + usage.get("cached_tokens", 0) * p_cached + out * p_out) / 1e6
    return tokens + searches * p_search / 1000


def parse_reply(text: str) -> dict:
    """Parse the model's JSON; fall back to plain text if it is not valid JSON."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"answer": (text or "").strip(), "suggestions": []}
    if not isinstance(data, dict):
        return {"answer": str(data), "suggestions": []}
    answer = data.get("answer") if isinstance(data.get("answer"), str) else ""
    sugg = data.get("suggestions") if isinstance(data.get("suggestions"), list) else []
    return {"answer": answer.strip(), "suggestions": [s for s in sugg if isinstance(s, dict)]}
