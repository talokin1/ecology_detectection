# Statistics: methods and insights

The base pipeline answers one question: "is there a trend?". Insights come from the follow-up
questions: when, on which days, why, how much more often. Every method below was added because it
answers one such question asked by a real person.

## Question → method → insight

| A person's question | Method | How the insight reads (example) |
| --- | --- | --- |
| Is something really changing? | Base pipeline (Sen + MK + OLS) | Evidence: the soil is getting drier |
| In which months is the change strongest? | M1 Monthly trend profile | Most of the drying happens in July and August |
| What does it mean for a vegetable garden? | M2 ETCCDI extreme indices | The frost-free season is 12 days longer than in the 1980s |
| Is it less rain, or is it the heat? | M3 SPI vs SPEI | Rain barely changed; heat dries the soil faster |
| Since which year is it no longer chance? | M4 Time of emergence | Since about 2008 the change is bigger than a normal year-to-year swing |
| How much more often do bad years come? | M5 Change in probability and return period | A summer this dry used to come once in 10 years, now about once in 3 |
| Do the hottest days change like ordinary days? | M6 Quantile regression | The hottest days warm faster than typical days |
| Is the change speeding up? | M7 Two half-periods + smooth trend | The second half of the record changed twice as fast |
| Have years become less predictable? | M8 Change in spread | Years became not only drier but also more uneven |
| Is it not just natural oscillation? | M9 NAO adjustment | The trend stays after removing the North Atlantic swing |
| How far can we trust the number? | M10 Block bootstrap | not an insight, an independent check for Methods |
| Did we find this by chance? | M11 FDR across all insights of a case | not an insight, a filter: we show only what passes it |

The numbers in the examples are made up and only show the shape of the sentence. Real results may
differ or fail the M11 filter altogether.

## Glossary

Each row says what the term means and why we cannot do without it. The "In plain words" column can
be moved almost verbatim into the app's Glossary.

| Term | In plain words | Why we need it |
| --- | --- | --- |
| Climate normal (baseline period) | The average value for each calendar month over fixed years, for us 1981–2010 | Reference point for anomalies, extreme thresholds and "how it was in the 80s" |
| Anomaly | How much this month differs from its normal: January is compared with January, not with July | Removes the seasons, which would otherwise hide the trend |
| Trend | A steady long drift in one direction. We look for a monotonic trend | The main object of the challenge |
| Theil-Sen slope | The median of the slopes between all pairs of points. A few odd months do not shift it | The rate of change "per decade" on every card |
| Mann-Kendall test (MK) | Counts whether later values are larger than earlier ones more often than chance would allow. It looks only at order, not at magnitudes | Main significance test; does not need a normal distribution |
| Autocorrelation, AR(1), φ | Neighbouring months are alike: a dry July often has a dry August. φ is how strongly a month "remembers" the previous one | Without correcting for it, classic MK gives 14–33% false trends instead of 5% |
| Effective sample size n\_eff | How many truly independent observations the series holds. 528 similar months may weigh as much as 150 independent ones | Honest interval widths and an honest p |
| Yue-Wang correction | Inflates the MK variance by as much as the series is autocorrelated | Keeps false alarms at 3–6% in our simulation |
| OLS t-test with n\_eff | Ordinary linear regression, but the degrees of freedom come from n\_eff | A second, independent judge for the verdict |
| p-value | If there is really no trend, this is the probability of seeing a trend this strong or stronger. It is not the probability that the trend is real | Threshold for verdict levels; shown in small print in the UI |
| Confidence interval (CI) | The range in which, with 95% confidence, the true rate lies. In the UI: "likely range" | The key number for a student: easier than p |
| False alarm and power | False alarm: the test says "trend" when there is none. Power: the chance of finding a trend when there is one | This is exactly what we measure in the simulation; our argument for Validity |
| Multiple testing, FDR, BH | Run 100 tests and about 5 will be "significant" by chance. The Benjamini-Hochberg procedure controls the share of false ones among the findings (q) | Map stippling and the insight filter (M11) |
| cos(latitude) weights | Grid cells near the poles are smaller in area, so they weigh less | Correct regional average |
| Reanalysis (MERRA-2) | A weather model continuously corrected by observations. Gives complete data with no gaps, but it is not a direct measurement | Source of POWER; we state its limits honestly in Methods |
| Percentile, extreme threshold | The 90th percentile is the value exceeded by only one day or month in ten during the baseline period | "Dry month", "hot day" without arbitrary numbers |
| Signal / noise | Total change along the trend divided by the typical year-to-year spread | The clearest measure of "is it noticeable yet" (M4) |
| Years to detection | How many years of data are needed for such a trend to become visible at this noise level | An answer instead of a dry "p > 0.05" |
| Series break, Pettitt test | An abrupt level jump, e.g. after a satellite replacement. The test shows where it is and whether it is real | Do not mistake a sensor jump for a trend |
| Block bootstrap | Resample whole chunks of the series many times and see how the result varies | Uncertainty where no ready formula exists (M5, M6, M10) |

