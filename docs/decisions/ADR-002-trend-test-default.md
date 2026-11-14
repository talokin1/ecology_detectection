# ADR-002 — Default significance test: Mann-Kendall with Yue-Wang AR(1) correction

- Status: Proposed (pending science-lead approval)
- Date: 2026-11-14
- Requirement IDs: R-04, R-05, R-16

## Context
The challenge asks for a rate of change plus a significance test (t-test, Mann-Kendall or CIs).
Monthly Earth-science anomalies are autocorrelated, which makes naive tests report false trends.

## Options
1. Classic Mann-Kendall — simple, widely known; 14–33% false positives at φ = 0.3–0.6 in our simulation.
2. Hamed-Rao modified MK — common in hydrology; 10–21% false positives in our simulation.
3. **Yue-Wang (2004) effective-sample-size MK (AR(1))** — 3–6% false positives; power equal to OLS n_eff.
4. OLS + t-test with lag-1 effective n (Santer et al., 2000) — 3–6% false positives; parametric.

## Decision (proposed)
Primary: option 3, with Theil-Sen slope and its 95% CI. Cross-check: option 4. Seasonal cycle removed
first. Evidence: `.claude/skills/trend-stats/scripts/validate_type1.py` table in `docs/10-methods.md`.

## Consequences
- Verdicts are conservative and defensible to scientist judges ("Best Use of Science").
- Fewer "significant" results on short records → we show "years until detectable" to keep them informative.
