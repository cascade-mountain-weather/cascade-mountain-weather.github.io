"""Small basemap for the Tea Leaves zone map: Washington, Oregon, British Columbia (and the edges of Idaho) clipped to the box the
map shows, from Natural Earth 50 m state and province polygons through cartopy (downloaded and cached on first use).

    python scripts/build_pnw_basemap.py            # writes assets/data/pnw_basemap.json (static; rerun only to change the box)
"""
import json
import sys
from pathlib import Path

import cartopy.io.shapereader as shp
from shapely.geometry import box

ROOT = Path(__file__).resolve().parent.parent
BBOX = (-125.6, 45.3, -119.2, 50.0)          # lon min, lat min, lon max, lat max
KEEP = {"Washington", "Oregon", "British Columbia", "Idaho", "Montana", "Alberta"}
TOL = 0.004


def rings(geom):
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    out = []
    for p in polys:
        for r in [p.exterior, *p.interiors]:
            c = [[round(x, 3), round(y, 3)] for x, y in r.coords]
            if len(c) >= 4:
                out.append(c)
    return out


def main():
    path = shp.natural_earth(resolution="50m", category="cultural", name="admin_1_states_provinces")
    clip = box(*BBOX)
    states = {}
    for rec in shp.Reader(path).records():
        name = rec.attributes.get("name")
        if name not in KEEP:
            continue
        g = rec.geometry.intersection(clip)
        if g.is_empty:
            continue
        states[name] = rings(g.simplify(TOL))
    out = {"bbox": list(BBOX), "states": states}
    f = ROOT / "assets" / "data" / "pnw_basemap.json"
    f.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print("wrote", f, f.stat().st_size // 1024, "KB;", {k: len(v) for k, v in states.items()})


if __name__ == "__main__":
    sys.exit(main())
