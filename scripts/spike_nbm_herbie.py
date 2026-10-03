"""Phase 0 spike: can Herbie pull the NBM fields the forecast and evaluation tools need?

Run with the cmw-herbie conda env (herbie-data, cfgrib, eccodes):

    python scripts/spike_nbm_herbie.py                      # latest available cycle
    python scripts/spike_nbm_herbie.py --cycle "2026-04-16 18:00"   # a past cycle (AWS archive)

What it does:
  1. Finds the newest NBM cycle that exists (or uses --cycle).
  2. Prints the GRIB inventory for one forecast hour, so field names are known, not guessed.
  3. Downloads only the wanted fields (byte ranges via the .idx file) and times it.
  4. Extracts the nearest grid point for a few sites and prints the values.
  5. Writes docs/nbm_spike_output.md (raw output; the write-up is docs/nbm_fields.md).

Nothing here is used by the site yet. It is a measurement tool.
"""
import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from herbie import Herbie

SITES = {
    # name: (lat, lon). Elevations are not applied in the spike.
    "Snoqualmie Pass": (47.4204, -121.4138),
    "Colchuck Lake": (47.4900, -120.8340),
    "Whistler": (50.0600, -122.9600),
}

# Search strings are regex over the .idx "variable:level" text. They are a first guess;
# the inventory printout is how we correct them.
# Corrected after the first run (see docs/nbm_fields.md). Percentile messages are 1-99% levels;
# the deterministic SNOWLVL is the "0 m above mean sea level" message. SNOWLVL is in meters.
WANTED = {
    "snow_level_m": r":SNOWLVL:0 m above mean sea level:",
    "snow_level_p50_m": r":SNOWLVL:surface:\d+ hour fcst:50% level:",
    "snow_ratio_p50": r":SNOWLR:surface:\d+ hour fcst:50% level:",
    "apcp_1h": r":APCP:surface:\d+-\d+ hour acc fcst:$",
    "temp_2m_K": r":TMP:2 m above ground:\d+ hour fcst:$",
    "gust_ms": r":GUST:10 m above ground:\d+ hour fcst:$",
    "cloud_pct": r":TCDC:surface:\d+ hour fcst:$",
}


def herbie_for(cycle, fxx):
    """NOMADS only keeps ~2 days; for older cycles pin the AWS archive. Do not pass
    source="aws": with verbose=False Herbie then still resolved to NOMADS and failed."""
    age = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None) - cycle
    kwargs = {"priority": ["aws"]} if age > pd.Timedelta(days=2) else {}
    return Herbie(cycle, model="nbm", product="co", fxx=fxx, verbose=False, **kwargs)


def find_cycle(requested, fxx):
    """Newest NBM cycle that has a file for this forecast hour."""
    if requested:
        return pd.Timestamp(requested)
    now = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None).floor("h")
    for back in range(0, 8):
        cycle = now - pd.Timedelta(hours=back)
        try:
            h = herbie_for(cycle, fxx)
            if h.grib:  # a resolved source URL means the file exists
                return cycle
        except Exception:
            continue
    raise RuntimeError("no NBM cycle found in the last 8 hours")


def nearest_index(ds, lat, lon):
    la, lo = ds["latitude"].values, ds["longitude"].values
    lo = np.where(lo > 180, lo - 360, lo)  # NBM longitudes are 0-360
    d2 = (la - lat) ** 2 + ((lo - lon) * np.cos(np.radians(lat))) ** 2
    return np.unravel_index(np.argmin(d2), d2.shape), float(np.sqrt(d2.min()) * 111.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle", help='UTC cycle, e.g. "2026-04-16 18:00"')
    ap.add_argument("--fxx", type=int, default=24, help="forecast hour to sample")
    ap.add_argument("--out", default="docs/nbm_spike_output.md")
    args = ap.parse_args()

    lines = ["# NBM fields via Herbie (Phase 0 spike)", ""]
    t0 = time.time()
    cycle = find_cycle(args.cycle, args.fxx)
    H = herbie_for(cycle, args.fxx)
    lines += [f"- Cycle: `{cycle:%Y-%m-%d %H}Z`, forecast hour {args.fxx}",
              f"- Source: {H.grib_source}", f"- URL: {H.grib}", ""]
    print(f"cycle {cycle}  source {H.grib_source}  ({time.time() - t0:.1f}s to locate)")

    inv = H.inventory()
    print(f"inventory: {len(inv)} messages")
    inv_cols = [c for c in ("variable", "level", "forward_time", "search_this") if c in inv.columns]
    lines += [f"## Inventory ({len(inv)} messages at F{args.fxx:03d})", "",
              "| variable | level | time |", "|---|---|---|"]
    seen = set()
    for _, r in inv.iterrows():
        key = (r.get("variable"), r.get("level"), r.get("forward_time"))
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"| {key[0]} | {key[1]} | {key[2]} |")
    lines.append("")
    print(inv[inv_cols].to_string(max_rows=80))

    lines += ["## Wanted fields", "", "| field | search | messages matched | size |", "|---|---|---|---|"]
    point_rows = {}
    for name, search in WANTED.items():
        try:
            sub = H.inventory(search)
        except Exception as exc:
            lines.append(f"| {name} | `{search}` | error: {exc} | |")
            continue
        n = len(sub)
        size = int(sub["end_byte"].sub(sub["start_byte"]).sum()) if n and "start_byte" in sub else 0
        lines.append(f"| {name} | `{search}` | {n} | {size / 1e6:.2f} MB |")
        print(f"{name}: {n} message(s), {size / 1e6:.2f} MB")
        if not n:
            continue
        t1 = time.time()
        try:
            ds = H.xarray(search, remove_grib=False)
        except Exception as exc:
            print(f"  could not open {name}: {exc}")
            lines[-1] += f" open failed: {exc}"
            continue
        dsl = ds if not isinstance(ds, list) else ds[0]  # p50 messages open as one cube
        print(f"  download+open {time.time() - t1:.1f}s; vars {list(dsl.data_vars)}")
        for site, (lat, lon) in SITES.items():
            idx, km = nearest_index(dsl, lat, lon)
            for var in dsl.data_vars:
                val = float(dsl[var].values[idx])
                point_rows.setdefault(site, []).append((name, var, round(val, 3), round(km, 1)))

    lines += ["", "## Point values", ""]
    for site, rows in point_rows.items():
        lines += [f"### {site}", "", "| field | variable | value | km to grid point |", "|---|---|---|---|"]
        lines += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
        lines.append("")
        print(site, rows)

    elapsed = time.time() - t0
    lines += [f"Total spike time: {elapsed:.0f} s", ""]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}  ({elapsed:.0f}s)")


if __name__ == "__main__":
    sys.exit(main())
