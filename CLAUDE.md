# CLAUDE.md — Earth System Trend Detective (NASA Space Apps 2026)

## Mission
Build the winning submission for the NASA Space Apps 2026 challenge
**"Be An Earth System Trend Detective!"** (Advanced · Earth Science · Software).
The tool lets students and the science-curious public **pick an Earth-science variable
and a region, see its time series, and learn what is changing, where, by how much,
and whether the change is statistically significant**.

Winning means scoring 5/5 on all judging criteria: **Impact, Creativity, Validity,
Relevance (NASA data as the core), Presentation**. When in doubt, optimise for
*scientific correctness first*, then clarity for a non-expert, then polish.

## Read first (context index)
| Need | File |
|---|---|
| What the challenge asks, bottlenecks, differentiators | `docs/01-challenge-brief.md` |
| Requirement IDs (R-xx) and their status | `docs/02-requirements-traceability.md` |
| How judges score us | `docs/03-judging-rubric.md` |
| System design and data flow | `docs/04-architecture.md` |
| Who owns what | `docs/05-team-and-roles.md` |
| Git / code / PR rules | `docs/06-conventions.md` |
| Statistical methods (judge-facing) | `docs/10-methods.md` |
| Decisions | `docs/decisions/` |
| Variables we may use | `data/catalog/variables.yaml` |

## Skills and agents (use them)
- `trend-stats` — any trend/significance computation. Reuse `.claude/skills/trend-stats/scripts/trend_stats.py`; never hand-roll a test.
- `nasa-data-access` — any data download, API call, caching, variable lookup.
- `trend-viz` — any chart, map, colour choice or verdict card.
- `peer-review` — reviewing a teammate's PR, notebook, analysis or copy.
- `submission-kit` — submission page, demo video script, slide deck, references.
- `project-management` — standup, status, task board, decision log.
- Subagents: `stats-validator` (independently re-checks numbers before they reach UI or slides),
  `code-reviewer` (diff review), `judge-panel` (simulated jury scoring).

## Non-negotiable rules
1. **English only** in everything that ships: code, comments, README, docs, UI, commits.
   (Linked materials must be English per submission rules.) Chat with the team in Ukrainian is fine.
2. **Scientific honesty.** Never fabricate, "tune" or hard-code a statistic. Every number shown
   in UI/slides must be reproducible from code + cached data in this repo. Report
   non-significant results as such — the challenge values them.
3. **Statistics defaults** (see `docs/10-methods.md`): monthly data → remove the seasonal cycle
   (anomalies) → Sen's slope + Mann-Kendall with Yue-Wang AR(1) correction as primary test; OLS + t-test
   with lag-1 effective sample size as secondary; report slope per decade with 95% CI,
   p-value, n, period. Area means use cos(latitude) weights. Per-pixel maps use FDR (Benjamini-Hochberg).
4. **Data provenance.** Every dataset used gets: short name, version, DOI/landing page, access
   date, processing steps → `docs/09-references.md` and the variable catalog.
5. **Secrets.** Earthdata tokens and API keys live in `.env` / `~/.netrc`, never in git, never in
   frontend code, never pasted into chat logs or docs.
6. **SI (Super Intelligence = AI) disclosure is mandatory.** Log each meaningful SI-assisted
   contribution in `docs/08-si-usage-log.md`. SI-generated images/videos need a visible
   watermark. SI-assisted code: commit trailer `Co-Authored-By` + note in the log.
   SI must not originate the solution concept — the team owns the idea (ADR-001).
7. **No NASA logos/branding** in generated content; no copyrighted media without permission;
   no images/voices of people under 18.
8. **Accessibility for the audience** (high-school/college students): every variable has a
   plain-language definition; every statistic has a one-sentence explanation.

## Repo layout
```
backend/     Python API (FastAPI) + analysis engine
frontend/    Web app (map + charts + wizard)
data/catalog Variable catalog (YAML) — curated, plain-language
data/cache   Pre-fetched NetCDF/Zarr/CSV (git-ignored if large; document how to rebuild)
notebooks/   Exploration; promote reusable code to backend/
scripts/     Data fetch / precompute scripts (idempotent, documented CLI)
docs/        Context, decisions, methods, logs
```

## Working agreements for Claude
- Before coding a feature, find its requirement ID in `docs/02-requirements-traceability.md`;
  update the status/evidence column when done.
- Prefer small PRs; follow `.github/pull_request_template.md`.
- Before any statistic is shown to users or judges, run the `stats-validator` agent on it.
- Record architectural or scientific choices as ADRs in `docs/decisions/`.
- When unsure about a dataset name/version, verify against the provider (CMR / GES DISC / LP DAAC)
  and set `verified: true` in the catalog; do not guess.
- Windows is the primary dev OS: give PowerShell-compatible commands, use `pathlib` in Python.
