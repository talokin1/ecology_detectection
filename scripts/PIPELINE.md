# Field-team data pipeline (24/7)

This machine downloads NASA data for the countries listed in `scripts/pipeline_load.py`
(currently **Ukraine only**) and keeps it up to date with the `experimental` branch. You work
on the data right here over SSH or the JupyterLab link (Tailscale, no open ports), so a slow
connection does not matter. Worldwide 2-degree grids are no longer fetched; any files already
on disk under `/srv/spaceapps/data/world/` were left in place and are not updated.

## Where things are

| What | Path |
|---|---|
| Per-country data (POWER series, daily Tmax/Tmin/precip inputs, GRACE, MODIS NDVI, OMI NO2) | `/srv/spaceapps/data/<country>/` (Ukraine: `.../ukraine/`) |
| &nbsp;&nbsp;raw cached series + `.provenance.json` sidecars | `<country>/power_zarr/`, `<country>/earthdata/` |
| &nbsp;&nbsp;output of your preprocessing hooks, labels | `<country>/processed/` |
| File list with sha256, sizes, periods (same format as `data/cache/MANIFEST.json`) | `<country>/MANIFEST.json` |
| Combined result of every stage for that country | `<country>/STAGE_STATUS.json` |
| Per-stage result (fast and slow each have their own file, so they never overwrite each other) | `<country>/STAGE_STATUS.<stage>.json` |
| Pipeline status (last commit, current step, timestamps) | `/srv/spaceapps/state/status.json` |
| Logs | `/srv/spaceapps/logs/` (`pipeline.log`, `ukraine.log`, `ukraine_slow.log`) |
| Your working copy of the repo (edit here) | `/srv/spaceapps/repo` |
| Deploy checkout the pipeline runs from (do not edit) | `/srv/spaceapps/deploy` |
| Python environment with all dependencies | `/opt/spaceapps/venv/bin/python` |

Ukraine is always the canonical `ukraine` preset: bbox `[22.0, 44.0, 40.5, 52.5]`, land cells only,
Crimea included (ADR-005).

Load data in Python:

```python
import pandas as pd
t2m = pd.read_csv("/srv/spaceapps/data/ukraine/processed/air_temperature_power.csv", index_col=0, parse_dates=True)
```

## Changing preprocessing / classification

Edit **`scripts/pipeline_load.py`** in `/srv/spaceapps/repo`. Everything you should need is in the
`EDIT HERE` block at the top: the `COUNTRIES` list, variable lists, and the hooks
`preprocess_series`, `classify_series`, `postprocess_country`.
Hooks never modify the raw cache; they write to `processed/`. Trend tests must come from
`.claude/skills/trend-stats/scripts/trend_stats.py` (CLAUDE.md rule 3).

Try a change without touching the live data:

```bash
cd /srv/spaceapps/repo
/opt/spaceapps/venv/bin/python scripts/pipeline_load.py --dry-run
/opt/spaceapps/venv/bin/python scripts/pipeline_load.py --data-dir /tmp/mytest --stage ukraine
```

## Adding a country

1. Add a region preset to `data/catalog/regions.yaml` (or a file that file includes) with an
   `id`, a `name`, and a `bbox` `[west, south, east, north]`. Set `land_only: true` when the
   series should average land cells only. For Ukraine, do not add a no-Crimea variant (ADR-005).
2. Append that `id` to the `COUNTRIES` list in the `EDIT HERE` block of `scripts/pipeline_load.py`.
   That is the only loader change needed. Each country gets a fast stage (`<id>`) and a slow
   stage (`<id>_slow`) and writes to `/srv/spaceapps/data/<id>/`.
3. Commit on `experimental`. The daemon picks it up within 5 minutes (or `touch /srv/spaceapps/state/rerun`).

If the id is not in `acquire.list_regions()`, that country's stage fails with a clear error in
`STAGE_STATUS` and `status.json`; other countries continue. Datasets that only have a regional
reader (MODIS NDVI, OMI NO2, and any future catalog variable with no world-grid job) are fetched
for every listed country automatically. Variables with no reader yet are listed as `unsupported`
instead of being left out. Readers that only accept a box (NDVI, NO2) will report `unsupported`
for outline-only presets such as the IPCC AR6 regions.

## How a re-run is triggered

The daemon checks every 5 minutes. It re-runs (channel -> each country's fast stage -> each
country's slow stage) when:

1. **you commit** on `experimental` in `/srv/spaceapps/repo` (`git commit -am "feat(pipeline): ..."`), or
2. a new commit lands on `experimental` on GitHub, or
3. you ask for it: `touch /srv/spaceapps/state/rerun` (picked up within seconds).

Updates are fast-forward only. If your commits and GitHub's diverge, the daemon logs it in
`status.json` (`poll_note`) and keeps the current version until the histories are merged.
Already downloaded files are skipped, so a re-run after a hook change takes seconds; only new
or deleted files are fetched. To force a fresh download, delete the file (and its sidecar).
An interrupted OMI NO2 or MODIS fetch resumes from its `.partial.csv`.

## Checking status and logs

```bash
cat /srv/spaceapps/state/status.json          # commit, current_step, steps.{channel,ukraine,ukraine_slow}
tail -f /srv/spaceapps/logs/pipeline.log      # daemon decisions
tail -f /srv/spaceapps/logs/ukraine.log       # loader output for one stage
jq .counts /srv/spaceapps/data/ukraine/STAGE_STATUS.json
jq .stages.ukraine.counts /srv/spaceapps/data/ukraine/STAGE_STATUS.json
```

Step states: `pending`, `running`, `done`, `failed` (data steps; failed stages are retried after
30 min); the `channel` step is `up`, `down` or `not_running` and never blocks the data steps.

## For the machine admin

- Supervised by **supervisord** (`/etc/supervisor/conf.d/spaceapps-pipeline.conf`),
  started by `/usr/local/sbin/spaceapps-start-services`. `sudo supervisorctl status|restart spaceapps-pipeline`.
- Config: `/etc/spaceapps/pipeline.env`. Secrets (`EARTHDATA_TOKEN`, `TS_AUTHKEY`):
  `/etc/spaceapps/secrets.env` (root, mode 600). Never commit or print them. Note: code run by the
  pipeline (including edits to the loader) can read the Earthdata token from its environment.
- The daemon itself (`scripts/pipeline_daemon.py`) is only reloaded on `supervisorctl restart`.
  Until then, a still-running older daemon may pass `--stage world`; the loader treats that as a
  no-op and does not delete existing world files.
- Previously built world grids may still be on disk at `/srv/spaceapps/data/world/`; they are not
  deleted or refreshed.
