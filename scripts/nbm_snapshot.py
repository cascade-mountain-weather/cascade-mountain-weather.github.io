"""Save a forecast-time NBM snapshot for the weekend forecast areas.

The NBM changes every hour and cannot be rebuilt later, so the numbers a forecast was written
against have to be captured when it is written. This script pulls them with Herbie (byte-range
reads, only the fields below) and writes one JSON file per forecast.

    python scripts/nbm_snapshot.py                          # next Fri-Sun, newest long cycle
    python scripts/nbm_snapshot.py --first-day 2026-10-03 --days 2   # Sat and Sun only
    python scripts/nbm_snapshot.py --cycle "2026-10-02 19:00"

Run in an environment with herbie-data, cfgrib and eccodes (conda env cmw-herbie).
Findings behind the choices here are in docs/nbm_fields.md.

Output: data/forecasts/nbm_snapshot_<first-day>.json (data/ is excluded from the Jekyll build).

What it records, per site, as median (p50) with 25th and 75th percentiles:
  - snowfall for each local day and for the whole period
  - snow level, every 3 hours
plus the deterministic values and 2 m temperature and gust every 3 hours.

Temperature is corrected from the NBM cell's mean elevation to the site's elevation with a moist
(saturated) adiabatic lapse rate (scripts/lapse.py). Both the corrected and the raw NBM values are
saved. Snow level is absolute (MSL) and is not corrected. Run scripts/site_elevations.py first.

Windows run 12Z to 12Z (4 am PST, 5 am PDT) because the NBM only offers 6/24/48/72-hour snowfall
windows ending on 6-hour boundaries.

Snowfall percentiles: a window that ends at the file's own forecast hour has real percentile
messages. An earlier window inside the same file (for example Saturday, which ends at the start of
Sunday) only has exceedance probabilities (chance of more than 0.1, 1, 2, 4 ... inches). For those,
the percentiles are interpolated from that curve and the entry says method "exceedance-interp".
"""
import argparse
import json
import re
import sys
import time
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lapse import adjust_temperature  # noqa: E402

warnings.filterwarnings("ignore")
from herbie import Herbie  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITES_FILE = ROOT / "data" / "nbm" / "sites.yml"
ELEV_FILE = ROOT / "data" / "nbm" / "site_elevations.json"  # written by scripts/site_elevations.py
OUT_DIR = ROOT / "data" / "forecasts"

LONG_CYCLES = (1, 7, 13, 19)   # the only cycles that reach F263 (docs/nbm_fields.md)
STEP_H = 3                     # series spacing; every hour <=F48 and every 3rd hour after exist
M_TO_FT = 3.28084
M_TO_IN = 1 / 0.0254
PCTS = (25, 50, 75)


def herbie_for(cycle, fxx):
    """NOMADS keeps ~2 days; pin the AWS archive for older cycles (do not use source=)."""
    age = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None) - cycle
    kwargs = {"priority": ["aws"]} if age > pd.Timedelta(days=2) else {}
    return Herbie(cycle, model="nbm", product="co", fxx=fxx, verbose=False, **kwargs)


def pick_cycle(requested, period_end):
    """Newest long cycle with a real (not ~1 MB placeholder) file at the period's last hour."""
    if requested:
        return pd.Timestamp(requested)
    now = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None).floor("h")
    for back in range(0, 40):
        cycle = now - pd.Timedelta(hours=back)
        last_fxx = int((period_end - cycle).total_seconds() // 3600)
        if cycle.hour not in LONG_CYCLES or last_fxx < 1:
            continue
        try:
            if len(herbie_for(cycle, last_fxx).inventory()) > 100:
                return cycle
        except Exception:
            continue
    sys.exit("no long NBM cycle with the needed forecast hour found")


class Grid:
    """Nearest-grid-point lookup, built from the first message opened."""

    def __init__(self, sites):
        self.sites, self.idx, self.km = sites, None, None

    def bind(self, ds):
        la, lo = ds["latitude"].values, ds["longitude"].values
        lo = np.where(lo > 180, lo - 360, lo)
        self.idx, self.km = [], []
        for s in self.sites:
            d2 = (la - s["lat"]) ** 2 + ((lo - s["lon"]) * np.cos(np.radians(s["lat"]))) ** 2
            i = np.unravel_index(np.argmin(d2), d2.shape)
            self.idx.append(i)
            self.km.append(round(float(np.sqrt(d2[i]) * 111.0), 1))

    def sample(self, ds):
        if self.idx is None:
            self.bind(ds)
        arr = ds[list(ds.data_vars)[0]].values
        return np.array([float(arr[i]) for i in self.idx])


def fetch(H, grid, search, tries=3):
    """One message -> value per site (NaN if the message is missing or unreadable)."""
    for attempt in range(tries):
        try:
            ds = H.xarray(search, remove_grib=False)
            ds = ds[0] if isinstance(ds, list) else ds
            return grid.sample(ds)
        except Exception as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"    gave up on {search}: {str(last)[:100]}", file=sys.stderr)
    return np.full(len(grid.sites), np.nan)


