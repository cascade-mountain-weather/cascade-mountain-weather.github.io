"""Scatter of storm-run SLR against 850 and 700 hPa temperature, colored by station elevation.

    python scripts/slr_scatter_hourly.py                  # Quillayute, writes data/slr/slr_scatter_850_700.png
    python scripts/slr_scatter_hourly.py --site SLE

Same storm runs and screens as scripts/slr_plot_hourly.py (half an inch of SWE or more). Each dot is one storm; the line is the median
of 2 C bins (at least 15 storms). Depth reads to whole inches, so SLR piles up on a few values; the dots are nudged vertically by up to
0.25 for legibility only (the line, r and slope use the true values).
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slr_plot_hourly import BANDS, build  # noqa: E402
from slr_analysis import SITES, SLR  # noqa: E402


COLORS = ["#74c0e8", "#2f6fc0", "#0a1f4d"]   # light to dark with elevation, strong enough to read as dots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="UIL", choices=SITES)
    ap.add_argument("--min-swe", type=float, default=0.5)
    ap.add_argument("--max-temp", type=float, default=34.0)
    ap.add_argument("--min-slr", type=float, default=2.0)
    ap.add_argument("--max-slr", type=float, default=25.0)
    a = ap.parse_args()
    d = build(a)
    rng = np.random.default_rng(0)
    name = {"UIL": "Quillayute", "OTX": "Spokane", "SLE": "Salem"}[a.site]

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#8a8f98"})
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8), sharey=True)
    for ax, lev in zip(axes, (850, 700)):
        col = f"{a.site}_{lev}"
        x = d.dropna(subset=[col, "band"])
        for band, color in zip(BANDS, COLORS):
            s = x[x["band"] == band]
            ax.scatter(s[col], s["slr"] + rng.uniform(-0.25, 0.25, len(s)), s=12, color=color, alpha=0.55, linewidths=0,
                       label=f"{band} ({len(s):,})")
        edges = np.arange(np.floor(x[col].min() / 2) * 2, np.ceil(x[col].max() / 2) * 2 + 2, 2)
        mid, med = [], []
        for lo, hi in zip(edges[:-1], edges[1:]):
            g = x[(x[col] > lo) & (x[col] <= hi)]
            if len(g) >= 15:
                mid.append((lo + hi) / 2)
                med.append(g["slr"].median())
        ax.plot(mid, med, color="#d94801", linewidth=2.6, marker="o", markersize=6, markeredgecolor="white", markeredgewidth=1.3, label="median of 2 C bins", zorder=5)
        r = x[col].corr(x["slr"])
        rs = x[col].corr(x["slr"], method="spearman")
        slope = np.polyfit(x[col], x["slr"], 1)[0]
        ax.set_title(f"{name} {lev} hPa\nn = {len(x):,}   Pearson {r:.2f}   Spearman {rs:.2f}   slope {slope:.2f} per C", loc="left", fontsize=11, fontweight="bold")
        ax.set_xlabel(f"{name} {lev} hPa temperature, mean of the launches during the storm (C)")
        ax.set_ylim(0, a.max_slr)
        ax.grid(color="#e3e6ea", linewidth=0.7)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("snow-to-liquid ratio (depth / SWE)")
    axes[0].legend(frameon=False, fontsize=9, loc="upper right", markerscale=2.2)
    fig.suptitle(f"Storm SLR at 28 Cascade and Olympic SNOTEL stations, 2005-2026 (SWE gain {a.min_swe:g} in or more); color = station elevation",
                 x=0.01, ha="left", fontsize=12.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = SLR / f"slr_scatter_850_700_swe{a.min_swe:g}.png"
    fig.savefig(out, dpi=150, facecolor="white")
    print("wrote", out)


if __name__ == "__main__":
    main()
