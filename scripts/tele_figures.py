"""Figures for the teleconnection analysis (reads data/teleconnections/results, writes docs/teleconnections/*.png).

    python scripts/tele_figures.py [--lag 6]
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "data" / "teleconnections" / "results"
OUT = ROOT / "docs" / "teleconnections"
TITLE = {"swe": "Snowfall (daily SWE gain), ratio to normal", "tanom": "Temperature anomaly (F)",
         "rain": "Rain (precip not stored as SWE), ratio to normal", "bigsnow": "Big snow days, ratio to normal frequency",
         "precip": "Precipitation, ratio to normal", "bigwet": "Big precip days, ratio to normal frequency"}
CLASS = {"mjo": {1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 0: "weak"},
         "pna": {-2: "strong -PNA\n(coldest 10%)", -1: "-PNA", 0: "neutral", 1: "+PNA", 2: "strong +PNA\n(top 10%)"},
         "enso": {-2: "La Nina\n(ONI<=-1)", -1: "weak La Nina", 0: "neutral", 1: "weak El Nino", 2: "El Nino\n(ONI>=1)"}}


def load():
    c = pd.read_csv(RES / "composites.csv", dtype={"station": str})
    st = pd.read_csv(RES / "stations.csv", dtype={"id": str}).set_index("id")
    return c, st


def order(st):
    return list(st.sort_values("lat", ascending=False).index)           # north to south


def heat(ax, M, rows, cols, metric, rl, cl, sig=None):
    ratio = metric in ("swe", "precip", "rain", "bigsnow", "bigwet")
    lim = np.nanpercentile(np.abs(M - (1 if ratio else 0)), 97) or 0.3
    lim = max(lim, 0.15 if ratio else 0.5)
    norm = TwoSlopeNorm(vcenter=1 if ratio else 0, vmin=(1 - lim) if ratio else -lim, vmax=(1 + lim) if ratio else lim)
    cmap = "BrBG" if metric in ("swe", "precip", "bigsnow", "bigwet") else ("RdYlBu_r" if metric == "tanom" else "PuOr")
    im = ax.imshow(M, aspect="auto", cmap=cmap, norm=norm)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cl, fontsize=8)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(rl, fontsize=6.5)
    if sig is not None:
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                if sig[i, j]:
                    ax.text(j, i, "·", ha="center", va="center", fontsize=11, color="k", fontweight="bold")
    return im


def station_heat(c, st, index, lag, metrics, fname, title):
    cats = list(CLASS[index])
    cats = [k for k in ([1, 2, 3, 4, 5, 6, 7, 8] if index == "mjo" else cats)]
    rows = order(st)
    rl = [f"{st.loc[r, 'name']} ({st.loc[r, 'elev_ft']:,} ft)" for r in rows]
    fig, axs = plt.subplots(1, len(metrics), figsize=(4.2 * len(metrics) + 2, 9.5), sharey=True)
    for ax, m in zip(np.atleast_1d(axs), metrics):
        d = c[(c["index"] == index) & (c["lag"] == lag) & (c["metric"] == m)]
        M = np.full((len(rows), len(cats)), np.nan)
        S = np.zeros_like(M, dtype=bool)
        base = 1 if m != "tanom" else 0
        for i, r in enumerate(rows):
            for j, k in enumerate(cats):
                x = d[(d["station"] == r) & (d["cat"] == k)]
                if len(x):
                    M[i, j] = x["value"].iloc[0]
                    S[i, j] = (x["lo"].iloc[0] > base) or (x["hi"].iloc[0] < base)
        im = heat(ax, M, rows, cats, m, rl, [CLASS[index][k] for k in cats], S)
        ax.set_title(TITLE[m], fontsize=9)
        fig.colorbar(im, ax=ax, fraction=0.05, pad=0.02)
    fig.suptitle(f"{title}  (lag {lag} d; dot = 90% bootstrap interval excludes no-change)", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / fname, dpi=110)
    plt.close(fig)


def lag_region(c, st):
    lags = sorted(c["lag"].unique())
    fig, axs = plt.subplots(2, 3, figsize=(15, 8))
    for ax, m in zip(axs.flat, ["swe", "tanom", "rain", "bigsnow", "precip", "bigwet"]):
        d = c[(c["index"] == "mjo") & (c["metric"] == m) & (c["cat"].between(1, 8))]
        g = d.groupby(["cat", "lag"])["value"].mean().unstack()
        im = heat(ax, g.values, list(g.index), list(g.columns), m, [f"phase {i}" for i in g.index], [str(l) for l in g.columns])
        ax.set_title(TITLE[m], fontsize=9)
        ax.set_xlabel("days after the MJO phase")
        fig.colorbar(im, ax=ax)
    fig.suptitle("MJO phase and Washington SNOTEL, average over 36 stations, by lag", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "mjo_region_by_lag.png", dpi=110)
    plt.close(fig)


def region_bars(c, st, index, lag, fname):
    cats = [1, 2, 3, 4, 5, 6, 7, 8] if index == "mjo" else [-2, -1, 0, 1, 2]
    ms = ["swe", "tanom", "rain", "bigsnow"]
    fig, axs = plt.subplots(1, 4, figsize=(17, 3.8))
    tiers = {"all": st.index, "low (<4000 ft)": st.index[st["elev_ft"] < 4000], "mid": st.index[(st["elev_ft"] >= 4000) & (st["elev_ft"] < 5000)], "high (>=5000 ft)": st.index[st["elev_ft"] >= 5000]}
    cols = {"all": "k", "low (<4000 ft)": "#b45309", "mid": "#0f766e", "high (>=5000 ft)": "#1d4ed8"}
    for ax, m in zip(axs, ms):
        d = c[(c["index"] == index) & (c["lag"] == lag) & (c["metric"] == m)]
        for k, (nm, ids) in enumerate(tiers.items()):
            y = [d[(d["cat"] == q) & d["station"].isin(ids)]["value"].mean() for q in cats]
            ax.plot(range(len(cats)), y, "-o", color=cols[nm], label=nm, lw=2.5 if nm == "all" else 1.3)
        ax.axhline(0 if m == "tanom" else 1, color="#94a3b8", lw=0.8)
        ax.set_xticks(range(len(cats)))
        ax.set_xticklabels([CLASS[index][q].replace("\n", " ") for q in cats], fontsize=8, rotation=0 if index == "mjo" else 20)
        ax.set_title(TITLE[m], fontsize=9)
    axs[0].legend(fontsize=7)
    fig.suptitle(f"{index.upper()} classes, regional average by elevation tier (lag {lag} d)", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / fname, dpi=110)
    plt.close(fig)


def best_worst_map(c, st, index, lag, metric, fname):
    d = c[(c["index"] == index) & (c["lag"] == lag) & (c["metric"] == metric) & (c["cat"].between(1, 8))]
    fig, axs = plt.subplots(1, 2, figsize=(13, 6.5))
    basins = json.load(open(ROOT / "assets" / "data" / "basins.geojson"))
    for ax, which in zip(axs, ["max", "min"]):
        for f in basins["features"]:
            g = f["geometry"]
            rings = g["coordinates"] if g["type"] == "Polygon" else [r for p in g["coordinates"] for r in p]
            for ring in rings[:1] if g["type"] == "Polygon" else rings:
                a = np.array(ring)
                ax.plot(a[:, 0], a[:, 1], color="#cbd5e1", lw=0.6)
        for sid, x in d.groupby("station"):
            r = x.loc[x["value"].idxmax() if which == "max" else x["value"].idxmin()]
            ratio = metric != "tanom"
            mag = abs(r["value"] - (1 if ratio else 0))
            sc = ax.scatter(st.loc[sid, "lon"], st.loc[sid, "lat"], c=[r["cat"]], cmap="twilight", vmin=0.5, vmax=8.5,
                            s=60 + 500 * mag / (0.8 if ratio else 3), edgecolor="k", linewidth=0.5)
            ax.text(st.loc[sid, "lon"] + 0.03, st.loc[sid, "lat"] + 0.03, str(int(r["cat"])), fontsize=8)
        ax.set_title(("Phase with the most " if which == "max" else "Phase with the least ") + TITLE[metric].split(",")[0].lower(), fontsize=10)
        ax.set_xlim(-124, -117)
        ax.set_ylim(45.6, 49.1)
        ax.set_aspect(1 / np.cos(np.radians(47)))
    fig.colorbar(sc, ax=axs, ticks=range(1, 9), label="MJO phase", fraction=0.025)
    fig.suptitle(f"Where each station does best and worst by MJO phase (lag {lag} d); marker size is the size of the effect", fontsize=11)
    fig.savefig(OUT / fname, dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lag", type=int, default=None, help="lag for the MJO station figures (default: the lag with the strongest regional signal)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    c, st = load()
    lag_region(c, st)
    d = c[(c["index"] == "mjo") & (c["metric"] == "swe") & c["cat"].between(1, 8)].groupby(["lag", "cat"])["value"].mean().unstack()
    spread = (d.max(axis=1) - d.min(axis=1))
    print("regional swe spread across MJO phases by lag:\n", spread.round(3).to_string())
    lag = a.lag if a.lag is not None else int(spread.idxmax())
    print("using lag", lag)
    for L in sorted({0, lag}):
        station_heat(c, st, "mjo", L, ["swe", "tanom", "rain", "bigsnow"], f"mjo_stations_lag{L}.png", "MJO phase")
        region_bars(c, st, "mjo", L, f"mjo_region_lag{L}.png")
    for L in (0, 3) if 3 in c["lag"].unique() else (0,):
        pass
    station_heat(c, st, "pna", 0, ["swe", "tanom", "rain", "bigsnow"], "pna_stations.png", "PNA class (5-day mean)")
    region_bars(c, st, "pna", 0, "pna_region.png")
    station_heat(c, st, "enso", 0, ["swe", "tanom", "rain", "bigsnow"], "enso_stations.png", "ENSO class (ONI)")
    region_bars(c, st, "enso", 0, "enso_region.png")
    best_worst_map(c, st, "mjo", lag, "swe", "mjo_map_snow.png")
    best_worst_map(c, st, "mjo", lag, "tanom", "mjo_map_temp.png")
    print("figures in", OUT)


if __name__ == "__main__":
    main()
