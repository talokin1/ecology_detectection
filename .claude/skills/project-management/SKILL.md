---
name: project-management
description: Run the Trend Detective team — standups, status reports, task breakdown, assigning owners, updating the requirements matrix and risk register, logging decisions as ADRs, planning milestones. Use when asked for a plan, status, standup, next steps, task list, who-does-what, or to record a decision.
---

# Project management

Source files: `docs/02-requirements-traceability.md` (scope), `docs/05-team-and-roles.md` (owners),
`docs/07-risk-register.md` (risks), `docs/decisions/` (ADRs), `docs/03-judging-rubric.md` (quality bar).
The team lead owns priorities; Claude proposes, the team decides.

## Standup / status report format
```
## Status <date time>
Overall: 🟢/🟡/🔴 — one sentence
Done since last: • R-xx … (owner)
Doing now:       • R-xx … (owner, ETA)
Blocked:         • … → needs … from …
Top risks:       • K-xx … (mitigation)
Decisions needed: • … (options, recommendation)
Judge-score snapshot: I/C/V/R/P = x/x/x/x/x
```

## Task breakdown rules
- Every task references a requirement ID (R-xx) or risk (K-xx); otherwise question whether it is needed.
- Tasks are ≤ half a day, have one owner, a clear done-criterion, and dependencies listed.
- Order: mandatory requirements (M) on the demo-critical path first → strongly scored (S) → could (C).
- Keep a single task board (GitHub Issues/Projects). Labels: `R-xx`, `science`, `data`, `backend`,
  `frontend`, `story`, `blocked`.

## Decisions
- Any choice that is hard to reverse or affects science/judging → ADR in `docs/decisions/`
  (copy `ADR-000-template.md`, next number, status Proposed → Accepted by the team lead).
- The solution concept must be decided by the team (SI rule) — record who decided in ADR-001.

## Updating the matrix
When work lands: set status, add evidence (PR link, screenshot, test name). `verified` only after an
independent check (another teammate or `stats-validator`).

## Milestone gates
1. **Concept locked** — ADR-001 accepted, variable shortlist and case files chosen.
2. **Data ready** — cached datasets for all case files with provenance.
3. **Engine ready** — analysis endpoint returns validated results for case files.
4. **App end-to-end** — wizard → map → series → verdict on live URL.
5. **Story ready** — demo video/slides, submission page draft, judge-panel ≥ 4 on all criteria.
6. **Submitted** — eligibility checklist all green.
