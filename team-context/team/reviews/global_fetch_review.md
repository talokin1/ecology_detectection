# Global size estimates and first global fetch — Critique review

Reviewer: Critique. 14 November 2026, 14:24 Europe/Kiev.
Sources: `team-context/data/docs/global_size_estimates.md`, `$GLOBAL_DATA/` (scratch in `team-context/team/reviews/global/`).
Scratch: `spotcheck.py`, `spotcheck2.py`, `spotcheck3.py`, `inspect_partial.json`, `spotcheck2_results.json`, `spotcheck3_results.json`.

## Verdict

**Approved with fixes.** On-disk slim sizes match the table to the byte, monthly file counts have no internal gaps, and Ukraine bbox cut-outs of the global files reproduce the earlier extracts (max abs difference at float/CSV-rounding level) — except the CHIRPS tail. Two analysis variables are still missing from the slim kit (MODIS QC, GLDAS Rainf), and the CHIRPS coverage claim is wrong.

I did not re-query CMR or HTTP HEAD this turn, so I did not independently re-verify native full-archive sizes or skipped-product estimates (POWER, ERA5, CCI SM daily, SWOT, MOD11A2). Those remain as documented.

## Ranked issues

### 1. Blocking for quality-aware MODIS work — QC layers still missing

The slim DAP4 subset is still NDVI+EVI only (`mod13c2_slim`) and LST day/night only (`mod11c3_slim`). No QC/QA variables. This is the same gap flagged on the Ukraine extract.

Current fill/range means do match the earlier extracts exactly: MOD11C3 LST_Day, all 321 months, max abs difference **0.0** (25 complete years also 0.0); four sample months are pixel-identical on the 161×363 window (58,443 cells, raw max abs 0). So the kit is fine for the current “valid = fill/range only” method, but it cannot support a QC-filtered VI or LST series until the QA layers are pulled.

### 2. Should fix — GLDAS Rainf was not fetched

Required land variables were Tair, SoilMoi 0–10, root zone, Evap, Qs, Qsb, SWE, **and Rainf**. Both GLDAS 2.0 and 2.1 slim files have the first seven only (`SoilMoi0_10cm_inst`, `RootMoist_inst`, `Evap_tavg`, `Qs_acc`, `Qsb_acc`, `SWE_inst`, `Tair_f_inst`). Rainf is absent, so a GLDAS water-balance / precipitation check cannot be run from this kit. (The earlier Ukraine extract also omitted Rainf; Tair itself matches that extract to 1.14×10⁻¹³ K on all 804 + 319 months.)

### 3. Should fix — CHIRPS coverage claim is wrong, and 2025-10 onward does not match the COG extract

The official monthly NetCDF on disk is **549 months, January 1981–September 2026**, complete (no internal gaps). The document says 550 months through October 2026. October 2026 exists only in the earlier COG-based Ukraine extract.

Units are mm/month. The Ukraine window is the same 160×362 cells, 55,092 valid pixels every month.

- January 1981–September 2025: 537 of 540 months agree to ~10⁻⁷ mm. The only material pre-2026 differences are **2025-10** (64.96 vs 62.98 mm) and **2025-11** (51.87 vs 50.09 mm); 2025-12 differs by 0.18 mm.
- All nine overlapping 2026 months differ; the largest is **2026-02** (63.37 vs 78.44 mm, abs 15.07).
- 2025 annual means differ by 0.33 mm; 1981–2024 annuals agree to ~10⁻⁷ mm.

This is a product-tail / archive difference (bundled monthly NetCDF vs monthly COGs), not a bbox or weighting bug. Fix the 550 / October 2026 wording, and do not mix 2025-10 onward across the two archives.

### 4. Should fix if wind or DTR is planned — MERRA-2 slim lacks wind and max/min

SLV slim is T2M, QV2M, SLP only; FLX slim is PRECTOT and PRECTOTCORR. No U10M/V10M (or wind speed) and no T2MMAX/T2MMIN. T2M itself matches the earlier extract to 1.7×10⁻¹³ K on all 561 months (46 complete years). U10M/V10M live in the same M2TMNXSLV collection and could still be pulled; monthly max/min would need a different collection.

### 5. Optional — IMERG has precipitation only (no gauge-relative weighting)

All 333 granules are **V07B** (January 1998–September 2025, no gaps), units **mm/hr**, matching the Ukraine extract (which starts 2000). Overlap of 309 months: max abs difference 5.6×10⁻¹⁷ mm/hr. Gauge-relative weighting was listed as optional and is not in the slim files.

### 6. Completeness nits — land-mask / coverage fields, CSR

