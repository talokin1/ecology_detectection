# 02 — Requirements Traceability Matrix

Every feature, PR and demo claim must map to a requirement ID.
Status: `todo` · `doing` · `done` · `verified` (independently checked) · `dropped` (with reason).
Priority: **M** = mandatory by challenge/rules · **S** = strongly scored (judging) · **C** = could.

## Challenge objectives (mandatory)
| ID | Requirement | Pri | Acceptance criteria | Owner | Status | Evidence |
|---|---|---|---|---|---|---|
| R-01 | Identify/select Earth-science variables that can be investigated for trends | M | User can browse/search ≥ 10 curated variables from ≥ 3 NASA sources, each with a plain-language definition and units | | doing | UI done (`#/catalog`, 21 variables, topic/place filters); 3 variables ready on synthetic data |
| R-02 | Acquire the variable for a particular region | M | User selects a region (preset, bbox, or click) and the app retrieves the regional series; area mean is cos(lat)-weighted | | doing | UI done: 6 prepared regions, map click opens them; cos-lat mean in stats pipeline |
| R-03 | Generate and visualize a time series long enough for statistics | M | Chart shows raw + deseasonalised series, trend line, period, n; minimum length guard (warn if < 10 years / < 120 months) | | doing | Case 'Over time' chart: anomalies + raw toggle, trend line, period, n; insufficient state in UI |
| R-04 | Rate of change over time | M | Slope per decade (and total change over period, %) with 95% CI and units | | doing | Verdict card: rate/decade + likely range, total change, % for ratio variables (synthetic data) |
| R-05 | Significance test (t-test / Mann-Kendall / CI) | M | Modified MK p-value + OLS t-test (effective n) shown; verdict text; validated by `stats-validator` | | doing | Verdict card 'How sure?' line: MK Yue-Wang + OLS n_eff; stats-validator pending on real data |
| R-06 | Visualization AND analysis in one tool ("full scope") | M | Both available in the same user flow without leaving the app | | doing | Map → case → verdict → findings in one flow (`frontend/`) |

## Challenge considerations (scored implicitly)
| ID | Requirement | Pri | Acceptance criteria | Owner | Status | Evidence |
|---|---|---|---|---|---|---|
| R-10 | Simple definitions of variables | S | Each catalog entry has ≤ 2-sentence definition + "why it might trend" | | doing | Catalog shows definition + why it might trend for every variable |
| R-11 | Question-driven search (what / where) | S | Wizard of ≤ 4 questions returns ranked variable suggestions | | todo | Replaced by catalog filters (plan v2, Q8); propose `dropped` |
| R-12 | Demonstration examples users can watch | S | ≥ 2 guided "case files" playable end-to-end | | doing | 3 cases playable end to end (`#/case/01..03`) on synthetic data |
| R-13 | SI suggests variables from region type / literature | C | Suggestions grounded in catalog; sources/rationale shown; disclosed as SI | | todo | |
| R-14 | Non-significant trends still informative | S | "Years until detectable" estimate + explanation | | doing | 'Years to detection' sentence on none/weak verdicts |
| R-15 | Regional opposite-sign trends ("where") | S | Per-pixel trend map with significance stippling, or two-region comparison | | doing | World trend map with FDR significance + Compare screen |
| R-16 | Seasonal cycle handled | S | Deseasonalisation on by default for sub-annual data, toggle to view raw | | doing | Anomalies by default, 'Actual values' toggle |
| R-17 | Daily/monthly data support | C | Monthly default; daily aggregated to monthly | | todo | |

## Submission rules (mandatory for eligibility)
| ID | Requirement | Pri | Acceptance criteria | Owner | Status | Evidence |
|---|---|---|---|---|---|---|
| R-30 | English in submission page and all linked materials | M | Repo, app UI, docs, slides/video subtitles in English | | doing | UI copy English only (`frontend/src/strings/en.ts`) |
| R-31 | Demo ≤ 30 s video or ≤ 7 slides, public link | M | Timed/ counted; opened in private browser window | | todo | |
| R-32 | Public final-project link, no login | M | Tested from private window + another network | | todo | |
| R-33 | ≥ 1 NASA data/resource used and listed | M | NASA Data field filled from `09-references.md` | | todo | |
| R-34 | All external resources listed in References | M | Code libs, datasets, images, fonts | | todo | |
| R-35 | SI usage disclosed; SI media watermarked | M | `08-si-usage-log.md` complete; watermarks visible | | todo | |
| R-36 | All team members registered for same Local Event, on Members tab | M | Checked on team page | | todo | |
| R-37 | Submitted before deadline (Sun 23:59 local event time) | M | Confirmation banner screenshot | | todo | |
| R-38 | No images/voices of minors; no NASA branding in generated content | M | Review of all media | | todo | |
| R-39 | FortiGuard Web Filter Classification requested for new site | C | Request sent | | todo | |
