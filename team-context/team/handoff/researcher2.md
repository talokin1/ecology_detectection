# Researcher 2 handoff

Updated 14 Nov 2026 after the archive pass.

## Done
- Extra-source catalogue is `data/docs/extra_sources.md` (GISTEMP, HadCRUT5, Berkeley Earth, CRU country series, GPCC, CHIRPS v3, CCI soil moisture).
- GRACE JPL mascon RL06.3Mv04 CRI is the pipeline headline (−11.242 cm/decade on the bbox, overlap weights). Not labelled groundwater.
- CCI soil moisture: no robust drying signal. The v09.2 combined product is break-adjusted and scaled to GLDAS, so it is not an independent level check.
- GPCC gauge counts were recomputed from the global v2025 1° files already on disk. Stations inside the bbox thin after the 1980s. Table: `stats/gpcc_gauge_counts.md`.
- Judging criteria used by this repository are `docs/03-judging-rubric.md` at the repository root (Impact, Creativity, Validity, Relevance, Presentation). The analysis archive is aimed at Validity and Best Use of Science.

## Not done
- ERA5 and ERA5-Land were not downloaded. The request script is `data/fetch/cds_requests.py`. It reads `CDSAPI_KEY` from the environment. That variable was unset, so the script was not run.
- A separate past-winners scrape was not added beyond the rubric already in `docs/03-judging-rubric.md` at the repository root.

## Left out of the public tree on purpose
Persona notes, charts, logs, and SWOT/KNMI sample files stay off this branch.
