"""Tools Gemini may call to look up our precomputed results (ADR-009 amendment: tool calling).

Every tool only READS files the web app already ships (frontend/public/data). No tool computes a
new statistic, so every number Gemini can quote is reproducible from the pipeline (CLAUDE.md
rule 2). Tool results are also added to the facts used by the server-side number check.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from .grounding import Grounding, safe_id

LEVEL_RANK = {"insufficient": -1, "none": 0, "weak": 1, "moderate": 2, "strong": 3}
SETS = {"countries": "c_", "world_regions": "ar6_"}
MULTIPLE_PLACES_NOTE = (
    "Each place is tested on its own. Across many places a few 'Evidence' results are expected by "
    "chance alone, so 'Strong evidence' results are the most reliable; say so when ranking."
)

# Function declarations in JSON Schema (google-genai `parameters_json_schema`).
DECLARATIONS = [
    {
        "name": "get_analysis",
        "description": (
            "Full precomputed trend analysis of one variable in one place: verdict, rate per decade "
            "with 95% range, p-values, seasons, months, extremes, years to detection, findings, "
            "deeper checks, data source. Use for any place, not only the one on screen."
        ),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "region_id": {"type": "string", "description": "id from the REGIONS list"},
                "variable_id": {"type": "string", "description": "id from the VARIABLES list"},
            },
            "required": ["region_id", "variable_id"],
        },
    },
    {
        "name": "rank_regions",
        "description": (
            "Places ranked by their trend rate for one variable, keeping only places whose verdict "
            "reaches min_level. Use for 'where is X changing the most / getting drier / warming fastest'."
        ),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "variable_id": {"type": "string"},
                "direction": {"type": "string", "enum": ["up", "down"]},
                "place_set": {"type": "string", "enum": ["countries", "world_regions", "stories", "all"]},
                "min_level": {"type": "string", "enum": ["weak", "moderate", "strong"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 15},
            },
            "required": ["variable_id", "direction"],
        },
    },
    {
        "name": "compare_regions",
        "description": (
            "Compare one variable in two places. Returns a tested difference when one was "
            "precomputed; otherwise both results side by side with difference_tested=false."
        ),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "region_a": {"type": "string"},
                "region_b": {"type": "string"},
                "variable_id": {"type": "string"},
            },
            "required": ["region_a", "region_b", "variable_id"],
        },
    },
    {
        "name": "get_series",
        "description": (
            "Yearly differences from normal (anomalies) of one variable in one place, for a range of "
            "years; with a single year, also its 12 monthly anomalies. Use for 'what happened in 2010'."
        ),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "region_id": {"type": "string"},
                "variable_id": {"type": "string"},
                "start_year": {"type": "integer"},
                "end_year": {"type": "integer"},
            },
            "required": ["region_id", "variable_id"],
        },
    },
    {
        "name": "map_cell",
        "description": (
            "Trend in the 2-degree map square containing a latitude/longitude, for one variable, and "
            "whether it passes the map-wide false-alarm filter. Use for a place that is not in REGIONS "
            "(a city, a lake, an ocean spot)."
        ),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "variable_id": {"type": "string"},
                "lat": {"type": "number", "minimum": -90, "maximum": 90},
                "lon": {"type": "number", "minimum": -180, "maximum": 180},
            },
            "required": ["variable_id", "lat", "lon"],
        },
    },
]


class ToolError(ValueError):
    """A bad tool call; the message goes back to the model so it can correct itself."""


class Tools:
    def __init__(self, g: Grounding):
        self.g = g
        self._maps: dict[str, dict] = {}

    # ------------------------------------------------------------------ dispatch
    def call(self, name: str, args: dict) -> dict:
        fn = {
            "get_analysis": self.get_analysis,
            "rank_regions": self.rank_regions,
            "compare_regions": self.compare_regions,
            "get_series": self.get_series,
            "map_cell": self.map_cell,
        }.get(name)
        if fn is None:
            raise ToolError(f"unknown tool {name!r}")
        try:
            return fn(**(args or {}))
        except TypeError as e:  # wrong or missing arguments
            raise ToolError(f"bad arguments for {name}: {e}") from None

    # ------------------------------------------------------------------ helpers
    def _region(self, rid) -> str:
        try:
            rid = safe_id(str(rid))
        except ValueError:
            rid = None
        if rid not in self.g.regions:
            raise ToolError(f"unknown region_id {rid!r}; use an id from the REGIONS list")
        return rid

    def _variable(self, vid) -> str:
        try:
            vid = safe_id(str(vid))
        except ValueError:
            vid = None
        if vid not in self.g.variables:
            raise ToolError(f"unknown variable_id {vid!r}; use an id from the VARIABLES list")
        return vid

    def _names(self, rid: str, vid: str) -> dict:
        v = self.g.variables[vid]
        return {"region": self.g.regions[rid]["name"], "variable": v["name"], "units": v.get("units")}

    # ------------------------------------------------------------------ tools
    def get_analysis(self, region_id, variable_id) -> dict:
        rid, vid = self._region(region_id), self._variable(variable_id)
        if not self.g.has_analysis(rid, vid):
            return {
                **self._names(rid, vid),
                "available": False,
                "reason": "no regional analysis (too little data there, or a map-only variable)",
            }
        return {"available": True, **json.loads(self.g.screen_block(rid, vid))}

    def rank_regions(self, variable_id, direction, place_set="all", min_level="moderate", limit=10) -> dict:
        vid = self._variable(variable_id)
        if direction not in ("up", "down"):
            raise ToolError("direction must be 'up' or 'down'")
        if min_level not in ("weak", "moderate", "strong"):
            raise ToolError("min_level must be weak, moderate or strong")
        limit = max(1, min(int(limit), 15))
        prefix = SETS.get(place_set)
        rows, tested = [], 0
        for key, v in self.g.index.get("verdicts", {}).items():
            rid, _, var = key.rpartition("__")
            if var != vid or rid not in self.g.regions:
                continue
            is_story = not rid.startswith(tuple(SETS.values()))
            if (prefix and not rid.startswith(prefix)) or (place_set == "stories" and not is_story):
                continue
            tested += 1
            if v.get("direction") != direction or LEVEL_RANK.get(v.get("level"), -1) < LEVEL_RANK[min_level]:
                continue
            rows.append(
                {
                    "region_id": rid,
                    "region": self.g.regions[rid]["name"],
                    "level": v.get("level"),
                    "headline": v.get("headline"),
                    "rate": v.get("rate"),
                    "rate_value": v.get("rate_value"),
                    "range": v.get("range_text"),
                }
            )
        rows.sort(key=lambda r: abs(r["rate_value"] or 0), reverse=True)
        return {
            "variable": self.g.variables[vid]["name"],
            "direction": direction,
            "place_set": place_set,
            "min_level": min_level,
            "places_tested": tested,
            "places_matching": len(rows),
            "top": rows[:limit],
            "note": MULTIPLE_PLACES_NOTE,
        }

    def compare_regions(self, region_a, region_b, variable_id) -> dict:
        a, b, vid = self._region(region_a), self._region(region_b), self._variable(variable_id)
        if a == b:
            raise ToolError("region_a and region_b must differ")
        for x, y in ((a, b), (b, a)):
            p = self.g.data_dir / "compare" / f"{x}__{y}__{vid}.json"
            if p.is_file():
                d = json.loads(p.read_text(encoding="utf-8"))
                d.pop("gap_series", None)
                d.pop("schema_version", None)
                return {"difference_tested": True, **d}
        side = {}
        for r in (a, b):
            v = self.g.verdict(r, vid) or {}
            side[r] = {
                "region": self.g.regions[r]["name"],
                "headline": v.get("headline"),
                "rate": v.get("rate"),
                "range": v.get("range_text"),
                "level": v.get("level"),
            }
        return {
            "difference_tested": False,
            "variable": self.g.variables[vid]["name"],
            "places": side,
            "rule": (
                "The difference between these two places was not tested. Report each place's own "
                "result; do not say one is changing faster or slower than the other."
            ),
        }

    def get_series(self, region_id, variable_id, start_year=None, end_year=None) -> dict:
        rid, vid = self._region(region_id), self._variable(variable_id)
        a = self.g.analysis(rid, vid)
        if a is None:
            return {**self._names(rid, vid), "available": False}
        s = a["series"]
        years, values = s["annual"]["years"], s["annual"]["anomaly"]
        y0 = int(start_year) if start_year is not None else years[0]
        y1 = int(end_year) if end_year is not None else (y0 if start_year is not None else years[-1])
        if y1 < y0:
            y0, y1 = y1, y0
        if y1 - y0 > 45:
            raise ToolError("ask for at most 45 years")
        out = {
            **self._names(rid, vid),
            "available": True,
            "units": s.get("anomaly_units"),
            "meaning": s.get("anomaly_label"),
            "baseline": s.get("baseline"),
            "record": f"{years[0]}–{years[-1]}",
            "yearly": [{"year": y, "anomaly": v} for y, v in zip(years, values) if y0 <= y <= y1],
        }
        if y0 == y1:
            out["monthly"] = [
                {"month": d, "anomaly": v, "value": r}
                for d, v, r in zip(s["dates"], s["anomaly"], s["raw"])
                if d.startswith(f"{y0}-")
            ]
            out["value_label"] = s.get("raw_label")
        if not out["yearly"]:
            out["note"] = f"no complete year in {y0}–{y1}; the record is {years[0]}–{years[-1]}"
        return out

    def map_cell(self, variable_id, lat, lon) -> dict:
        vid = self._variable(variable_id)
        lat, lon = float(lat), float(lon)
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ToolError("lat must be in -90..90 and lon in -180..180")
        m = self._map(vid)
        g = m["grid"]
        i = min(int((lat - (g["lat0"] - g["dlat"] / 2)) // g["dlat"]), g["nlat"] - 1)
        j = min(int((lon - (g["lon0"] - g["dlon"] / 2)) // g["dlon"]), g["nlon"] - 1)
        k = i * g["nlon"] + j
        slope = m["slope_per_decade"][k]
        clat, clon = g["lat0"] + i * g["dlat"], g["lon0"] + j * g["dlon"]
        out = {
            "variable": self.g.variables[vid]["name"],
            "units": m.get("units_label"),
            "square_centre": {"lat": clat, "lon": clon},
            "square_size_deg": g["dlat"],
            "period": m.get("period"),
            "map_mask": m.get("mask"),
        }
        if slope is None:
            return {**out, "available": False, "reason": "no value for this square (masked or no data)"}
        return {
            **out,
            "available": True,
            "trend_per_decade": slope,
            "passes_false_alarm_filter": bool(m["significant"][k]),
            "method": m.get("caption"),
        }

    def _map(self, vid: str) -> dict:
        if vid not in self._maps:
            p = Path(self.g.data_dir) / "map" / f"{vid}.json"
            if not p.is_file():
                raise ToolError(f"no map for {vid}")
            self._maps[vid] = json.loads(p.read_text(encoding="utf-8"))
        return self._maps[vid]
