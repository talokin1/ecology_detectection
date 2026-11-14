# Researcher handoff

Updated 14 Nov 2026 after the archive pass.

## Done
- Ukraine bbox extracts and the global monthly archive used by the pipeline are on the analysis machine. The pipeline, not the older entry-point script, is the reproduction path.
- OMI OMNO2d monthly bbox means cover 2004-10 through 2026-11. Trends for the row-anomaly era (2007–2025) are in `stats/omi_bbox_trends.md`. No significant NO2 trend.
- OMTO3e ozone on disk is 2004-10 through 2018-12 (171 months). Annual 2005–2018 is not a significant trend. The extract was not extended.

## Still open
- Kyiv urban heat (MOD11A2 + MCD12Q1). The AppEEARS task was still `processing` on a later status check. No rasters were analysed. Do not treat 0.05° CMG LST as a district-scale heat-island result.
- Eight GES DISC review notes on the pre-pipeline scripts: the pipeline already converts GLDAS `Qs_acc` with ×8×days, does not splice GLDAS 2.0 and 2.1, excludes AIRS 2025 from trends, and cuts gridded fields with the region mask. The old trend summary is not regenerated here. Quote pipeline numbers. See `stats/CAVEATS.md`.

## Recreate
Earthdata Login in the environment as `EARTHDATA_TOKEN` (and username/password for AppEEARS). Never write the values down. Data roots: `UKRAINE_SAMPLES` and `GLOBAL_DATA`.
