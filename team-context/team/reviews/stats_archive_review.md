> **HISTORICAL (2026-11-14).** Kept as a record. Its method wording (HAC/Hamed–Rao "robust", "Yue–Wang not used for wording") is superseded by ADR-003 and the conservative-verdict rule (`.claude/skills/trend-stats/SKILL.md:26-28`).

# Stats archive plan — critique (14 Nov 2026, Europe/Kiev)

**Later decision (team lead, 15:17).** Section B1 below asked to stop treating repository Yue–Wang as the primary test. That recommendation was not adopted. ADR-003 keeps `trend_stats.py` Yue–Wang as the official test, keeps HAC and Hamed–Rao lag-3 as sensitivity, and leaves `docs/10-methods.md` and ADR-002 in place. The v1.4 rerun is `yw_v14_review.md`. The text under this note is the review as written.

**Target:** `./docs/team/STATS_ARCHIVE_PLAN.md` (untracked, 94 lines). Repo `.`, local branch `stats-archive` @ `5bfd779` (= `origin/stats`). Working tree clean except this untracked plan. Nothing committed or pushed. This review is read-only; no checkout, commit, or push was made.

**Verdict: approve the plan with blocking fixes. Do not commit or push until the three blockers below are fixed.**

The inventory, “no raw NetCDF / no secrets / no frontend”, and “rewrite `/workspace` paths then run the smoke test from the repo copy” are the right shape. The plan is not yet safe to execute as written: it would ship two contradictory trend standards, and the copied pipeline would not actually be able to reproduce the smoke-test numbers.

Method-comparison numbers: `team-context/team/reviews/stats_archive_method_compare.json`.

---

## Blocking

### B1. Method conflict is unresolved and would be committed as two sources of truth

The plan correctly flags the conflict, then leaves it as “ADR adopting ours, or run both,” to be settled later. That is not safe to defer past the first archive commit.

Today the repo already claims a single source of truth:

- `docs/10-methods.md` line 3: implementation is `.claude/skills/trend-stats/scripts/trend_stats.py`.
- `docs/decisions/ADR-002-trend-test-default.md`: primary = Yue–Wang AR(1) MK + Sen; cross-check = OLS lag-1 effective n. Status: Proposed.
- `.claude/skills/trend-stats/SKILL.md` rule 3: “Do not use classic MK or Hamed-Rao as the reported result for autocorrelated data,” citing `validate_type1.py` (HR false-positive 10–21% at φ = 0.3–0.6).

Our approved findings use a different rule, in `$UKRAINE_SAMPLES/_staging/trend_methods.py` and `analysis/headline_findings.txt`:

- Slope: OLS + time-aware Theil–Sen (`scipy.stats.theilslopes` vs calendar/decimal year).
- Significance: Newey–West HAC (lag 1 annual, lag 3 monthly) and Hamed–Rao **with lag=3** (not pymannkendall’s all-lag default).
- “Robust” = both p < 0.05 with the same sign. Disagreement → “method-dependent,” not a detection.
- Yue–Wang is stored but **not used for wording**, because pymannkendall’s YW can be anti-conservative on these series.

These are not the same Hamed–Rao. The repo’s Monte Carlo and “do not use HR” warning apply to a **significant-lags rank-ACF** implementation (`trend_stats.mann_kendall(..., method="hamed_rao")`). Our HR is `pymannkendall.hamed_rao_modification_test(..., lag=3)`. The repo simulation does not automatically discredit lag-3 HR, and our findings must not be restated under YW-primary wording without an ADR.

**Fix before commit:** write `docs/decisions/ADR-003-trend-test-ukraine-analysis.md` (or update ADR-002) adopting the reconciliation in §5 below; then edit `docs/10-methods.md`, the trend-stats skill, and the stats-validator agent so they no longer call `trend_stats.py` / YW the single source of truth for this team’s findings. Keep the repo module as a vendored sensitivity implementation, not a second primary.

### B2. After a literal copy, the smoke test cannot be re-run from the repo

The plan says “run smoke test from the repo copy” and “rewrite absolute `/workspace` paths,” but it does not list the imports that will break, and `requirements.txt` cannot even import the pipeline.

Hardcoded paths that the smoke test / pipeline import today:

- `pipeline/smoke_test.py:21` and `ukpipe/grace_method.py:17` — `sys.path.insert(0, "$UKRAINE_SAMPLES/_staging")` for `trend_methods`.
- `ukpipe/grace_method.py:20` — `GRACE_CSV = "$UKRAINE_SAMPLES/grace/ukraine_tws_monthly.csv"` (needed for `time_center`; the production −11.242 series cannot be rebuilt from the tidy parquet alone).
- `ukpipe/core.py` — `SAMPLES = Path("$UKRAINE_SAMPLES")`, `GLOBAL = Path("$GLOBAL_DATA")`.
- `ukpipe/trends.py`, `run_pipeline.py`, `pipeline/README.md` — more `...` and `python`.

