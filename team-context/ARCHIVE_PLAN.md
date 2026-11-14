# team-context archive plan v2 (team lead 15:00) — nothing committed or pushed

Branch: `stats-archive` (local, from origin/stats). All team material goes under one top-level folder `team-context/`.

```
team-context/
  README.md            how to set everything up from scratch (accounts, secrets by NAME only, env, run order)
  .gitignore           data/raw/, data/global/, *.nc *.nc4 *.h5 *.zarr *.npz, caches, logs, >50 MB
  team/                architecture, TEAM_BRIEF, rules, handoffs (one per bot), decision log, chat-context summary
  data/                fetch scripts + preprocessing pipeline (+ config, smoke test), dataset manifest,
                       data dictionary / coverage / size docs; data itself gitignored (raw/, global/, cache/)
  stats/               trend_methods.py + analysis scripts, trend tables, findings write-ups
```
Open: Critique reviews and research notes don't fit cleanly (see "unclassified" list).

## Critique blocking fixes (15:01, team-context/team/reviews/stats_archive_review.md) — before first commit
1. DECIDED by team lead 15:17: repo MK + Yue–Wang (repo trend_stats.py) is OFFICIAL; HAC/HR lag-3 are sensitivity columns. Write ADR-003 recording this (Critique's reconciliation proposal rejected); docs/10-methods.md and ADR-002 stay. Worker re-running pipeline v1.3 with repo-YW primary; Critique reviews verdict diff.
2. Rewrite hardcoded /workspace paths (smoke_test.py, grace_method.py, GRACE time_center CSV); add pandas, pyarrow, statsmodels, pymannkendall, xarray, netCDF4, PyYAML, pyshp, shapely to requirements. Smoke expectations: POWER +0.5526, HadCRUT +0.5793, GRACE -11.242 ±0.005.
3. Write sync script with denylist + 50 MB cap (CHIRPS bbox 87.6 MB, GISTEMP cache 54.5 MB over cap); gitignore .nc4, data caches, .cdsapirc, cookies.txt; keep GRACE MD5 in manifest.
High: architecture doc as its own file; list approved findings files; exclude _staging/legacy/; decide Natural Earth raw_aux (needed for masks); caveats file; fix stale "GRACE not downloaded" line.
