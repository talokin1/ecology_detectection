# 02 — Requirements Traceability Matrix

Every feature, PR and demo claim must map to a requirement ID.
Status: `todo` · `doing` · `done` · `verified` (independently checked) · `dropped` (with reason).
Priority: **M** = mandatory by challenge/rules · **S** = strongly scored (judging) · **C** = could.

## Challenge objectives (mandatory)
| ID | Requirement | Pri | Acceptance criteria | Owner | Status | Evidence |
|---|---|---|---|---|---|---|
| R-01 | Identify/select Earth-science variables that can be investigated for trends | M | User can browse/search ≥ 10 curated variables from ≥ 3 NASA sources, each with a plain-language definition and units | | todo | |
| R-02 | Acquire the variable for a particular region | M | User selects a region (preset, bbox, or click) and the app retrieves the regional series; area mean is cos(lat)-weighted | | todo | |
| R-03 | Generate and visualize a time series long enough for statistics | M | Chart shows raw + deseasonalised series, trend line, period, n; minimum length guard (warn if < 10 years / < 120 months) | | todo | |
| R-04 | Rate of change over time | M | Slope per decade (and total change over period, %) with 95% CI and units | | todo | |
| R-05 | Significance test (t-test / Mann-Kendall / CI) | M | Modified MK p-value + OLS t-test (effective n) shown; verdict text; validated by `stats-validator` | | todo | |
| R-06 | Visualization AND analysis in one tool ("full scope") | M | Both available in the same user flow without leaving the app | | todo | |

## Challenge considerations (scored implicitly)
| ID | Requirement | Pri | Acceptance criteria | Owner | Status | Evidence |
|---|---|---|---|---|---|---|
| R-10 | Simple definitions of variables | S | Each catalog entry has ≤ 2-sentence definition + "why it might trend" | | todo | |
| R-11 | Question-driven search (what / where) | S | Wizard of ≤ 4 questions returns ranked variable suggestions | | todo | |
| R-12 | Demonstration examples users can watch | S | ≥ 2 guided "case files" playable end-to-end | | todo | |
| R-13 | SI suggests variables from region type / literature | C | Suggestions grounded in catalog; sources/rationale shown; disclosed as SI | | todo | |
| R-14 | Non-significant trends still informative | S | "Years until detectable" estimate + explanation | | todo | |
| R-15 | Regional opposite-sign trends ("where") | S | Per-pixel trend map with significance stippling, or two-region comparison | | todo | |
| R-16 | Seasonal cycle handled | S | Deseasonalisation on by default for sub-annual data, toggle to view raw | | todo | |
| R-17 | Daily/monthly data support | C | Monthly default; daily aggregated to monthly | | todo | |

## Submission rules (mandatory for eligibility)
| ID | Requirement | Pri | Acceptance criteria | Owner | Status | Evidence |
|---|---|---|---|---|---|---|
| R-30 | English in submission page and all linked materials | M | Repo, app UI, docs, slides/video subtitles in English | | todo | |
| R-31 | Demo ≤ 30 s video or ≤ 7 slides, public link | M | Timed/ counted; opened in private browser window | | todo | |
| R-32 | Public final-project link, no login | M | Tested from private window + another network | | todo | |
| R-33 | ≥ 1 NASA data/resource used and listed | M | NASA Data field filled from `09-references.md` | | todo | |
| R-34 | All external resources listed in References | M | Code libs, datasets, images, fonts | | todo | |
| R-35 | SI usage disclosed; SI media watermarked | M | `08-si-usage-log.md` complete; watermarks visible | | todo | |
| R-36 | All team members registered for same Local Event, on Members tab | M | Checked on team page | | todo | |
| R-37 | Submitted before deadline (Sun 23:59 local event time) | M | Confirmation banner screenshot | | todo | |
| R-38 | No images/voices of minors; no NASA branding in generated content | M | Review of all media | | todo | |
| R-39 | FortiGuard Web Filter Classification requested for new site | C | Request sent | | todo | |
