# Offline JSON climate statistics pipeline

The pipeline accepts regional or point time series as JSON and writes statistics as strict JSON.
It accepts all **28 catalog variables and 3 internal inputs**, including variables whose NASA
download reader is not implemented: the caller supplies the actual values.

The implementation is `backend/trend_detective/climate_stats/`. It runs entirely offline and does
not depend on the web app, Earthdata credentials, statsmodels, or the archive analysis environment.

## Quick start

From the repository root:

```powershell
python -m pip install -r requirements-climate-stats.txt
python scripts/analyze_climate.py --input examples/climate/input.json --output examples/climate/output.json
```

The example is **synthetic**, not a finding about Ukraine. Regenerate it, or create a daily example:

```powershell
python scripts/make_climate_example.py --output examples/climate/input.json
python scripts/make_climate_example.py --daily --output examples/climate/daily-input.json
python scripts/analyze_climate.py --input examples/climate/daily-input.json --output examples/climate/daily-output.json
python scripts/analyze_climate.py --list-variables
```

The example and normal default use 999 resampling replicates. A smoke run can explicitly choose
39, with much coarser uncertainty. The smallest attainable resampling p-value is `1 / (B + 1)`;
999 is not a guarantee of adequate resolution for every multiple-testing family. The FDR audit
reports resolution and the replication count needed to reach the rank-one BH threshold.
Use `bootstrap_samples: 0` to disable resampling; unavailable
inference is explicitly marked rather than replaced with an independence-based test.

## Input contract

Schema: [`climate-input.schema.json`](../schema/climate-input.schema.json).

```json
{
  "schema_version": "1.0",
  "metadata": {"project": "regional climate analysis"},
  "config": {
    "baseline": [1981, 2010],
    "alpha": 0.05,
    "fdr_q": 0.05,
    "bootstrap_samples": 999,
    "seed": 1729
  },
  "series": [
    {
      "id": "ukraine_temperature",
      "variable_id": "air_temperature_power",
      "region_id": "ukraine",
      "latitude": 49.0,
      "frequency": "monthly",
      "units": "degC",
      "values": [
        {"date": "1981-01", "value": -4.2},
        {"date": "1981-02", "value": null},
        {"date": "1981-03", "value": 2.1}
      ]
    }
  ]
}
```

This snippet illustrates structure only; three observations cannot support a climate trend. The
generated example contains complete 1981–2024 records. Dates can differ among series. Values need
not be sorted; duplicate dates at the declared frequency are rejected.

| Field | Meaning |
|---|---|
| `id` | Unique series key. Multiple regions or sources need distinct keys. |
| `variable_id` | Exact `id` from [`variables.yaml`](../data/catalog/variables.yaml), including `T2M_MAX`, `T2M_MIN`, or `PRECTOTCORR_SUM`. |
| `region_id` | Caller-defined region/point identifier. Derived combinations use only series in the same region. |
| `frequency` | `daily`, `monthly`, or `annual`. |
| `units` | Physical units, validated and normalized. Required to prevent hidden scaling mistakes. |
| `latitude` | Optional latitude in degrees, required for PET and hemisphere-dependent indices. Values for one region must agree. |
| `values` | Array of `{date, value}` records; a value is a finite number or `null`. |
| `fill_values` | Optional numeric sentinels such as `[-999]`, replaced with missing values before unit conversion. |
| `provenance` | Optional source/processing metadata, preserved in the output. |
| `semantics` | Monthly `T2M_MAX` requires `mean_daily_maximum`; monthly `T2M_MIN` requires `mean_daily_minimum`. |

Daily dates use `YYYY-MM-DD`; monthly dates use `YYYY-MM` or `YYYY-MM-DD` and normalize to the
month's first day; annual dates use `YYYY` or `YYYY-01-01`. Supported years are 1800–2200. A document
contains at most 200 primary series; each series contains at most 200,000 records/calendar steps.

