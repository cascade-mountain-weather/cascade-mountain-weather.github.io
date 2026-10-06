"""Write the NBM snowfall "plume" data the precipitation page draws: 6-hour snowfall (25th, 50th and
75th percentile and the deterministic value) at each forecast area, for the next several days.

    python scripts/nbm_plume.py                 # newest long NBM cycle, 5 days
    python scripts/nbm_plume.py --hours 96 --cycle "2026-10-06 13:00"

It also records the NBM 6-hour liquid precipitation (deterministic, the only version the NBM carries for
these windows) for the same windows, and total cloud cover (percent, deterministic) every 3 hours.

Output: assets/data/nbm_plumes.json (under assets/ so the site can serve it; bot-generated, do not hand-edit).

This reuses the Herbie helpers in scripts/nbm_snapshot.py (see docs/nbm_fields.md for what each NBM file
holds). Windows are 6 hours long and end at 00, 06, 12 and 18Z, because those are the windows the long NBM
cycles (01, 07, 13, 19Z) carry with percentile levels. A window the NBM does not have comes out as null, and
the method per window is recorded ("percentile", or "exceedance-interp" when the percentiles had to be
interpolated from exceedance probabilities). Percentiles do not add, so the page shows the cumulative curve
as an approximation and says so.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nbm_snapshot as nbm  # noqa: E402  (imports Herbie)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "nbm_plumes.json"
WINDOW_H = 6


def newest_long_cycle(hours):
    """Newest long cycle whose file at the last needed hour is real (not a ~1 MB placeholder)."""
    now = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None).floor("h")
    # Only some hours have real files (hourly to F48, then F50, F53, F56, ...), so test the last of those,
    # not `hours` itself (F120 is a placeholder). A real file has dozens of messages; a placeholder has one.
    check = cloud_hours(hours)[-1]
    for back in range(0, 40):
        cycle = now - pd.Timedelta(hours=back)
        if cycle.hour not in nbm.LONG_CYCLES:
            continue
        try:
            n = len(nbm.herbie_for(cycle, check).inventory())
            print(f"  cycle {cycle:%Y-%m-%d %H}Z F{check:03d}: {n} messages", file=sys.stderr)
            if n > 10:
                return cycle
        except Exception as exc:  # say why, so a failed scheduled run explains itself
            print(f"  cycle {cycle:%Y-%m-%d %H}Z F{check:03d}: {str(exc)[:100]!r}", file=sys.stderr)
            continue
    sys.exit("no long NBM cycle with the needed forecast hour found")


def liquid_window(cycle, start, end, grid):
    """6-hour liquid precipitation (inches) per site, from the same file as the snowfall window, or None."""
    fs, fe = int((start - cycle).total_seconds() // 3600), int((end - cycle).total_seconds() // 3600)
    try:
        H = nbm.herbie_for(cycle, fe)
        return nbm.fetch(H, grid, re.escape(f":APCP:surface:{fs}-{fe} hour acc fcst:") + "$") / 25.4   # kg/m2 -> inches
    except Exception as exc:
        print(f"  precip window ending {end:%d %H}Z failed: {str(exc)[:80]}", file=sys.stderr)
        return None


def window_ends(cycle, hours):
    """Window end times: every 6 h on the 00/06/12/18Z grid, from the first full window after the cycle."""
    first = cycle.ceil("6h")
    ends, e = [], first + pd.Timedelta(hours=WINDOW_H)
    while int((e - cycle).total_seconds() // 3600) <= hours:
        ends.append(e)
        e += pd.Timedelta(hours=WINDOW_H)
    return ends


def cloud_hours(hours):
    """Forecast hours that have a real NBM file: hourly to F48, then every 3rd hour starting at F50."""
    return list(range(3, 49, 3)) + list(range(50, hours + 1, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle", help='UTC cycle, e.g. "2026-10-06 13:00" (default: newest long cycle)')
    ap.add_argument("--hours", type=int, default=120, help="forecast hours to cover (default 120)")
    ap.add_argument("--out", help="output path (default assets/data/nbm_plumes.json)")
    args = ap.parse_args()

    cfg = yaml.safe_load(nbm.SITES_FILE.read_text(encoding="utf-8"))
    sites = cfg["sites"]
    cycle = pd.Timestamp(args.cycle) if args.cycle else newest_long_cycle(args.hours)
    print(f"cycle {cycle:%Y-%m-%d %H}Z, {args.hours} h")

    grid = nbm.Grid(sites)
    t0 = time.time()
    ends = window_ends(cycle, args.hours)
    per_site = {s["name"]: {k: [] for k in ("p25", "p50", "p75", "det", "method", "precip")} for s in sites}
    for e in ends:
        s = e - pd.Timedelta(hours=WINDOW_H)
        try:
            w = nbm.snowfall_window(cycle, s, e, grid, len(sites))
        except Exception as exc:  # a missing or placeholder file: leave the window empty
            print(f"  window ending {e:%d %H}Z failed: {str(exc)[:80]}", file=sys.stderr)
            w = {"method": None}
        print(f"  {e:%a %d %H}Z  {w['method']}  ({time.time() - t0:.0f}s)")
        qpf = liquid_window(cycle, s, e, grid)
        for k, site in enumerate(sites):
            d = per_site[site["name"]]
            d["method"].append(w["method"])
            d["precip"].append(nbm.r(qpf[k], 2) if qpf is not None else None)
            for key, src in (("p25", "p25"), ("p50", "p50"), ("p75", "p75"), ("det", "deterministic")):
                d[key].append(nbm.r(w[src][k]) if w.get(src) is not None else None)

    # total cloud cover (percent) every 3 hours
    cloud_times, cloud = [], {s["name"]: [] for s in sites}
    for f in cloud_hours(args.hours):
        H = nbm.herbie_for(cycle, f)
        vals = nbm.fetch(H, grid, rf":TCDC:surface:{f} hour fcst:$")
        cloud_times.append(f"{cycle + pd.Timedelta(hours=f):%Y-%m-%dT%H:%MZ}")
        for k, site in enumerate(sites):
            cloud[site["name"]].append(nbm.r(vals[k], 0))
    print(f"  cloud cover: {len(cloud_times)} times ({time.time() - t0:.0f}s)")

    out = {
        "schema": 1,
        "generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",
        "cycle_utc": f"{cycle:%Y-%m-%dT%H:%MZ}",
        "window_hours": WINDOW_H,
        "window_end_utc": [f"{e:%Y-%m-%dT%H:%MZ}" for e in ends],
        "units": "inches of snow and of liquid precipitation per window; cloud cover in percent",
        "cloud_time_utc": cloud_times,
        "notes": [
            "NBM core CONUS (2.5 km), nearest grid point to each site; not corrected for elevation.",
            "p25/p50/p75 are percentiles of the NBM blend for each 6-hour window ending at the listed time.",
            "Percentiles of consecutive windows do not add; cumulative curves built from them are approximate.",
            "precip is the NBM deterministic liquid precipitation (rain plus the water in snow) for the same 6-hour windows.",
        ],
        "sites": {name: {"km_to_grid_point": grid.km[i], **per_site[name], "cloud_pct": cloud[name]} for i, name in enumerate(per_site)},
    }
    path = Path(args.out) if args.out else OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {path} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
