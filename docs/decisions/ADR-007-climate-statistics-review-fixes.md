# ADR-007 — Correct offline climate inference after scientific review

- Status: Implemented; human scientific sign-off pending
- Date: 2026-11-14
- Scope: Offline JSON pipeline 1.1.0; input/output envelope version remains 1.0
- Requirement IDs: R-03, R-04, R-05

## Context

Review of commit `552e581` reproduced degenerate SPEI fits, unstable rare-event inference,
seasonal-control attenuation, and ambiguous coverage thresholds. The synthetic example and
passing tests did not establish scientific validity for those cases. Integration with the web
contract and spatial processing is a separate scope; this change retains the JSON-in/JSON-out API.

## Decisions

1. Fit SPEI with unbiased probability-weighted moments and the generalized-logistic parameter
   mapping used by the author package/lmomco. Support reflected skewness and the logistic limit;
   reject invalid moments/support. Report calibration diagnostics and explicit tail clipping.
   SPI's zero-adjusted gamma fit is unchanged.
2. Estimate annual-event logistic coefficients with Firth's Jeffreys penalty. Keep point
   probabilities/ratios descriptive. Remove the contradictory basic-slope/percentile-ratio CIs.
   Test only sufficiently populated tails (10 events and 10 non-events) on complete annual series
   with at least six blocks. Permute full raw-value blocks, refit the baseline threshold in every
   permutation, and keep a short trailing remainder fixed. Any fit failure suppresses inference.
   This is an exchangeable-block approximation, not a general guarantee for arbitrary persistence.
3. Fit target, time, covariates and calendar-month effects jointly on the common observation
   window. Use calendar-aware Newey-West covariance with Bartlett weights and HC1 correction.
   One selected calendar month is treated as annual for covariance lags. HAC remains asymptotic.
4. Separate minimum valid sample size from actual calendar coverage. Introduce an independent
   daily aggregation threshold, fixed months for annual summaries, and an opt-in climatology-
   adjusted partial-mean policy. Partial precipitation totals remain prohibited. Adjusted partial
   means assume representative observed anomalies and do not propagate estimated-normal uncertainty.
5. Keep the declared global BH family; do not split tests after inspecting results. Increase the
   default and example resampling count to 999, expose resolution limits and both-method conservative
   flags. The number of significant tests is not the number of independent discoveries.
6. Preserve catalog cautions and expose a structured catalog status. Valid negative satellite
   NO2 retrievals and already decoded inputs are not blindly clipped or rescaled.

## Validation

The committed regression tests are in `backend/tests/test_climate_stats.py`. Run:

```powershell
python -m pytest -q backend/tests/test_climate_stats.py .claude/skills/trend-stats/scripts/test_trend_stats.py
python -m ruff check backend/trend_detective/climate_stats backend/tests/test_climate_stats.py
python scripts/make_climate_example.py
python scripts/analyze_climate.py --input examples/climate/input.json --output examples/climate/output.json
```

Independent checks performed during this change:

Final automated result: **70 tests passed**, Ruff lint/format checks passed, both JSON schemas
validated, and all 274 FDR audit pointers resolved to matching test values. The regenerated example
uses 999 replicates and contains 176 BH passes; these correlated synthetic tests are not independent
climate discoveries. Its original observation arrays were checked unchanged against commit `552e581`.

- Exact unbiased-PWM fixture `[-4,-2,-1,0,1,3,8,20]`: parameters
  `xi=0.2984869231271787`, `alpha=2.8157493540026324`, `kappa=-0.46320346320346323`.
  Agreement with an independent Fisk-CDF calculation to floating-point precision; reflected and
  symmetric-limit fixtures also checked. These are source-derived references, not an executed R run.
- Six saturated two-group Firth fits, including separation and constant outcomes, match
  `(successes + 0.5)/(group_size + 1)`, with maximum coefficient error `9.35e-8`.
- HAC agrees with an independent dense Bartlett-calendar-kernel sandwich at `rtol=1e-11`, using
  regular/irregular positions and bandwidths 0, 1, 3, 12, 300. Formula checked against statsmodels;
  that package was not installed or executed.
- Event-test sanity check: seed 641987, 100 independent 120-year Gaussian series in each of IID
  and AR(1) phi=0.6 scenarios, first 30 years as baseline, 39 permutations, 3-year blocks, two tails.
  IID: 154 eligible tests, 2 rejections at 0.05, 46 sparse-event skips. AR(1): 142 eligible,
  4 rejections, 58 sparse-event skips. No fit failures. Tail tests are dependent; this small check
  is evidence against an obvious failure, not a calibration guarantee.

Cached product checks used local files as of this date; no new NASA download was performed:

| Input cache | Explicit analysis policy | Observed behavior |
|---|---|---|
| `grace_lwe_022660a21500.csv` | coverage 0.8, adjusted partial annual means | 261/294 monthly values; 17 usable annual aggregates vs 14 strict. Monthly trend available; annual coverage still insufficient. |
| `mod13c2_ndvi_d92a40a99621.csv` | coverage 0.8, annual months April–September | 27 complete seasonal aggregates vs 3 complete calendar years; seasonal annual trend available. |
| `omno2d_daily_89cb466a32bb.csv` | daily coverage 0.4, series coverage 0.7, adjusted annual means | 203/266 retained months vs 3 strict; monthly trend available, annual inference still unavailable. The catalog's scientific caution remains. |

These policies are explicit sensitivity checks, not provider-approved universal quality thresholds.
The reports intentionally do not force unsupported methods to return a number.

Also checked the real Ukraine daily cache, restricted to 1981–2024, baseline 1981–2010:
`merra2_daily_T2M_MAX_896f393ef74d.csv`, `merra2_daily_T2M_MIN_7b47af8cfecb.csv`, and
`merra2_daily_PRECTOTCORR_f41449ef7210.csv`. The three sources share the same cached regional
bounding box; PET used its midpoint latitude 48.25 degrees. Daily indices and all four SPI/SPEI
scales calibrated successfully. SPEI-3 baseline standardized SDs were 0.9884–1.0066 and SPEI-6
0.9887–1.0095 across calendar months, with no clipped CDF warnings. These checks concern numerical
behavior and data handling, not a new attributed climate finding.

## Compatibility and remaining limits

`pipeline_version` changes to 1.1.0. SPEI parameter names and calibration method change; logistic
CI fields disappear, and sparse cases explicitly lack inference. New coverage guards can make
previously accepted sparse series return `skipped`. The documentation specifies the new settings.
The original raw synthetic values remain unchanged; its resampling configuration and results are
regenerated. Existing v1.0.0 SPEI/event uncertainty and document-wide q-values should be recomputed.

General AR(1)/HAC approximations, finite resampling resolution, missing-not-at-random satellite
observations, quantile inference on monthly rather than daily values, and exploratory change-point
power remain limitations. None are claimed solved by a passing test suite.

Primary sources and complete method details are linked from
[`climate-statistics-pipeline.md`](../climate-statistics-pipeline.md).
