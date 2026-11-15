"""Grounding for the SI (AI) assistant: everything the model may know, read from the same
precomputed JSON the web app ships (frontend/public/data), plus the methods page.

The server, never the browser, loads these files: a visitor cannot inject numbers into the
prompt. The model explains numbers; it never computes them (CLAUDE.md rule 2).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = ROOT / "frontend" / "public" / "data"
DEFAULT_METHODS = ROOT / "docs" / "10-methods.md"

# Parts of an analysis file that are long arrays for charts, not facts to explain.
_DROP_ANALYSIS_KEYS = {"series", "insights_audit", "schema_version"}
_DROP_TREND_KEYS = {"line", "band95"}

_ID = re.compile(r"^[a-z0-9_]{1,40}$")


def safe_id(value: str | None) -> str | None:
    """Region/variable ids are short snake_case tokens; anything else is rejected (no paths)."""
    if value is None or value == "":
        return None
    if not _ID.match(value):
        raise ValueError(f"invalid id: {value!r}")
    return value


@dataclass
class Grounding:
    data_dir: Path = DEFAULT_DATA_DIR
    methods_path: Path = DEFAULT_METHODS
    index: dict = field(init=False)
    catalog: dict = field(init=False)
    methods: str = field(init=False)

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self.index = json.loads((self.data_dir / "index.json").read_text(encoding="utf-8"))
        self.catalog = json.loads((self.data_dir / "catalog.json").read_text(encoding="utf-8"))
        self.methods = Path(self.methods_path).read_text(encoding="utf-8")
        self.variables = {v["id"]: v for v in self.index["variables"]}
        self.regions = {r["id"]: r for r in self.index["regions"]}
        self._catalog_by_id = {v["id"]: v for v in self.catalog.get("variables", [])}

    # ------------------------------------------------------------------ lookups
    def has_analysis(self, region_id: str, variable_id: str) -> bool:
        return (self.data_dir / "analysis" / f"{region_id}__{variable_id}.json").is_file()

    def analysis(self, region_id: str, variable_id: str) -> dict | None:
        region_id, variable_id = safe_id(region_id), safe_id(variable_id)
        if region_id not in self.regions or variable_id not in self.variables:
            return None
        return _load_analysis(str(self.data_dir), region_id, variable_id)

    def verdict(self, region_id: str, variable_id: str) -> dict | None:
        return self.index.get("verdicts", {}).get(f"{region_id}__{variable_id}")

    # ------------------------------------------------------------------ prompt blocks
    def variables_block(self) -> str:
        rows = []
        for v in self.index["variables"]:
            cat = self._catalog_by_id.get(v.get("catalog_id"), {})
            rows.append(
                {
                    "id": v["id"],
                    "name": v["name"],
                    "units": v.get("units"),
                    "period": v.get("period"),
                    "source": v.get("source"),
                    "topic": v.get("topic"),
                    "land_only": v.get("land_only"),
                    "map_only": v.get("map_only"),
                    "definition": cat.get("definition"),
                    "why_it_trends": cat.get("why_it_trends"),
                    "place_types": cat.get("place_types"),
                }
            )
        return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

    def regions_block(self) -> str:
        rows = [
            {"id": r["id"], "name": r["name"], "type": r.get("place_type")} for r in self.index["regions"]
        ]
        return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

    def screen_block(self, region_id: str | None, variable_id: str | None) -> str:
        """The analysis open on the visitor's screen, without chart arrays."""
        if not (region_id and variable_id):
            return "No analysis is open. The visitor is on the world map or another page."
        a = self.analysis(region_id, variable_id)
        if a is None:
            return (
                f"The visitor is looking at region '{region_id}' and variable '{variable_id}', "
                "but no precomputed analysis exists for this pair."
            )
        slim = {k: v for k, v in a.items() if k not in _DROP_ANALYSIS_KEYS}
        if isinstance(slim.get("trend"), dict):
            slim["trend"] = {k: v for k, v in slim["trend"].items() if k not in _DROP_TREND_KEYS}
        head = {
            "region": self.regions[region_id]["name"],
            "variable": self.variables[variable_id]["name"],
            "units": self.variables[variable_id].get("units"),
        }
        return json.dumps({"on_screen": head, "analysis": slim}, ensure_ascii=False, separators=(",", ":"))

    def facts_text(self, region_id: str | None, variable_id: str | None) -> str:
        """All text whose numbers the model may repeat (used by the number check)."""
        return "\n".join([self.screen_block(region_id, variable_id), self.variables_block(), self.methods])


@lru_cache(maxsize=256)
def _load_analysis(data_dir: str, region_id: str, variable_id: str) -> dict | None:
    p = Path(data_dir) / "analysis" / f"{region_id}__{variable_id}.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------- number check
# Numbers in English and in languages with a decimal comma (Ukrainian "0,54"):
# - "1,000" / "12,345.6": comma + exactly three digits after a non-zero integer part = thousands;
# - any other "d,d" (e.g. "0,54", "2,4", "0,545") = decimal comma.
_NUM = re.compile(r"(?<![\w.,])[-+−]?\d+(?:,\d{3})*(?:[.,]\d+)?")
_THOUSANDS = re.compile(r"^[1-9]\d{0,2}(?:,\d{3})+(?:\.\d+)?$")


def _normalise(s: str) -> str:
    s = s.replace("−", "-").lstrip("+-")
    if _THOUSANDS.match(s):
        return s.replace(",", "")
    if "," in s and "." not in s:
        return s.replace(",", ".")  # decimal comma
    return s.replace(",", "")


def _numbers(text: str) -> list[str]:
    return [_normalise(m.group(0)) for m in _NUM.finditer(text)]


def _decimals(s: str) -> int:
    return len(s.split(".")[1]) if "." in s else 0


def unverified_numbers(answer: str, facts: str) -> list[str]:
    """Numbers in the answer that do not appear in the facts, even after rounding.

    A number counts as grounded when some fact rounds to it at the answer's precision
    (0.5446 grounds "0.54" and "0.5"). Small whole numbers (0-12) are ignored: they are
    usually counts or list words ("two tests", "4 seasons"), not statistics.
    """
    fact_vals = set()
    for s in _numbers(facts):
        try:
            fact_vals.add(float(s))
        except ValueError:
            continue
    out: list[str] = []
    for s in _numbers(answer):
        try:
            v = float(s)
        except ValueError:
            continue
        if _decimals(s) == 0 and v <= 12:
            continue
        d = _decimals(s)
        tol = 0.5 * 10 ** (-d) + 1e-9
        if not any(abs(v - f) <= tol for f in fact_vals):
            if s not in out:
                out.append(s)
    return out
