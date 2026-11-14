# Thinker handoff (updated 2026-11-14 14:00 Kyiv)
Role: brainstorm analysis questions/methods, route work to Researcher/Researcher 2 (data), Worker (implementation); every finished result -> Critique; big decisions -> team lead. Scope: DATA ANALYSIS only; all sources must be GLOBAL (Ukraine = test cut-out). Speed > perfection.

## 1. Done
- Data dictionary (236 rows) + overlaps/global-size/preprocessing notes + per-type summary (raw vs gap-excluded % valid, station counts/decade, GRACE gaps), all Critique-approved. Page: (internal Page, not public)
- Access verified: GES DISC (approved), AppEEARS (token), KNMI (box browser session only).
- Findings (bbox): warming ~+0.55–0.62 °C/dec 1981–2025, robust, all sources (but station grids share GHCN inputs, not independent); precip: no detectable trend, sources disagree on sign (CHIRPS/GPCC/IMERG/POWER); GRACE TWS −11.22 cm/dec 2003–2025 robust (CSR −9.8; GLDAS soil+snow explains ~−2.3; not labelled groundwater; ~3° regional); GLDAS soil drying caveated; SWOT too short; Kherson not a confirmed step.
- ESA CCI SM v09.2 (1978-11–2024-12, extra/cci_sm/, Critique-approved): no robust drying; break-adjusted, rescaled to GLDAS so not independent in level; warm-season decline only significant from 1991/92 start.
- Extra global sources catalog (Researcher 2), Critique-approved: GISTEMP, HadCRUT5 (coarse context), Berkeley 1° (primary check), CRU-CY, GPCC, CHIRPS v3.
- Preprocessing plan v2 (Critique-reviewed) handed to Worker 13:50. Worker v1 built (run_pipeline.py --region ukraine_bbox ukraine_mask; smoke POWER +0.5526, HadCRUT +0.5793, GRACE -11.2221 PASS); in Critique review.
- Global fetch done 14:06: 30.4 GB slim monthly in $GLOBAL_DATA/ (75 GB disk free); table in analysis/global_size_estimates.md; sent to Critique.

## 2. In progress / next
- Worker: v1 in Critique review; asked to add loaders from $GLOBAL_DATA/ so masks work for gridded sources. Open team lead question: GRACE overlap weights (-11.242) vs old selection (-11.222).
- Global fetch Critique-approved; fixes pulled 14:46 (MODIS QC, GLDAS Rainf/Snowf, MERRA-2 wind + T2MMAX/MIN from M2SMNXSLV): $GLOBAL_DATA/ now 39.7 GB, 70 GB free. Worker asked to add loaders + rerun.
- GRACE: team lead chose overlap weights. bbox -11.242, ukraine_mask (incl. Crimea) -12.120 cm/dec. Pipeline v1.1 Critique-approved.
- ERA5/ERA5-Land: CDS token required (CDSAPI_KEY); downloads need it (specs from Researcher 2). CEDA skipped (CRU TS open from UEA).
- Researcher 2: CCI SM done; minor CHIRPS/HadCRUT doc fixes. ERA5 on hold pending team lead creating a Copernicus CDS account (ARCO hourly too slow: ~3 h for Ukraine).
- Researcher: OMI pull; AppEEARS Kyiv MOD11A2+MCD12Q1 (urban heat island, the key "wow" finding).
- Pending team lead decisions: CDS account (ERA5), CEDA (CRU TS grids).

