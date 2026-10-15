"""Terrain shading and terrain-view factors for each corn-model class (PLAN.md, "Terrain-reflected shortwave").

    python scripts/corn_terrain_shading.py --box cascades            # writes data/corn/class_terrain_cascades.csv
    python scripts/corn_terrain_shading.py --box olympics --stride 2

For every STRIDE-th cell of the 30 m DEM above the cutoff (default 4000 ft) and under 45 degrees, it finds the horizon elevation
angle in 16 compass directions (searching out to MAX_KM over the DEM), then for a surface of that cell's own slope and aspect:
  * svf_flat   sky-view factor of a horizontal surface, mean over azimuth of cos^2(horizon);
  * vd         the share of the sky hemisphere seen by the tilted surface (cosine weighted, 0 to 1; unobstructed it equals (1+cos slope)/2);
  * ct         terrain configuration factor = (1 + cos slope)/2 - vd, the cosine-weighted share of the view that is terrain
               (Dozier and Frew 1990), which is what multiplies the light the surrounding terrain reflects;
  * horizon    the mean horizon angle (degrees) in each of the 16 azimuths (0 = north, 22.5 steps clockwise).
Cells are grouped by the same class id as scripts/corn_class_raster.py (500 ft band x flat or slope bin x aspect octant) and
averaged. One table per box, one row per class, is small enough to commit.
Limits: nearest-neighbor sampling of the DEM along each ray, no Earth curvature (about 0.09 degree at 20 km), terrain beyond the
box edge is not seen (cells within MAX_KM of an edge see a truncated horizon; the box edges are mostly low ground or border), the
class mean of the horizon angles is a rough stand-in for a class whose cells vary, and horizons are not weighted by the cell's own
shading (a deep valley class has a high horizon, a ridge class a low one, which is the intent).
"""
import argparse
import math
import time
from pathlib import Path

import numba as nb
import numpy as np
import pandas as pd

import corn_class_raster as cc

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "corn"
N_AZ_H = 16
MAX_KM = 20.0
N_ELEV = 12
DY_M = 110574.0 / cc.PER
DX_M0 = 111320.0 / cc.PER


def distances():
    d = list(np.arange(30, 600, 30)) + list(np.arange(600, 3000, 100)) + list(np.arange(3000, 10000, 300)) + list(np.arange(10000, MAX_KM * 1000 + 1, 1000))
    return np.array(d, dtype=np.float64)


