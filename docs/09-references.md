# 09 — References (feeds "NASA Data" and "References" submission fields)

Add every dataset, tool, library, image and font actually used. Mark `used: yes` only when it is in the final product.

## NASA data and tools
| Name | Short name / version | DOI / URL | Used for | used |
|---|---|---|---|---|
| Giovanni | — | https://giovanni.gsfc.nasa.gov/ | Area-averaged time series, cross-checks | |
| Hydrology Data Rods (GES DISC) | — | https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Time%20Series | **Discontinued** (GES DISC alert, 2025-10-01); not used. Hydrology comes from POWER (MERRA-2 soil wetness, evaporation) and GRACE | no |
| AppEEARS (LP DAAC) | — | https://appeears.earthdatacloud.nasa.gov/ | MODIS subsets | |
| NASA POWER API | v2 | https://power.larc.nasa.gov/ | Live meteorological series (MERRA-2/CERES) | |
| NASA POWER Zarr archive (AWS Open Data) | POWER 10.0.0; stores `power_merra2_monthly_temporal_utc`, `power_imerg_monthly_temporal_utc`, `power_syn1deg_monthly_temporal_utc`, `power_merra2_daily_temporal_utc` | https://registry.opendata.aws/nasa-power/ | Live regional monthly series without login (`backend/trend_detective/power_zarr.py`) | |
| MODIS Terra Vegetation Indices Monthly L3 Global 0.05Deg CMG (LP DAAC) | MOD13C2 v061 | https://doi.org/10.5067/MODIS/MOD13C2.061 | Regional monthly NDVI via Earthdata OPeNDAP subsets; accessed 2026-11-14; `backend/trend_detective/modis_ndvi.py` (fill -3000, divide by 10000, pixel_reliability 0-1 kept, cos(lat) area mean, month dropped if < 80% land area valid) | |
| JPL GRACE and GRACE-FO Mascon Ocean, Ice, and Hydrology Equivalent Water Height CRI Filtered (PO.DAAC) | TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4 (RL06.3Mv04) | https://doi.org/10.5067/TEMSC-3JC634 | Regional monthly total water storage anomaly (cm, 2004-2009 baseline); accessed 2026-11-14; `backend/trend_detective/grace.py` (land_mask only, no gain factors, cos(lat) area mean) | |
| Earthdata OPeNDAP (Hyrax, cloud) | DAP4 | https://opendap.earthdata.nasa.gov/ | Server-side spatial subsetting of MOD13C2 granules | |
| MERRA-2 | see catalog | https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/ | Temperature, precipitation, aerosols | |
| GLDAS Noah | see catalog | https://ldas.gsfc.nasa.gov/gldas | Soil moisture, evapotranspiration, runoff, SWE | |
| GPM IMERG | see catalog | https://gpm.nasa.gov/data/imerg | Precipitation | |
| MODIS | see catalog | https://modis.gsfc.nasa.gov/ | NDVI, land surface temperature, snow cover | |
| OMI | see catalog | https://aura.gsfc.nasa.gov/omi.html | NO2, ozone | |
| AIRS | see catalog | https://airs.jpl.nasa.gov/ | Surface air temperature, water vapour | |

