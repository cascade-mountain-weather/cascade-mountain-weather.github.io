"""Write the point-forecast meteogram data for the main page: NBM, HRRR and HRDPS at each ski area in data/nbm/sites.yml.

    python scripts/meteograms.py                       # newest cycle of each model, 48 hours
    python scripts/meteograms.py --hours 12 --sites "Mt. Baker" "Crystal"    # quick test

Output: assets/data/meteograms.json (bot-generated, do not hand-edit). Per model: the cycle used, then per site hourly
series of 2 m temperature (F), 2 m relative humidity (%), 10 m wind speed (mph) and one-hour liquid precipitation (in).
Values are the model grid cell nearest the site, NOT downscaled or corrected for elevation (the page says so);
`grid_km` is the distance from the site to that cell. All three models are read through Herbie like the plume pages.

  NBM    deterministic fields from the long-cycle (01/07/13/19Z) hourly files: TMP, RH, WIND (10 m), APCP (1 h).
  HRRR   TMP, RH, wind speed from UGRD/VGRD (10 m), APCP (1 h); the 00/06/12/18Z cycles run 48 hours.
  HRDPS  TMP, RH, WIND (10 m), APCP accumulated from the start of the run (hourly values are differences); 48 hours.
Forecast hours 1..48 only for now: beyond F48 the NBM files are 3-hourly and carry no 3-hour precipitation total.
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from herbie import Herbie

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hires_models as hm  # noqa: E402
import nbm_snapshot as nbm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "meteograms.json"
WORKERS = 4
MPS_TO_MPH = 2.236936
MM_TO_IN = 1 / 25.4
LABELS = {"nbm": "NBM (NOAA blend, 2.5 km)", "hrrr": "HRRR (NOAA, 3 km)", "hrdps": "HRDPS (Environment Canada, 2.5 km)"}


def k_to_f(k):
    return (k - 273.15) * 9 / 5 + 32


def rd(x, n=1):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def newest_nbm_cycle(hours):
    now = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None).floor("h")
    for back in range(0, 40):
        cycle = now - pd.Timedelta(hours=back)
        if cycle.hour not in nbm.LONG_CYCLES:
            continue
        try:
            if len(nbm.herbie_for(cycle, hours).inventory()) > 10:
                return cycle
        except Exception:
            continue
    return None


def multi(H, grid, search, tries=3):
    """One Herbie call for several messages -> {cfgrib variable name: value per site}. Missing messages are just absent."""
    last = None
    for attempt in range(tries):
        try:
            dss = H.xarray(search, remove_grib=False)
            out = {}
            for ds in (dss if isinstance(dss, list) else [dss]):
                if grid.idx is None:
                    grid.bind(ds)
                for v in ds.data_vars:
                    arr = ds[v].values
                    out[v] = np.array([float(arr[i]) for i in grid.idx])
            return out
        except Exception as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"    gave up on {search[:60]}: {str(last)[:100]}", file=sys.stderr)
    return {}


def nan(grid):
    return np.full(len(grid.sites), np.nan)


def run_hours(one_hour, hours, grid, keys=("temp_f", "rh", "dewpoint_f", "wind_mph", "wind_dir", "precip_in")):
    """Run one_hour(f) for f = 1..hours (the first one alone so the grid binds, then in threads); -> {var: [arrays]}."""
    res = {1: one_hour(1)}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for f, r in zip(range(2, hours + 1), ex.map(one_hour, range(2, hours + 1))):
            res[f] = r
    return {k: [res[f][k] for f in range(1, hours + 1)] for k in keys}


def nbm_series(cycle, hours, grid):
    def one(f):
        H = nbm.herbie_for(cycle, f)
        v = multi(H, grid, rf"(:(TMP|RH):2 m above ground:{f} hour fcst:nan|:WIND:10 m above ground:{f} hour fcst:nan"
                           rf"|:APCP:surface:{f - 1}-{f} hour acc fcst:nan)")
        # dew point and wind direction in their own request: if the NBM names them differently they stay empty
        # instead of taking temperature, wind and precipitation down with them
        x = multi(H, grid, rf"(:DPT:2 m above ground:{f} hour fcst:nan|:WDIR:10 m above ground:{f} hour fcst:nan)", tries=1)
        print(f"  nbm F{f:02d} {sorted(v)} {sorted(x)}")
        return {"temp_f": k_to_f(v.get("t2m", nan(grid))), "rh": v.get("r2", nan(grid)),
                "dewpoint_f": k_to_f(x.get("d2m", nan(grid))), "wind_dir": x.get("wdir10", nan(grid)),
                "wind_mph": v.get("si10", nan(grid)) * MPS_TO_MPH, "precip_in": v.get("tp", nan(grid)) * MM_TO_IN}
    return run_hours(one, hours, grid)


def wind_from(u, v):
    """Direction (degrees) the wind blows FROM, from its eastward and northward components."""
    return (270 - np.degrees(np.arctan2(v, u))) % 360


def hrrr_series(cycle, hours, grid):
    def one(f):
        H = Herbie(cycle, model="hrrr", product="sfc", fxx=f, verbose=False)
        v = multi(H, grid, rf"(:(TMP|RH|DPT):2 m above ground:|:(UGRD|VGRD):10 m above ground:|:APCP:surface:{f - 1}-{f} hour acc fcst)")
        print(f"  hrrr F{f:02d} {sorted(v)}")
        return {"temp_f": k_to_f(v.get("t2m", nan(grid))), "rh": v.get("r2", nan(grid)),
                "dewpoint_f": k_to_f(v.get("d2m", nan(grid))),
                "wind_dir": wind_from(v.get("u10", nan(grid)), v.get("v10", nan(grid))),
                "wind_mph": np.hypot(v.get("u10", nan(grid)), v.get("v10", nan(grid))) * MPS_TO_MPH,
                "precip_in": v.get("tp", nan(grid)) * MM_TO_IN}
    return run_hours(one, hours, grid)


def hrdps_field(cycle, var, level, fxx, grid):
    n = len(grid.sites)
    last = None
    for attempt in range(3):
        try:
            H = Herbie(cycle, model="hrdps", product="continental", variable=var, level=level, fxx=fxx, verbose=False)
            ds = H.xarray(remove_grib=False)
            ds = ds[0] if isinstance(ds, list) else ds
            return grid.sample(ds)
        except Exception as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"    gave up on HRDPS {var} F{fxx:03d}: {str(last)[:100]}", file=sys.stderr)
    return np.full(n, np.nan)


def hrdps_series(cycle, hours, grid):
    def one(f):
        r = {"temp_f": k_to_f(hrdps_field(cycle, "TMP", "AGL-2m", f, grid)), "rh": hrdps_field(cycle, "RH", "AGL-2m", f, grid),
             "dewpoint_f": k_to_f(hrdps_field(cycle, "DPT", "AGL-2m", f, grid)),
             "wind_dir": hrdps_field(cycle, "WDIR", "AGL-10m", f, grid),
             "wind_mph": hrdps_field(cycle, "WIND", "AGL-10m", f, grid) * MPS_TO_MPH,
             "cum_in": hrdps_field(cycle, "APCP", "Sfc", f, grid) * MM_TO_IN}      # accumulated since the run started
        print(f"  hrdps F{f:02d}")
        return r
    res = run_hours(one, hours, grid, keys=("temp_f", "rh", "dewpoint_f", "wind_dir", "wind_mph", "cum_in"))
    cum, prev, per_hour = res.pop("cum_in"), np.zeros(len(grid.sites)), []
    for c in cum:
        per_hour.append(np.maximum(c - prev, 0))
        prev = np.where(np.isfinite(c), c, prev)
    res["precip_in"] = per_hour
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--models", nargs="+", default=["nbm", "hrrr", "hrdps"], choices=["nbm", "hrrr", "hrdps"])
    ap.add_argument("--sites", nargs="+", help="site names to include (default: all ski areas in data/nbm/sites.yml)")
    ap.add_argument("--out", help="output path (default assets/data/meteograms.json)")
    args = ap.parse_args()
    if args.hours > 48:
        sys.exit("--hours above 48 is not supported yet (see the module docstring)")

    cfg = yaml.safe_load(nbm.SITES_FILE.read_text(encoding="utf-8"))
    sites = [s for s in cfg["sites"] if not args.sites or s["name"] in args.sites]
    out = {"schema": 1, "generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",
           "units": {"temp_f": "F, 2 m", "rh": "percent, 2 m", "dewpoint_f": "F, 2 m", "wind_mph": "mph, 10 m", "wind_dir": "degrees the wind blows FROM, 10 m", "precip_in": "inches of liquid per hour"},
           "notes": ["Model grid-cell values at the point nearest each ski area; not downscaled or corrected for elevation or terrain."],
           "sites": [{"name": s["name"], "lat": s["lat"], "lon": s["lon"]} for s in sites], "models": {}}
    t0 = time.time()
    path = Path(args.out or OUT)
    try:
        previous = json.loads(path.read_text(encoding="utf-8")).get("models", {})
    except Exception:
        previous = {}
    for model in args.models:
        cycle = newest_nbm_cycle(args.hours) if model == "nbm" else hm.newest_cycle(model)
        block = None
        for attempt in range(3):                      # newest cycle first; if it has no data yet, try the one before
            if cycle is None:
                break
            print(f"{model} cycle {cycle:%Y-%m-%d %H}Z")
            grid = nbm.Grid(sites)
            fn = {"nbm": nbm_series, "hrrr": hrrr_series, "hrdps": hrdps_series}[model]
            ser = fn(cycle, args.hours, grid)
            arr = {k: np.array(v) for k, v in ser.items()}           # hours x sites
            if not np.isfinite(arr["temp_f"]).any():
                print(f"{model}: cycle {cycle:%d %H}Z returned no data (not fully posted yet?)", file=sys.stderr)
                cycle = (cycle - pd.Timedelta(hours=6)) if model == "nbm" else hm.newest_cycle(model, latest=cycle - pd.Timedelta(hours=1))
                continue
            times = [f"{cycle + pd.Timedelta(hours=f):%Y-%m-%dT%H:%MZ}" for f in range(1, args.hours + 1)]
            block = {
                "label": LABELS[model], "cycle_utc": f"{cycle:%Y-%m-%dT%H:%MZ}", "time_utc": times,
                "sites": {s["name"]: {"grid_km": grid.km[k] if grid.km else None,
                                      **{key: [rd(x, 2 if key == "precip_in" else 1) for x in a[:, k]] for key, a in arr.items()}}
                          for k, s in enumerate(sites)},
            }
            break
        if block is None and model in previous:
            print(f"{model}: no fresh data, keeping the previous run ({previous[model].get('cycle_utc')})", file=sys.stderr)
            block = previous[model]
        if block is None:
            print(f"{model}: no usable data, skipped", file=sys.stderr)
            continue
        out["models"][model] = block
        print(f"{model} done ({time.time() - t0:.0f}s)")
    path.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print("wrote", path)


if __name__ == "__main__":
    main()