Input values must already have satellite packing/scale factors decoded. For example, NDVI `8000`
must become `0.8` before input. The pipeline does not evaluate YAML `convert` expressions or apply
packing factors implicitly. It uses an explicit conversion table:

| Input | Analysis units / operation |
|---|---|
| Temperature in K | °C: subtract 273.15, including MODIS land-surface temperature. |
| Temperature already in °C / `degC` | Keep unchanged. |
| POWER soil wetness, sea ice or snow fractions supplied as % | Fraction 0–1: divide by 100. |
| Cloud/MODIS snow percentages supplied as fractions | Percent: multiply by 100. |
| Solar radiation in W/m² | MJ/m²/day: multiply by 0.0864. Already converted values remain unchanged. |
| GLDAS evapotranspiration in kg/m²/s | mm/day: multiply by 86,400. |
| Other catalog units | Preserve physical units; unsupported units fail validation. |

GRACE remains an anomaly in equivalent water-height cm. `Qs_acc` keeps its stated 3-hour
accumulation units; the pipeline does not silently treat it as river discharge or monthly totals.
IMERG supplied in mm/day is not multiplied by 24. Temperature/GRACE percent changes are suppressed
according to catalog semantics. Relative change for other variables uses the physical mean, never
the near-zero anomaly mean, and requires nonnegative values and a positive mean.

## Time, baseline and missing-data rules

- Each series represents an already aggregated region or point. Gridded input and spatial area
  weighting are upstream responsibilities; the pipeline does not average unrelated regions.
- Calendar gaps are inserted explicitly as missing values. Nothing is interpolated.
- Daily state/rate values become monthly means when at least `daily_min_coverage` of actual days
  are valid. If unset, it inherits `min_coverage` (90%). Accepted means estimate the observed-day
  population; relaxing coverage does not correct cloud/sampling bias.
- Annual and seasonal means are weighted by days in each month. The default `strict` policy
  requires every constituent month. `annual_months` selects a fixed set, such as April–September
  for vegetation; this changes the annual diagnostics, not the main full monthly trend. The set
  January/February/December always uses DJF years regardless of its input order.
- Opt-in `annual_missing_policy: "climatology_adjusted"` permits partial state/rate means when
  `annual_min_coverage` of selected months exists (default 80%). It adds the day-weighted full
  selected-month climatology to the day-weighted mean of observed anomalies. Every selected month
  needs a valid baseline normal. This assumes observed anomalies represent missing months; it
  cannot remove nonrandom missingness and does not propagate climatology-estimation uncertainty.
  `annual` records the policy, months and caveat. Daily indices remain complete-year diagnostics.
- `PRECTOTCORR_SUM` is summed, with units mm/year or mm/season for those aggregates. Daily
  precipitation totals used by drought indices require every day of the month; partial sums are
  never presented as complete totals.
- Daily event counts and runs require complete years. Missing days never become dry days or
  frost-free days. DJF is labeled by the year of January/February.
- `baseline: null` (default) uses the full input record and records that choice. An explicit
  baseline is restricted to its actual overlap; it is never silently replaced. Monthly anomalies
  require at least five baseline observations per calendar month by default. Insufficient months
  remain missing.
- Trend/quantile inference requires at least `min_years * observations_per_year` valid observations,
  at least `min_years` calendar duration, and actual calendar coverage >= `min_coverage`.
  Monthly coverage uses every calendar month in the input window, including explicit gaps.
  Insufficient adjacent residual pairs suppress AR(1)-based p-values and confidence intervals.
- Block resampling requires a complete regular analysis series. It reports a skip reason for gaps,
  rather than removing gaps and pretending that distant observations are adjacent.

For satellite records, choose policies explicitly before interpreting results. For example,
`{"annual_months": [4,5,6,7,8,9], "min_coverage": 0.8}` produces fixed growing-season annual
diagnostics, while `{"daily_min_coverage": 0.4}` permits sparse daily retrievals to form means.
These are sensitivity-analysis settings, not universally approved product QA thresholds.
`analysis_quality` reports retained monthly values and usable annual aggregates. Missing runs
can still prevent annual trends or block inference. Catalog warnings, including OMI's `under review`,
are retained in `quality.warnings`; `catalog_status` also exposes the status directly.

