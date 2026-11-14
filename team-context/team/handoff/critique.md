# Critique handoff

Updated 14 Nov 2026 after the archive pass.

## Done
- Earlier reviews are in `team/reviews/`. They were written when HAC + Hamed–Rao lag-3 was the wording rule. Read them with ADR-003: repository Yue–Wang is now primary.
- v1.4 verdict review is `team/reviews/yw_v14_review.md`. POWER precipitation does **not** become a detection once the OLS cross-check, Bonferroni, and the Ukraine mask are included.
- `tools/sync_check.py` is the pre-commit gate (secrets, private names, 50 MB, denylisted types).

## Still true from earlier reviews
- GHCN-family temperature grids are not independent of each other.
- SWOT is too short. The Kherson step is not a confirmed dam-break signal.
- GLDAS-2.1 snow and precipitation are forcing diagnostics.
- CCI soil moisture is not an independent drying detection.

## Recreate
Re-run `team-context/data/pipeline/smoke_test.py` after `run_pipeline.py`. Compare headline rows in `outputs/verdict_changes_v1.3_to_v1.4.csv` with `yw_v14_review.md`.
