"""Test build of the corn model's terrain-class raster, to measure the hosted file size (PLAN.md, "Corn model: design").

    python scripts/corn_class_raster.py --min-ft 5000 --out PATH.png

Reads the WA Cascades from USGS 3DEP 1/3 arc-second tiles (public S3, through the ~30 m overviews, 1/3600 degree cells),
computes slope and aspect, and writes one 16-bit PNG whose value is the terrain class id (0 = below the cutoff or no data).
Class = elevation band x (flat | slope bin x aspect octant). The band width, slope bins and flat limit are PLACEHOLDERS to
tune (not sourced); this script exists to size the file, not to fix the classes.
"""
import argparse
import math

import numpy as np
import rasterio
from rasterio.env import Env
from rasterio.windows import from_bounds

BASE = "/vsicurl/https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/{t}/USGS_13_{t}.tif"
M_PER_FT = 0.3048
BOX = (-122.7, 45.6, -119.8, 49.0)  # west, south, east, north (same Cascades box as corn_terrain_area.py)
PER = 3600  # cells per degree

BAND_FT = 500
FLAT_DEG = 10
SLOPE_EDGES = (FLAT_DEG, 25, 35, 45)  # bins: <10 flat, 10-25, 25-35, 35-45, >=45
N_SLOPE_BINS = len(SLOPE_EDGES)  # non-flat bins
N_AZ = 8


def load_dem():
    """Int16 meters on a 1/3600 degree grid covering BOX (snapped outward to whole cells)."""
    w, s, e, n = BOX
    w0, e0, s0, n0 = math.floor(w), math.ceil(e), math.floor(s), math.ceil(n)
    dem = np.full(((n0 - s0) * PER, (e0 - w0) * PER), -32768, dtype=np.int16)
    with Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="3"):
        for lat in range(s0 + 1, n0 + 1):
            for lon in range(-e0 + 1, -w0 + 1):
                name = f"n{lat}w{lon:03d}"
                try:
                    d = rasterio.open(BASE.format(t=name))
                except Exception as ex:
                    print("skip", name, str(ex)[:50])
                    continue
                with d:
                    win = from_bounds(-lon, lat - 1, -lon + 1, lat, d.transform)
                    z = d.read(1, window=win, out_shape=(PER, PER), masked=True)
                r0, c0 = (n0 - lat) * PER, (lon * -1 - w0) * PER
                dem[r0:r0 + PER, c0:c0 + PER] = np.where(z.mask, -32768, np.round(z.filled(0))).astype(np.int16)
                print("read", name)
    # crop to BOX
    r0, r1 = int(round((n0 - n) * PER)), int(round((n0 - s) * PER))
    c0, c1 = int(round((w - w0) * PER)), int(round((e - w0) * PER))
    return dem[r0:r1, c0:c1], (w0 + c0 / PER, n0 - r0 / PER)


def classify(dem, north, min_ft, chunk=1500):
    """Class id per cell, in row chunks (1-row overlap for the gradient)."""
    out = np.zeros(dem.shape, dtype=np.uint16)
    rows = dem.shape[0]
    min_m = min_ft * M_PER_FT
    for r in range(0, rows, chunk):
        a, b = max(r - 1, 0), min(r + chunk + 1, rows)
        z = dem[a:b].astype(np.float32)
        z[z < -1000] = np.nan
        lat = north - (np.arange(a, b) + 0.5) / PER
        dy = (1 / PER) * 110574.0
        dx = (1 / PER) * 111320.0 * np.cos(np.radians(lat))[:, None]
        dzdy, dzdx = np.gradient(z)          # per cell, rows increase southward, cols eastward
        gy, gx = dzdy / dy, dzdx / dx        # dz/dnorthward = -gy
        slope = np.degrees(np.arctan(np.hypot(gx, gy)))
        # aspect = compass direction the slope faces (downhill): downhill vector = (-gx east, +gy north)
        asp = (np.degrees(np.arctan2(-gx, gy)) + 360) % 360
        sl = slope[r - a:r - a + min(chunk, rows - r)]
        asp = asp[r - a:r - a + sl.shape[0]]
        zz = z[r - a:r - a + sl.shape[0]]
        ok = np.isfinite(zz) & (zz >= min_m)
        band = np.clip(((np.nan_to_num(zz) / M_PER_FT - min_ft) // BAND_FT).astype(np.int32), 0, None)
        sbin = np.digitize(np.nan_to_num(sl), SLOPE_EDGES)  # 0 flat, 1..3
        octant = (((asp + 22.5) % 360) // 45).astype(np.int32)
        per_band = 1 + N_SLOPE_BINS * N_AZ
        within = np.where(sbin == 0, 0, 1 + (sbin - 1) * N_AZ + octant)
        cls = 1 + band * per_band + within
        out[r:r + sl.shape[0]] = np.where(ok, cls, 0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-ft", type=int, default=5000)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    dem, (west, north) = load_dem()
    print("dem", dem.shape)
    cls = classify(dem, north, args.min_ft)
    print("classes used:", len(np.unique(cls)) - 1, "cells:", int((cls > 0).sum()), "max id:", int(cls.max()))
    prof = dict(driver="PNG", height=cls.shape[0], width=cls.shape[1], count=1, dtype="uint16", ZLEVEL=9)
    with rasterio.open(args.out, "w", **prof) as dst:
        dst.write(cls, 1)
    import os
    print(f"wrote {args.out}: {os.path.getsize(args.out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
