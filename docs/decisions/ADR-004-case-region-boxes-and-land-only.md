# ADR-004 — Case-region boxes and land-only regional means

- Status: Proposed (pending team approval; data plan decision D1)
- Date: 2026-11-14
- Deciders (names): _fill in_
- Requirement IDs: R-02, R-12, R-15

## Context
Plan v2 fixes three first-wave cases on POWER data: (1) drought in southern Ukraine (root-zone soil
wetness, precipitation), (2) warming of Ukraine (T2M), (3) opposite precipitation trends in northern and
southern Europe. Each needs a region box. Two risks:
- **Cherry-picking:** a box chosen or adjusted after seeing its trend makes the result meaningless.
- **Sea cells:** POWER precipitation has values over the sea. The northern box would be 15% sea and the
  southern 24% sea, but the questions are about land ("rain in Europe", "drought on farmland").

## Options
1. Boxes from named region definitions, whole box averaged. Simple; mixes sea into land questions.
2. Boxes from named region definitions, **land cells only**. Answers the question asked; one more processing
   step to document.
3. Boxes tuned per case by eye. Fast, but indefensible: a judge can ask "why this box?".

## Decision (proposed)
Option 2, with boxes fixed **before** any trend is computed for them:

| Preset | Box [W, S, E, N] | Basis | Land share |
|---|---|---|---|
| `south_ukraine` | [28.5, 44.4, 37.5, 48.5] | southern steppe oblasts (Odesa, Mykolaiv, Kherson, Zaporizhzhia) and Crimea | 93% |
| `ukraine` | [22.0, 44.0, 40.5, 52.5] | whole country (existing preset) | — |
| `north_europe` | [5.0, 55.0, 31.0, 71.0] | European part of IPCC AR6 region NEU (Iturbide et al., 2020): Fennoscandia, Denmark, Baltic states | 85% |
| `south_europe` | [-10.0, 36.0, 28.0, 45.0] | European part of IPCC AR6 region MED: Iberia, southern France, Italy, Balkans, Greece | 76% |

Land-only: a cell counts if MERRA-2 has root-zone soil wetness there (excludes ocean, lakes and ice
sheets); IMERG (0.1°) and SYN1deg (1°) cells take the nearest MERRA-2 cell's flag. Set per preset
(`land_only: true` in `data/catalog/regions.yaml`) and recorded in every series' provenance.
Alternatives considered: mainland-only southern Ukraine [28.5, 46.0, 37.5, 48.5] (99% land); NEU including
the UK and Ireland [-10, 55, 31, 71] (63% land).

## Consequences
- Boxes and the land-only rule must not change after results are seen; any change gets a new ADR.
- Sea-ice fraction cannot be used with land-only presets (it is an ocean variable; acquire raises "no data").
- IMERG covers the whole northern box up to 71°N (checked 2026-11-14: 100% of cells in Jan and Jul), but
  satellite precipitation over snow is less reliable; MERRA-2 is the primary series, IMERG the cross-check.
- Follow-up: team approves or edits, then removes `status: proposed` from the presets.
