"""Re-derive the v1.4 verdict columns under the B-3 conservative-verdict rule (offline).

SI-assisted (GOD / Grok Bot, 2026-11-14), pending team review.

The tidy parquet inputs (`data/tidy/**`) are not in the repo, so `run_pipeline.py` cannot be re-run offline
(A1-14 / MC-4). This script applies `ukpipe.verdict.apply_conservative_verdict` (the same function the
pipeline now calls) to the committed `outputs/v1.4/*_trends.csv`. Every statistic is unchanged: only
`robust_call`, `mt_bonferroni_pass`, `mt_bh_pass` change, plus the new columns `conservative_override` and
`verdict_provenance` = "re-derived, not recomputed". Sensitivity columns are renamed (A2-07/A2-12).
It also writes `outputs/v1.4/verdict_changes_b3.csv` and patches `qc_report.md` (B-3 section,
multiple-testing lists and the headline-table rows). Idempotent.

Usage: python tools/rederive_verdicts.py [--check]
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
OUT = PIPE / "outputs" / "v1.4"
REGIONS = ["ukraine_bbox", "ukraine_mask", "ukraine_mask_no_crimea"]
PROVENANCE = "re-derived, not recomputed (B-3 conservative rule applied to committed v1.4 table, 2026-11-14)"
MARK_START, MARK_END = "<!-- B-3 re-derivation: start -->", "<!-- B-3 re-derivation: end -->"


def _verdict_module():
    # load ukpipe/verdict.py directly: importing the ukpipe package would pull in loaders and data paths
    spec = importlib.util.spec_from_file_location("ukpipe_verdict", PIPE / "ukpipe" / "verdict.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _lab(d: pd.DataFrame) -> str:
    sfx = d.window.astype(str).str.extract(r"_(JJA|AMJJAS)$")[0].fillna("")
    names = d.source + ":" + d.variable + sfx.map(lambda x: f" ({'JJA' if x == 'JJA' else 'Apr-Sep'})" if x else "")
    return ", ".join(sorted(set(names))) or "none"


def _mt_line(reg: str, t: pd.DataFrame) -> str:
    h = t[t.headline == True]  # noqa: E712
    raw_sig = h[h.robust_call.astype(str).str.startswith("significant at 0.05")]
    md = h[h.robust_call.astype(str).str.startswith("method-dependent")]
    return (f"- `{reg}`: Bonferroni pass: {_lab(h[h.mt_bonferroni_pass])}. "
            f"BH only: {_lab(h[h.mt_bh_pass & ~h.mt_bonferroni_pass])}. "
            f"Yue-Wang raw 0.05 but fail BH: {_lab(raw_sig[~raw_sig.mt_bh_pass])}. "
            f"Method-dependent (YW p<0.05, OLS n_eff p>=0.05; not a detection): {_lab(md)}.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="only verify the gate (0 violating rows); write nothing")
    a = ap.parse_args(argv)
    v = _verdict_module()
    changes, tables, bad = [], {}, 0
    for reg in REGIONS:
        p = OUT / f"{reg}_trends.csv"
        old = pd.read_csv(p)
        if a.check:  # gate on the table as committed, without re-applying the rule
            bad += len(v.violations(old))
            continue
        if "verdict_provenance" in old.columns:
            print(f"{reg}: already re-derived; nothing to do (restore the v1.4 table from git to redo)")
            return 1 if len(v.violations(old)) else 0
        new = v.rename_sensitivity_columns(v.apply_conservative_verdict(old))
        new["verdict_provenance"] = PROVENANCE
        bad += len(v.violations(new))
        tables[reg] = new
        for i in new.index[new.conservative_override]:
            changes.append(dict(region=reg, source=new.at[i, "source"], variable=new.at[i, "variable"],
                                series=new.at[i, "series"], window=new.at[i, "window"],
                                headline=bool(new.at[i, "headline"]), yw_p=new.at[i, "yw_p"],
                                yw_ols_neff_p=new.at[i, "yw_ols_neff_p"],
                                old_robust_call=old.at[i, "robust_call"], new_robust_call=new.at[i, "robust_call"],
                                old_mt_bh_pass=bool(old.at[i, "mt_bh_pass"]),
                                old_mt_bonferroni_pass=bool(old.at[i, "mt_bonferroni_pass"]),
                                downgraded=bool(new.at[i, "yw_p"] < v.ALPHA)))
        new.to_csv(p, index=False)
    if a.check:
        print(f"violations (disagreement rows still called significant or passing MT): {bad}")
        return 1 if bad else 0
    ch = pd.DataFrame(changes)
    n_flip = int(ch.downgraded.sum()) if len(ch) else 0
    print(f"disagreement rows: {len(ch)}; YW-significant rows downgraded: {n_flip} "
          f"(headline: {int((ch.downgraded & ch.headline).sum()) if len(ch) else 0}); violations: {bad}")
    ch.to_csv(OUT / "verdict_changes_b3.csv", index=False)
    _patch_report(tables, ch)
    return 1 if bad else 0


def _patch_report(tables: dict, ch: pd.DataFrame) -> None:
    rp = PIPE / "qc_report.md"
    s = rp.read_text()
    # 1) B-3 section right after the title block
    s = re.sub(re.escape(MARK_START) + r".*?" + re.escape(MARK_END) + r"\n*", "", s, flags=re.S)
    flips = ch[ch.downgraded]
    rows = "\n".join(f"| {r.region} | {r.source} | {r.variable} | {r.series} | {'yes' if r.headline else ''} | "
                     f"{r.yw_p:.4g} | {r.yw_ols_neff_p:.4g} | {'BH' if r.old_mt_bh_pass else ''} |"
                     for r in flips.itertuples())
    sec = f"""{MARK_START}