## Base level in formulas

All of this already exists in `trend_stats.py` and is tested. The formulas are collected here so
that anyone on the team can explain them to a judge.

**Anomaly.** Subtract the mean of the value's calendar month m(t).

```math
a_t = x_t - \bar{x}_{m(t)}
```

**Sen's slope.** Median over all n(n − 1)/2 pairs.

```math
\hat\beta = \operatorname{median}_{i<j} \frac{a_j - a_i}{t_j - t_i}
```

**Mann-Kendall with the Yue-Wang correction.** S counts pairs where the later value is larger minus
pairs where it is smaller. The factor η inflates the variance as if there were fewer data. r₁ is the
autocorrelation of the series after removing the Sen trend.

```math
S = \sum_{i<j} \operatorname{sgn}(a_j - a_i), \qquad \operatorname{Var}(S) = \frac{n(n-1)(2n+5)}{18}
```

```math
\operatorname{Var}^*(S) = \eta \operatorname{Var}(S), \qquad \eta = 1 + 2\sum_{k=1}^{n-1}\left(1-\frac{k}{n}\right) r_1^{\,k}, \qquad Z = \frac{S - \operatorname{sgn}(S)}{\sqrt{\operatorname{Var}^*(S)}}
```

**OLS with effective n.** The second test uses n\_eff − 2 degrees of freedom.

```math
n_{\text{eff}} = n\,\frac{1-r_1}{1+r_1}
```

**Years to detection (Weatherhead et al., 1998).** σ\_N is the noise, φ its autocorrelation, ω₀ the
trend per year. The formula gives the number of years after which such a trend is detected with
probability 90% at α = 0.05.

```math
n^* = \left[\frac{3.3\,\sigma_N}{|\omega_0|}\sqrt{\frac{1+\phi}{1-\phi}}\right]^{2/3}
```

**Benjamini-Hochberg.** Sort the m p-values in ascending order. The first k become significant,
where k is the largest index for which the condition holds.

```math
p_{(k)} \le \frac{k}{m}\,q
```

## Advanced statistics

Each method follows one template: how we compute it, why we need it, where the pitfalls are, and
what appears in `analysis.json`. All trends on new series use the same Sen + MK Yue-Wang. We do not
invent new trend tests.

### M1. Monthly trend profile

- **How.** For each calendar month take a separate annual series (44 points) and compute Sen + MK.
  The overall test is Seasonal Kendall (Hirsch, Slack & Smith, 1982): S = Σ S\_m over months
- **Why.** 12 bars with CIs show when in the year the change happens. For a garden this matters more
  than the annual mean
- **Pitfalls.** These are 12 tests, so they go through M11. 44 points each give wide CIs
- **Output.** `monthly_profile[12]`: slope, CI, p, q

### M2. ETCCDI extreme indices

- **How.** From daily T2M\_MAX, T2M\_MIN, PRECTOTCORR (POWER) compute annual indices using the ETCCDI
  definitions (Zhang et al., 2011). Each index is an annual series; its trend is computed exactly as
  for the base series
  - **FD** — days with Tmin < 0 °C
  - **GSL** — growing season length: from the first 6 consecutive days with Tmean > 5 °C to the first
    6 days with Tmean < 5 °C after 1 July
  - **Last spring frost date** — the last day with Tmin < 0 °C before 1 July. This is our addition,
    not ETCCDI
  - **TX90p** — share of days with Tmax above the baseline-period 90th percentile
  - **CDD** — longest run of days with precipitation < 1 mm
- **Why.** Translates climate into the language of a garden: when to plant, how long the season
  lasts, how long a dry spell lasts. A direct answer to grandma
- **Pitfalls.** POWER is a reanalysis with 0.5° cells and does not see frost in low-lying spots.
  TX90p has a known bias inside the baseline period (Zhang et al., 2005); we note it in Methods.
  Both dates are expressed as day of year, not calendar date
- **Output.** `indices.{fd, gsl, last_frost_doy, tx90p, cdd}`: annual series + trend

### M3. SPI vs SPEI: rain or heat

