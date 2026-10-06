"""High-resolution deterministic models, read through Herbie, for the plume page and the evaluation.

    HRRR   NOAA's 3 km Rapid Refresh, cycles every hour; the 00, 06, 12 and 18Z cycles run 48 hours.
    HRDPS  Environment Canada's 2.5 km High Resolution Deterministic Prediction System, 00/06/12/18Z, 48 hours.

Both give snow and precipitation as totals accumulated from the start of the run, so a window is the
difference between two forecast hours. Values are taken at the grid point nearest each site (not corrected
for elevation).

  HRRR   snowfall = ASNOW (accumulated snow depth, m, as the model reports it; the model chooses its own ratio)
         liquid   = APCP  (kg/m2 = mm)
  HRDPS  snowfall = WEASN (accumulated water equivalent of snow, kg/m2) x 10: HRDPS has no snow-depth
                    accumulation, so a 10:1 ratio is ASSUMED. Treat HRDPS snowfall as liquid snow x 10.
         liquid   = APCP

Data for old cycles: HRRR is in the AWS archive back to 2014 (Herbie finds it). HRDPS is only kept for a few
weeks on Environment Canada's servers, so it cannot be backfilled for past seasons.
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from herbie import Herbie

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nbm_snapshot as nbm  # noqa: E402  (Grid, fetch)

M_TO_IN = 1 / 0.0254
MM_TO_IN = 1 / 25.4
HRDPS_RATIO = 10.0          # assumed snow-to-liquid ratio for HRDPS (see the module docstring)
CYCLES = (0, 6, 12, 18)     # the cycles that run 48 hours
MAX_HOURS = 48


def newest_cycle(model, now=None, latest=None):
    """Newest 00/06/12/18Z cycle that has its last forecast hour posted (or, with `latest`, at or before it)."""
    now = pd.Timestamp(now or datetime.now(timezone.utc)).tz_localize(None).floor("h") if latest is None else latest
    for back in range(0, 48):
        c = now - pd.Timedelta(hours=back)
        if c.hour not in CYCLES:
            continue
        if available(model, c, MAX_HOURS):
            return c
    return None


def available(model, cycle, fxx):
    try:
        if model == "hrrr":
            return len(Herbie(cycle, model="hrrr", product="sfc", fxx=fxx, verbose=False).inventory()) > 10
        H = Herbie(cycle, model="hrdps", product="continental", variable="APCP", level="Sfc", fxx=fxx, verbose=False)
        return H.grib is not None and H.grib_source is not None
    except Exception:
        return False


def cumulative(model, cycle, fxx, grid):
    """Accumulated snowfall (in) and liquid precipitation (in) from the cycle to forecast hour fxx, per site."""
    n = len(grid.sites)
    if fxx == 0:
        return np.zeros(n), np.zeros(n)
    if model == "hrrr":
        H = Herbie(cycle, model="hrrr", product="sfc", fxx=fxx, verbose=False)
        # whole days are labelled in days ("0-1 day acc" at F24, "0-2 day acc" at F48)
        span = f"0-{fxx // 24} day" if fxx % 24 == 0 else f"0-{fxx} hour"
        snow = nbm.fetch(H, grid, f":ASNOW:surface:{span} acc fcst:") * M_TO_IN
        liq = nbm.fetch(H, grid, f":APCP:surface:{span} acc fcst:") * MM_TO_IN
        return snow, liq
    out = []
    for var in ("WEASN", "APCP"):
        for attempt in range(3):
            try:
                H = Herbie(cycle, model="hrdps", product="continental", variable=var, level="Sfc", fxx=fxx, verbose=False)
                ds = H.xarray(remove_grib=False)
                ds = ds[0] if isinstance(ds, list) else ds
                out.append(grid.sample(ds) * MM_TO_IN)
                break
            except Exception as exc:
                last = exc
                time.sleep(1.5 * (attempt + 1))
        else:
            print(f"    gave up on HRDPS {var} F{fxx:03d}: {str(last)[:100]}", file=sys.stderr)
            out.append(np.full(n, np.nan))
    snow_swe, liq = out
    return snow_swe * HRDPS_RATIO, liq


def windows(model, cycle, ends, grid, verbose=True):
    """6-hour snowfall and liquid precipitation (in) per site for each window end in `ends`.
    Returns {end_timestamp: (snow[n], liquid[n])}; a window outside the model's 48 hours is NaN."""
    cache = {}

    def cum(fxx):
        if fxx not in cache:
            cache[fxx] = cumulative(model, cycle, fxx, grid)
        return cache[fxx]

    out = {}
    n = len(grid.sites)
    for e in ends:
        fe = int((e - cycle).total_seconds() // 3600)
        fs = fe - 6
        if fs < 0 or fe > MAX_HOURS:
            out[e] = (np.full(n, np.nan), np.full(n, np.nan))
            continue
        s1, l1 = cum(fe)
        s0, l0 = cum(fs)
        out[e] = (np.maximum(s1 - s0, 0), np.maximum(l1 - l0, 0))
        if verbose:
            print(f"  {model} {e:%a %d %H}Z (F{fs:02d}-F{fe:02d}) done")
    return out


def for_snapshot(nbm_cycle, spans, sites, models=("hrrr", "hrdps"), verbose=True):
    """HRRR and HRDPS snowfall and liquid precipitation for the snapshot's windows, for scoring.

    nbm_cycle  the NBM cycle the snapshot used; each model's newest 48-hour cycle at or before it is used
               (the forecast was made with what existed then)
    spans      {window id: (start, end)} as naive UTC Timestamps; only windows that end within 48 hours of the
               model's cycle can be filled (normally Friday only), and the weekend "total" is skipped
    sites      forecast sites (dicts with name, lat, lon)
    Returns {model: {"cycle_utc", "windows": {wid: {"fxx": [a, b]}}, "sites": {name: {"snowfall_in": {wid: x}, "liquid_in": {wid: x}}}}}
    A model with no cycle available (HRDPS for an old weekend, which is not archived) is left out.
    """
    out = {}
    latest = pd.Timestamp(nbm_cycle).floor("6h")
    for model in models:
        cycle = newest_cycle(model, latest=latest)
        if cycle is None:
            if verbose:
                print(f"  {model}: no cycle available at or before {latest:%Y-%m-%d %H}Z, skipped")
            continue
        grid = nbm.Grid(sites)
        res, fxx = {}, {}
        for wid, (s, e) in spans.items():
            if wid == "total":
                continue
            fs, fe = int((s - cycle).total_seconds() // 3600), int((e - cycle).total_seconds() // 3600)
            if fs < 0 or fe > MAX_HOURS:
                continue
            s1, l1 = cumulative(model, cycle, fe, grid)
            s0, l0 = cumulative(model, cycle, fs, grid)
            res[wid], fxx[wid] = (np.maximum(s1 - s0, 0), np.maximum(l1 - l0, 0)), [fs, fe]
            if verbose:
                print(f"  {model} {wid}: F{fs:02d}-F{fe:02d} from the {cycle:%Y-%m-%d %H}Z run")
        if not res:
            continue
        out[model] = {"cycle_utc": f"{cycle:%Y-%m-%dT%H:%MZ}", "windows": {w: {"fxx": f} for w, f in fxx.items()},
                      "sites": {s["name"]: {"snowfall_in": {w: nbm.r(res[w][0][k]) for w in res},
                                            "liquid_in": {w: nbm.r(res[w][1][k], 2) for w in res}} for k, s in enumerate(sites)}}
    return out
