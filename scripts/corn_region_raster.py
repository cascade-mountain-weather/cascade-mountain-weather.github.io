"""Region raster for the corn model: which forcing region each cell of the class raster belongs to.

    python scripts/corn_region_raster.py --out PATH.png

Same grid as scripts/corn_class_raster.py (WA Cascades box, 1/3600 degree cells). Each cell gets the 1-based index (order in
data/corn/regions.yml) of the NEAREST region forecast point by great-circle distance; 8-bit PNG. Nearest-point is the first
rule, to be revisited (crest and east-west contrasts are not considered). Regions outside the box (Hurricane Ridge, in the
Olympics) only claim cells inside the box that are nearer to them than to any other point.
"""
import argparse
import os
from pathlib import Path

import numpy as np
import rasterio
import yaml

import corn_class_raster as cc

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    regs = yaml.safe_load((ROOT / "data" / "corn" / "regions.yml").read_text(encoding="utf-8"))["regions"]
    plat = np.radians([r["lat"] for r in regs])
    plon = np.radians([r["lon"] for r in regs])
    w, s, e, n = cc.BOX
    rows, cols = int(round((n - s) * cc.PER)), int(round((e - w) * cc.PER))
    lon = np.radians(w + (np.arange(cols) + 0.5) / cc.PER)
    out = np.zeros((rows, cols), dtype=np.uint8)
    for r0 in range(0, rows, 1000):
        r1 = min(r0 + 1000, rows)
        lat = np.radians(n - (np.arange(r0, r1) + 0.5) / cc.PER)[:, None]
        best = np.full((r1 - r0, cols), np.inf, dtype=np.float32)
        for k in range(len(regs)):
            # haversine (unit sphere), monotone in distance
            h = np.sin((plat[k] - lat) / 2) ** 2 + np.cos(lat) * np.cos(plat[k]) * np.sin((plon[k] - lon[None, :]) / 2) ** 2
            h = h.astype(np.float32)
            closer = h < best
            best = np.where(closer, h, best)
            out[r0:r1][closer] = k + 1
    counts = np.bincount(out.ravel(), minlength=len(regs) + 1)
    for k, r in enumerate(regs):
        print(f"{k + 1:2d} {r['id']:16s} {100 * counts[k + 1] / out.size:5.1f}% of the box")
    prof = dict(driver="PNG", height=rows, width=cols, count=1, dtype="uint8", ZLEVEL=9)
    with rasterio.open(args.out, "w", **prof) as dst:
        dst.write(out, 1)
    print(f"wrote {args.out}: {os.path.getsize(args.out) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
