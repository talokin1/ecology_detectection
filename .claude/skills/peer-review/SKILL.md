---
name: peer-review
description: Structured review of a teammate's work for the Trend Detective project — pull requests, code diffs, notebooks, statistical analyses, data fetchers, UI copy, slides or submission text. Use when asked to review, check, critique, approve or give feedback on any project artifact.
---

# Peer review

Be specific, kind, and blunt about real problems. Every finding cites file:line (or slide/section),
says why it matters (which requirement or judging criterion), and proposes a fix.

## Output format
```
## Review: <artifact> — verdict: APPROVE | APPROVE WITH NITS | CHANGES REQUESTED
### Blocking
1. [category] file:line — problem → impact → fix
### Should fix
### Nits
### What's good (1–3 bullets)
### Requirement IDs touched: R-xx (status suggestion)
```
Blocking = wrong science, wrong data, broken build, secret leak, rule violation (English, SI, branding),
or anything a judge would catch.

## Checklists (apply the relevant ones)

### Science & statistics
- Uses `trend_stats.py` (no re-implemented tests); default method Yue-Wang MK + Sen + OLS n_eff cross-check.
- Seasonal cycle removed for sub-annual data; area mean cos(lat)-weighted; FDR on maps.
- Period, n, method, units, CI reported with every p-value; no cherry-picked start/end years.
- Percent change only for ratio-scale variables. Verdict wording matches `trend-stats` thresholds.
- Claims about causes are hedged and sourced; correlation ≠ causation.
- Numbers shown to users re-checked by `stats-validator`.

### Data
- Dataset short name/version match the catalog and CMR; `variable_verified` set after opening a granule.
- Fill values/scale factors decoded; units converted in one place; no version splicing.
- Provenance sidecar exists; cache is reproducible by a documented script; no secrets.

### Code
- Readable, typed public functions, tests for new logic, no dead code, no hard-coded paths/keys.
- Errors handled with user-visible fallbacks (cached data) rather than silent failures.
- Performance: no O(n²) on daily series; heavy work precomputed.

### Frontend / UX
- Follows `trend-viz` (palettes, stippling, units, alt text, CI band).
- Copy is plain English for a 16-year-old; every statistic has a "what does this mean" explanation.
- Works on a laptop and a phone width; loads without login.

### Rules & submission
- English everywhere; SI usage logged; SI media watermarked; no NASA logos; no minors' likeness.
- Requirement IDs updated in `docs/02-requirements-traceability.md`.

## For code diffs in Claude Code
Prefer delegating to the `code-reviewer` subagent for the diff and `stats-validator` for numbers,
then merge their findings into the format above.
