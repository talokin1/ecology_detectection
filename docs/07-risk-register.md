# 07 — Risk Register

Likelihood/Impact: L/M/H.

| ID | Risk | L | I | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|
| K-01 | Earthdata/Giovanni/AppEEARS outages, quotas or slow queues | M | H | Cache all demo data early; NASA POWER as live fallback; static JSON fallback for case files | Data | open |
| K-02 | Wrong statistics (seasonality, autocorrelation, multiple testing) → loses Validity | M | H | `trend-stats` defaults; `stats-validator` on every shown number; compare with published trends | Science | open |
| K-03 | Wrong dataset names/versions/units in catalog | M | M | `verified` flag; check via CMR/landing pages; unit tests on conversions | Data | open |
| K-04 | Scope creep, nothing polished | M | H | Requirement priorities; demo-critical path first | Lead | open |
| K-05 | Hosting down or blocked during judging (weeks) | M | H | Static-first; free tier keep-alive; FortiGuard classification; mirror on GitHub Pages | Backend | open |
| K-06 | Demo exceeds 30 s / 7 slides or not English → ineligible | L | H | Checklist in `submission-kit`; timed render | Story | open |
| K-07 | SI rules breach (undisclosed use, no watermark, SI-originated idea) | L | H | SI log; ADR-001 records team-owned concept; watermark step | Lead | open |
| K-08 | Secrets leaked in repo | L | H | `.gitignore`, `.env.example`, settings deny; pre-commit check | Backend | open |
| K-09 | Team member not registered at same Local Event → ineligible | L | H | Verify Members tab early | Lead | open |
| K-10 | SI partner hallucinates variables or numbers | M | M | Grounding on catalog + computed JSON only; output validation; label as SI | Backend | open |