## B-3: conservative verdict re-derived (2026-11-14, Europe/Kiev)

**Verdict columns re-derived, not recomputed.** Rule (main, `.claude/skills/trend-stats/SKILL.md:26-28`): when
repo MK Yue-Wang and the OLS n_eff cross-check disagree at 0.05, use the more conservative verdict.
`tools/rederive_verdicts.py` applied `ukpipe/verdict.py` to the committed v1.4 tables because the tidy
inputs are not available offline. No statistic changed. {len(ch)} rows disagree; on the {len(flips)} rows where Yue-Wang alone
is significant, "significant at 0.05" now reads "method-dependent ... not a detection" (also inside
"[raw call: ...]" of diagnostic rows); the other {len(ch) - len(flips)} rows (only OLS significant) get a
"methods disagree" note; and `mt_bonferroni_pass` /
`mt_bh_pass` are cleared on every disagreement row. Full list: `outputs/v1.4/verdict_changes_b3.csv`.
Sensitivity columns renamed: `mk_yw_p` -> `sens_pymk_yw_p_do_not_use`, `theil_sen_per_decade` ->
`sens_theil_sen_per_decade` (the reported slope is `yw_sen_slope_per_decade` with its 95% CI).
Sections below generated before 2026-11-14 keep their old statistics; the verdict cells of the headline
tables and the multiple-testing lists were patched to match.

| region | source | variable | series | headline | YW p | OLS n_eff p | was BH pass |
|---|---|---|---|---|---|---|---|
{rows}

Reworded claims: POWER PRECTOTCORR (bbox), POWER WS10M (all three regions) and GLDAS-2.0 rainfall (bbox)
are **not detections**. Precipitation and wind trends are method-dependent; quote them only as
"Yue-Wang p<0.05 but the OLS cross-check is not significant, so the methods disagree".
{MARK_END}

"""
    s = s.replace("\n## Smoke test", "\n" + sec + "## Smoke test", 1)
    # 2) multiple-testing lists
    for reg, t in tables.items():
        s = re.sub(rf"^- `{reg}`: Bonferroni pass:.*$", lambda _m, l=_mt_line(reg, t): l, s, count=1, flags=re.M)
    # 3) headline-table rows inside each region section
    parts = re.split(r"(?m)^(## Region `[a-z_]+`)$", s)
    for k in range(1, len(parts), 2):
        reg = parts[k].split("`")[1]
        if reg not in tables:
            continue
        for r in ch[(ch.region == reg) & ch.downgraded].itertuples():
            pat = re.compile(rf"^(\| {re.escape(r.source)} \| {re.escape(r.variable)} \| [^|]+ \| "
                             rf"{re.escape(r.series)} \| .*?\| )({re.escape(r.old_robust_call)})( \| )(True|False)"
                             rf"( \| )(True|False)( \|)", re.M)
            parts[k + 1] = pat.sub(lambda m, nc=r.new_robust_call: m.group(1) + nc + m.group(3) + "False"
                                   + m.group(5) + "False" + m.group(7), parts[k + 1])
    rp.write_text("".join(parts))


if __name__ == "__main__":
    sys.exit(main())
