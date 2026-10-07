"""One-time script: DEM elevations for the ski tool's access points and forecast points (run by hand, commit the result).

    python scripts/ski_dem.py

Reads data/ski/destinations.yml, writes data/ski/elevations.json: for each zone the elevation of every access point,
the winter access point and the forecast point, in feet. Source: USGS 3DEP (National Map Elevation Point Query Service,
about 10 m, US only), the same service scripts/site_elevations.py uses. Points outside the US (Whistler) are left null;
fill them by hand in `elevation_override_ft` in destinations.yml. `top_ft` and vert stay hand values until a terrain
(track cluster) pass exists, see PLAN.md.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

import requests

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "ski" / "destinations.yml"
OUT = ROOT / "data" / "ski" / "elevations.json"


EPQS = "https://epqs.nationalmap.gov/v1/json"


def dem_ft(lat, lon, tries=3):
    """Elevation in feet from the USGS point query service (same call as scripts/site_elevations.py, which needs Herbie)."""
    for _ in range(tries):
        try:
            r = requests.get(EPQS, params={"x": lon, "y": lat, "wkid": 4326, "units": "Feet", "includeDate": "false"}, timeout=30)
            r.raise_for_status()
            v = r.json().get("value")
            return float(v) if v is not None and float(v) > -1000 else None
        except Exception:
            time.sleep(2)
    return None


def main():
    cfg = yaml.safe_load(SRC.read_text(encoding="utf-8"))
    out = {}
    for z in cfg["zones"]:
        pts = {"forecast_point": z["forecast_point"], "winter_access": z["winter_access"]}
        pts.update({"ap:" + a["id"]: a for a in z.get("access_points", [])})
        e = {}
        for k, p in pts.items():
            v = z.get("elevation_override_ft", {}).get(k) if isinstance(z.get("elevation_override_ft"), dict) else None
            if v is None:
                v = dem_ft(p["lat"], p["lon"])
                time.sleep(0.2)
            e[k] = round(v) if v is not None else None
        out[z["id"]] = e
        print(f"{z['id']:15s}", e)
    OUT.write_text(json.dumps({"generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",
                               "source": "USGS 3DEP point query (ft)", "zones": out}, indent=1), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