## 3. Details / gotchas
- Units: IMERG mm/hr mean (extract already mm/month); MERRA-2/GLDAS flux kg m-2 s-1 ×86400; GLDAS Qs ×8×days; CHIRPS/GPCC mm/month; CRU tmp absolute °C; GHCN tenths.
- Never splice GLDAS 2.0/2.1 (+0.495 °C). POWER = MERRA-2 (not independent); POWER solar 2001+. MODIS CMG no QA, clear-sky LST. Drop partial 2026. Annual = 12/12 months. Smoke test on ukraine_bbox ±0.005. Use trend_methods.py (don't reimplement). GSOM TAVG long-record stations unusable 2020–24.
- Bbox 22.1–40.2E, 44.4–52.4N (~2x Ukraine). Crimea default included, verify mask.
- Credentials in env only: EARTHDATA_USERNAME/PASSWORD/TOKEN — never print or pass to agents.
- Teammates: Researcher de70b767-…, Researcher 2 f1f41ba8-…, Worker 9217a26e-…, PM 4e24ae1d-…, Critique 328b3609-…

## 4. Files
- Team repo: https://github.com/talokin1/ecology_detectection (public, main; backend/ frontend/ data/ docs/ notebooks/ scripts/). Our scope = analysis parts only; app parts belong to other team. Pushes need a GitHub token (GITHUB_TOKEN).
- team-context/TEAM_BRIEF.md
- team-context/data/docs/{data_dictionary.csv,data_dictionary.md,data_types_summary.md,data_overview_extras.md,station_coverage.csv,global_size_estimates.md(in progress)}, scripts/build_data_dictionary.py
- team-context/research/{personas_current_tools.md,extra_sources.md}
- team-context/data/pipeline/PREPROCESSING_PLAN.md
- $UKRAINE_SAMPLES/ (README.md, analysis/, merra2/, gldas/, gpm_imerg/, airs/, grace/, extra/ incl. chirps_v3/, _staging/trend_methods.py)
- $GLOBAL_DATA/ (global fetch target)
- team-context/team/reviews/*.md (reviews)

## 5. Recreate
Read TEAM_BRIEF.md, this file, data_types_summary.md and the critique reviews first. Earthdata creds must be in env (ask team lead via secure secret request; GES DISC + AppEEARS already authorised on that account). Python with xarray/netCDF4/pandas/pymannkendall/statsmodels (+rasterio for CHIRPS COG) on the shared box; data already on disk under $UKRAINE_SAMPLES and $GLOBAL_DATA. Re-dispatch any in-progress items above to the same teammates and route every finished result through Critique before reporting to team lead.

- 15:17 team lead: repo Yue–Wang = official trend test. Worker rerunning pipeline v1.3 (Critique-approved) with repo-YW primary -> Critique -> report to team lead. Archive plan moved to ./team-context/ARCHIVE_PLAN.md (+TEAM_ARCHITECTURE.md), branch stats-archive, nothing committed; awaiting team lead on the unclassified-items list and on public IDs.

## MIGRATION HANDOFF (15:21, Nov 14)
State: all work stopped at 15:25. Repo clone is this checkout, local branch stats-archive (from origin/stats). At that moment nothing new was committed or pushed. Layout lives in team-context/ (ARCHIVE_PLAN.md, team/, data/, stats/, .gitignore). My part is staged there: thinker handoff, architecture doc, fetch scripts, data docs (792 KB, clean secret scan).
Open threads:
2. team lead hasn't answered on the unclassified items: Critique reviews (proposed team/reviews, notes only), persona research (skip), charts (skip), Page json (skip), logs (skip), SWOT/KNMI samples (skip), parquet/npz caches (gitignore).
3. team lead's 15:17 decision: repo Yue–Wang is OFFICIAL. Write ADR-003 recording it. Worker's v1.4 YW rerun stopped half-way (see worker.md); finish it, then Critique, then flag verdict flips (POWER precip expected to flip).
4. Critique's blocking items (team-context/team/reviews/stats_archive_review.md): rewrite /workspace paths (27 in data/fetch alone), complete requirements, sync script with denylist and 50 MB cap (CHIRPS bbox 87.6 MB, GISTEMP cache 54.5 MB), caveats file, stale "GRACE not downloaded" line, Natural Earth raw_aux decision.
Next steps: get team lead's answers to 1-2, apply the Critique fixes, write the README and ADR-003, copy in the other bots' parts, rerun smoke test from the clone, Critique sign-off, then PM pushes after team lead approves.
- 15:25: Merged PM's staged part into the clone (team/). Built team-context/tools/sync_check.py (denylist, 50 MB cap, secret scan, /workspace path warnings). It passes. Pending merges: Worker, Critique, Researcher, Researcher 2 from team-context/<bot>/ via their MANIFESTs.
- 15:22 team lead answers (via PM): (1) ROLES ONLY in the public repo: no bot IDs, no team lead name ('team lead'), no secret-ownership details; full versions stay only in /workspace handoffs. (2) Keep Critique reviews under team/reviews; skip personas, charts, logs, SWOT/KNMI samples. Repo copies scrubbed; sync_check.py blocks these patterns.
