# GPCC v2025 gauge counts inside the Ukraine bbox

Recomputed from the global 1° files under `$GLOBAL_DATA/gpcc_v2025_1deg` (no re-download).
Cell centres inside 22.1–40.2°E, 44.4–52.4°N: 144 cells (8 × 18), the same centre rule as the first extract.
`gauge` is the number of gauges in the cell. The bbox sum is the count of gauges inside the box.
`gauge_int` counts gauges the interpolation used, including stations outside the cell, so its sum is not a station count.

| Decade | Months | Mean gauges inside the bbox | Mean gauge_int sum |
|---|---:|---:|---:|
| 1890–1899 | 108 | 63 | 1387 |
| 1900–1909 | 120 | 65 | 1374 |
| 1910–1919 | 120 | 62 | 1271 |
| 1920–1929 | 120 | 71 | 1249 |
| 1930–1939 | 120 | 99 | 1282 |
| 1940–1949 | 120 | 104 | 1163 |
| 1950–1959 | 120 | 218 | 1301 |
| 1960–1969 | 120 | 444 | 1376 |
| 1970–1979 | 120 | 469 | 1367 |
| 1980–1989 | 120 | 503 | 1381 |
| 1990–1999 | 120 | 416 | 1322 |
| 2000–2009 | 120 | 275 | 1172 |
| 2010–2019 | 120 | 276 | 1331 |
| 2020–2029 | 72 | 227 | 1373 |

1981–2025 mean of the monthly bbox gauge sum: **346**.
The network inside the box peaked in the 1980s (about 500) and is about 230 in 2020–2025.
A precipitation trend over that window is estimated on a thinning gauge set. Interpolation still draws on a wider network (`gauge_int` sum stays near 1,200–1,400), which is why the precip field can look complete while the in-box station count falls.
Annual means: `gpcc_gauge_annual.csv`.
