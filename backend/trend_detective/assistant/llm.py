"""Gemini on Google Cloud (Vertex AI / Gemini Enterprise Agent Platform) behind a tiny interface,
so tests can swap in a fake model and never touch the network.

Authentication is Application Default Credentials: on Cloud Run the service account, locally
`gcloud auth application-default login`. There is no API key anywhere (CLAUDE.md rule 5).
"""

from __future__ import annotations

import json
import os
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


class Model(Protocol):
    name: str

    async def reply(self, system: str, turns: list[dict]) -> dict:
        """turns: [{"role": "user"|"model", "text": str}, ...] -> REPLY_SCHEMA dict."""
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

    async def reply(self, system: str, turns: list[dict]) -> dict:
        from google.genai import types

        contents = [types.Content(role=t["role"], parts=[types.Part(text=t["text"])]) for t in turns]
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,
            max_output_tokens=int(os.environ.get("ASSISTANT_MAX_OUTPUT_TOKENS", "2048")),
            response_mime_type="application/json",
            response_json_schema=REPLY_SCHEMA,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        )
        resp = await self._client.aio.models.generate_content(
            model=self.name, contents=contents, config=config
        )
        out = parse_reply(resp.text or "")
        out["usage"] = usage_counts(getattr(resp, "usage_metadata", None))
        return out


def usage_counts(meta) -> dict:
    """Token counts Gemini reports for one call (thinking tokens are billed as output)."""
    get = (lambda k: int(getattr(meta, k, None) or 0)) if meta is not None else (lambda k: 0)
    return {
        "prompt_tokens": get("prompt_token_count"),
        "cached_tokens": get("cached_content_token_count"),
        "output_tokens": get("candidates_token_count"),
        "thinking_tokens": get("thoughts_token_count"),
    }


def estimated_usd(usage: dict) -> float:
    """Rough cost of one call from env prices in USD per 1M tokens (defaults: gemini-3.8-flash
    global endpoint, introductory 2026 rate; check the Vertex AI pricing page)."""
    p_in = float(os.environ.get("PRICE_INPUT_PER_M", "0.75"))
    p_cached = float(os.environ.get("PRICE_CACHED_PER_M", "0.075"))
    p_out = float(os.environ.get("PRICE_OUTPUT_PER_M", "3.75"))
    fresh = max(usage.get("prompt_tokens", 0) - usage.get("cached_tokens", 0), 0)
    out = usage.get("output_tokens", 0) + usage.get("thinking_tokens", 0)
    return (fresh * p_in + usage.get("cached_tokens", 0) * p_cached + out * p_out) / 1e6


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
