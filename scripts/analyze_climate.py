"""Offline JSON -> climate statistics -> JSON. Run --help for the CLI contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from trend_detective.climate_stats import analyze_file
from trend_detective.climate_stats.contracts import catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Input JSON: regional monthly/daily/annual series")
    parser.add_argument("--output", type=Path, help="Output statistics JSON (written atomically)")
    parser.add_argument(
        "--list-variables", action="store_true", help="Print the 28 catalog variables and 3 inputs"
    )
    args = parser.parse_args(argv)
    if args.list_variables:
        print(
            json.dumps(
                [
                    {
                        "id": e["id"],
                        "name": e["name"],
                        "units": e["units"],
                        "internal": e.get("internal", False),
                    }
                    for e in catalog().values()
                ],
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0
    if args.input is None or args.output is None:
        parser.error("--input and --output are required unless --list-variables is used")
    try:
        result = analyze_file(args.input, args.output)
    except (ValueError, OSError) as exc:
        print(f"Analysis failed: {exc}", file=sys.stderr)
        return 2
    audit = result["insights_audit"]
    print(
        f"Wrote {args.output}: {len(result['series'])} series, "
        f"{audit['tested']} tests, {audit['significant']} pass FDR q={audit['q_threshold']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
