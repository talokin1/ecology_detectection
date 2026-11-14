# Ukraine cut-out of global datasets — data types

Computed 14 November 2026 (Europe/Kiev) from `$UKRAINE_SAMPLES/`. This is a Ukraine cut-out (bbox 22.1–40.2°E, 44.4–52.4°N, or Ukraine UP stations) of global datasets. Station gaps and valid rates are Ukraine-specific; a global pull of the same products will look different. Every date, count, gap, and percentage is calculated from the files.

**Gap rule.** A gap is a run of 3 or more consecutive months in which more than 50% of *active* stations or reaches have no valid value. A station or reach is active in a month if that month falls between its first and last valid observation. Units that never report the variable are dropped first. Isolated 1–2 month holes are not listed as main gaps. For snow depth, summer non-reporting is out of season, not a gap; winter is November–March. For gridded series, a gap is 3 or more missing months in the series. Two valid rates are given for stations: **raw** (share of in-span station-months or station-days with a value, before dropping gap months) and **after excluding network gaps**. Incomplete 2026 (and IMERG’s incomplete 2025, which ends in September) should be dropped from climate annual trends.

Challenge resources: NOAA CDO (GSOM/GHCN), MODIS via LP DAAC DAP4 (not AppEEARS), GES DISC. SWOT is challenge-adjacent (CSA SWOT material is on the challenge Resources tab). Outside sources: NASA POWER, GRACE/GRACE-FO (PO.DAAC).

## Air temperature (mean, min, max)

- **NASA POWER** (outside source; MERRA-2-derived, not independent) — monthly bbox mean, 464 cells, January 1981–December 2025. T2M, T2M_MAX, T2M_MIN. No gaps; 100% of cell-months valid. Over 1981–2025, POWER T2M vs native MERRA-2 M2TMNXSLV has r = 1.000 to three decimals (computed 0.999996).
- **NASA MERRA-2 M2TMNXSLV** (challenge, GES DISC) — monthly bbox mean, 464 of 464 cells every month (414 of 414 land-masked), January 1980–September 2026. 2 m temperature only. No gaps; 100% of months valid. Drop incomplete 2026.
- **NOAA GSOM** (challenge, NOAA CDO) — monthly, 183 of 204 UP stations report TAVG and 186 report TMAX/TMIN, January 1900–October 2026. TAVG stations per decade: 1900s 10, 1910s 11, 1920s 12, 1930s 21, 1940s 21, 1950s 38, 1960s 42, 1970s 48, 1980s 55, 1990s 49, 2000s 180, 2010s 85, 2020s 32. Main shared wartime gap: August 1941–May 1944. After the 1960s, recurring winter holes and multi-year stretches (TAVG notably May 2004–June 2008 and August 2008–June 2014; TMIN September 1984–December 1999; TMAX October 1981–February 1991 and November 1993–December 1999). Valid rates: TAVG 47.3% raw, 71.8% after excluding network gaps; TMAX 49.5% / 72.0%; TMIN 43.1% / 74.3%. Headline long-record TAVG (9 stations): 9 stations through 2012, 4 in 2013–2019, **no usable annual values in 2020–2024**, 4 in 2025. That 2020–2024 hole is real for the headline series: none of the 9 have ≥10 months in those years (4 stations have only 3–7 months each year). It is not a total blackout of the 183-station archive (24–29 other stations also have a few months, none with ≥10), so the general >50%-of-active-stations rule does not list 2020–2024 as one continuous network gap. Drop incomplete 2026 (21 stations have some TAVG months; none have ≥10).
- **NOAA GHCN-Daily** (challenge, NOAA CDO) — daily, 27 of 28 UP city stations, 1 January 1881–6 November 2026. TAVG stations per decade: 1880s 3, 1890s 4, 1900s 3, 1910s 3, 1920s 3, 1930s 11, 1940s 21, 1950s–1990s 26, 2000s 27, 2010s 24, 2020s 21. TAVG gaps: August 1939–June 1940, June 1941–December 1945, July–September 1950, January 1964–December 1968, July 1971–December 1972. TMAX/TMIN mainly August 1941–April/May 1944. Valid rates: TAVG 81.2% raw, 86.7% after excluding network gaps; TMAX 77.9% / 78.8%; TMIN 74.8% / 75.7%. Headline annual tmean: 20 stations in 2020–2021, 15 in 2022, 19 in 2023–2024, 9 in 2025. Drop incomplete 2026.
- **GLDAS Noah 0.25° Tair** (challenge, GES DISC) — monthly, 2,128 of 2,128 cells every month. Version 2.0: January 1948–December 2014. Version 2.1: January 2000–July 2026. No gaps; 100% of months valid. These are **separate series and must not be joined**: over the January 2000–December 2014 overlap (180 months), Tair 2.0 minus 2.1 averages **+0.495 °C** (computed +0.4948 °C). Drop incomplete 2026 (2.1 ends in July).
- **AIRS 3STM 7.0 surface air temperature** (challenge, GES DISC) — monthly bbox mean, September 2002–October 2026, 290 consecutive months, no gaps, 100% of months have a valid mean. Spatial coverage: typically 288 of 288 1° cells; the lowest month has **263 of 288**. Drop incomplete 2026.

