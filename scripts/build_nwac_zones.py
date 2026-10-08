"""Build assets/data/nwac_zones.geojson: the NWAC forecast-zone boundaries the live conditions map and the
station maps draw to group nearby stations.

Source: the public avalanche.org map-layer feed for the Northwest Avalanche Center (NWAC). Only each zone's
NAME, ID and OUTLINE are kept. The feed also carries danger ratings and travel advice; those are deliberately
dropped. This site shows the zone boundaries for orientation only; it does not republish or imitate an NWAC
forecast, and every place the outlines appear says so and points to nwac.us.

Polygons are simplified (about 300 m) and rounded to keep the file small. Static: re-run only if NWAC redraws
its zones (the zone-boundary map layer rarely changes). Run from the repo root:

    python scripts/build_nwac_zones.py
"""
import json
import math
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "assets" / "data" / "nwac_zones.geojson"
URL = "https://api.avalanche.org/v2/public/products/map-layer/NWAC"
TOL = 0.003  # degrees, roughly 300 m


def dp(points, tol):
    """Douglas-Peucker line simplification (iterative)."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = points[a], points[b]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy) or 1e-12
        best, idx = 0.0, None
        for i in range(a + 1, b):
            d = abs(dy * (points[i][0] - x1) - dx * (points[i][1] - y1)) / norm
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(points, keep) if k]


def ring(coords):
    pts = [(round(c[0], 3), round(c[1], 3)) for c in coords]
    out = dp(pts[:-1], TOL) if pts[0] == pts[-1] else dp(pts, TOL)
    return [list(p) for p in out] + [list(out[0])] if len(out) >= 3 else None


def simplify(geom):
    if geom["type"] == "Polygon":
        rings = [r for r in (ring(r) for r in geom["coordinates"]) if r]
        return {"type": "Polygon", "coordinates": rings} if rings else None
    polys = []
    for poly in geom["coordinates"]:
        rings = [r for r in (ring(r) for r in poly) if r]
        if rings:
            polys.append(rings)
    return {"type": "MultiPolygon", "coordinates": polys} if polys else None


def main():
    resp = requests.get(URL, timeout=60, headers={"User-Agent": "cascade-mountain-weather (zone outlines only)"})
    resp.raise_for_status()
    feats = []
    for f in resp.json().get("features", []):
        p = f.get("properties", {})
        geom = f.get("geometry")
        if not geom or geom.get("type") not in ("Polygon", "MultiPolygon") or not p.get("name"):
            continue
        if p.get("state") and p["state"] != "WA":     # the feed also covers Mt Hood (OR); the site covers Washington
            continue
        g = simplify(geom)
        if g:
            feats.append({"type": "Feature", "properties": {"zone": p["name"], "id": p.get("id")}, "geometry": g})
    if not feats:
        raise SystemExit("no zone polygons found in the feed")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT}: {len(feats)} zones ({', '.join(f['properties']['zone'] for f in feats)}), {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