## Required citation texts (copy into the submission and the site footer)
- **NASA POWER** (required by https://power.larc.nasa.gov/docs/referencing/, checked 2026-11-14: include both texts).
  - POWER's Reference: "The data was obtained from National Aeronautics and Space Administration (NASA) Langley
    Research Center's Prediction Of Worldwide Energy Resources (POWER) project funded through the NASA Earth Science
    Division."
  - Data reference (POWER's template is "The data was obtained from the POWER Project's <service> <version> on
    YYYY/MM/DD."; ours uses the Zarr archive): "The data was obtained from the POWER Project's Zarr archive on AWS
    Open Data, POWER Version 10.0.0, on 2026/11/14." Update the date at each data refresh (`data/cache/MANIFEST.json`).
  - POWER also asks for a link or description of the use to larc-power-project@mail.nasa.gov (team decision).
- **MODIS NDVI**: Didan, K. (2021). MODIS/Terra Vegetation Indices Monthly L3 Global 0.05Deg CMG V061. NASA EOSDIS
  LP DAAC. https://doi.org/10.5067/MODIS/MOD13C2.061 (accessed 2026-11-14).
- **GRACE/GRACE-FO**: JPL GRACE and GRACE-FO Mascon Ocean, Ice, and Hydrology Equivalent Water Height Coastal
  Resolution Improvement (CRI) Filtered, Release 06.3, Version 04 (RL06.3Mv04). PO.DAAC, CA, USA.
  https://doi.org/10.5067/TEMSC-3JC634 (accessed 2026-11-14). Method: Watkins et al. (2015); CRI filter: Wiese et
  al. (2016).

## Space agency partner / other resources
| Name | URL | Used for | used |
|---|---|---|---|
| KNMI Climate Explorer | https://climexp.knmi.nl/ | Validation of trends | |
| NOAA Climate Data Online | https://www.ncei.noaa.gov/cdo-web/ | Station validation | |
| CSA SWOT / RCM | https://www.asc-csa.gc.ca/eng/satellites/swot/ | (optional) | |

## Scientific references (methods)
- Wiese, D. N., Landerer, F. W., & Watkins, M. M. (2016). Quantifying and reducing leakage errors in the JPL RL05M GRACE mascon solution. *Water Resources Research*, 52. https://doi.org/10.1002/2016WR019344 (CRI filter used by the GRACE product.)
- Iturbide, M., et al. (2020). An update of IPCC climate reference regions for subcontinental analysis of climate model data. *Earth System Science Data*, 12, 2959–2970. https://doi.org/10.5194/essd-12-2959-2020 (basis for the `north_europe` / `south_europe` boxes.)
- Rodell, M., Velicogna, I., & Famiglietti, J. S. (2009). Satellite-based estimates of groundwater depletion in India. *Nature*, 460, 999–1002. (GRACE plausibility check for NW India.)
- Watkins, M. M., Wiese, D. N., Yuan, D.-N., Boening, C., & Landerer, F. W. (2015). Improved methods for observing Earth's time variable mass distribution with GRACE using spherical cap mascons. *JGR Solid Earth*, 120, 2648–2671.
- Didan, K. (2021). MODIS/Terra Vegetation Indices Monthly L3 Global 0.05Deg CMG V061. NASA EOSDIS LP DAAC. https://doi.org/10.5067/MODIS/MOD13C2.061
- Mann, H. B. (1945). Nonparametric tests against trend. *Econometrica*, 13, 245–259.
- Kendall, M. G. (1975). *Rank Correlation Methods*. Griffin.
- Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. *JASA*, 63, 1379–1389.
- Yue, S., & Wang, C. (2004). The Mann-Kendall test modified by effective sample size to detect trend in serially correlated hydrological series. *Water Resources Management*, 18, 201–218.
- Hamed, K. H., & Rao, A. R. (1998). A modified Mann-Kendall trend test for autocorrelated data. *J. Hydrology*, 204, 182–196.
- Hirsch, R. M., Slack, J. R., & Smith, R. A. (1982). Techniques of trend analysis for monthly water quality data. *Water Resources Research*, 18, 107–121.
- Santer, B. D., et al. (2000). Statistical significance of trends and trend differences in layer-average atmospheric temperature time series. *JGR*, 105, 7337–7356.
- Weatherhead, E. C., et al. (1998). Factors affecting the detection of trends: Statistical considerations and applications to environmental data. *JGR*, 103, 17149–17161.
- Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate. *JRSS B*, 57, 289–300.
- Wilks, D. S. (2016). "The stippling shows statistically significant grid points." *BAMS*, 97, 2263–2273.
- Gilbert, R. O. (1987). *Statistical Methods for Environmental Pollution Monitoring*. Wiley.

## Software libraries
| Library | License | Used for | used |
|---|---|---|---|
| numpy, scipy, pandas | BSD | Statistics, data handling | |
| xarray, netCDF4 | Apache/MIT | Gridded data | |
| earthaccess, harmony-py | MIT | NASA data access | |
| FastAPI | MIT | API | |
| React, Vite, MapLibre GL, Plotly/ECharts | MIT/BSD | Frontend | |