def exceedance_quantile(thr_in, probs, q):
    """Value x with P(X <= x) = q from exceedance probabilities P(X > t) at thresholds t (ascending).

    Below the first threshold (0.1 in) the curve is unknown, so a quantile whose exceedance is under
    P(>0.1 in) is reported as 0. A quantile past the last threshold is reported as that threshold.
    """
    target = 1.0 - q
    if np.isnan(probs).any():
        return float("nan")
    if probs[0] < target:
        return 0.0
    for i in range(len(thr_in) - 1):
        if probs[i] >= target >= probs[i + 1]:
            if probs[i] == probs[i + 1]:
                return float(thr_in[i])
            frac = (probs[i] - target) / (probs[i] - probs[i + 1])
            return float(thr_in[i] + frac * (thr_in[i + 1] - thr_in[i]))
    return float(thr_in[-1])


def snowfall_window(cycle, start, end, grid, n):
    """Snowfall (in) for [start, end] per site: dict of arrays and the method used."""
    fs, fe = int((start - cycle).total_seconds() // 3600), int((end - cycle).total_seconds() // 3600)
    dt = fe - fs
    H = herbie_for(cycle, fe)
    inv = H.inventory()
    base = f":ASNOW:surface:{fs}-{fe} hour acc"
    out = {"method": None}

    pct_msgs = {p: base + f"@(fcst,dt={dt} hour),missing=0:{p}% level:" for p in PCTS}
    have = set(inv.search_this)
    if all(m in have for m in pct_msgs.values()):
        for p, m in pct_msgs.items():
            out[f"p{p}"] = fetch(H, grid, re.escape(m) + "$") * M_TO_IN
        out["method"] = "percentile"
    else:
        probs = []
        for m in sorted(s for s in have if s.startswith(base + " fcst:prob >")):
            thr = float(re.search(r"prob >([\d.]+):", m).group(1)) * M_TO_IN
            p = fetch(H, grid, re.escape(m) + "$")
            probs.append((thr, p / 100.0 if np.nanmax(p) > 1.5 else p))
        if probs:
            probs.sort(key=lambda x: x[0])
            thr = np.array([t for t, _ in probs])
            mat = np.vstack([p for _, p in probs])
            for p in PCTS:
                out[f"p{p}"] = np.array([exceedance_quantile(thr, mat[:, k], p / 100.0) for k in range(n)])
            out["method"] = "exceedance-interp"
    det = base + " fcst:"
    if det in have:
        out["deterministic"] = fetch(H, grid, re.escape(det) + "$") * M_TO_IN
    return out


def r(x, nd=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle", help='UTC cycle, e.g. "2026-10-02 19:00" (default: newest long cycle)')
    ap.add_argument("--first-day", help="first local date of the period, YYYY-MM-DD (default: next Friday)")
    ap.add_argument("--days", type=int, default=3, help="number of days (default 3: Fri, Sat, Sun)")
    args = ap.parse_args()

    if args.first_day:
        first = datetime.strptime(args.first_day, "%Y-%m-%d").date()
    else:
        today = datetime.now(timezone.utc).date()
        first = today + timedelta(days=(4 - today.weekday()) % 7 or 7)
    p_start = pd.Timestamp(first.isoformat() + " 12:00")
    p_end = p_start + pd.Timedelta(days=args.days)

    sites = yaml.safe_load(SITES_FILE.read_text(encoding="utf-8"))["sites"]
    n = len(sites)
    cycle = pick_cycle(args.cycle, p_end)
    print(f"cycle {cycle:%Y-%m-%d %H}Z, period {p_start:%Y-%m-%d %H}Z to {p_end:%Y-%m-%d %H}Z")

    grid = Grid(sites)
    t0 = time.time()

    # snowfall windows: each local day, then the whole period
    windows, snow = {}, {}
    day_edges = [p_start + pd.Timedelta(days=i) for i in range(args.days + 1)]
    spans = [(f"day{i + 1}", day_edges[i], day_edges[i + 1]) for i in range(args.days)]
    if args.days in (2, 3):
        spans.append(("total", p_start, p_end))
    for wid, s, e in spans:
        windows[wid] = {"start_utc": f"{s:%Y-%m-%dT%H:%MZ}", "end_utc": f"{e:%Y-%m-%dT%H:%MZ}",
                        "fxx": [int((s - cycle).total_seconds() // 3600), int((e - cycle).total_seconds() // 3600)]}
        print(f"snowfall {wid}: F{windows[wid]['fxx'][0]}-F{windows[wid]['fxx'][1]}")
        snow[wid] = snowfall_window(cycle, s, e, grid, n)
        print(f"    method: {snow[wid]['method']}")

    # 3-hourly series
    fxx0 = int((p_start - cycle).total_seconds() // 3600)
    fxx1 = int((p_end - cycle).total_seconds() // 3600)
    hours = list(range(fxx0, fxx1 + 1, STEP_H))
    series = {k: [] for k in ("p25", "p50", "p75", "det", "tmp", "gust")}
    times = []
    for f in hours:
        H = herbie_for(cycle, f)
        times.append(f"{cycle + pd.Timedelta(hours=f):%Y-%m-%dT%H:%MZ}")
        for p in PCTS:
            series[f"p{p}"].append(fetch(H, grid, rf":SNOWLVL:surface:{f} hour fcst:{p}% level:") * M_TO_FT)
        series["det"].append(fetch(H, grid, r":SNOWLVL:0 m above mean sea level:") * M_TO_FT)
        series["tmp"].append(fetch(H, grid, rf":TMP:2 m above ground:{f} hour fcst:$"))  # kelvin
        series["gust"].append(fetch(H, grid, rf":GUST:10 m above ground:{f} hour fcst:$") * 2.23694)
        print(f"  F{f:03d} done ({time.time() - t0:.0f}s)")

    elev = json.loads(ELEV_FILE.read_text(encoding="utf-8"))["sites"] if ELEV_FILE.exists() else {}
    if not elev:
        print("warning: data/nbm/site_elevations.json missing; temperatures will not be corrected",
              file=sys.stderr)

    out = {
        "schema": 1,
        "generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",
        "source": {"model": "NBM core CONUS", "cycle_utc": f"{cycle:%Y-%m-%dT%H:%MZ}",
                   "via": "Herbie", "first_day_local": first.isoformat(), "days": args.days},
        "notes": [
            "Values are the nearest 2.5 km grid point. Only 2 m temperature is corrected for elevation "
            "(temp_2m_f); temp_2m_nbm_f is the raw grid value. Snow level is MSL and not corrected.",
            "Temperature correction: saturated adiabatic lapse rate from the NBM cell's mean elevation to "
            "the site's elevation. It assumes saturated air, so in dry or clear weather it under-corrects, "
            "and under an inversion the true change can have the opposite sign.",
            "Snowfall windows run 12Z to 12Z (4 am PST / 5 am PDT).",
            "p25/p50/p75 are the 25th, 50th (median) and 75th percentiles of the NBM ensemble blend.",
            "snowfall method 'exceedance-interp' means the percentiles were interpolated from "
            "exceedance probabilities (more than 0.1, 1, 2, 4, 6, 8, 10, 12, 18, 24 in); treat as approximate.",
        ],
        "windows": windows,
        "series_times_utc": times,
        "sites": {},
    }
    for k, s in enumerate(sites):
        entry = {"lat": s["lat"], "lon": s["lon"], "km_to_grid_point": grid.km[k], "snowfall_in": {}}
        for wid, d in snow.items():
            entry["snowfall_in"][wid] = {
                "method": d["method"],
                **{key: r(d[key][k]) for key in ("p25", "p50", "p75", "deterministic") if key in d},
            }
        entry["snow_level_ft"] = {
            "p25": [r(v[k], 0) for v in series["p25"]], "p50": [r(v[k], 0) for v in series["p50"]],
            "p75": [r(v[k], 0) for v in series["p75"]], "deterministic": [r(v[k], 0) for v in series["det"]],
        }
        raw_k = [float(v[k]) for v in series["tmp"]]
        to_f = lambda tk: (tk - 273.15) * 9 / 5 + 32  # noqa: E731
        e = elev.get(s["name"], {})
        if e.get("site_ft") is not None and e.get("nbm_cell_ft") is not None:
            cell_m, site_m = e["nbm_cell_ft"] / 3.28084, e["site_ft"] / 3.28084
            entry["elevation_ft"] = {"site": e["site_ft"], "nbm_cell": e["nbm_cell_ft"],
                                     "site_minus_cell": e["site_ft"] - e["nbm_cell_ft"],
                                     "site_source": e.get("site_source"), "correction": "moist-adiabatic"}
            entry["temp_2m_f"] = [r(to_f(adjust_temperature(t, cell_m, site_m)), 1) for t in raw_k]
        else:
            entry["elevation_ft"] = None
            entry["temp_2m_f"] = [r(to_f(t), 1) for t in raw_k]  # uncorrected: no elevations on file
        entry["temp_2m_nbm_f"] = [r(to_f(t), 1) for t in raw_k]
        entry["gust_mph"] = [r(v[k], 0) for v in series["gust"]]
        out["sites"][s["name"]] = entry

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"nbm_snapshot_{first.isoformat()}.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
