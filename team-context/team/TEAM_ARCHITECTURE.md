# Space Apps 2026 Team: Architecture, Rules and How to Recreate It
Maintained by Project manager (PM). Created 2026-11-14 14:00 (Europe/Kiev). Read this first, then TEAM_BRIEF.md, then each bot's handoff file.

## 1. Mission
NASA Space Apps 2026 challenge "Be An Earth System Trend Detective!"
(https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/?tab=resources), deadline about 2 days from Nov 14, 2026.
Owner and final decision-maker: the team lead. Our team's SCOPE IS DATA ANALYSIS ONLY: acquiring, cleaning, exploring and analysing data (trends and significance), and producing findings and analysis-ready outputs. Visualization and app/pipeline development belong to a different human team. Quick exploratory plots are fine.

## 2. Architecture (who does what)
Every bot is a separate Grok Bot agent with its own chat and memory. All bots share ONE Linux computer, so they share the filesystem; each bot has its own desktop and browser.
| Bot | Agent id | Role |
|---|---|---|
| Project manager | [id removed] | Orchestrator: plans, routes tasks, relays the team lead's rules, maintains TEAM_BRIEF.md and this file |
| Thinker | [id removed] | Design: analysis questions, methods, and which findings to pursue |
| Worker | [id removed] | Builds analysis code (scripts, notebooks, stats pipelines), not UI |
| Researcher 2 | [id removed] | Scouting: extra sources, judging criteria, prior work |
| Critique | [id removed] | Reviewer: statistical and method rigor; checks every finished deliverable |

Flow: the team lead gives direction to PM. PM briefs the bots. Thinker designs, Researcher(s) fetch data, and Worker builds. Each finished piece goes to Critique, the bot revises, and then reports to PM. PM updates the brief and reports to the team lead.
Communication: bot-to-bot messages through SendToAgent (priority=true only when the recipient must act). PM can read other bots' transcripts. Big decisions go to the team lead directly.

## 3. Rules (all from the team lead)
1. Critique gate: when any bot finishes a task, it sends the result to Critique, weighs the feedback, and revises before calling it done.
2. Big questions (direction, scope, trade-offs) go to the team lead directly; bots don't decide them among themselves.
3. Scope: data analysis only (see section 1).
4. Speed: time is critical. Take the simple performance wins: subset before loading, cache downloads with an exists-check, reuse outputs. Many jobs share the computer, so cap threads and parallel jobs (for example OMP_NUM_THREADS=2, 2 to 4 concurrent downloads), use `nice` for heavy jobs, and free RAM.
5. Handoff docs: every bot keeps team-context/team/handoff/<bot>.md with Done / In progress / Details / Files / Recreate, and updates it after every new piece of work. Never write secret values.
6. Migration trigger: when the team lead signals that tokens are running low, PM tells every bot to STOP, finish documenting what's left in its handoff file, and then the team lead and PM migrate.
7. Statistical standard (from Critique): use autocorrelation-aware significance (AR(1)/HAC OLS, Hamed-Rao or prewhitened Mann-Kendall, time-aware Theil-Sen), and flag short records and multiple testing.

## 4. File layout (team-context/)
- TEAM_BRIEF.md: live status, findings, blockers and the review log (PM).
- handoff/: this file plus one handoff file per bot (pm.md, thinker.md, worker.md, researcher.md, researcher2.md, critique.md).
- analysis/: data dictionary, data-type summaries, size estimates, and global fetch scripts (analysis/scripts/global_fetch/).
- pipeline/: PREPROCESSING_PLAN.md, run_pipeline.py, config/, data/, qc_report.md.
- research/: scouting notes.
Other locations: $UKRAINE_SAMPLES/ holds the Ukraine case study (the reference method is in _staging/revise_analysis.py + trend_methods.py). team-context/team/reviews/ holds reviews and recomputes. $GLOBAL_DATA/ holds global downloads. The zips are ukraine_part1..3_*.zip.

## 5. How to recreate this team in a future Grok Bot setup
1. Create six agents in the Grok Bot app named Project manager, Thinker, Worker, Researcher, Researcher 2 and Critique. Give each the role text from section 2 as its description, plus "You are on the team lead's NASA Space Apps 2026 team; read team-context/team/handoff/README_TEAM_ARCHITECTURE.md and your handoff file first."
2. Copy team-context/ onto the new computer. Point `UKRAINE_SAMPLES` and `GLOBAL_DATA` at the sample tree and the global downloads (or restore those from the zips). Docs use those variables instead of machine-absolute paths.
4. Python packages used: numpy, pandas, xarray, netCDF4, scipy, statsmodels, pymannkendall, matplotlib, requests (check each handoff's Recreate paragraph for extras).
5. Update the new agent ids in section 2. Tell PM to message each bot to read its handoff file and continue from "In progress". Re-state rules 1 to 8 to every bot.
6. Known access quirks: the AppEEARS API rejects the bearer token (use DAP4/OPeNDAP or a username/password login instead), and KNMI Climate Explorer needs a human check in a browser.

## 6. Current state (keep short; details live in TEAM_BRIEF.md)
- The Ukraine trend case study is DONE and approved by Critique. Warming of +0.55 to +0.67 C/decade since 1981 is robust; precipitation, wind and EVI are not clear detections; the SWOT claim was dropped.
- GES DISC is unblocked (MERRA-2 monthly and GLDAS verified at 12:40).
- Thinker is working on analysis questions and methods. Worker, Researcher and Researcher 2 continue their analysis tasks under the speed rule.