- **How.** SPI (McKee et al., 1993) is computed from precipitation only. SPEI (Vicente-Serrano et al.,
  2010) from the water balance D = P − PET. PET follows Hargreaves & Samani (1985) from Tmax, Tmin
  and latitude (Ra is computed astronomically). Then accumulate over 3 and 6 months, fit a
  distribution for each calendar month (gamma for SPI, log-logistic for SPEI) and convert to a
  z-scale. Drought means index < −1

```math
PET = 0.0023\,R_a\,(T_{mean}+17.8)\sqrt{T_{max}-T_{min}}
```

- **Why.** This is the main "why" for case 01. If SPI does not change but SPEI falls, the drought is
  driven by heat, not by lack of rain. Two series on one chart make a strong frame
- **Pitfalls.** Accumulation makes the series highly autocorrelated: neighbouring SPEI-6 values share
  5 of 6 months. So we test the trend on one value per year, e.g. August SPEI-6. Hargreaves is crude.
  The more accurate Penman-Monteith needs wind, radiation and humidity; POWER has them, so it is in
  level B
- **Output.** `drought.{spi3, spei3, spei6}`: series, trend, drought months per decade

### M4. Time of emergence

- **How.** Following Hawkins & Sutton (2012): the signal S(t) is the change along the trend relative
  to the start of the series; the noise N is the std of detrended annual anomalies. ToE is the first
  year after which S/N stays > 1

```math
\frac{S(t)}{N} = \frac{\hat\beta\,(t-t_0)}{\operatorname{sd}(\text{detrended annual anomalies})}
```

- **Why.** Answers "since when is it no longer chance" in years. People remember a year better than
  any slope
- **Pitfalls.** ToE depends on the threshold (1 or 2). We fix 1 and write exactly "bigger than a
  typical year-to-year swing". Shown only for verdicts of moderate and above
- **Output.** `emergence.{year, ratio_now}`

### M5. Change in the probability of a bad year

- **How.** The threshold u is the 10th or 90th percentile of seasonal values over 1981–2010, fixed in
  advance. The primary approach is logistic regression of the exceedance probability on year: it
  gives a smooth p(t) from which we take p at the start and at the end of the series. Check: direct
  counts in 1981–2000 and 2005–2024. CI: block bootstrap over years

```math
\operatorname{logit} P(x_t > u) = \alpha + \gamma t, \qquad PR = \frac{p_{\text{now}}}{p_{\text{then}}}, \qquad \text{return period} = \frac{1}{p}
```

- **Why.** "Once in 10 years → once in 3" is understood instantly. Attribution studies use this
  format (the probability-ratio idea: Stott et al., 2004), but for us it describes observations, not
  attribution
- **Pitfalls.** Samples are small (20 years each), so CIs are wide and must be shown. The threshold
  must not be tuned to the result. We do not write "because of climate change": that is attribution,
  which we do not do
- **Output.** `odds.{threshold, p_then, p_now, pr, pr_ci, return_then, return_now}`

### M6. Quantile regression: are the tails growing

- **How.** Koenker-Bassett (1978) regression on daily anomalies of summer Tmax for τ = 0.1, 0.5, 0.9.
  Compare the slopes β(0.9) and β(0.5). CI: block bootstrap by whole years, because days are strongly
  dependent
- **Why.** The mean may rise slowly while the very hot days that hurt crops rise fast. Dashboard apps
  do not show this insight
- **Pitfalls.** Needs daily data (about 4,000 points per season); 500 bootstrap runs take minutes.
  A faster-growing tail does not yet mean higher variability; M8 checks that
- **Output.** `quantiles[{tau, slope, ci}]`

### M7. Acceleration

- **How.** The split in half is fixed in advance: 1981–2002 and 2003–2024. Compute Sen for each half
  and the difference with a bootstrap CI. For the chart add a smooth LOESS line labelled "smoothed,
  not a test"
- **Why.** "The change is faster in the second half" is what people feel themselves
- **Pitfalls.** The biggest trap is searching for the breakpoint that gives the prettiest result.
  That is p-hacking, and we do not do it. The halves are short, so we show the insight only when the
  difference is significant
- **Output.** `acceleration.{slope_first, slope_second, diff, ci}`, `smooth[]`

### M8. Change in spread

- **How.** Take the std of detrended annual anomalies in the two halves. Test the ratio σ₂/σ₁ with
  the Brown-Forsythe test or a bootstrap
- **Why.** For agriculture, "years became uneven" matters as much as a shift in the mean
- **Pitfalls.** With 22 points the power is low, and the result will often be "no clear change". That
  is an honest result, but we do not show it as an insight
- **Output.** `variability.{sd_first, sd_second, ratio, p}`

### M9. North Atlantic Oscillation (NAO) adjustment

