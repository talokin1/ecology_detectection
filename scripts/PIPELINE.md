# Field-team data pipeline (24/7)

This machine downloads NASA data for **Ukraine first, then the whole world**, and keeps it up to
date with the `experimental` branch. You work on the data right here over SSH (Cloudflare Tunnel,
no open ports), so a slow connection does not matter.

## Where things are

| What | Path |
|---|---|
| Ukraine data (POWER series, daily Tmax/Tmin/precip inputs, GRACE, MODIS NDVI) | `/srv/spaceapps/data/ukraine/` |
| &nbsp;&nbsp;raw cached series + `.provenance.json` sidecars | `ukraine/power_zarr/`, `ukraine/earthdata/` |
| &nbsp;&nbsp;output of your preprocessing hooks, labels | `ukraine/processed/` |
| World grids (2-degree monthly NetCDF, one per POWER variable, + GRACE) | `/srv/spaceapps/data/world/grids/` |
| File list with sha256, sizes, periods (same format as `data/cache/MANIFEST.json`) | `<stage>/MANIFEST.json` |
| Per-item result of the last run | `<stage>/STAGE_STATUS.json` |
| Pipeline status (last commit, current step, timestamps) | `/srv/spaceapps/state/status.json` |
| Logs | `/srv/spaceapps/logs/` (`pipeline.log`, `ukraine.log`, `world.log`, `ukraine_slow.log`) |
| Your working copy of the repo (edit here) | `/srv/spaceapps/repo` |
| Deploy checkout the pipeline runs from (do not edit) | `/srv/spaceapps/deploy` |
| Python environment with all dependencies | `/opt/spaceapps/venv/bin/python` |

Ukraine is always the canonical `ukraine` preset: bbox `[22.0, 44.0, 40.5, 52.5]`, land cells only,
Crimea included (ADR-005). World data is never committed to git (it lives outside the repo).

Load data in Python:

```python
import pandas as pd, xarray as xr
t2m = pd.read_csv("/srv/spaceapps/data/ukraine/processed/air_temperature_power.csv", index_col=0, parse_dates=True)
world = xr.open_dataset("/srv/spaceapps/data/world/grids/merra2_T2M_2deg.nc")
```

## Changing preprocessing / classification

Edit **`scripts/pipeline_load.py`** in `/srv/spaceapps/repo`. Everything you should need is in the
`EDIT HERE` block at the top: variable lists, world resolution, and the hooks
`preprocess_series`, `classify_series`, `postprocess_ukraine`, `postprocess_world`.
Hooks never modify the raw cache; they write to `processed/`. Trend tests must come from
`.claude/skills/trend-stats/scripts/trend_stats.py` (CLAUDE.md rule 3).

Try a change without touching the live data:

```bash
cd /srv/spaceapps/repo
/opt/spaceapps/venv/bin/python scripts/pipeline_load.py --dry-run
/opt/spaceapps/venv/bin/python scripts/pipeline_load.py --data-dir /tmp/mytest --stage ukraine
```

## How a re-run is triggered

The daemon checks every 5 minutes. It re-runs (channel -> Ukraine -> world -> slow Ukraine series) when:

1. **you commit** on `experimental` in `/srv/spaceapps/repo` (`git commit -am "feat(pipeline): ..."`), or
2. a new commit lands on `experimental` on GitHub, or
3. you ask for it: `touch /srv/spaceapps/state/rerun` (picked up within seconds).

Updates are fast-forward only. If your commits and GitHub's diverge, the daemon logs it in
`status.json` (`poll_note`) and keeps the current version until the histories are merged.
Already downloaded files are skipped, so a re-run after a hook change takes seconds; only new
or deleted files are fetched. To force a fresh download, delete the file (and its sidecar).

## Checking status and logs

```bash
cat /srv/spaceapps/state/status.json          # commit, current_step, steps.{channel,ukraine,world}.state
tail -f /srv/spaceapps/logs/pipeline.log      # daemon decisions
tail -f /srv/spaceapps/logs/world.log         # loader output for one stage
jq .counts /srv/spaceapps/data/ukraine/STAGE_STATUS.json
```

Step states: `pending`, `running`, `done`, `failed` (data steps; failed stages are retried after
30 min); the `channel` step is `up`, `down` or `not_running` and never blocks the data steps.

## For the machine admin

- Supervised by **supervisord** (`/etc/supervisor/conf.d/spaceapps-pipeline.conf`, `cloudflared.conf`),
  started by `/usr/local/sbin/spaceapps-start-services`. `sudo supervisorctl status|restart spaceapps-pipeline`.
- Config: `/etc/spaceapps/pipeline.env`. Secrets (`EARTHDATA_TOKEN`, `TUNNEL_TOKEN`):
  `/etc/spaceapps/secrets.env` (root, mode 600). Never commit or print them. Note: code run by the
  pipeline (including edits to the loader) can read the Earthdata token from its environment.
- The daemon itself (`scripts/pipeline_daemon.py`) is only reloaded on `supervisorctl restart`.
- MODIS NDVI has no global-grid reader yet, so the world stage has no NDVI grid.