Smoke-test expected values (already in `smoke_test.py`, tolerance ±0.005), which the plan should restate so they survive a path rewrite:

| Check | Reference |
|---|---|
| POWER T2M annual 12/12, 1981–2025, OLS | **+0.5526** °C/decade (exact 0.5527065; plan/doc often rounds to 0.553) |
| HadCRUT5 15-cell overlap annual 1981–2025, OLS | **+0.5793** °C/decade |
| GRACE monthly deseasonalised, production overlap weights | **−11.242** cm/decade (exact −11.24197) |
| GRACE cell-centre (legacy, non-blocking) | −11.222 |

`requirements.txt` is only `numpy>=2.0`, `scipy>=1.11`, `pytest>=8.0`. The pipeline and `trend_methods.py` also need **pandas, pyarrow, statsmodels, pymannkendall, xarray, netCDF4, PyYAML, pyshp, shapely**. Current box versions (for pinning, not as a commit): numpy 2.5.4, scipy 1.18.1, pandas 3.1.1, xarray 2026.9.0, netCDF4 1.7.5.1.post1, statsmodels 0.15.0, pymannkendall 1.4.3, pyarrow 26.0.1, PyYAML 6.0.3, pyshp 3.1.8, shapely 2.2.0.

**Fix:** vendor `trend_methods.py` at a repo-relative path (see §5); point `grace_method.py` at a repo-relative `ukraine_tws_monthly.csv`; replace `/workspace` with repo-relative or `Path(__file__)` paths; add a pinned `requirements-analysis.txt`; document `python scripts/pipeline/smoke_test.py` from the repo root after installing that file, with the four numbers above.

### B3. The planned copy is not yet gated, and two files over the 50 MB cap sit in source trees

`scripts/team/sync_to_repo.sh` does not exist. `.gitignore` ignores `data/cache/raw/`, `data/cache/**/*.nc`, `.h5`, `.zarr`, `.hdf`, `.env`, `.netrc` — but **not `.nc4`**, and not `data/cache/` as a whole (only `raw/`). No Git LFS / `.gitattributes`. GitHub warns at 50 MB and rejects at 100 MB.

Files that a sloppy copy of planned sources would pick up:

- **87.6 MB** `$UKRAINE_SAMPLES/extra/chirps_v3/chirps_v3_ukraine_bbox_monthly.nc` — over the plan’s 50 MB cap (still under GitHub’s hard 100 MB limit, so it can be pushed if no gate exists).
- **54.5 MB** `team-context/data/pipeline/data/cache/gistemp1200_GHCNv4_ERSSTv5.nc`.
- Other `.nc`/`.nc4` under 50 MB (HadCRUT 31.3 MB, CCI SM 3.8 MB, `merra2_const_frland.nc4`, GRACE bbox extract 356 KB, etc.).

The plan correctly keeps `$GLOBAL_DATA/` (**39.69 GB SI**, `du` reports 37G because that is ~37 GiB) out of git, in favour of a manifest + rebuild script. That part is right. GRACE official MD5 already lives in `fetch_grace_verified.py`, `download_grace_mascon.py`, and `grace/README.md` — put it on the manifest.

**Fix:** write the sync script first, with a denylist (`*.nc`, `*.nc4`, `*.h5`, `*.hdf`, `*.zarr`, `*.env`, `.netrc`, `_staging/legacy/`, `critique/ukraine_samples_repro/`, `critique/ukraine_samples_rerun/`) and a hard size cap of 50 MB. Extend `.gitignore` with `*.nc4` and `data/cache/**` except curated parquet/csv + `*.provenance.json`. Do not enable LFS for raw data.

---

## High (missing / misplaced)

1. **The plan file is two documents concatenated.** Line 43 starts “Space Apps 2026 Team: Architecture…”, which is the content of `team-context/team/handoff/README_TEAM_ARCHITECTURE.md`. Split it out to `docs/team/README_TEAM_ARCHITECTURE.md`. Do not leave the architecture text inside the archive plan.

2. **Approved findings files are not named.** The plan says “findings/README .md.” The approved set is `ukraine_samples/analysis/headline_findings.txt`, `trend_summary.csv`, `swot_findings.txt`, `modis_findings.txt`, `swot_kherson_kakhovka_step.json`, plus `ukraine_samples/README.md` (legacy warning + entry point) and `grace/findings.md` / `ukraine_tws_monthly.csv`. Those `.txt`/`.csv` must be in `docs/analysis/findings/` (or `data/cache/curated/ukraine_samples/`).