@nb.njit(parallel=True, fastmath=True)
def kernel(dem, rows, cols, north, dists, nodata):
    n = len(rows)
    hz = np.empty((n, N_AZ_H), dtype=np.float32)
    vflat = np.empty(n, dtype=np.float32)
    vd = np.empty(n, dtype=np.float32)
    ct = np.empty(n, dtype=np.float32)
    slope_o = np.empty(n, dtype=np.float32)
    sin_az = np.empty(N_AZ_H)
    cos_az = np.empty(N_AZ_H)
    for k in range(N_AZ_H):
        sin_az[k] = math.sin(2 * math.pi * k / N_AZ_H)
        cos_az[k] = math.cos(2 * math.pi * k / N_AZ_H)
    nr, nc = dem.shape
    for i in nb.prange(n):
        r, c = rows[i], cols[i]
        lat = north - (r + 0.5) / 3600.0
        dx = DX_M0 * math.cos(math.radians(lat))
        z0 = float(dem[r, c])
        # slope and aspect from central differences, as in corn_class_raster.classify
        zn, zs = float(dem[max(r - 1, 0), c]), float(dem[min(r + 1, nr - 1), c])
        ze, zw = float(dem[r, min(c + 1, nc - 1)]), float(dem[r, max(c - 1, 0)])
        gy = (zs - zn) / 2.0 / DY_M            # rows increase southward: dz/drow
        gx = (ze - zw) / 2.0 / dx
        slope = math.atan(math.hypot(gx, gy))
        asp = math.atan2(-gx, gy)              # direction the slope faces, radians from north, clockwise
        slope_o[i] = math.degrees(slope)
        for k in range(N_AZ_H):
            best = -math.pi / 2
            for j in range(len(dists)):
                d = dists[j]
                rr = r - int(round(d * cos_az[k] / DY_M))
                cc_ = c + int(round(d * sin_az[k] / dx))
                if rr < 0 or rr >= nr or cc_ < 0 or cc_ >= nc:
                    break
                zz = dem[rr, cc_]
                if zz == nodata:
                    continue
                a = math.atan((float(zz) - z0) / d)
                if a > best:
                    best = a
            hz[i, k] = math.degrees(best)
        # sky-view factors
        sf = 0.0
        sv = 0.0
        nx, ny, nz = math.sin(slope) * math.sin(asp), math.sin(slope) * math.cos(asp), math.cos(slope)
        dphi = 2 * math.pi / N_AZ_H
        for k in range(N_AZ_H):
            h = math.radians(hz[i, k])
            sf += math.cos(max(h, 0.0)) ** 2
            if h >= math.pi / 2:
                continue
            de = (math.pi / 2 - h) / N_ELEV
            for m in range(N_ELEV):
                e = h + (m + 0.5) * de
                cth = nx * math.cos(e) * sin_az[k] + ny * math.cos(e) * cos_az[k] + nz * math.sin(e)
                if cth > 0:
                    sv += cth * math.cos(e) * de * dphi
        vflat[i] = sf / N_AZ_H
        vd[i] = sv / math.pi
        ct[i] = (1 + math.cos(slope)) / 2 - sv / math.pi
    return hz, vflat, vd, ct, slope_o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", choices=list(cc.BOXES), default="cascades")
    ap.add_argument("--min-ft", type=int, default=4000)
    ap.add_argument("--stride", type=int, default=4, help="evaluate every STRIDE-th cell in each direction")
    a = ap.parse_args()
    dem, (west, north) = cc.get_dem(a.box)
    cf = cc.CACHE / f"classes_{a.box}_{a.min_ft}.npy"
    if cf.exists():
        cls = np.load(cf)
    else:
        cls = cc.classify(dem, north, a.min_ft)
        np.save(cf, cls)
    print("dem", dem.shape, "forecastable cells", int((cls > 0).sum()))
    rr, ccol = np.meshgrid(np.arange(a.stride // 2, dem.shape[0], a.stride), np.arange(a.stride // 2, dem.shape[1], a.stride), indexing="ij")
    rr, ccol = rr.ravel(), ccol.ravel()
    keep = cls[rr, ccol] > 0
    rows, cols = rr[keep].astype(np.int64), ccol[keep].astype(np.int64)
    print("sample cells", len(rows))
    t0 = time.time()
    hz, vflat, vd, ct, slope = kernel(dem, rows, cols, north, distances(), np.int16(-32768))
    print(f"kernel {time.time() - t0:.0f} s")
    cid = cls[rows, cols].astype(np.int64)
    per_band = 1 + cc.N_SLOPE_BINS * cc.N_AZ
    n = int(cid.max()) + 1
    cnt = np.bincount(cid, minlength=n)

    def mean(x):
        return np.bincount(cid, weights=x, minlength=n) / np.maximum(cnt, 1)

    tab = pd.DataFrame({"class": np.arange(n), "cells_sampled": cnt, "svf_flat": mean(vflat), "vd": mean(vd), "ct": mean(ct)})
    for k in range(N_AZ_H):
        tab[f"h{int(360 * k / N_AZ_H):03d}"] = mean(hz[:, k])
    tab = tab[tab["class"] > 0]
    tab = tab[tab.cells_sampled > 0].copy()
    k0 = tab["class"] - 1
    tab.insert(1, "band", k0 // per_band)
    within = k0 % per_band
    tab.insert(2, "slope_bin", np.where(within == 0, 0, 1 + (within - 1) // cc.N_AZ))
    tab.insert(3, "octant", np.where(within == 0, -1, (within - 1) % cc.N_AZ))
    tab.insert(4, "elev_ft_mid", a.min_ft + tab.band * cc.BAND_FT + cc.BAND_FT // 2)
    f = OUT / f"class_terrain_{a.box}.csv"
    tab.to_csv(f, index=False, float_format="%.3f")
    print(f"wrote {f}: {len(tab)} classes, {f.stat().st_size / 1e3:.0f} KB")
    print(f"mean over cells: svf_flat {vflat.mean():.2f}  vd {vd.mean():.2f}  ct {ct.mean():.3f}  slope {slope.mean():.0f} deg")
    print("by slope bin: (0 flat, 1 10-25, 2 25-35, 3 35-45)")
    t = tab.assign(w=tab.cells_sampled)
    for sb, g in t.groupby("slope_bin"):
        print(f"  {sb}: svf_flat {np.average(g.svf_flat, weights=g.w):.2f}  vd {np.average(g.vd, weights=g.w):.2f}  ct {np.average(g.ct, weights=g.w):.3f}")
    print("by aspect octant (0 N, 1 NE, ... 7 NW), non-flat classes: vd and ct")
    for oc, g in t[t.octant >= 0].groupby("octant"):
        print(f"  {oc}: vd {np.average(g.vd, weights=g.w):.2f}  ct {np.average(g.ct, weights=g.w):.3f}")


if __name__ == "__main__":
    main()