- **How.** Regress winter (DJF) anomalies on time and the NAO index (NOAA CPC, monthly). Compare β
  before and after accounting for NAO. Check the residuals for autocorrelation the same way as in
  OLS n\_eff

```math
a_t = \alpha + \beta t + \gamma\,\mathrm{NAO}_t + \varepsilon_t
```

- **Why.** A scientist judge will ask "maybe it is just NAO?". If the trend survives the adjustment,
  the verdict becomes much stronger
- **Pitfalls.** The source is not NASA: that is allowed, but it must be added to the references. NAO
  is meaningful only for winter in Europe. If NAO itself has a trend, the effects cannot be cleanly
  separated
- **Output.** `drivers.nao.{beta_raw, beta_adjusted, gamma, r2}`

### M10. Block bootstrap as an independent check

- **How.** Moving-block bootstrap (Künsch, 1989): 12-month blocks, 1,000 runs. From it, the CI of
  Sen's slope, compared with the analytic one
- **Why.** The check does not rely on the AR(1) assumption. An "analytic CI vs bootstrap" table for
  each case goes on the Methods page
- **Pitfalls.** The result depends on block length. 12 months is the natural choice, but sensitivity
  for 6 and 24 should be shown
- **Output.** `tests.bootstrap.{ci95, block}`

### M11. FDR across all insights of a case

- **How.** For each case collect all p-values from M1–M9: about 25–35 tests. Apply BH with q = 0.10
  to the whole family, and show an insight only if it passes. The main verdict is not filtered: it is
  a hypothesis declared in advance
- **Why.** Without this, 1–2 of 30 "discoveries" would be due to chance, and those are exactly the
  ones we would show as the most interesting. On Methods we write honestly: "we tested 31 things and
  show the 4 that hold up". A strong argument for Validity
- **Pitfalls.** The tests are correlated (months and seasons). BH is valid under positive dependence
  (PRDS), which is plausible here. For maps, Wilks (2016) recommends α\_FDR = 2·α\_global under strong
  spatial correlation. Our q = 0.05 is more cautious, and this is worth stating
- **Output.** `insights_audit.{tested, shown, q}`, and a `q` field in every insight

## Priorities

We start with level A: it yields the most insights for the grandma case and builds on functions that
already exist. M11 ships together with the first method that produces more than one p.

| Method | Level | Effort | POWER data | Cases |
| --- | --- | --- | --- | --- |
| M11 FDR across insights | A | low | — | all |
| M1 Monthly profile | A | low | monthly | all |
| M2 ETCCDI indices | A | medium | daily T2M\_MAX, T2M\_MIN, PRECTOTCORR | 01, 02 |
| M3 SPI vs SPEI | A | medium | monthly PRECTOTCORR, T2M\_MAX, T2M\_MIN | 01, 03 |
| M4 Time of emergence | A | low | monthly | 02 |
| M5 Change in probability | A | medium | monthly | 01, 02 |
| M10 Block bootstrap | B | low | — | Methods |
| M7 Acceleration | B | low | monthly | 02 |
| M6 Quantile regression | B | medium | daily T2M\_MAX | 02 |
| M8 Change in spread | C | low | monthly | 01 |
| M9 NAO adjustment | C | medium | + NOAA CPC index | 02, 03 |

The data engineer adds daily T2M\_MAX, T2M\_MIN, PRECTOTCORR for the case regions to the fetcher.
Levels A and B are computed from one download.

## Pitfalls that break insights

| Pitfall | What happens | How we avoid it |
| --- | --- | --- |
| Tuning the period, threshold or breakpoint | A "discovery" that vanishes with another choice | All parameters are fixed in `config.yaml` before the first run on real data |
| Many tests, showing the best ones | 1–2 chance "insights" per case | M11 |
| Autocorrelation of accumulated series (SPEI-6, 12-month mean) | False significance even with Yue-Wang | Test on non-overlapping values (one per year) |
| Percentages for temperature | "+20% warmer" depends on °C vs K | Percentages only for variables with an absolute zero (precipitation, NO₂) |
| Reanalysis as an "observation" | A climatologist judge takes Validity points off | One plain sentence in every variable definition and the S12 cross-check |
| Words about causes | "Because of climate change" is attribution, which we do not do | Insight templates describe the change, not its cause. Exceptions: M3 and M9, which concern the mechanism |

## Sources

All references are given from memory and must be verified before they are added to
`09-references.md`: Hirsch, Slack & Smith (1982); Zhang et al. (2005, 2011); McKee et al. (1993);
Vicente-Serrano et al. (2010); Hargreaves & Samani (1985); Hawkins & Sutton (2012); Stott et al.
(2004); Koenker & Bassett (1978); Künsch (1989); Wilks (2016).