- GRACE official file includes `land_mask`, `scale_factor`, and `mascon_ID`. MD5 `1567b9401ec2a704aab16598fcce5e70` recomputed and matches. Land-only means and the Ukraine bbox subset are identical (unscaled monthly max abs 5×10⁻⁷ cm = CSV rounding; pixel max abs 0.0 on 576 cells). CSR was not fetched globally.
- Berkeley `Complete_TAVG_LatLong1.nc` includes `land_mask`. 3,300 months (January 1750–December 2024) match the earlier cut-out to 6.8×10⁻⁷ °C; one UA month is empty (1752-09).
- GISTEMP 1200 km LOTI has only `tempanomaly` (no land mask) — expected for this blended, heavily smoothed product. HadCRUT.5.2.0.0 ensemble-mean analysis has `tas_mean` and bounds, no coverage field. Both files are hard-linked to the copies used for the Ukraine extracts and reproduce those cuts (HadCRUT 15 overlap cells, GISTEMP 50 cells; max abs ~5×10⁻⁷ °C). Landish columns already depend on an external ERA5 mask, not a field in these files.

### 7. Nits — free-space units, GLDAS-2.0 CMR sample, filenames

- The note defines GB as 10⁹ bytes, then says the disk has “75 GB free (42% used)”. `df` on `/workspace` is 79,995,256,832 bytes free = **80.00 GB SI** (74.51 GiB). 42% used is the binary `df` figure. The 128 GB filesystem marketing size is 127.4 GiB / 136.8 GB SI. Not a data-size error.
- GLDAS 2.0 **native** size is “measured (CMR, 800 of 804)”. Slim on disk is complete (804/804 months). The native figure may be a few tenths of a percent low.
- NASA slim filenames have a cosmetic double suffix (`.nc4.nc4`) because the fetcher appends `.nc4` to a producer id that already ends in `.nc4`.

## Size method (check 1)

Every on-disk slim/official path in the fetch-log table matches `du` / file-byte sums **exactly**, except the GRACE directory, which is 9,575 bytes larger than the data-file figure because of the release notes and `download_meta.txt` (the log already quotes 46,365,171 for the NetCDF alone).

| Group | Documented | Measured file bytes |
|---|---:|---:|
| NASA monthly slim (3,510 files) | 20.70 GB | 20,695,834,530 (20.696 GB) |
| GRACE + GISTEMP + HadCRUT5 + Berkeley + GPCC 1° | 0.75 GB | 748,180,571 data-only / 748,190,146 with GRACE sidecars |
| CHIRPS v3 monthly NetCDF | 8.96 GB | 8,960,342,547 |
| **Total on disk** | **30.41 GB** | **30,405,074,531** (30.405 GB), including 9,883 bytes of sidecars/README vs the log’s 30,405,064,648 |

No order-of-magnitude errors in the on-disk columns. Tags (on disk / HEAD / CMR / estimated) are used appropriately for those rows. I did not re-check estimated or CMR-native sizes for skipped products.

## Completeness and time coverage (check 2)

| Source | Files / months | Span | Internal gaps | Notes |
|---|---|---|---|---|
| MERRA-2 SLV+FLX | 561 + 561 | 1980-01–2026-09 | none | v5.12.4; DOIs 10.5067/AP1B0BA5PD2K, 10.5067/0JRLVL8YV2Y4 |
| GLDAS 2.0 / 2.1 | 804 / 319 | 1948-01–2014-12 / 2000-01–2026-07 | none | Rainf missing (item 2). No DOI in slim attrs. |
| IMERG V07B | 333 | 1998-01–2025-09 | none | precipitation only, mm/hr |
| AIRS 3STM v7.0 | 290 | 2002-09–2026-10 | none | SurfAirTemp + TotH2OVap A/D present. DOI 10.5067/UBENJB9D3T2H. Granule versions v7.0.3.0 early, v7.0.9.3 late. |
| MOD13C2 / MOD11C3.061 | 321 + 321 | 2000-02–2026-10 | none | QC missing (item 1). DOIs 10.5067/MODIS/MOD13C2.061, 10.5067/MODIS/MOD11C3.061 |
| GPCC v2025 1° | 47 files, 1,628 months | 1891-01–2026-08 | none | `precip` (mm/month) **and** `gauge` (“number of gauges per grid cell”), plus err/sys_err/gauge_int/etc. |
| CHIRPS v3 | 1 file, 549 months | 1981-01–2026-09 | none | See item 3. Not 550 / Oct 2026. |
| GRACE JPL CRI RL06.3Mv04 | 261 months | 2002-04–2026-09 | official gaps only (attr `months_missing`) | land_mask present. DOI/id 10.5067/TEMSC-3JC634. CSR not fetched. |
| GISTEMP 1200 km | 1,762 months | 1880-01–2026-10 | none | no land mask in file |
| HadCRUT.5.2.0.0 analysis mean | 2,121 months | 1850-01–2026-09 | none | no coverage field in this file |
| Berkeley land TAVG 1° | 3,300 months | 1750-01–2024-12 | none (1752-09 empty in the cut-out) | land_mask present; TMAX/TMIN not fetched (as documented) |

