# NASA Space Apps 2026 – Team Brief (maintained by Project manager)
Last updated: Sat 14 Nov 2026, 14:00 (Europe/Kiev)

## Challenge
"Be An Earth System Trend Detective!" (Advanced; Earth Science, Software)
https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/?tab=resources
Build a tool where a user (1) picks Earth-science variables from missions/models (MODIS, OMI, AIRS, GPM, MERRA-2, GLDAS…),
(2) pulls them for a region, (3) plots a long time series, (4) reports rate of change + significance (t-test, Mann-Kendall, CIs).
Daily/monthly data and linear trends are enough. Deadline: ~2 days from now (user wants speed).
User's view: impressing judges is the top priority; aim big, but credibly (any variable, any region, cross-checked sources).

## OUR SCOPE (the team lead, 12:26)
Our team does DATA ANALYSIS only: learn, understand and work with the data (acquisition, cleaning, exploration, trend/significance analysis, findings, analysis-ready outputs). Visualization and other pipelines/app development are handled by a DIFFERENT team. Don't build UI/apps; quick exploratory plots for our own analysis are fine.
Researcher's revised Ukraine results (post-Critique): warming +0.55 to +0.67 C/decade robust after HAC and Hamed-Rao; precip/wind/EVI_JJA no longer clear detections; SWOT claim dropped; GSOM gap disclosed. Revision sent back to Critique.

## Team and roles
- Project manager (me): orchestration, plan, status, keeps this brief current.
- Thinker: brainstorms analysis questions, methods and findings to pursue; asks Researchers for info, hands build tasks to Worker.
- Researcher: data access + sample extraction (data access via an Earthdata token read from the environment; downloads; trend analysis of samples).
- Researcher 2: supplementary sources, scouting (e.g. judging criteria, prior winners, extra datasets).
- Worker: implements analysis code (pipelines for stats/trend analysis, notebooks, scripts), not UI/apps.
- Critique: reviewer; critiques ideas/solutions and flags problems. Send concepts and builds to Critique before finalizing.

## What's done so far
1. Researcher: described all 13 Resources-tab links. Only 5 give real data: Giovanni, GES DISC Hydrology Time Series,
   AppEEARS, NOAA Climate Data Online, KNMI Climate Explorer. Rest = methods articles + Canadian (CSA) radar/SWOT/Geo.ca material.
2. Researcher (asked by Researcher 2): 29 extra sources NOT on the Resources tab. Fastest no-login: NASA POWER, GISTEMP,
   NSIDC Sea Ice Index, NOAA GML CO2, GPCC, ERSST/OISST, JAXA Earth API. With logins: ERA5 (CDS), GRACE/GRACE-FO, Harmony, earthaccess.
3. Researcher: Ukraine samples (bbox 22.1–40.2E, 44.4–52.4N), 64 MB in $UKRAINE_SAMPLES/
   (README.md, analysis/trend_summary.csv, analysis/headline_findings.txt, charts/combined_ukraine_trends.png).
   Zips: ukraine_part1_analysis_charts_power_modis_swot.zip, ukraine_part2_noaa_and_raw.zip
   Headlines: warming ~+0.55 to +0.67 °C/decade since 1981 (NASA POWER, NOAA GSOM, GHCN; MK p<0.0001);
   MODIS LST 2001–2025 ~+0.82 day / +0.87 night °C/decade; precip ~+15 mm/decade (mostly not significant);
   MODIS EVI +0.008/decade (significant); SWOT river levels falling (Desna, Dnieper, Dniester) but only since Apr 2023 (Theil-Sen on month-of-year anomalies). Note: reach file 'Lviv_Dniester' is actually on the lower Dniester, not near Lviv.

## Known blockers
- GES DISC (MERRA-2, GLDAS, AIRS, OMI, Hydrology Time Series) returns 403 until the user approves the GES DISC app once:
  https://urs.earthdata.nasa.gov/approve_app?client_id=e2WVk8Pw6weeLUKZYOxvTQ  (user action pending)
- AppEEARS API rejects bearer token (needs username/password login); MODIS was pulled via DAP4 instead.
- KNMI Climate Explorer needs a human check in a browser.

## Critique review of Ukraine samples (12:07)
Report: team-context/team/reviews/ukraine_methods_review.md. Warming headline holds (survives AR(1)). SWOT 'rivers falling' claim WITHDRAWN (slope bug, ~3 yr record, autocorrelation, Kakhovka step). Precip/wind/EVI significance overstated. Researcher is fixing.
Tool requirement for Thinker/Worker: build autocorrelation-aware significance (AR(1)/HAC OLS, Hamed-Rao or prewhitened MK, time-aware Sen slope) in from day one, and warn on short records / multiple testing.

## Status
No solution concept, architecture, tech stack or repo yet. Waiting on the team lead's go-ahead: Thinker proposes concept/MVP, Researcher 2 looks up judging criteria, then Worker builds.

## Risks
- 2-day clock; scope creep from 'aim big'.
- Data-access friction (GES DISC approval, AppEEARS, KNMI); login-gated sources need Researcher.
- Short records (SWOT since 2023) can mislead trend tests; autocorrelation/seasonality can inflate significance.
- Size-based claims ('petabytes') won't impress informed judges; demonstrable reach and cross-checks will.

## Open decisions (next)
- Product concept + MVP scope (Thinker to propose).
- Tech stack (Worker, after concept).
- Which judging criteria to target (Researcher 2 can look up).

## Working rules
- REQUIRED (from the team lead): when you finish any task, send the result to Critique ([id removed]) for review, consider the feedback, and revise before reporting it done.
- Big questions (direction, scope, trade-offs, anything needing the team lead's decision) go to the team lead directly; don't decide them among bots.
- Everyone shares one computer: put team files under team-context/ (code in team-context/app/).
- Don't duplicate work: check this brief first; send status changes to Project manager.
- Keep messages between bots short; priority only when someone must act.

## Update 2026-11-14 13:38 (UTC+2)
- PERFORMANCE RULE (from the team lead): time is critical. Where it's simple, optimize tasks for speed: subset before loading, cache downloads with an exists-check, and reuse existing outputs. Many tasks share this computer at once, so cap threads and parallel jobs (for example OMP_NUM_THREADS=2, 2 to 4 concurrent downloads), use `nice` for heavy jobs, and free RAM promptly. Quick wins only.
- GES DISC blocker CLEARED: the team lead approved the app, and Thinker verified at 12:40 that MERRA-2 monthly and GLDAS downloads work.
- Ukraine trend analysis DONE: Critique gave final approval, and the outputs reproduce byte-for-byte. Reference method: $UKRAINE_SAMPLES/_staging/revise_analysis.py + trend_methods.py. Kherson is not a confirmed dam-breach step, and EVI_AMJJAS is not robust. Three cosmetic nits are deferred.

## Update 14:00
- HANDOFF RULE (the team lead): every bot keeps team-context/team/handoff/<bot>.md (Done / In progress / Details / Files / Recreate paragraph) and updates it after each new piece of work. Main architecture doc: handoff/README_TEAM_ARCHITECTURE.md. On the team lead's low-token signal, all bots STOP and document what is left for migration.

## Update 14:33

## Update 14:50

## Update 15:20: MIGRATION STARTED
the team lead signalled low tokens. All bots: stop, finish their handoff file, and stage their repo part under team-context/<bot>/ with a MANIFEST.md. Thinker owns the GitHub plan (repo talokin1/ecology_detectection, likely the existing `stats` branch). Only PM pushes, after the team lead approves. CDS ERA5 test job stopped while still queued (licence accepted at 14:46; the full pull never ran).
