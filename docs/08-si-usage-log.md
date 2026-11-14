# 08 — Super Intelligence (SI / AI) Usage Log

Required by NASA Space Apps 2026 rules: the submission must describe how SI tools were used.
SI-generated images/videos need a visible watermark; SI-assisted code and data must be acknowledged
in descriptive text and metadata. SI must not be used to come up with the solution idea.

## Policy for this team
- Log every meaningful SI contribution below (one row per task, not per prompt).
- Code: keep the `Co-Authored-By` trailer in commits; mention SI assistance in the module docstring
  for substantially generated files (`"""... SI-assisted (Claude, Anthropic)."""`).
- Media: watermark "SI-generated" on any SI image/video frame.
- In-product SI features (e.g. variable suggestions, explanations) are labelled in the UI.

## Log
| Date | Who | Tool | What it was used for | Artifact(s) | Human review |
|---|---|---|---|---|---|
| 2026-11-14 | Lead | Claude (Anthropic) | Summarised challenge page, rules and data-access docs; drafted project setup docs, checklists, review skills and a reference statistics module | `docs/`, `.claude/`, `CLAUDE.md` | Lead |
| 2026-11-14 | Lead | Claude (Anthropic) | Repo onboarding review (found doc inconsistencies), git init, branch scheme proposal (approved by Lead), fixed primary-test wording in CLAUDE.md and architecture example | `README.md`, `CLAUDE.md`, `docs/00`, `docs/04`, `docs/06`, `requirements.txt` | Lead |
| 2026-11-14 | Lead | Claude (Anthropic) | Translated the team's Ukrainian plan v2 and statistics-methods notes into English (content and decisions are the team's) | `docs/planning/2026-11-14-plan-v2.md`, `docs/planning/2026-11-14-stats-methods.md` | Lead |
| 2026-11-14 | Lead | Claude (Anthropic) | Built the web app on branch `viz` from the team's plan v2 and web-app plan: React/MapLibre/Plotly frontend, JSON schema contract, synthetic-data generator (statistics via the team's `trend_stats.py`), geo/basemap script, tests. All data shown are synthetic and labelled as such in the UI | `frontend/`, `schema/`, `scripts/make_geo.py`, `scripts/make_synthetic_data.py`, `scripts/check_data.py`, `data/regions/` | Lead (pending) |

## Draft text for the submission field "Use of Super Intelligence"
> We used Claude (Anthropic) as a development assistant: to summarise documentation, scaffold
> project documents, generate and review code (all SI-assisted commits are marked with a
> Co-Authored-By trailer), and to cross-check statistical calculations. The concept, variable
> selection and scientific interpretation were decided by the team. Inside the product, an SI
> assistant suggests catalog variables and explains already-computed statistics; it never
> generates data values, and its output is labelled in the interface.
(Update before submission.)
