# 00 — Project Setup Checklist

Configuration of the Claude environment (claude.ai Project + Claude Code) for the
NASA Space Apps 2026 challenge **"Be An Earth System Trend Detective!"**.

Legend: `[x]` created by setup · `[ ]` manual action by the team

## A. Shared context (single source of truth)
- [x] `docs/01-challenge-brief.md` — challenge text digest, requirements, bottlenecks, differentiation
- [x] `docs/02-requirements-traceability.md` — every requirement with an ID (R-xx), status, evidence
- [x] `docs/03-judging-rubric.md` — 5 judging criteria + how we score 5/5 on each
- [x] `docs/04-architecture.md` — target system architecture and data flow
- [x] `docs/05-team-and-roles.md` — roles, RACI, ownership (names to fill)
- [x] `docs/06-conventions.md` — git, branching, code style, PR rules, English-only rule
- [x] `docs/07-risk-register.md` — risks, owners, mitigations
- [x] `docs/08-si-usage-log.md` — mandatory log of Super Intelligence (AI) usage
- [x] `docs/09-references.md` — every dataset/tool/library used (feeds the References field)
- [x] `docs/10-methods.md` — statistical methodology (citable, judge-facing)
- [x] `docs/decisions/` — ADR template + ADR-001 (concept, must be decided by the team) + ADR-002 (default trend test)

## B. Claude Code (local repo)
- [x] `CLAUDE.md` — project memory loaded in every Claude Code session
- [x] `.claude/settings.json` — permissions (allow common dev commands, deny secrets)
- [x] Skills in `.claude/skills/`:
  - [x] `trend-stats` — statistical trend analysis + tested reference implementation
  - [x] `nasa-data-access` — how to fetch/cache NASA data (POWER, Giovanni, Harmony, earthaccess, AppEEARS)
  - [x] `trend-viz` — visual language for trend maps, time series, verdict cards
  - [x] `peer-review` — review checklist for colleagues' code, analysis and copy
  - [x] `submission-kit` — submission page text, 30-s video script, 7-slide deck, references
  - [x] `project-management` — standups, task board, decision logging, status reports
- [x] Subagents in `.claude/agents/`:
  - [x] `stats-validator` — independent re-check of any statistical result
  - [x] `code-reviewer` — reviews diffs against conventions and the peer-review checklist
  - [x] `judge-panel` — simulates the 5-criteria jury on the current state of the project
- [x] `.claude/` and `.github/` installed (the one-off `setup/` installer is not part of the repo)
- [x] `git init`, pushed to a **public** GitHub repo; branches `main`, `data`, `stats`, `viz`, `story` (see `06-conventions.md`)
- [ ] Each teammate: install Claude Code, open the repo folder, run `/skills` to confirm skills load

## C. claude.ai Project "Nasa Space App"
- [x] Project docs uploaded (brief, requirements, rubric, architecture, methods, conventions, team)
- [ ] **Paste `docs/claude-ai-project-instructions.md` into Project → Custom instructions** (cannot be set by Claude)
- [ ] Save the proposed account skills from the review card (trend stats, peer review, trend viz)
- [ ] Invite teammates to the Project (if on a Team plan) or share docs

## D. Repo skeleton
- [x] `README.md` (public-facing, English)
- [x] `.gitignore`, `.env.example` (Earthdata token, Anthropic key placeholders — never commit real values)
- [x] `.github/pull_request_template.md`
- [x] `data/catalog/variables.yaml` — seed catalog of 21 candidate variables (dataset short names/versions verified in CMR; in-file variable names still to verify)
- [x] `backend/`, `frontend/`, `notebooks/`, `scripts/`, `data/cache/` with READMEs

## E. Accounts and secrets (manual)
- [ ] Every data person: create a NASA **Earthdata Login** account (urs.earthdata.nasa.gov) and approve GES DISC / LP DAAC applications
- [ ] Put credentials in `~/.netrc` or `.env` (never in git)
- [ ] Decide hosting (frontend + backend) and create accounts
- [ ] All team members registered for the **same Local Event** and listed on the team page

## F. Team decisions required before build (see ADR-001)
- [ ] Confirm the concept and differentiators (the idea must be the team's own — SI rule)
- [ ] Pick the final variable shortlist and the demo "case files"
- [ ] Assign owners for each role in `docs/05-team-and-roles.md`
