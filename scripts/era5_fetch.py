"""Download ERA5 for the synoptic regime (storm-type) analysis. Run by hand; resumable.

    python scripts/era5_fetch.py                  # everything, 3 requests at a time
    python scripts/era5_fetch.py --years 2022     # one calendar year (a quick test)

Fields (Copernicus CDS ERA5 hourly datasets, the 00, 06, 12 and 18 UTC analyses on a 1 degree grid, NE Pacific and western
North America: 20-65N, 180W-100W). The analysis averages the four times into a UTC daily mean. (The "daily statistics"
datasets work for a single month but refuse a whole cold season as "cost limits exceeded".)
  z500   geopotential at 500 hPa              (reanalysis-era5-pressure-levels)
  t850   temperature at 850 hPa               (reanalysis-era5-pressure-levels)
  ivt_u, ivt_v   vertically integrated eastward / northward water vapour flux, kg/m/s
                 (reanalysis-era5-single-levels; IVT = hypot(ivt_u, ivt_v))
One NetCDF per field and calendar year holding the cold-season months (Nov-May: Jan-May and Nov-Dec of that year), written to
data/era5/ (git-ignored: a few hundred MB in all). Needs a CDS account and ~/.cdsapirc with the current API URL
(https://cds.climate.copernicus.eu/api) and a key without the old UID: prefix, and the ERA5 licence accepted on the CDS site.
"""
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cdsapi

OUT = Path(__file__).resolve().parent.parent / "data" / "era5"
AREA = [65, -180, 20, -100]       # north, west, south, east
MONTHS = ["01", "02", "03", "04", "05", "11", "12"]
FIELDS = {
    "z500": ("reanalysis-era5-pressure-levels", {"variable": ["geopotential"], "pressure_level": ["500"]}),
    "t850": ("reanalysis-era5-pressure-levels", {"variable": ["temperature"], "pressure_level": ["850"]}),
    "ivt_u": ("reanalysis-era5-single-levels", {"variable": ["vertical_integral_of_eastward_water_vapour_flux"]}),
    "ivt_v": ("reanalysis-era5-single-levels", {"variable": ["vertical_integral_of_northward_water_vapour_flux"]}),
}


def fetch(job, tries=4):
    name, year = job
    path = OUT / f"{name}_{year}.nc"
    if path.exists() and path.stat().st_size > 10_000:
        return name, year, "have"
    dataset, extra = FIELDS[name]
    req = {"product_type": "reanalysis", "year": str(year), "month": MONTHS, "day": [f"{d:02d}" for d in range(1, 32)],
           "time": ["00:00", "06:00", "12:00", "18:00"], "area": AREA, "grid": [1.0, 1.0],
           "data_format": "netcdf", "download_format": "unarchived", **extra}
    for attempt in range(tries):
        try:
            cdsapi.Client(quiet=True).retrieve(dataset, req, str(path) + ".part")
            Path(str(path) + ".part").replace(path)
            return name, year, "ok"
        except Exception as exc:  # the queue or the network: wait and try again
            last = str(exc)[:200]
            time.sleep(30 * (attempt + 1))
    return name, year, "FAILED: " + last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, default=list(range(1991, 2027)))
    ap.add_argument("--fields", nargs="+", default=list(FIELDS), choices=list(FIELDS))
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(f, y) for y in a.years for f in a.fields]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for name, year, status in ex.map(fetch, jobs):
            print(f"{name} {year}: {status} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    sys.exit(main())
