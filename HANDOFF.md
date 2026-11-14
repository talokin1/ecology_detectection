# Data handoff — Earth System Trend Detective

For teammates who need the project's NASA data. Owner: the data engineer (ask before changing anything
in `data/cache/`). Written 2026-11-14.

## Get the data (5 minutes)
All data is committed to the repo on branch **`experimental`**. No Earthdata login or token is needed.

```powershell
git fetch origin
git switch experimental
git pull
pip install -r requirements.txt
python scripts/check_cache.py     # must end with "passed: 0 problem(s)"
```

`check_cache.py` confirms that your copy is complete and unchanged: every file matches its sha256 in
`data/cache/MANIFEST.json`, every file has provenance, and no credentials are present. CI runs the
same check on Linux and Windows on every push (`.github/workflows/data.yml`).

## What you get (`data/cache/`)
| What | Where | Notes |
|---|---|---|
| Monthly regional series, case regions | `power_zarr/`, `earthdata/` | 16 variables for `ukraine`, `south_ukraine`, `north_europe`, `south_europe` (plus test presets `sahel`, `arctic_cap`, `nw_india`) |
| Monthly regional series, whole world | `power_zarr/`, `earthdata/` | 13 variables (12 POWER + GRACE) for the 43 IPCC AR6 land regions (`ar6_neu`, `ar6_sah`, `ar6_eas`, ...) |
| World map grids, 2°, monthly | `grids/*.nc` | 14 grids: every POWER catalog variable (temperature, precipitation, soil wetness, snow, evaporation, sea ice, ozone, water vapour, solar, clouds, aerosol, IMERG rainfall) plus GRACE water storage; 191 MB in total. Read with `xarray.open_dataset`; `valid_fraction` and `n_valid_months` say how much data each cell has |
| Freeze list | `MANIFEST.json` | Every file with sha256, rows, period, region id |
| Provenance | `<file>.provenance.json` next to every file | Source, version, DOI, processing steps, access date, script, git commit |

Periods: MERRA-2 variables 1981-01 → 2026-09; CERES (solar, clouds, aerosol) 2001 → 2026-08;
IMERG rainfall 1998 → 2026-10; GRACE 2002-04 → 2026-09 (11-month mission gap 2017-07 → 2018-05).

## Read it in Python
```python
import sys; sys.path.insert(0, "backend")
from trend_detective import acquire

acquire.list_variables(available_only=True)   # the 16 deliverable variables, plain-language definitions
acquire.list_regions()                        # region ids and outlines
s = acquire.get_series("air_temperature_power", "ar6_neu")   # pandas Series, monthly, catalog units
s.attrs["provenance"]                         # where it came from
s.attrs["assessment"]                         # "ok" / "caution" / "too_short" / "no_variation", with reasons
```
App-ready JSON with catalog unit conversions: `python scripts/build_all.py` writes `build/app-series/`.

## Rules
- **Do not refetch or edit `data/cache/`.** The data is frozen; the check and CI fail on any change.
  New variables, regions or a refresh: ask the data engineer.
- **Never commit `.env`, tokens or `~/.netrc`.**
- Trend statistics come from the stats pipeline (`trend_stats.py`), never hand-rolled; run the
  `stats-validator` agent before a number reaches the app or slides.
- `assessment` = `no_variation` (e.g. snow depth in the Sahara) or `too_short` means: do not show a trend.

## Things to know
- AR6 regions are polygon outlines, not boxes, averaged over land cells only. Greenland and Antarctica
  are not built (the land mask excludes ice sheets). Rules: `docs/decisions/ADR-005-*.md`, amendment 1.
- MODIS NDVI and OMI NO2 exist only for Ukraine / Kyiv; NO2 is under science review (winter values as
  low as summer). Sea ice is refused for land-only regions by design.
- Cached POWER series were cross-checked against the official POWER REST API: 11/11 checkable
  variables pass (`docs/planning/2026-11-14-power-rest-crosscheck.md`).
- The GRACE map counts glaciers and ice sheets as land: big negative values there are ice loss.

## More detail
`data/cache/README.md` (file layout, quirks) · `docs/10-methods.md` (methods, data checks) ·
`docs/09-references.md` (citations) · `docs/planning/2026-11-14-data-plan.md` (status, open tasks).
