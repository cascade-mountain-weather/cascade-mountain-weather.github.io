"""One-off measurement for the corn model: land area (and cell counts) above 4000/5000/6000 ft in the WA Cascades and Olympics.

    python scripts/corn_terrain_area.py

Reads USGS 3DEP 1/3 arc-second (about 10 m, bare-earth, meters) 1-degree tiles straight from the public S3 bucket, using the
tiles' built-in overviews so only a coarse (~30 m) version is downloaded. Prints, per cutoff and region, the area in km2 and
the cell count at 30 m and at the native 10 m. Needs rasterio and numpy. Writes nothing; PLAN.md records the result.
"""
import math

import numpy as np
import rasterio
from rasterio.env import Env
from rasterio.windows import from_bounds

BASE = "/vsicurl/https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/{t}/USGS_13_{t}.tif"
CUTOFFS_FT = (4000, 5000, 6000)
M_PER_FT = 0.3048
DECIM = 3  # 10 m -> ~30 m

# name -> (west, south, east, north), degrees
REGIONS = {
    "Cascades (WA, 45.6-49N)": (-122.7, 45.6, -119.8, 49.0),
    "Olympics": (-124.8, 47.4, -122.9, 48.3),
}


def tiles_for(w, s, e, n):
    for lat in range(math.floor(s) + 1, math.ceil(n) + 1):  # tile name = NW corner
        for lon in range(math.floor(-e) + 1, math.ceil(-w) + 1):  # and west-edge longitude magnitude
            yield lat, lon


def main():
    totals = {r: {c: [0.0, 0] for c in CUTOFFS_FT} for r in REGIONS}
    with Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="3"):
        for region, (w, s, e, n) in REGIONS.items():
            for lat, lon in tiles_for(w, s, e, n):
                name = f"n{lat}w{lon:03d}"
                try:
                    d = rasterio.open(BASE.format(t=name))
                except Exception as ex:
                    print(f"  skip {name}: {str(ex)[:60]}")
                    continue
                with d:
                    # clip the tile to the region box
                    bw, bs = max(w, d.bounds.left), max(s, d.bounds.bottom)
                    be, bn = min(e, d.bounds.right), min(n, d.bounds.top)
                    if bw >= be or bs >= bn:
                        continue
                    win = from_bounds(bw, bs, be, bn, d.transform)
                    h, wd = max(1, int(win.height / DECIM)), max(1, int(win.width / DECIM))
                    z = d.read(1, window=win, out_shape=(h, wd), masked=True)
                    lats = np.linspace(bn, bs, h, endpoint=False) - (bn - bs) / h / 2
                    # cell area in km2 for each row (cell is dlat x dlon degrees)
                    dlat, dlon = (bn - bs) / h, (be - bw) / wd
                    row_km2 = (dlat * 110.574) * (dlon * 111.320 * np.cos(np.radians(lats)))
                    for c in CUTOFFS_FT:
                        m = (z.filled(-9999) >= c * M_PER_FT)
                        totals[region][c][0] += float((m.sum(axis=1) * row_km2).sum())
                        totals[region][c][1] += int(m.sum())
                print("done", region, name)
    print()
    for region, t in totals.items():
        print(region)
        for c, (km2, n30) in t.items():
            print(f"  >= {c} ft: {km2:9.0f} km2   ~{n30:>11,} cells at 30 m   ~{km2 / 1e-4:>14,.0f} cells at 10 m")


if __name__ == "__main__":
    main()
