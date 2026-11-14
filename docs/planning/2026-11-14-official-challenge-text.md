# Official challenge: Be An Earth System Trend Detective!

Source: https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/
(read in the browser on 2026-11-14; the old URL `/be-an-earth-system-trend-detective/` gives a 404)

**Difficulty:** Advanced · **Subjects:** Earth Science, Software

## Summary
Create a tool that can **select** variables measured by Earth science missions or produced by
Earth science models, **visualize** how they change over time, and determine **what** is
changing, **where**, **how much**, and whether the change is **significant**. A variable can
trend one way in one region and the opposite way in another, even when one process drives both.

## Background (key points)
- Instruments named: **MODIS, OMI, AIRS, GPM**. Models named: **MERRA-2, GLDAS**.
- Two parts to the problem: (a) *finding* variables that trend, from simple ones (temperature,
  rainfall) to complex ones (**evaporation, streamflow**); (b) *analyzing* trends in particular
  regions of land, ocean, or **levels of the atmosphere**.
- Relating significant trends to the processes causing them is one of the most important uses
  of NASA Earth data.

## Objectives (the judging checklist)
1. Identify Earth science variables of interest that can be investigated for trends.
2. Acquire the variables **for a particular region** (most trends are not global).
3. Generate and **visualize a time series** long enough for statistical analysis.
4. Do a basic statistical analysis: **rate of change**, and **significance** via t-test,
   Mann-Kendall, or confidence intervals.
> "A response that does both the visualization and the analysis meets the full scope."

## Potential considerations (optional, but they show what the judges hope to see)
**Audience:** high school and college students, and the public with some science background.
- Give **simple definitions of variables**.
- Users should become "data detectives": find a variable → is it trending → is it significant.

**Approach:**
- A **short series of questions** (what / where to investigate) that leads to matching variables.
- **A couple of demonstration examples** users can watch to learn the tool.
- **SI/AI** (optional) to suggest variables likely to trend in an area, using news articles and
  research papers, or region type (desert, rain forest, tidal estuary, air above a big city).

**Working with the data:**
- Daily and monthly data are easiest.
- A trend that is **not significant is still interesting**; a longer record may make it significant.
- Consider outside hydrology plotting tools such as **CUAHSI** (HydroShare / HIS / Data Rods Explorer).
- Trends can be non-linear, and some only appear once the **seasonal cycle is removed**.
  Linear trends are "a great start"; complex analysis is out of scope.

## Resources tab (official list)
### NASA data & resources
| Resource | What it is | URL |
|---|---|---|
| Giovanni | Menus of many variables; makes and downloads time series | https://giovanni.gsfc.nasa.gov/ |
| Hydrology Time Series (Data Rods) | Hydrology time series (GLDAS, NLDAS, ...) | https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Time%20Series |
| AppEEARS | Subsets and transforms geospatial data, time series included | https://appeears.earthdatacloud.nasa.gov/ |
| Climate Data Online (NOAA NCEI) | Global historical station weather and climate data, with a map tool | https://www.ncei.noaa.gov/cdo-web/ |
| SeaWiFS chlorophyll time-series paper | Worked example of building a time series and testing significance | https://ntrs.nasa.gov/api/citations/20090042747/downloads/20090042747.pdf |

### Space agency partner resources
| Resource | URL |
|---|---|
| KNMI Climate Explorer | https://climexp.knmi.nl/ |
| Statistical test methods to detect trends (Medium) | https://medium.com/@snp.kriss/statistical-test-methods-to-detect-trends-in-time-series-data-b361a0ec530b |
| Guide to statistical significance (Statsig) | https://www.statsig.com/perspectives/a-comprehensive-guide-to-statistical-significance |
| CSA RADARSAT Constellation Mission data | https://donnees-data.asc-csa.gc.ca/en/dataset/rcm |
| Geo.ca (Canada open geospatial data) | http://geo.ca/ |
| SWOT mission info (CSA) | https://www.asc-csa.gc.ca/eng/satellites/swot/ |
| Monitoring ecosystems from space (CSA) | https://www.asc-csa.gc.ca/eng/satellites/everyday-lives/monitoring-and-protecting-our-ecosystems-from-space.asp |
| SAR Python tutorial (CSA) | https://github.com/asc-csa/Synthetic_Aperture_Radar_Tutorial |
