# 09 — References (feeds "NASA Data" and "References" submission fields)

Add every dataset, tool, library, image and font actually used. Mark `used: yes` only when it is in the final product.

## NASA data and tools
| Name | Short name / version | DOI / URL | Used for | used |
|---|---|---|---|---|
| Giovanni | — | https://giovanni.gsfc.nasa.gov/ | Area-averaged time series, cross-checks | |
| Hydrology Data Rods (GES DISC) | — | https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Time%20Series | Point hydrology series | |
| AppEEARS (LP DAAC) | — | https://appeears.earthdatacloud.nasa.gov/ | MODIS subsets | |
| NASA POWER API | v2 | https://power.larc.nasa.gov/ | Live meteorological series (MERRA-2/CERES) | |
| MERRA-2 | see catalog | https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/ | Temperature, precipitation, aerosols | |
| GLDAS Noah | see catalog | https://ldas.gsfc.nasa.gov/gldas | Soil moisture, evapotranspiration, runoff, SWE | |
| GPM IMERG | see catalog | https://gpm.nasa.gov/data/imerg | Precipitation | |
| MODIS | see catalog | https://modis.gsfc.nasa.gov/ | NDVI, land surface temperature, snow cover | |
| OMI | see catalog | https://aura.gsfc.nasa.gov/omi.html | NO2, ozone | |
| AIRS | see catalog | https://airs.jpl.nasa.gov/ | Surface air temperature, water vapour | |

## Space agency partner / other resources
| Name | URL | Used for | used |
|---|---|---|---|
| KNMI Climate Explorer | https://climexp.knmi.nl/ | Validation of trends | |
| NOAA Climate Data Online | https://www.ncei.noaa.gov/cdo-web/ | Station validation | |
| CSA SWOT / RCM | https://www.asc-csa.gc.ca/eng/satellites/swot/ | (optional) | |

## Scientific references (methods)
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
