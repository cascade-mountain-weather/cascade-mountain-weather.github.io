"""Write the NBM snowfall "plume" data the precipitation page draws: 6-hour snowfall (25th, 50th and
75th percentile and the deterministic value) at each forecast area, for the next several days.

    python scripts/nbm_plume.py                 # newest long NBM cycle, 5 days
    python scripts/nbm_plume.py --hours 96 --cycle "2026-10-06 13:00"

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
    for back in range(0, 40):
        cycle = now - pd.Timedelta(hours=back)
        if cycle.hour not in nbm.LONG_CYCLES:
            continue
        try:
            if len(nbm.herbie_for(cycle, hours).inventory()) > 100:
                return cycle
        except Exception:
            continue
    sys.exit("no long NBM cycle with the needed forecast hour found")


def window_ends(cycle, hours):
    """Window end times: every 6 h on the 00/06/12/18Z grid, from the first full window after the cycle."""
    first = cycle.ceil("6h")
    ends, e = [], first + pd.Timedelta(hours=WINDOW_H)
    while int((e - cycle).total_seconds() // 3600) <= hours:
        ends.append(e)
        e += pd.Timedelta(hours=WINDOW_H)
    return ends


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
    per_site = {s["name"]: {k: [] for k in ("p25", "p50", "p75", "det", "method")} for s in sites}
    for e in ends:
        s = e - pd.Timedelta(hours=WINDOW_H)
        try:
            w = nbm.snowfall_window(cycle, s, e, grid, len(sites))
        except Exception as exc:  # a missing or placeholder file: leave the window empty
            print(f"  window ending {e:%d %H}Z failed: {str(exc)[:80]}", file=sys.stderr)
            w = {"method": None}
        print(f"  {e:%a %d %H}Z  {w['method']}  ({time.time() - t0:.0f}s)")
        for k, site in enumerate(sites):
            d = per_site[site["name"]]
            d["method"].append(w["method"])
            for key, src in (("p25", "p25"), ("p50", "p50"), ("p75", "p75"), ("det", "deterministic")):
                d[key].append(nbm.r(w[src][k]) if w.get(src) is not None else None)

    out = {
        "schema": 1,
        "generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",
        "cycle_utc": f"{cycle:%Y-%m-%dT%H:%MZ}",
        "window_hours": WINDOW_H,
        "window_end_utc": [f"{e:%Y-%m-%dT%H:%MZ}" for e in ends],
        "units": "inches of snow per window",
        "notes": [
            "NBM core CONUS (2.5 km), nearest grid point to each site; not corrected for elevation.",
            "p25/p50/p75 are percentiles of the NBM blend for each 6-hour window ending at the listed time.",
            "Percentiles of consecutive windows do not add; cumulative curves built from them are approximate.",
        ],
        "sites": {name: {"km_to_grid_point": grid.km[i], **per_site[name]} for i, name in enumerate(per_site)},
    }
    path = Path(args.out) if args.out else OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {path} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
