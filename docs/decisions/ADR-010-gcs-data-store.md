# ADR-010 — Large cache files in a GCS data store, pinned by MANIFEST

- Status: Proposed (Molfarion, data engineer, 2026-11-15; team confirmation pending)
- Date: 2026-11-15
- Deciders (names): Molfarion; team to confirm
- Requirement IDs: R-01, R-02, R-15; CLAUDE.md rule 4 (provenance)
- Supersedes: the "commit the map grids" part of ADR-006

## Context
ADR-006 kept the 2° world-map grids in git. There are now 14 grids (191 of the cache's 224 MB),
and every new global variable (GRACE, MODIS NDVI, AIRS, OMI NO₂, ...) adds 16–26 MB of history that
every clone and CI run downloads. GitHub warns above ~1 GB and rejects files over 100 MB.
The demo itself does not need the grids: the site serves small precomputed JSON (46 MB).

## Options
1. Keep grids in git — simple, but the repository grows without bound.
2. Git LFS — 1 GB/month free bandwidth; CI would exhaust it.
3. GitHub Release assets — free and public, but awkward for frequent refreshes.
4. **Google Cloud Storage bucket, content-addressed, public read** — cheap, no size pressure, uses
   the GCP project that already hosts the assistant (ADR-009).
5. A database (BigQuery/Postgres) — only needed for live queries, which the static app does not make.

## Decision
Option 4. Bucket `gs://trend-detective-data` (europe-west1, uniform access, public read).
- Large files (`grids/*.nc`) are stored as `sha256/<sha256>`; objects are immutable, so each git
  commit's `data/cache/MANIFEST.json` pins the exact bytes it was built from.
- Git keeps MANIFEST, all provenance sidecars and the small CSV series (provenance stays readable in
  the repo).
- `scripts/sync_cache.py pull` downloads over plain HTTPS (no login) and verifies size and sha256;
  `push` uploads with `gcloud` (write access needed). CI pulls before `check_cache.py`.

## Consequences
- After cloning: `python scripts/sync_cache.py pull` (about 190 MB).
- The bucket must stay public and must not be emptied during judging; deleting an object breaks
  reproducibility of the commits that pin it. Writers: the data engineer (others on request).
- Cost: ~$0.02/GB-month storage plus egress (~$0.12/GB): cents at this size.
- Old grid blobs remain in git history (no history rewrite); the repository stops growing from now on.
- Next: GRACE and further global layers are added as bucket objects only.