## Computed statistics and insight building blocks

| Method / configuration key | Output | Questions it can support |
|---|---|---|
| Always: descriptive statistics | `descriptive`, `analysis_descriptive`, `annual.descriptive` | Typical level, range, variability, tails, zero frequency. Mean, median, sample SD/variance, min/max and dates, quantiles, IQR, MAD, trimmed mean, skewness, excess kurtosis and appropriate CV. |
| Always: monthly climatology | `climatology` | Seasonal cycle, peak month, seasonal amplitude, ordinary and standardized anomalies. |
| `trend` | `trend`, `annual.trend` | Direction and magnitude: Sen slope and CI per decade; tie-corrected MK with AR(1) variance inflation; secondary OLS with effective sample size; detectability estimate. |
| M1: `monthly_profile`, `seasonal` | `monthly_profile`, `seasonal.DJF/MAM/JJA/SON` | Which calendar months/seasons change most? Each has its own distribution and trend tests. |
| M2: `indices` | `daily_indices`, `derived.<region>.temperature` | FD, TR, TNn, SU, ID, TXx, TX90p variant, last spring frost, CDD/CWD, Rx1day/Rx5day, R10mm/R20mm, PRCPTOT, SDII, DTR and growing-season length where inputs permit. |
| M3: `drought` | `derived.<region>.drought` | SPI and SPEI at configured accumulation scales, PET, dry-month frequencies by decade and fixed-end-month annual trends. |
| M4: `emergence` | `emergence` | When fitted change first exceeds one detrended annual SD. Candidate year is descriptive; visible `year` requires both annual MK and OLS to pass FDR. |
| M5: `probability` | `probability_change` | Baseline low/high event counts, Firth logistic point estimates and eligible block-permutation tests; no logistic confidence interval is claimed. |
| M6 adaptation: `quantiles` | `quantile_trends` | Slopes of configured quantiles of monthly anomalies or annual values; direct upper-tail-minus-median slope contrast. |
| M7: `acceleration` | `acceleration` | Sen slopes in two prespecified halves, block CI/test of their difference, and a local-linear smooth curve labeled as visualization. |
| M8: `variability` | `variability` | Ratio of separately detrended annual SDs; block inference on the log ratio. Brown–Forsythe p is labeled IID-only and excluded from FDR. |
| M9/general controls: `drivers` | `drivers` | Time trend and covariates jointly adjusted for month effects; Newey–West HAC uncertainty. |
| M10: `bootstrap` | `bootstrap` | Moving-block residual-bootstrap uncertainty for Sen's slope. |
| Additional: `change_point` | `change_point` | Pettitt maximum-rank level-shift diagnostic on detrended annual data, calibrated by block resampling. |
| Additional: `relationships` | `relationships`, `region_contrasts` | Detrended Pearson/Spearman associations at explicit lags; paired difference trends for the same variable in different regions. |
| M11: always | `insights_audit` and each computed test | Document-wide BH adjusted p-values and significance decisions. |

The aggregate Seasonal Kendall test from the method brief is not implemented; month-specific
MK tests and the full anomaly-series MK test are reported separately. Quantile regression is on
monthly anomalies (or annual input), not daily summer Tmax. Therefore it cannot substantiate a
claim about the hottest individual days; daily indices provide separate evidence about those.

### Statistical implementation

Sen pairwise slopes, tie-corrected MK statistics/variance and BH adjustment reuse
[the existing reference engine](../.claude/skills/trend-stats/scripts/trend_stats.py).
The new adapter computes lag-one correlation only from actual adjacent calendar observations.
For observed calendar positions `s_i`, it uses:

```text
eta = 1 + (2/n) * sum(i < j) max(rho, 0) ** (s_j - s_i)
Var_corrected(S) = eta * Var_iid(S)
n_eff = n / eta
```

