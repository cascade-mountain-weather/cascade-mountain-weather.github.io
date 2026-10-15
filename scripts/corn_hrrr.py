"""HRRR point forcing for the corn validation days that fall outside Synoptic's history (2022-2025).

    python scripts/corn_hrrr.py --day 2023-03-22 --workers 5        # fetch (resumable) the hours one validation day needs

For each valid hour it reads the 1-hour forecast from the run one hour earlier (hrrr.tHHz.wrfsfcf01; the analysis file has no
usable radiation) through Herbie, at the grid point nearest the site: 2 m temperature and dew point, 10 m wind components,
downward shortwave and longwave at the surface, surface pressure and the model terrain height. Hours: hourly for the last 48 h
before the end of the window (the day before and the target day), every 3 h before that. Cached in data/corn/validation/hrrr_<id>.pkl.
Needs Herbie and cfgrib. The HRRR terrain is smoothed (3 km), so the caller adjusts temperature to the site elevation.
"""
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "corn" / "validation"
PAT = r"(:TMP:2 m above|:DPT:2 m above|:UGRD:10 m above|:VGRD:10 m above|:DSWRF:surface|:DLWRF:surface|:HGT:surface|:PRES:surface)"
SPINUP_DAYS = 4


def hours_needed(date):
    d = pd.Timestamp(date)
    end = d + pd.Timedelta(days=1) + pd.Timedelta(hours=8)                  # local midnight after the day, in UTC (PST)
    start = d - pd.Timedelta(days=SPINUP_DAYS + 1) + pd.Timedelta(hours=8)
    hourly_from = end - pd.Timedelta(hours=48)
    out = list(pd.date_range(start.ceil("3h"), hourly_from, freq="3h")) + list(pd.date_range(hourly_from, end, freq="1h"))
    return sorted(set(out))


def read_one(args):
    valid, lat, lon, tmp = args
    os.environ["PYTHONIOENCODING"] = "utf-8"
    import io, contextlib
    from herbie import Herbie
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        H = Herbie(valid - pd.Timedelta(hours=1), model="hrrr", product="sfc", fxx=1, save_dir=tmp, verbose=False)
        dss = H.xarray(PAT, remove_grib=True)
    row = {"valid": valid}
    for ds in dss:
        la, lo = ds["latitude"].values, ds["longitude"].values
        lo = np.where(lo > 180, lo - 360, lo)
        d2 = (la - lat) ** 2 + ((lo - lon) * np.cos(np.radians(lat))) ** 2
        iy, ix = np.unravel_index(np.argmin(d2), d2.shape)
        for v in ds.data_vars:
            row[v] = float(ds[v].values[iy, ix])
    return row


def fetch(date, site_id, lat, lon, workers=5):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"hrrr_{site_id}_{date}.pkl"
    have = pd.read_pickle(f) if f.exists() else pd.DataFrame()
    todo = [t for t in hours_needed(date) if have.empty or t not in have.index]
    tmp = str(Path(os.environ.get("TEMP", ".")) / "herbie_corn")
    print(f"{site_id} {date}: {len(todo)} hours to fetch ({len(have)} cached)", flush=True)
    rows = []
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(read_one, (t, lat, lon, tmp)): t for t in todo}
        for n, fu in enumerate(as_completed(futs), 1):
            try:
                rows.append(fu.result())
            except Exception as e:
                print("  failed", futs[fu], repr(e)[:100], flush=True)
            if n % 20 == 0:
                print(f"  {n}/{len(todo)}", flush=True)
                _save(f, have, rows)
    return _save(f, have, rows)


def _save(f, have, rows):
    if rows:
        new = pd.DataFrame(rows).set_index("valid")
        have = pd.concat([have, new]).sort_index()
        have = have[~have.index.duplicated()]
        have.to_pickle(f)
    return have


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--workers", type=int, default=5)
    a = ap.parse_args()
    import corn_validate as cv
    d = next(x for x in cv.DAYS if x["date"] == a.day)
    fetch(d["date"], d["id"], d["lat"], d["lon"], a.workers)