3. **Legacy hard-exit scripts are not excluded.** `_staging/legacy/analyze_and_plot.py` and `analyze_modis_and_finalize.py` raise `SystemExit("Retired script...")` and, if the guard were removed, would overwrite revised results with unit-index Sen and classical MK only. Exclude the directory, or vendor it under a clearly marked `legacy/` that is not on any run path.

4. **Natural Earth shapefiles (`pipeline/data/raw_aux/`, 28 MB) are unmentioned.** `config/regions.yaml` points at `data/raw_aux/natural_earth/ne_10m_admin_0_countries(_ukr).shp` (8.4 MB each, under the cap). Without these, or a fetch script + checksum, `ukraine_mask` cannot be rebuilt. `pipeline/data/cache/` (58 MB) should stay out; tidy parquet (~6.8–7.7 MB per region) is fine to commit.

5. **Review caveats are not collected.** They already exist, but only if the right files are archived: SWOT withdrawn / too short (`headline_findings.txt`, `swot_findings.txt`, pipeline `too_short_for_climate_inference`); AIRS 2025 excluded (`pipeline/README.md`, `qc_report.md`, flag `airs_2025_bias_unverified`, window 2003–2024 n=22); CCI SM v09.2 **is** break-adjusted in the main COMBINED product from v08.1 (`extra/cci_sm/README.md` — do not repeat the earlier “no break adjustment” wording); CHIRPS v3 official monthly is **549 months, Jan 1981–Sep 2026**, and must not be mixed with the COG extract from 2025-10 on (`global_size_estimates.md`, `qc_report.md`). Add a short `docs/analysis/CAVEATS.md` that points at those sources.

6. **`data_dictionary.md` is stale** (still says “GRACE is not downloaded,” OMI in progress). Stamp or refresh before archiving, or readers will distrust every other version string. Pipeline `config/variables.yaml` already has IMERG V07B, GRACE RL06.3Mv04, CHIRPS v3, CCI SM; the repo `data/catalog/variables.yaml` does not (IMERG is `"07"`, no CHIRPS/CCI/HadCRUT/GISTEMP/GPCC). Update the catalog as the plan already says.

7. **If YW is reported as a sensitivity column, do not use pymannkendall’s `yue_wang_modification_test`.** On the three series below, pymk YW gives p = 0 (POWER T2M, GRACE) and p = 2.5×10⁻¹¹ (POWER precip), vs the repo’s YW p = 9.8×10⁻⁶, 1.1×10⁻⁵, and 0.019. Use the repo `mann_kendall(..., method="yue_wang")` (or a checked port) for that column.

---

## Secrets

Scanned planned source trees and the repo working tree (paths and pattern names only; values not printed). **No live secrets found.**

- Hits: only `./.env.example` (empty `EARTHDATA_TOKEN=` and `EARTHDATA_PASSWORD=`, no values stored). That file should stay.
- No `.env`, `.netrc`, `_netrc`, `.cdsapirc`, `*.pem`, or `cookies.txt` exists under the planned trees or the repo.
- `.gitignore` already has `.env`, `.netrc`, `_netrc`, `*.pem`.
- Fetch scripts read `EARTHDATA_TOKEN` from the environment and contain official GRACE MD5 hexes (not secrets).

**Nit:** also gitignore `.cdsapirc` and `cookies.txt`. Re-run a path-only secrets scan inside the sync script before `git add`.

---

## Reproducibility (other than B2)

- Fetch dates: `ukraine_samples/README.md` says 14 Nov 2026 (Europe/Kiev). Keep that, and add a fetch-date column on the global manifest.
- Data versions to record on the manifest / `variables.yaml`: IMERG **V07B** Final (pipeline config; dictionary still says V07 in places), GLDAS Noah 2.0 and 2.1 (do not splice), CCI SM COMBINED **v09.2**, GRACE JPL **RL06.3Mv04** CRI, CHIRPS **v3.0** (549 months), AIRS 3STM 7.0, MERRA-2 5.12.4, MODIS C6.1, HadCRUT5, GISTEMP, GPCC v2025 1°.
- Random seeds: not used in the trend code; nothing to pin.
- `*.provenance.json` sidecars are specified but do not exist yet — generate them at copy time.
- `data/catalog/global_data_manifest.csv` does not exist yet; build it from `global_size_estimates.md` plus checksums (GRACE MD5 is already verified).
- Pipeline rebuild of masks also needs `raw_aux` or a Natural Earth fetch (item 4).