## Precipitation

- **NASA POWER** (outside source; MERRA-2-derived, not independent) — monthly bbox mean of PRECTOTCORR (mm/day), 464 cells, January 1981–December 2025. No gaps; 100% valid. Over 1981–2025, POWER PRECTOTCORR vs native MERRA-2 M2TMNXFLX has r = 0.9997 (1.000 to three decimals).
- **NASA MERRA-2 M2TMNXFLX** (challenge, GES DISC) — monthly bbox mean, 464 of 464 cells every month, January 1980–September 2026. Totals already in mm. No gaps; 100% of months valid. Drop incomplete 2026.
- **GPM IMERG V07 Final** (challenge, GES DISC) — monthly bbox mean of 14,480 of 14,480 0.1° cells every month, January 2000–September 2025. Totals already in mm. No gaps; 100% of months valid. Drop incomplete 2025 (the series ends in September) as well as any later year.
- **NOAA GSOM** (challenge, NOAA CDO) — monthly, 201 of 204 UP stations, January 1900–March 2026. Stations per decade: 1900s 13, 1910s 14, 1920s 14, 1930s 61, 1940s 80, 1950s 182, 1960s 197, 1970s 198, 1980s 198, 1990s 179, 2000s 95, 2010s 11, 2020s 3. Gaps: August 1941–April 1944, January–October 1976, January 1991–August 1992, and January 1994–December 2003. After 2003 the network thins (those endings are not counted as gaps once a station has stopped). Valid rates: 82.3% raw, 92.9% after excluding network gaps. Recent years: 3 stations with ≥10 months in each of 2020–2024, 1 in 2025. Drop incomplete 2026.
- **NOAA GHCN-Daily** (challenge, NOAA CDO) — daily, 28 stations, 6 February 1879–20 March 2026. Stations per decade: 1870s 1, 1880s 9, 1890s 9, 1900s 10, 1910s 10, 1920s 9, 1930s 16, 1940s 25, 1950s–1980s 28, 1990s 27, 2000s 27, 2010s 25, 2020s 21. Gaps: March 1879–December 1880 and August 1941–March 1944. Valid rates: 75.7% raw, 76.6% after excluding network gaps. Headline annual totals rest on 2 stations in 2020–2024 and none in 2025. Drop incomplete 2026.

## Humidity

- **NASA POWER** (outside source; MERRA-2-derived, not independent) — monthly bbox mean of QV2M (g/kg), 464 cells, January 1981–December 2025. No gaps; 100% valid. Vs native MERRA-2 QV2M, r = 1.000 to three decimals (computed 0.999994).
- **NASA MERRA-2 M2TMNXSLV** (challenge, GES DISC) — 464 of 464 cells (414 land) every month, January 1980–September 2026. No gaps; 100% of months valid. Drop incomplete 2026.

## Wind

- **NASA POWER** (outside source; MERRA-2-derived) — monthly bbox mean of 10 m wind speed, 464 cells, January 1981–December 2025. No gaps; 100% valid. No other wind source is in the extract.

## Solar radiation

- **NASA POWER** (outside source) — monthly bbox mean of all-sky shortwave, 144 CERES 1° cells, January 1984–December 2025. No gaps in that span; 100% valid. Starts in 1984, not 1981; official documentation places a GEWEX SRB to CERES transition at 2001. This solar field is not a MERRA-2 variable.

## Snow depth

- **NOAA GHCN-Daily** (challenge, NOAA CDO) — daily, 26 of 28 stations, 1 January 1973–12 March 2026. Stations per decade: 1970s–1990s 26, 2000s 25, 2010s 24, 2020s 21. Summer non-reporting is seasonal, not a network gap; no 3+ month winter (November–March) network gaps. 77.1% of November–March station-months have at least one valid depth; 32.1% of November–March station-days have a value (raw and after gaps are the same, because no winter network gaps were listed). Drop incomplete 2026.

