"""One-time script: elevation of each forecast site and of the NBM grid cell it falls in.

    python scripts/site_elevations.py

Reads data/nbm/sites.yml and writes data/nbm/site_elevations.json. Run it again only when a site is
added or moved. Run in the cmw-herbie env (it opens one NBM message to learn the grid cell centers).

  site_ft      forecast elevation: the site's own elevation (`elevation_ft` in sites.yml if set, else the
               DEM at lat/lon), raised to `forecast_floor_ft` (5000) when it is lower
  site_dem_ft  DEM elevation at lat/lon (always recorded, so an override can be compared with it)
  nbm_cell_ft  mean DEM elevation over the ~2.5 km NBM cell around the nearest grid point

nbm_snapshot.py uses the difference to correct 2 m temperature (see lapse.py). Snow level is absolute
(MSL) and needs no correction.

DEM source: USGS 3DEP via the National Map Elevation Point Query Service (about 10 m). The NBM files
carry no terrain field, so the cell elevation is the DEM averaged over the cell, 5 x 5 points 0.5 km
apart, which approximates the 2.5 km box. Falls back to None per point on request errors, and the
cell mean is only kept if at least 20 of the 25 points answered.
"""
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nbm_snapshot import Grid, LONG_CYCLES, herbie_for  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITES_FILE = ROOT / "data" / "nbm" / "sites.yml"
OUT = ROOT / "data" / "nbm" / "site_elevations.json"
EPQS = "https://epqs.nationalmap.gov/v1/json"
CELL_OFFSETS_KM = (-1.0, -0.5, 0.0, 0.5, 1.0)


def dem_ft(lat, lon, tries=3):
    for attempt in range(tries):
        try:
            r = requests.get(EPQS, params={"x": lon, "y": lat, "wkid": 4326, "units": "Feet",
                                           "includeDate": "false"}, timeout=30)
            r.raise_for_status()
            v = r.json().get("value")
            return float(v) if v is not None and float(v) > -1000 else None
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None


def grid_centers(sites):
    """Lat/lon of the nearest NBM grid point for each site (opens one small message)."""
    now = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None).floor("h")
    for back in range(0, 12):
        cycle = now - pd.Timedelta(hours=back)
        try:
            H = herbie_for(cycle, 1)
            ds = H.xarray(r":TMP:2 m above ground:1 hour fcst:$", remove_grib=False)
            ds = ds[0] if isinstance(ds, list) else ds
            break
        except Exception:
            continue
    else:
        sys.exit("could not open an NBM message to find the grid points")
    grid = Grid(sites)
    grid.sample(ds)
    la, lo = ds["latitude"].values, ds["longitude"].values
    out = []
    for i in grid.idx:
        lon = float(lo[i])
        out.append((float(la[i]), lon - 360 if lon > 180 else lon))
    return out


def main():
    cfg = yaml.safe_load(SITES_FILE.read_text(encoding="utf-8"))
    sites, floor = cfg["sites"], cfg.get("forecast_floor_ft")
    centers = grid_centers(sites)
    result = {"generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",
              "source": "USGS 3DEP via National Map EPQS", "sites": {}}
    for s, (clat, clon) in zip(sites, centers):
        site_dem = dem_ft(s["lat"], s["lon"])
        samples = []
        for dy in CELL_OFFSETS_KM:
            for dx in CELL_OFFSETS_KM:
                lat = clat + dy / 111.0
                lon = clon + dx / (111.0 * math.cos(math.radians(clat)))
                v = dem_ft(lat, lon)
                if v is not None:
                    samples.append(v)
        cell = round(sum(samples) / len(samples)) if len(samples) >= 20 else None
        own = s.get("elevation_ft") if s.get("elevation_ft") is not None else site_dem
        own_source = "sites.yml override" if s.get("elevation_ft") is not None else "DEM at lat/lon"
        if own is not None and floor is not None and own < floor:
            site_ft, source = floor, f"raised to {floor} ft floor (own elevation {round(own)} ft)"
        else:
            site_ft, source = own, own_source
        entry = {
            "site_ft": None if site_ft is None else round(site_ft),
            "site_source": source,
            "site_dem_ft": None if site_dem is None else round(site_dem),
            "nbm_cell_ft": cell,
            "cell_min_ft": round(min(samples)) if samples else None,
            "cell_max_ft": round(max(samples)) if samples else None,
            "cell_samples": len(samples),
            "grid_lat": round(clat, 4), "grid_lon": round(clon, 4),
        }
        delta = None if entry["site_ft"] is None or cell is None else entry["site_ft"] - cell
        entry["site_minus_cell_ft"] = delta
        result["sites"][s["name"]] = entry
        print(f"{s['name']:16s} forecast at {entry['site_ft']} ft ({entry['site_source']}), cell mean {cell} ft "
              f"[{entry['cell_min_ft']}-{entry['cell_max_ft']}], site - cell = {delta} ft")
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
