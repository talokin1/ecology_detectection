"""Charts the assistant may ask for. The model names only ids; every plotted number is read here
from the app's own precomputed files, so a chart can never show a value the pipeline did not make.

Kinds:
- "yearly": yearly differences from normal for 1-3 places, one variable (lines).
- "rates":  rate per decade with its 95% range for 2-8 places, one variable (bars with error bars),
            coloured by evidence level.
"""

from __future__ import annotations

from .grounding import Grounding, safe_id

MAX_ITEMS = {"yearly": 3, "rates": 8}
LEVEL_WORD = {
    "strong": "Strong evidence",
    "moderate": "Evidence",
    "weak": "A hint",
    "none": "No clear trend yet",
    "insufficient": "Not enough data",
}

CHART_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["yearly", "rates"]},
        "variable_id": {"type": "string"},
        "region_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
    },
    "required": ["kind", "variable_id", "region_ids"],
}


def build_chart(g: Grounding, spec: dict | None) -> dict | None:
    """A plottable chart from ids, or None when the request is invalid or has no data."""
    if not isinstance(spec, dict):
        return None
    kind = spec.get("kind")
    if kind not in MAX_ITEMS:
        return None
    try:
        vid = safe_id(str(spec.get("variable_id", "")))
    except ValueError:
        return None
    if vid not in g.variables:
        return None
    var = g.variables[vid]
    rids = []
    for r in spec.get("region_ids") or []:
        try:
            r = safe_id(str(r))
        except ValueError:
            continue
        if r in g.regions and r not in rids and g.has_analysis(r, vid):
            rids.append(r)
    rids = rids[: MAX_ITEMS[kind]]
    if not rids or (kind == "rates" and len(rids) < 2):
        return None
    if kind == "yearly":
        series = []
        for r in rids:
            a = g.analysis(r, vid)["series"]["annual"]
            series.append({"label": g.regions[r]["name"], "region_id": r, "x": a["years"], "y": a["anomaly"]})
        return {
            "kind": "yearly",
            "variable_id": vid,
            "title": f"{var['name']}: yearly difference from normal",
            "units": var.get("anomaly_units") or var.get("units"),
            "series": series,
            "source": var.get("source"),
            "palette": var.get("palette"),
        }
    bars = []
    for r in rids:
        v = g.verdict(r, vid) or {}
        if v.get("rate_value") is None or not v.get("ci95"):
            continue
        bars.append(
            {
                "label": g.regions[r]["name"],
                "region_id": r,
                "value": v["rate_value"],
                "low": v["ci95"][0],
                "high": v["ci95"][1],
                "level": v.get("level"),
                "level_word": LEVEL_WORD.get(v.get("level"), v.get("level")),
            }
        )
    if len(bars) < 2:
        return None
    return {
        "kind": "rates",
        "variable_id": vid,
        "title": f"{var['name']}: trend per decade with 95% range",
        "units": var.get("rate_units"),
        "bars": bars,
        "source": var.get("source"),
        "palette": var.get("palette"),
    }
