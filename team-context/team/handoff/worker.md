# Worker handoff

Updated 14 Nov 2026 after the archive pass.

## Done
- Pipeline v1.3 (HAC + Hamed–Rao) is archived under `data/pipeline/outputs/archive_v1.3/`.
- Pipeline v1.4 is in `data/pipeline/`. Primary test is repository Yue–Wang (ADR-003). HAC and Hamed–Rao stay as sensitivity columns. Bonferroni and BH are computed on `yw_p`.
- Ran both regions (bbox and Ukraine mask; the without-Crimea variant was removed, Ukraine always includes Crimea) from this tree's code path (caches reused) and the smoke test: POWER +0.5526, HadCRUT5 +0.5793, GRACE −11.242, legacy GRACE −11.222. All passed ±0.005.
- Paths resolve from `UKRAINE_SAMPLES`, `GLOBAL_DATA`, and the checkout. `trend_methods.py` is vendored. `requirements-analysis.txt` is pinned.
- Verdict table: `data/pipeline/outputs/verdict_changes_v1.3_to_v1.4.csv`. Review: `team/reviews/yw_v14_review.md`.

## Not claimed as detections
- NASA POWER precipitation, bbox: Yue–Wang p = 0.019, OLS n_eff p = 0.086 (disagree), so the conservative verdict applies: method-dependent, BH/Bonferroni flags cleared (B-3). The mask is not significant (p = 0.077). Not a detection.
- OMI and SWOT remain bbox-only. The OMI file is one regional mean, so a Ukraine polygon cannot be cut from it. SWOT is too short for a climate trend.

## Recreate
See `team-context/README.md`. Then `cd team-context/data/pipeline` and run `run_pipeline.py` and `smoke_test.py` as written there.