For regular observations this is the reference finite AR(1) variance factor. This adapter's
adjacent-pair correlation estimate and finite-sample OLS correction need not produce bitwise
identical values to the earlier engine's complete-series convenience function. Negative serial
correlation is not used to narrow CIs. AR(1) is an approximation, not a guarantee for arbitrary
long-memory processes. Pairwise Sen/MK calculations stop above the reference engine's 3,000-point
limit; daily data are first aggregated to months.

Bootstrap intervals for slopes/differences use the basic centered interval. Their approximate
two-sided p-values compare centered bootstrap deviations with the absolute observed effect,
including the `+1` finite-resampling correction. Quantile regression resamples blocks of observed
pairs while retaining original time coordinates. Failed resamples suppress inference and report
attempted/successful/failed counts. All resampling uses reproducible per-method seeds.

Trend objects expose `methods_disagree`, `conservative_significant_unadjusted` and, after FDR,
`conservative_significant_fdr`. The conservative flags require both MK and OLS to pass. The FDR
audit still counts individual tests rather than claiming independent discoveries. Zero-heavy
derived indices also receive tied-value/zero-Sen-slope warnings.

### Rare annual events

Logistic point estimates maximize `log L + 0.5 log det(X' W X)` (Firth/Jeffreys adjustment).
They remain finite under separation and are explicitly descriptive; large probability ratios
and model-based recurrence intervals are not independently established climate risks.

Inference requires at least 10 events and 10 non-events, a complete annual series, and six
complete blocks. These are conservative eligibility rules, not guarantees of calibration.
Full nonoverlapping blocks of raw annual values are permuted; the final short remainder stays
fixed. Every permutation refits the baseline quantile, event labels and Firth model. The
two-sided statistic is the absolute time coefficient and p is `(1 + exceedances)/(B + 1)`.
Any optimization failure suppresses the entire test. This is conditional on exchangeable
blocks and only approximate for dependence crossing block boundaries. No basic/percentile
logistic CIs are emitted, avoiding contradictory evidence for the same null effect.

### Daily indices

