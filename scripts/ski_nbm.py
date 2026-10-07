"""Extract this week's NBM forecast at every ski-tool zone for the ski tool (needs Herbie: run in the cmw-herbie env).

    python scripts/ski_nbm.py                       # next Friday, Saturday, Sunday, newest long cycle
    python scripts/ski_nbm.py --first-day 2026-10-09 --days 3 --cycle "2026-10-07 19:00"

Output: data/ski/nbm_extract.json (raw numbers per zone and local day); scripts/ski_features.py --real turns it into assets/data/ski_features.json.

For each local day D at each zone's forecast point (the nearest 2.5 km NBM grid point, not corrected for elevation):
  new snow        24 h ending at 00Z after the ski day (about 4-5 pm local): four 6 h NBM windows combined with the fitted scaled sum
                  (nbm_snapshot.scaled_sum), median with 25th and 75th percentile, plus the sum of the deterministic values
  liquid          the NBM deterministic 6 h liquid precipitation over the same windows
  snow ratio      SNOWLR 50th percentile, at the forecast hour nearest the middle of the ski day (snow-to-liquid ratio, the powder proxy)
  snow level      mean SNOWLVL 50th percentile over the ski window (07:00-16:00 local), feet MSL
  gust            maximum 10 m gust, mph;  cloud, visibility, temperature: means over the ski window (cloud %, miles, F)
Forecast hours with a real file are hourly to F48 and every third hour from F50 (docs/nbm_fields.md); the ski window is sampled every third of those.
Nothing is invented: a value that cannot be read is left null and the tool says so.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nbm_plume as pl  # noqa: E402
import nbm_snapshot as nbm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "ski" / "destinations.yml"
OUT = ROOT / "data" / "ski" / "nbm_extract.json"
PT = ZoneInfo("America/Los_Angeles")
M_TO_FT = 3.28084
MS_TO_MPH = 2.23694


def real_hours(cycle, start, end):
    """Forecast hours whose valid time is in [start, end] (naive UTC) and that have a real NBM file, thinned to every third."""
    out = []
    for t in pd.date_range(start, end, freq="h"):
        f = int((t - cycle).total_seconds() // 3600)
        if f < 1:
            continue
        if (f <= 48 and f % 3 == 0) or (f >= 50 and (f - 50) % 3 == 0):
            out.append(f)
    return out


def local_day(d):
    """(ski window start, end, snow window start, end) in naive UTC for local date d."""
    s = datetime(d.year, d.month, d.day, 7, tzinfo=PT).astimezone(timezone.utc).replace(tzinfo=None)
    e = datetime(d.year, d.month, d.day, 16, tzinfo=PT).astimezone(timezone.utc).replace(tzinfo=None)
    snow_end = pd.Timestamp(e).ceil("6h")
    return pd.Timestamp(s), pd.Timestamp(e), snow_end - pd.Timedelta(hours=24), snow_end


def field(cycle, f, grid, search):
    return nbm.fetch(nbm.herbie_for(cycle, f), grid, search)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle", help='UTC cycle, e.g. "2026-10-07 19:00" (default: newest long cycle that reaches the last day)')
    ap.add_argument("--first-day", help="first local date, YYYY-MM-DD (default: next Friday)")
    ap.add_argument("--days", type=int, default=3)
    a = ap.parse_args()

    cfg = yaml.safe_load(DEST.read_text(encoding="utf-8"))
    zones = cfg["zones"]
    sites = [{"name": z["id"], "lat": z["forecast_point"]["lat"], "lon": z["forecast_point"]["lon"]} for z in zones]
    today = datetime.now(PT).date()
    first = datetime.strptime(a.first_day, "%Y-%m-%d").date() if a.first_day else today + timedelta(days=(4 - today.weekday()) % 7 or 7)
    days = [first + timedelta(days=k) for k in range(a.days)]
    wins = [local_day(d) for d in days]
    last_end = max(w[3] for w in wins)
    cycle = pd.Timestamp(a.cycle) if a.cycle else None
    if cycle is None:
        # newest long cycle that still has a real file at the last hour needed
        need = int((last_end - pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None).floor("h")).total_seconds() // 3600) + 30
        cycle = pl.newest_long_cycle(max(need, 80))
    print(f"cycle {cycle:%Y-%m-%d %H}Z; days {days[0]} to {days[-1]}; last forecast hour F{int((last_end - cycle).total_seconds() // 3600)}")
    grid = nbm.Grid(sites)
    n = len(sites)
    t0 = time.time()
    res = {z["id"]: [] for z in zones}
    for d, (ws, we, ss, se) in zip(days, wins):
        print(f"{d}: ski window {ws:%d %HZ}-{we:%d %HZ}, snow window {ss:%d %HZ}-{se:%d %HZ}  ({time.time() - t0:.0f}s)")
        # snow and liquid: four 6 h windows
        parts, qpf = [], []
        for k in range(4):
            s6, e6 = ss + pd.Timedelta(hours=6 * k), ss + pd.Timedelta(hours=6 * (k + 1))
            try:
                parts.append(nbm.snowfall_window(cycle, s6, e6, grid, n))
            except Exception as exc:
                print(f"    snow window ending {e6:%d %HZ} failed: {str(exc)[:80]}", file=sys.stderr)
                parts.append({"method": None})
            q = pl.liquid_window(cycle, s6, e6, grid)
            qpf.append(q)
        sn = nbm.scaled_sum(parts)
        liquid = None if any(q is None for q in qpf) else sum(qpf)
        # point fields over the ski window
        hrs = real_hours(cycle, ws, we)
        series = {k: [] for k in ("tmp", "gust", "tcdc", "vis", "snowlvl")}
        for f in hrs:
            series["tmp"].append(field(cycle, f, grid, rf":TMP:2 m above ground:{f} hour fcst:$") - 273.15)
            series["gust"].append(field(cycle, f, grid, rf":GUST:10 m above ground:{f} hour fcst:$") * MS_TO_MPH)
            series["tcdc"].append(field(cycle, f, grid, rf":TCDC:(surface|reserved):{f} hour fcst:$"))
            series["vis"].append(field(cycle, f, grid, rf":VIS:surface:{f} hour fcst:$") / 1609.34)
            series["snowlvl"].append(field(cycle, f, grid, rf":SNOWLVL:surface:{f} hour fcst:50% level:$") * M_TO_FT)
        mid = ws + (we - ws) / 2
        fm = min(real_hours(cycle, ws - pd.Timedelta(hours=3), we + pd.Timedelta(hours=3)) or hrs or [0], key=lambda f: abs((cycle + pd.Timedelta(hours=f)) - mid)) if hrs else None
        ratio = field(cycle, fm, grid, rf":SNOWLR:surface:{fm} hour fcst:50% level:$") if fm else np.full(n, np.nan)
        stack = lambda k: np.vstack(series[k]) if series[k] else np.full((1, n), np.nan)
        for i, z in enumerate(zones):
            g = lambda arr, fn: nbm.r(fn(arr[:, i]), 1) if arr.size and not np.isnan(arr[:, i]).all() else None
            res[z["id"]].append({
                "date": str(d), "hours_sampled": hrs,
                "snow_method": sn.get("method"),
                "snow_p25_in": nbm.r(sn["p25"][i], 1) if sn.get("method") else None,
                "snow_p50_in": nbm.r(sn["p50"][i], 1) if sn.get("method") else None,
                "snow_p75_in": nbm.r(sn["p75"][i], 1) if sn.get("method") else None,
                "snow_det_in": nbm.r(sn["deterministic"][i], 1) if sn.get("method") and "deterministic" in sn else None,
                "liquid_in": nbm.r(liquid[i], 2) if liquid is not None else None,
                "snow_ratio": nbm.r(ratio[i], 1) if not np.isnan(ratio[i]) else None,
                "snow_level_ft": g(stack("snowlvl"), np.nanmean) if series["snowlvl"] else None,
                "gust_mph": g(stack("gust"), np.nanmax) if series["gust"] else None,
                "cloud_pct": g(stack("tcdc"), np.nanmean) if series["tcdc"] else None,
                "vis_mi": g(stack("vis"), np.nanmean) if series["vis"] else None,
                "temp_f": nbm.r(np.nanmean(stack("tmp")[:, i]) * 9 / 5 + 32, 0) if series["tmp"] and not np.isnan(stack("tmp")[:, i]).all() else None,
            })
    out = {"schema": 1, "generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}", "cycle_utc": f"{cycle:%Y-%m-%dT%H:%MZ}",
           "model": "NOAA National Blend of Models (core CONUS, 2.5 km), via Herbie", "km_to_grid_point": dict(zip(res, grid.km)),
           "windows_utc": [{"date": str(d), "ski": [f"{w[0]:%Y-%m-%dT%H:%MZ}", f"{w[1]:%Y-%m-%dT%H:%MZ}"], "snow": [f"{w[2]:%Y-%m-%dT%H:%MZ}", f"{w[3]:%Y-%m-%dT%H:%MZ}"]} for d, w in zip(days, wins)],
           "notes": ["Nearest grid point to each zone's forecast point; temperature, snowfall and wind are not corrected for the elevation of the point.",
                     "Snowfall is the median of the NBM (with 25th and 75th percentiles) over the 24 hours ending 00Z after the ski day, from four 6 h windows combined with the fitted scaled sum.",
                     "Snow level, gust, cloud, visibility and temperature are over 07:00 to 16:00 local time (Pacific)."],
           "zones": res}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {OUT} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