## Snow water equivalent

- **GLDAS Noah 0.25°** (challenge, GES DISC) — monthly, 2,121 of 2,121 land cells every month. Version 2.0: January 1948–December 2014. Version 2.1: January 2000–July 2026. No gaps; 100% of months valid. Keep 2.0 and 2.1 as separate series; do not join them. Drop incomplete 2026.

## Vegetation (NDVI / EVI)

- **MODIS Terra MOD13C2.061** (challenge, pulled via LP DAAC DAP4, not AppEEARS) — monthly bbox mean of valid 0.05° pixels (mean 53,304; range 53,148–53,340), February 2000–October 2026. 321 consecutive months, no gaps; 100% of months have a valid NDVI and EVI mean. Drop incomplete 2026.

## Land surface temperature (day / night)

- **MODIS Terra MOD11C3.061** (challenge, pulled via LP DAAC DAP4, not AppEEARS) — monthly bbox mean, February 2000–October 2026, 321 months, no gaps; 100% of months have a valid day and night mean. Daytime valid pixels average 53,472 and fall to a minimum of **49,965 in December 2007**; night-time average 53,487, minimum 53,209. LST is clear-sky only, which thins winter counts and can bias winter means. Drop incomplete 2026.

## River water-surface elevation (SWOT)

- **SWOT Hydrocron / RiverSP Version D** (challenge-adjacent: CSA SWOT material is on the challenge Resources tab) — irregular overpasses on 8 reaches with data, 5 April 2023–10 November 2026. No 3+ month network gaps. After dropping fill values, 96.5% of 1,380 observations are valid (raw and after gaps are the same). About 3.3 years — too short for climate inference.

## Soil moisture

- **GLDAS Noah 0.25°** (challenge, GES DISC) — monthly 0–10 cm and root-zone, 2,121 of 2,121 land cells every month. Version 2.0: January 1948–December 2014 (804 months). Version 2.1: January 2000–July 2026 (319 months). No gaps; 100% of months valid. Keep the two versions separate; do not join them. Drop incomplete 2026.

## Evaporation / runoff

- **GLDAS Noah 0.25°** (challenge, GES DISC) — same versions and periods as soil moisture, 2,121 land cells, no gaps, 100% of months valid. Evapotranspiration is already stored as mm/month. Surface runoff is Qs_mm = Qs_acc × 8 × days in the month (exact match in both version files). Version 2.1 mean annual runoff is **23.1 mm/year** over complete years 2000–2025 (range 5.3–56.5). Version 2.0 mean annual runoff is 14.9 mm/year over 1948–2014. Do not join the two versions. Drop incomplete 2026.

## Water vapour

- **AIRS 3STM 7.0 total column water vapour** (challenge, GES DISC) — monthly bbox mean, **288 of 288** 1° cells every month, September 2002–October 2026, 290 months, no gaps, 100% valid. Drop incomplete 2026.

## Terrestrial water storage

- **GRACE/GRACE-FO JPL mascon CRI RL06.3Mv04** (outside source, PO.DAAC; downloaded by Researcher 2) — monthly bbox land mean, 528 of 528 land cells in every present month, April 2002–September 2026, **261** monthly solutions. Verified from the file: the inter-mission gap is **July 2017–May 2018** (11 months; June 2017 is present), plus **August–September 2018**. There are also 20 other official missing months (mostly one- or two-month outages: June–July 2002, June 2003, and later battery/accelerometer holes). In all, 33 months are missing of 294 expected in April 2002–September 2026. Drop incomplete 2026. Do not interpolate the inter-mission gap into a trend without saying so.

## Not fully in hand

- **OMI tropospheric NO₂** (challenge, GES DISC) is still downloading. A partial extract is on disk for 1 October 2004–31 December 2006 (805 of 822 days present; 24 further days have fill in the tropospheric column). The OMI row anomaly begins in **2007**; when the rest arrives, use `XTrackQualityFlags` and do not treat unflagged row-anomaly pixels as an NO₂ trend.
- **AppEEARS 1 km LST and land cover** (challenge) is being pulled by Researcher (not yet on disk in this folder).
- **Hydrology Data Rods** is discontinued, not blocked.
- **KNMI Climate Explorer** and **RADARSAT** remain blocked.