---

## Nits (one line each)

- Merge `origin/main` first, as the plan says: one commit (`4bda27f`, `docs/planning/README.md` + small convention edits) is ahead of `stats`.
- Decide `stats-archive` vs committing on long-lived `stats` before the first push (conventions prefer one branch per area).
- Exclude `team-context/team/reviews/ukraine_samples_repro/` (67 MB) and `ukraine_samples_rerun/` (62 MB); the 129 MB critique tree shrinks to ~351 KB of `.md`+`.py` without them.
- Charts under `ukraine_samples/charts/` are not listed; optional, not required for the analysis archive.
- Repo `pytest` is listed in `requirements.txt` but is not installed in `.venv`.
- Conventional Commits / `Co-Authored-By` / SI log are process, not archive content; fine.
- The 39.7 GB vs `du` 37G figure is SI GB vs GiB, not a size error.

---

## Trend-method comparison and reconciliation

Inspected: repo `trend_stats.py` (YW primary, OLS lag-1 n_eff secondary, Sen CI widened with YW `var_s`, HR = significant lags, min n = 4, “insufficient” if record < 10 years, BH-FDR on maps, deseason = calendar-month mean) vs `trend_methods.py` (HAC lag 1/3, HR lag=3, time-aware Sen, TFPW, YW stored but unused, min_n = 8, Bonferroni + BH, “robust” = HAC and HR). Repo OLS n_eff is applied only when residual r₁ > 0; ours also adjusts when r < 0 (n_eff > n, anti-conservative — already flagged in our HR rule).

Ran both stacks on three saved series (POWER T2M annual 1981–2025 12/12; GRACE production monthly deseasonalised, complete-year climatology, drop 2002/2017/2018/2026, `time_center`; POWER PRECTOTCORR annual 1981–2025). OLS and Sen slopes match to printed precision.

| Series | OLS / Sen per decade | Our HAC p / HR lag-3 p | Repo YW p / OLS n_eff p | Our call | Repo full rule | Differ? |
|---|---|---|---|---|---|---|
| POWER T2M annual | +0.5526 / +0.5343 °C | 1.8e-07 / 6.3e-08 | 9.8e-06 / 4.3e-06 | robust | strong | No |
| GRACE monthly headline | −11.242 / −11.258 cm | 1.2e-36 / 9.1e-12 | 1.1e-05 / 4.6e-07 | robust | strong | No |
| POWER precip annual | +14.83 / +16.09 mm | **0.135** / **0.019** | **0.019** / **0.086** | method-dependent | method-dependent (conservative = n.s.) | No |

On the two strong signals, every test agrees. On precip, **the full rules also agree: not a clear detection.** What would flip precip to a detection is using YW (or HR) *alone*: repo YW p = 0.019, our HR p = 0.019, pymk YW p = 2.5e-11. HAC (p = 0.13) and OLS n_eff (p = 0.086) are the conservative brakes. That is the point of a two-test rule.

### Recommendation (adopt as ADR-003)

1. **`trend_methods.py` is the single source of truth for this team’s published findings.** Vendor a copy under e.g. `scripts/analysis/trend_methods.py` with a content hash in the ADR (and a comment pointing at the original path). Pipeline and smoke test import that copy only — do not reimplement.
2. **The repo may keep `trend_stats.py`**, but it is a sensitivity library, not a second primary. Prefer calling it (or a vendored copy + hash) for the YW / OLS n_eff / years-to-detect / map-FDR columns. Do not let the app or slides take numbers from it until this ADR is accepted by the team lead.
3. **Report YW as a sensitivity column**, computed with the repo’s `mann_kendall(..., method="yue_wang")`, not pymannkendall’s YW (see High item 7).
4. **Define “robust”** = HAC and Hamed–Rao lag-3 both p < 0.05 with the same sign (HAC lag 1 on annual series, lag 3 on monthly). Short records, strongly negative residual AR (r < −0.3), and unequal spacing stay as in `robust_call()`.
5. **If HAC and HR disagree, or if YW / OLS n_eff disagree with that call, label the row method-dependent** and do not treat it as a detection. When a single headline number is required, use the more conservative result (not significant if either family fails). Do not silently switch tests.
6. **Do not replace lag-3 HR with the repo’s significant-lags HR in the robust rule** without a new Type-I study; they are different tests, and the existing `validate_type1.py` table does not apply to lag=3.
7. Evidence from the three series above: under this rule the published conclusions do not change. A YW-primary rule without the OLS cross-check *would* have called POWER precip a detection.

The team lead still signs off on the ADR (big method question). Thinker should take that, not treat this review as approval to push.
