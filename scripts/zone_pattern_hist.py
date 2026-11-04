"""Explainer: how a zone's storm-day SWE vs its expectation splits into under / average / over, for all storm days and for one storm pattern.

    python scripts/zone_pattern_hist.py                                  # Mt. Baker, pattern 0
    python scripts/zone_pattern_hist.py --zone "Hurricane Ridge" --pattern 0

Writes docs/storms/hist_<zone>_p<pattern>.png.
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

ROOT = Path(__file__).resolve().parent.parent
OVER_IN, BW = 0.5, 0.12
C = {"under": "#eab308", "average": "#cbd5e1", "over": "#2563eb"}
INK, MUTED = "#1e293b", "#64748b"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", default="Mt. Baker")
    ap.add_argument("--pattern", type=int, default=0)
    a = ap.parse_args()
    ZONE, PAT = a.zone, a.pattern
    z = pd.read_csv(ROOT / "data/storms/zone_daily.csv", index_col=0, parse_dates=True)
    lab = pd.read_csv(ROOT / "data/storms/idisp_days_nwac_k6.csv", parse_dates=["date"]).set_index("date")["cluster"]
    d = z.loc[lab.index].copy()
    d["pat"] = lab
    d = d[d[f"anom_{ZONE}"].notna()]
    a_all, a_p = d[f"anom_{ZONE}"].values, d.loc[d.pat == PAT, f"anom_{ZONE}"].values
    cls = lambda a: np.where(a >= OVER_IN, "over", np.where(a < -OVER_IN, "under", "average"))
    def share(m):                                   # from the saved over/under flags, the same ones the page's table uses
        o, u = d.loc[m, f"over_{ZONE}"].astype(bool).mean() * 100, d.loc[m, f"under_{ZONE}"].astype(bool).mean() * 100
        return {"under": u, "average": 100 - o - u, "over": o}
    s_all, s_p = share(d.pat >= 0), share(d.pat == PAT)
    print("all storm days", len(a_all), {k: round(v, 1) for k, v in s_all.items()})
    print(f"pattern {PAT}", len(a_p), {k: round(v, 1) for k, v in s_p.items()})

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(9, 7.4), gridspec_kw={"height_ratios": [2.3, 1]}, constrained_layout=True)
    # smooth densities (Gaussian kernel, about 0.12 in wide); the area under a curve in a region is the share of days in it
    x = np.linspace(-1.5, 2.5, 600)
    grid = np.linspace(-4, 6, 4000)
    kde = lambda a: gaussian_kde(a, bw_method=BW / a.std())(grid)
    f_all, f_p = np.interp(x, grid, kde(a_all)), np.interp(x, grid, kde(a_p))
    lo, hi = x < -OVER_IN, x > OVER_IN
    mid = ~lo & ~hi
    ax.fill_between(x, 0, f_all, color="#e2e8f0", linewidth=0)           # the usual distribution, as a faint backdrop
    DARK = {"under": "#a16207", "average": "#64748b", "over": "#1e40af"}
    for m, k in ((lo, "under"), (hi, "over")):                            # the difference in the two tails: solid where the pattern has more days than usual, hatched where fewer
        ax.fill_between(x, f_all, f_p, where=m & (f_p >= f_all), color=C[k], linewidth=0, interpolate=True)
        ax.fill_between(x, f_p, f_all, where=m & (f_p < f_all), facecolor="none", edgecolor=DARK[k], hatch="///", linewidth=0, interpolate=True)
    ax.plot(x, f_all, color="#475569", linewidth=1.4, linestyle="--")
    ax.plot(x, f_p, color=INK, linewidth=2.2)
    for xv in (-OVER_IN, OVER_IN):
        ax.axvline(xv, color=MUTED, linestyle=":", linewidth=1)
    top = max(f_all.max(), f_p.max())
    ax.text(-1.0, top * 0.93, "Under-performed\n(half an inch or more\nbelow expectation)", ha="center", va="top", fontsize=10, color=INK)
    ax.text(0, top * 1.1, "About average", ha="center", va="bottom", fontsize=10, color=INK)
    ax.set_ylim(0, top * 1.2)
    ax.text(1.5, top * 0.93, "Over-performed\n(half an inch or more\nabove expectation)", ha="center", va="top", fontsize=10, color=INK)
    ax.set_xlim(x[0], x[-1])
    ax.set_xlabel("Water gained minus what the zone usually gets for a storm of that size (inches)", color=MUTED)
    ax.set_ylabel("Density of storm days", color=MUTED)
    ax.set_yticks([])
    ax.set_title(f"{ZONE}: how storm days split into under, average and over\n{len(a_all)} storm days, {len(a_p)} of them in pattern {PAT}", loc="left", fontsize=12, color=INK)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=C["over"], label="More days than usual (shaded)"),
                       Patch(facecolor="none", edgecolor=DARK["over"], hatch="///", label="Fewer days than usual (hatched)"),
                       Line2D([0], [0], color=INK, linewidth=2.2, label=f"Pattern {PAT} storm days"),
                       Line2D([0], [0], color="#475569", linewidth=1.4, linestyle="--", label="All storm days")],
              frameon=False, loc="upper right", bbox_to_anchor=(1.0, 0.6), fontsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    rows = [("All storm days", s_all), (f"Pattern {PAT}", s_p)]
    for y, (name, s) in enumerate(rows[::-1]):
        left = 0
        for k in ("under", "average", "over"):
            ax2.barh(y, s[k], left=left, color=C[k], edgecolor="white", linewidth=2, height=0.62)
            ax2.text(left + s[k] / 2, y, f"{s[k]:.0f}%" if s[k] >= 5 else "", ha="center", va="center", fontsize=11, fontweight="bold", color="#fff" if k == "over" else INK)
            if s[k] < 5:
                ax2.text(left + s[k] / 2, y + 0.42, f"{s[k]:.1f}%", ha="center", va="bottom", fontsize=9, color=INK)
            left += s[k]
    ax2.set_yticks([0, 1]); ax2.set_yticklabels([r[0] for r in rows[::-1]], fontsize=11)
    ax2.set_xlim(0, 100); ax2.set_ylim(-0.5, 1.75); ax2.set_xlabel("Share of days (%)", color=MUTED)
    ax2.set_title("Same days, as shares:  yellow = under,  grey = average,  blue = over", loc="left", fontsize=11, color=INK, pad=10)
    for s in ("top", "right", "left"):
        ax2.spines[s].set_visible(False)
    ax2.tick_params(axis="y", length=0)
    out = ROOT / "docs/storms" / f"hist_{ZONE.replace(' ', '_').replace('.', '')}_p{PAT}.png"
    fig.savefig(out, dpi=130)
    print("wrote", out)


if __name__ == "__main__":
    sys.exit(main())