FD/TR and TNn require daily `T2M_MIN`; SU/ID, TXx and TX90p require daily `T2M_MAX`.
Precipitation indices require daily precipitation rates. Threshold/range/spell definitions follow
the [Climdex index reference](https://www.climdex.org/learn/indices/) where stated, with explicit
implementation boundaries:

- TX90p uses a centered five-calendar-day baseline window and handles February 29 separately.
  It **does not implement ETCCDI's in-baseline bootstrap correction**, so it is labeled a fixed-baseline variant.
- CDD/CWD are bounded by calendar years; Rx5day windows are wholly within the reported year.
- GSL uses six-day warm/cold runs and July–June years in the Southern Hemisphere. It requires
  latitude. A year without an observed cold-season endpoint is censored rather than fabricated.
- Last spring frost DOY is an additional Northern Hemisphere indicator. No-frost years are null,
  so its trend is explicitly conditional on years with a frost event.

### SPI, SPEI and PET

Each precipitation source in a region is analyzed separately. Multiple ambiguous Tmax/Tmin
sources cause the combined temperature/PET method to skip rather than choose a source silently.
Annual-only precipitation cannot produce SPI/SPEI.

SPI uses a zero-adjusted gamma distribution fitted by maximum likelihood for each calendar month.
SPEI uses unbiased probability-weighted moments of accumulated `P - PET`, mapped to the
generalized-logistic parameterization in the author package: `xi`, `alpha`, `kappa`. This includes
the positive-skew log-logistic, reflected negative-skew form and symmetric logistic limit.
Invalid L-moments or a support boundary excluding baseline observations fail calibration.
Fits require at least 20 baseline values per calendar month by default and report failures.
Overlapping accumulation windows are not treated as independent trend observations: trend tests
use one configured end month per year. Clipped CDF tails prevent infinite standardized values;
per-month diagnostics count clipping and actual support violations separately, and report
baseline standardized medians/SDs. A nonstationary full record need not have median zero or SD one.

PET uses monthly means of daily Tmax/Tmin and monthly mean extraterrestrial radiation. The
Hargreaves calculation includes **0.408 to convert radiation in MJ/m²/day to equivalent water**,
as required by [FAO-56, meteorological data and equation 52](https://www.fao.org/4/x0490e/x0490e07.htm).
This is an approximation to reference evaporative demand, not actual land evaporation. The
pipeline does not substitute `EVLAND` for PET or infer a causal attribution from SPI/SPEI divergence.

## Optional NAO or other covariates

Covariates are supplied explicitly; there is no network fetch. They use the same time-series
structure but omit `variable_id`. Add a control specification:

```json
{
  "controls": [
    {
      "series_id": "ukraine_temperature",
      "covariate_ids": ["nao"],
      "months": [12, 1, 2]
    }
  ]
}
```

The `covariates` array must contain the `nao` record with its actual dates and values. Within the
common observation window the model jointly fits raw target values on time, aligned covariates
and calendar-month fixed effects. This adjusts target, time and controls consistently, including
seasonal controls; covariates already expressed as anomalies remain supported.

Uncertainty uses the Newey–West sandwich with Bartlett weights at actual calendar distances,
`n/(n-k)` correction and approximate t inference. Bandwidth is `block_months` for monthly fits
or `block_years` for annual/one-calendar-month fits; `hac_lag_unit` records the distinction.
This is asymptotic inference whose sensitivity to bandwidth should be checked. Constant/collinear
covariates and insufficient observations cause a skip. Selecting an appropriate driver and
season remains the analyst's responsibility; NAO is not automatically applied to every region.

## Configuration

| Setting | Default | Meaning |
|---|---|---|
| `baseline` | `null` | Full input record, or explicit `[first_year, last_year]`. |
| `alpha` | `0.05` | Unadjusted test threshold and CI tail probability. |
| `fdr_q` | `0.05` | Document-wide BH threshold. |
| `min_years` | `10` | Minimum calendar span and valid observation count divided by frequency. |
| `min_climatology_years` | `5` | Minimum baseline count per calendar month. |
| `min_coverage` | `0.9` | Actual calendar coverage required for trend/quantile/relationship inference. |
| `daily_min_coverage` | `null` | Daily-to-monthly coverage; null inherits `min_coverage`. |
| `annual_months` | `[1,...,12]` | Fixed months for annual summaries and DTR; daily indices unchanged. |
| `annual_missing_policy` | `strict` | Require all months, or opt into `climatology_adjusted` partial means. |
| `annual_min_coverage` | `0.8` | Minimum fraction of selected months for adjusted partial means; totals always complete. |
| `bootstrap_samples` | `999` | Bootstrap/permutation replicates; `0` disables, otherwise at least 19. |
| `block_months`, `block_years` | `12`, `3` | Resampling block lengths and HAC calendar bandwidths. |
| `seed` | `1729` | Reproducible resampling seed. |
| `split_year` | `null` | Last year of first period; default calendar midpoint, not an optimized break. |
| `drought_scales` | `[3, 6]` | Accumulation windows in months, 1–24. |
| `drought_end_month` | `8` | Fixed annual SPI/SPEI observation used for trend inference. |
| `min_drought_baseline_years` | `20` | Minimum calendar-month calibration sample. |
| `quantiles` | `[0.1, 0.5, 0.9]` | Quantile regression probabilities. |
| `correlation_lags` | `[0]` | Monthly or annual lags; positive means left variable leads right. |
| `include_series` | `true` | Include time series/anomalies in the output. |
| `methods` | All listed methods | Choose an explicit subset; `[]` gives descriptive statistics/climatology only. |

## Output and interpretation

Schema: [`climate-output.schema.json`](../schema/climate-output.schema.json). It validates the
output envelope; method-specific contents are documented above and covered by numerical tests.

```text
schema_version, pipeline_version, status
config, metadata, provenance, assumptions
series.<id>
  quality, analysis_quality, catalog_status, descriptive, analysis_descriptive, climatology
  trend, annual, monthly_profile, seasonal
  emergence, probability_change, quantile_trends
  acceleration, variability, bootstrap, change_point, daily_indices
derived.<region>
  temperature.{dtr,gsl}
  drought.sources.<precipitation_series_id>
relationships[], region_contrasts[], drivers
insights_audit
```

Methods not requested are omitted. Requested but inapplicable methods use
`{"status": "skipped", "reason": "..."}`. Missing/undefined numeric results are `null`, never
`NaN` or `Infinity`. Top-level `status: ok` means the analysis executed, not that every test found
a significant effect. Descriptive summaries do not have p-values because no null hypothesis is
defined for an ordinary mean, median or range.

Each inferential test has `p_value`, `q_value`, `significant_unadjusted`, and `significant_fdr`
when inference is available. Use the FDR flag, effect size, interval and quality warnings together
when selecting an insight. All computed tests, including primary and secondary checks, enter one
family because the input does not declare a single pre-registered primary hypothesis. This is
deliberately broader than the per-case family in the method brief. BH assumes independence or
appropriate positive dependence; it does not establish causation or physical importance.

`insights_audit.tests` contains JSON-pointer paths to tested objects. User metadata and provenance
are excluded from hypothesis collection. No automatic insight prose is produced.
`resampling_resolution` records minimum attainable p-values and
`replicates_for_rank_one_resolution` reports `ceil(number_of_tests / fdr_q) - 1`. This is a
rank-one resolution diagnostic, not a necessary replication count for every BH rejection.
The family is retained globally rather than split after looking at significant results.

`provenance` records the normalized input hash, catalog hash, reference-engine hash, library
versions and seed. There is no runtime timestamp, so rerunning identical inputs in the same
environment produces identical results. Output is written atomically; invalid input leaves an
existing output untouched, and input/output paths must differ.

## Python API

When `backend` is on the Python path:

```python
from trend_detective.climate_stats import analyze, analyze_file

result = analyze(payload)  # strict-JSON-compatible dict; invalid input raises ValueError
result = analyze_file("input.json", "statistics.json")
```

## Verification and references

```powershell
python -m pytest -q backend/tests/test_climate_stats.py .claude/skills/trend-stats/scripts/test_trend_stats.py
```

Tests exercise known trends, serial correction, units, all 31 variable ids, calendar gaps,
constant/empty series, baseline failures, FDR, daily missingness, leap days, both hemispheres,
PET units, SPI, quantile optimization, driver adjustment, schemas and atomic JSON writing.
Review regressions also cover source-derived PWM fixtures, reflected/logistic limits, Firth's
saturated-binomial closed form, threshold re-estimation inside permutations, solver failures,
seasonal controls, actual calendar coverage, selected-season aggregation and metadata isolation.

Project method context: [`10-methods.md`](10-methods.md) and
[the supplied method brief](<../Статистика методи.md>). The implementation distinguishes the brief's
illustrative insights from actual computed evidence.

Brown–Forsythe uses the median-centered implementation documented in
[SciPy's Levene test](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.levene.html).
Quantile regression minimizes pinball loss with
[SciPy's linear-programming solver](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html).
The existing reference engine remains the source for Sen/MK/BH formulas.

Additional primary implementation references:

- [SPEI author manual: PWM and distributions](https://sbegueria.r-universe.dev/SPEI/doc/manual.html).
- [lmomco PWM](https://raw.githubusercontent.com/cran/lmomco/master/R/pwm.R),
  [parameter mapping](https://raw.githubusercontent.com/cran/lmomco/master/R/parglo.R),
  [CDF](https://raw.githubusercontent.com/cran/lmomco/master/R/cdfglo.R).
- [Firth logistic likelihood and inference](https://search.r-project.org/CRAN/refmans/logistf/html/logistf-package.html).
- [Newey–West covariance reference implementation](https://www.statsmodels.org/stable/_modules/statsmodels/stats/sandwich_covariance.html).
- [Review fixes and validation](decisions/ADR-007-climate-statistics-review-fixes.md).
