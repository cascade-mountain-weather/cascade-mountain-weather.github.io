"""Plot SLR of storm runs against 700 hPa temperature, one panel per station-elevation band.

    python scripts/slr_plot_hourly.py                      # Quillayute 700 hPa, writes data/slr/slr_storms_by_elevation.png
    python scripts/slr_plot_hourly.py --site OTX --level 850 --min-swe 0.75

Uses the storm runs from scripts/slr_analysis_hourly.py (same screens). Boxes are the 25th to 75th percentile with the median bar,
whiskers the 10th to 90th, bins of 2 C with at least --min-n storms. The fourth panel puts the three band medians on one axis,
with the ratio of total depth to total SWE (dashed) beside them.
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import slr_analysis_hourly as H  # noqa: E402
from slr_analysis import LEVELS, SITES, SLR, load_soundings  # noqa: E402

BANDS = ["3,000-4,000 ft", "4,000-5,000 ft", "over 5,000 ft"]
COLORS = ["#9ecae1", "#4292c6", "#08306b"]   # one hue, light to dark: higher station, darker


def build(a):
    series = H.station_series()
    snd = load_soundings()
    idx = {(s, l): snd[snd["station"] == s].drop_duplicates("valid").set_index("valid")[f"t{l}_c"] for s in SITES for l in LEVELS}
    w = pd.concat([H.windows(k, df, idx) for k, df in series.items()], ignore_index=True)
    runs = H.storm_runs(w, a)
    d = H.screen(runs, a, min_swe=a.min_swe, verbose=False)
    meta = pd.read_csv(SLR / "snotel_stations.csv").rename(columns={"triplet": "station"}).set_index("station")[["name", "elevation_ft"]]
    d = d.join(meta, on="station")
    d["band"] = pd.cut(d["elevation_ft"], [0, 4000, 5000, 20000], labels=BANDS)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="UIL", choices=SITES)
    ap.add_argument("--level", type=int, default=700, choices=LEVELS)
    ap.add_argument("--min-swe", type=float, default=0.5, help="smallest total SWE of a storm run, inches")
    ap.add_argument("--min-n", type=int, default=15, help="fewest storms in a bin to draw it")
    ap.add_argument("--max-temp", type=float, default=34.0)
    ap.add_argument("--min-slr", type=float, default=2.0)
    ap.add_argument("--max-slr", type=float, default=25.0)
    a = ap.parse_args()

    d = build(a)
    col = f"{a.site}_{a.level}"
    d = d.dropna(subset=[col, "band"])
    edges = np.arange(np.floor(d[col].min() / 2) * 2, np.ceil(d[col].max() / 2) * 2 + 2, 2)
    d["bin"] = pd.cut(d[col], edges)
    mids = {iv: iv.mid for iv in d["bin"].cat.categories}

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#8a8f98",
                         "axes.labelcolor": "#2b2f36", "xtick.color": "#4a5058", "ytick.color": "#4a5058"})
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5), sharex=True)
    xlim = (edges[0] - 1, edges[-1] + 1)
    summary = {}
    for ax, band, color in zip(axes.flat[:3], BANDS, COLORS):
        sub = d[d["band"] == band]
        stats, boxes = [], []
        for iv, g in sub.groupby("bin", observed=True):
            if len(g) < a.min_n:
                continue
            s = g["slr"]
            boxes.append({"med": s.median(), "q1": s.quantile(.25), "q3": s.quantile(.75), "whislo": s.quantile(.10), "whishi": s.quantile(.90),
                          "fliers": []})
            stats.append((mids[iv], len(g), g["depth"].sum() / g["swe"].sum(), s.median(), s.quantile(.25), s.quantile(.75)))
        pos = [t[0] for t in stats]
        ax.bxp(boxes, positions=pos, widths=1.3, showfliers=False, patch_artist=True, manage_ticks=False,
               boxprops={"facecolor": color, "edgecolor": "#2b2f36", "linewidth": 0.8, "alpha": 0.85},
               medianprops={"color": "#111", "linewidth": 1.8}, whiskerprops={"color": "#6b717a"}, capprops={"color": "#6b717a"})
        for x, n, *_ in stats:
            ax.text(x, 0.4, f"n={n}", ha="center", va="bottom", fontsize=7.5, color="#4a5058")
        ax.set_title(f"{band}: {len(sub):,} storms, {sub['station'].nunique()} stations", loc="left", fontsize=11, fontweight="bold")
        ax.set_xlim(*xlim)
        ax.set_ylim(0, a.max_slr)
        ax.grid(axis="y", color="#e3e6ea", linewidth=0.7)
        ax.set_axisbelow(True)
        ax.set_xticks(np.arange(edges[0], edges[-1] + 1, 4))
        summary[band] = stats

    ax = axes[1, 1]
    for band, color in zip(BANDS, COLORS):
        st = summary[band]
        if not st:
            continue
        x = np.array([t[0] for t in st])
        ax.fill_between(x, [t[4] for t in st], [t[5] for t in st], color=color, alpha=0.18, linewidth=0)
        ax.plot(x, [t[3] for t in st], color=color, linewidth=2.2, marker="o", markersize=5, markeredgecolor="white", markeredgewidth=1.2, label=f"{band} median")
        ax.plot(x, [t[2] for t in st], color=color, linewidth=1.3, linestyle="--")
    ax.plot([], [], color="#4a5058", linestyle="--", linewidth=1.3, label="total depth / total SWE")
    ax.set_title("Medians by elevation (band = 25th-75th percentile)", loc="left", fontsize=11, fontweight="bold")
    ax.set_xlim(*xlim)
    ax.set_ylim(0, a.max_slr * 0.7)
    ax.grid(axis="y", color="#e3e6ea", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")

    name = {"UIL": "Quillayute", "OTX": "Spokane", "SLE": "Salem"}[a.site]
    for ax in axes[1]:
        ax.set_xlabel(f"{name} {a.level} hPa temperature, mean of the launches during the storm (C)")
    for ax in axes[:, 0]:
        ax.set_ylabel("snow-to-liquid ratio (depth / SWE)")
    fig.suptitle(f"Snow-to-liquid ratio of storms at 28 Cascade and Olympic SNOTEL stations, 2005-2026 (SWE gain {a.min_swe:g} in or more)",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = SLR / f"slr_storms_by_elevation_swe{a.min_swe:g}.png"
    fig.savefig(out, dpi=150, facecolor="white")
    print("wrote", out)
    for band in BANDS:
        print(band)
        for t in summary[band]:
            print(f"  {t[0]:6.1f} C  n={t[1]:4d}  median {t[3]:5.1f}  depth/SWE {t[2]:5.1f}")


if __name__ == "__main__":
    main()