## Spot-check vs earlier Ukraine extracts (check 3)

Same bbox 22.1–40.2°E, 44.4–52.4°N, and the same weighting each extract used (GES DISC: cos-lat of cell centres; MODIS: unweighted valid mean on DAP4 window [Y 752–912, X 4042–4404]; CHIRPS/GPCC/Berkeley: cos-lat of centres in the box; GRACE: land_mask==1 with spherical cell-area weights; HadCRUT/GISTEMP: intersection-area overlap weights). Annual comparison uses 12/12 complete years.

| Series | Months compared | Max abs monthly | Max abs annual (12/12) | Comment |
|---|---:|---:|---:|---|
| MERRA-2 T2M (unmasked) | 561 | 1.7×10⁻¹³ K | 1.7×10⁻¹³ K (n=46) | Match |
| GLDAS-2.1 Tair | 319 | 1.1×10⁻¹³ K | 1.1×10⁻¹³ K (n=26) | Match |
| GLDAS-2.0 Tair | 804 | 1.1×10⁻¹³ K | 1.1×10⁻¹³ K (n=67) | Match |
| IMERG precipitation | 309 (from 2000) | 5.6×10⁻¹⁷ mm/hr | 1.4×10⁻¹⁷ (n=25) | V07B = V07B, not V07A |
| MODIS LST_Day | 321 | **0.0 K** | **0.0 K** (n=25) | Four sample months pixel-identical |
| CHIRPS precip | 549 | 15.07 mm (2026-02) | 0.33 mm (2025) | Historical match; tail diverges (item 3) |
| GPCC precip | 1,628 | 5.0×10⁻⁷ mm | 2.2×10⁻⁷ mm (n=135) | CSV rounding |
| GRACE lwe unscaled | 261 | 5.0×10⁻⁷ cm | 1.7×10⁻⁷ cm (n=14) | Pixel max abs 0.0 vs bbox subset |
| HadCRUT tas (15 cells) | 2,121 | 5.0×10⁻⁷ °C | 2.2×10⁻⁷ °C (n=176) | Same inode as the extract file |
| GISTEMP (50 cells) | 1,762 | 5.0×10⁻⁷ °C | 2.5×10⁻⁷ °C (n=146) | Same inode as the extract file |
| Berkeley TAVG | 3,299 finite of 3,300 | 6.8×10⁻⁷ °C | 2.9×10⁻⁷ °C (n=274) | 1752-09 empty in the UA CSV |
| AIRS SurfAirTemp A/D mean | 4 months (2002-09, 2010-07, 2020-07, 2026-10) | **0.0 K** | — | Sample only; full annual series not recomputed |

## Versions, DOIs, checksums (check 4)

Verified from file attributes or names this turn:

- MERRA-2 VersionID 5.12.4; SLV DOI `10.5067/AP1B0BA5PD2K`; FLX `10.5067/0JRLVL8YV2Y4`.
- IMERG filenames `V07B`; collection GPM_3IMERGM v07.
- AIRS DOI `10.5067/UBENJB9D3T2H`.
- MOD13C2.061 DOI `10.5067/MODIS/MOD13C2.061`; MOD11C3.061 `10.5067/MODIS/MOD11C3.061`.
- GRACE title “JPL GRACE and GRACE-FO MASCON RL06.3Mv04 CRI”; attribute `id` = `10.5067/TEMSC-3JC634`; `product_version` = v3.0. MD5 recomputed, matches official `1567b9401ec2a704aab16598fcce5e70`.
- HadCRUT.5.2.0.0; source CRUTEM.5.2.0.0 + HadSST.4.2.0.0; file built 2026-10-22.
- GISTEMP history: created 2026-11-10, ILAND=1200, IOCEAN=NCDC/ER5, baseline 1951-1980.
- Berkeley history 09-Jan-2025; land 1° TAVG.
- GPCC “Analysis Monthly Version 2025”, mm/month, 1.0 degree.
- CHIRPS “Version 3.0”. On-disk size equals the fetch log’s Content-Length (8,960,342,547). I did not re-HEAD.

No other official checksums were present to recompute. GLDAS slim files have no DOI attribute; I did not invent one.
