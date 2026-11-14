#!/usr/bin/env python3
"""ERA5 and ERA5-Land monthly-mean requests for the Ukraine bbox.

Not run in the archive pass: CDSAPI_KEY was not set in the environment, so
nothing was downloaded. The script reads that variable and never prints it.
Accept the Copernicus licence on the dataset page before the first request.
Install cdsapi>=0.7.2. Existing files are skipped.
"""
import os
from pathlib import Path

import cdsapi

OUT = Path(os.environ.get("UKRAINE_SAMPLES", "ukraine_samples")) / "extra" / "era5_cds"
AREA = [52.4, 22.1, 44.4, 40.2]  # N, W, S, E
MONTHS = [f"{m:02d}" for m in range(1, 13)]


def client():
    key = os.environ.get("CDSAPI_KEY")
    if not key:
        raise SystemExit("CDSAPI_KEY is not set")
    return cdsapi.Client(url="https://cds.climate.copernicus.eu/api", key=key)


def get(c, dataset, variables, y0, y1, tag):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{tag}_{y0}-{y1}.nc"
    if path.exists():
        print("skip", path.name)
        return
    c.retrieve(dataset, {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": variables,
        "year": [str(y) for y in range(y0, y1 + 1)],
        "month": MONTHS,
        "time": ["00:00"],
        "area": AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }, str(path))


ERA5_VARS = ["2m_temperature", "total_precipitation",
             "volumetric_soil_water_layer_1", "volumetric_soil_water_layer_2",
             "volumetric_soil_water_layer_3", "volumetric_soil_water_layer_4",
             "snow_depth", "land_sea_mask"]
LAND_VARS = ["2m_temperature", "total_precipitation",
             "volumetric_soil_water_layer_1", "volumetric_soil_water_layer_2",
             "volumetric_soil_water_layer_3", "volumetric_soil_water_layer_4",
             "snow_depth_water_equivalent", "total_evaporation", "potential_evaporation"]


def main():
    c = client()
    for y0, y1 in [(1940, 1969), (1970, 1999), (2000, 2025)]:
        get(c, "reanalysis-era5-single-levels-monthly-means", ERA5_VARS, y0, y1, "era5_monthly")
    for y0, y1 in [(1950, 1979), (1980, 2004), (2005, 2025)]:
        get(c, "reanalysis-era5-land-monthly-means", LAND_VARS, y0, y1, "era5land_monthly")


if __name__ == "__main__":
    main()
