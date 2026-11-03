"""Do the storm-SOM regimes line up with the phase of the MJO (NOAA OMI by default, BoM RMM optional)?

    python scripts/storm_som_mjo.py                       # the default 3x3 z500 map for the nwac period
    python scripts/storm_som_mjo.py --tag nwac_g3x3_pc6   # which node file in data/storms/som_days_<tag>.csv

Needs data/storms/som_days_<tag>.csv (written by scripts/storm_som_fullmaps.py: the node of every storm day) and
data/teleconnections/cache/omi.csv or rmm.csv (scripts/tele_fetch.py). MJO state on a day is the phase (1-8) when its amplitude is at
least 1, else "weak". For lag L the MJO state is read L days BEFORE the storm day.

Two things are reported for each lag 0..MAX_LAG:
  * Cramer's V of the node x MJO-state table (0 = unrelated). Its significance comes from circularly shifting the whole RMM series
    against the storm days (1000 random shifts of 60 days or more), which keeps the MJO's own persistence and the clumping of storm
    days, so it is much stricter than a chi-square test (storm days come in multi-day events).
  * at chosen lags, node x phase ratios: share of a node's days in a phase divided by that phase's share over all storm days
    (1 = no difference), with a 90% range from resampling whole seasons.
Writes docs/storms/som_mjo_lags_<tag>.png and som_mjo_ratios_<tag>_lag<L>.png, and data/storms/som_mjo_<tag>.json
(with --index rmm the files carry an _rmm suffix).
Reading the lag curve: testing 21 lags at once, so one lag just above the shift-null band is expected by chance now and then.
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "storms"
FIG = ROOT / "docs" / "storms"
RMM = ROOT / "data" / "teleconnections" / "cache" / "rmm.csv"
MAX_LAG = 20
STATES = ["1", "2", "3", "4", "5", "6", "7", "8", "weak"]


def mjo_state(index):
    """Daily MJO state: phase 0-7 when the amplitude is at least 1, 8 = weak, -1 = no data. RMM (BoM) ends 2024-02-24, so
    the default is NOAA's OMI (to the present), with its phases rotated to the RMM convention as in scripts/tele_analysis.py."""
    if index == "rmm":
        r = pd.read_csv(RMM, parse_dates=["date"]).set_index("date")
        r = r.reindex(pd.date_range(r.index.min(), r.index.max(), freq="D"))
        st = np.where(r["amp"].isna(), -1, np.where(r["amp"] >= 1, r["phase"].fillna(1).astype(int) - 1, 8))
        return r.index, st.astype(int)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import tele_analysis as T
    shift, agree, near, n = T.phase_check()
    print(f"OMI phases rotated by {shift} to match RMM ({100 * agree:.0f}% exact, {100 * near:.0f}% within one phase, {n} days)")
    o = pd.read_csv(RMM.parent / "omi.csv", parse_dates=["date"]).set_index("date")
    o = o.reindex(pd.date_range(o.index.min(), o.index.max(), freq="D"))
    ang = (np.degrees(np.arctan2(o["pc2"], o["pc1"])) + 360) % 360
    ph = (((ang - 180) % 360) // 45).astype(float)
    ph = (ph + shift) % 8
    st = np.where(o["amp"].isna(), -1, np.where(o["amp"] >= 1, ph.fillna(0).astype(int), 8))
    return o.index, st.astype(int)


def cramers_v(node, state, nn):
    ok = state >= 0
    ct = np.zeros((nn, 9))
    np.add.at(ct, (node[ok], state[ok]), 1)
    ct = ct[:, ct.sum(0) > 0]
    n = ct.sum()
    exp = ct.sum(1, keepdims=True) * ct.sum(0, keepdims=True) / n
    chi2 = ((ct - exp) ** 2 / exp).sum()
    return float(np.sqrt(chi2 / (n * (min(ct.shape) - 1))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="nwac_g3x3_pc6")
    ap.add_argument("--index", choices=["omi", "rmm"], default="omi", help="MJO index (RMM stops in Feb 2024)")
    ap.add_argument("--lags", type=int, nargs="+", default=[0, 5, 10], help="lags for the node x phase ratio heatmaps")
    ap.add_argument("--shifts", type=int, default=1000)
    ap.add_argument("--boot", type=int, default=500)
    a = ap.parse_args()

    suffix = "" if a.index == "omi" else "_rmm"
    d = pd.read_csv(OUT / f"som_days_{a.tag}.csv", parse_dates=["date"])
    node = d["node"].values
    nn = int(node.max()) + 1
    season = np.where(d["date"].dt.month >= 11, d["date"].dt.year + 1, d["date"].dt.year).astype(int)
    dr, st = mjo_state(a.index)
    base = (d["date"] - dr[0]).dt.days.values
    rng = np.random.default_rng(0)
    print(f"{len(d)} storm days, {nn} nodes; {a.index.upper()} {dr[0].date()} to {dr[-1].date()}")

    lags = list(range(MAX_LAG + 1))
    v_obs, v_null95, pval = [], [], []
    for L in lags:
        idx = base - L
        ok = (idx >= 0) & (idx < len(st))
        v = cramers_v(node[ok], st[idx[ok]], nn)
        null = []
        for _ in range(a.shifts):
            sh = int(rng.integers(60, len(st) - 60))
            null.append(cramers_v(node[ok], np.roll(st, sh)[idx[ok]], nn))
        v_obs.append(v)
        v_null95.append(float(np.percentile(null, 95)))
        pval.append(float((np.sum(np.array(null) >= v) + 1) / (a.shifts + 1)))
    best = int(np.argmin(pval))
    print("lag  V      null95  p")
    for L in lags:
        print(f"{L:3d}  {v_obs[L]:.3f}  {v_null95[L]:.3f}  {pval[L]:.3f}")
    print(f"smallest p: lag {best} (p={pval[best]:.3f}); lags with p<0.05: {[L for L in lags if pval[L] < 0.05]}")

    FIG.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.plot(lags, v_obs, "-o", color="#1d4ed8", label="observed")
    ax.plot(lags, v_null95, "--", color="#64748b", label="95th percentile of shifted-MJO null")
    ax.set_xlabel("days the MJO state precedes the storm day")
    ax.set_ylabel("Cramer's V (node vs MJO state)")
    ax.set_xticks(range(0, MAX_LAG + 1, 2))
    ax.legend(frameon=False, fontsize=8)
    ax.set_title(f"SOM regime vs MJO ({a.tag}, n={len(d)} storm days)", fontsize=10)
    fig.savefig(FIG / f"som_mjo_lags_{a.tag}{suffix}.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    useasons = np.unique(season)
    boots = [np.concatenate([np.flatnonzero(season == s) for s in rng.choice(useasons, len(useasons), replace=True)]) for _ in range(a.boot)]
    res = {"tag": a.tag, "n_storm_days": int(len(d)), "lags": lags, "cramers_v": v_obs, "null95": v_null95, "p": pval, "ratios": {}}
    for L in a.lags:
        idx = base - L
        ok = (idx >= 0) & (idx < len(st))
        s_ = np.where(ok, st[np.clip(idx, 0, len(st) - 1)], -1)
        M = np.full((nn, 9), np.nan)
        sig = np.zeros((nn, 9), bool)
        cnt = np.zeros((nn, 9), int)
        have = s_ >= 0
        for j in range(9):
            allshare = (s_[have] == j).mean()
            for n in range(nn):
                m = (node == n) & have
                cnt[n, j] = int(((s_ == j) & m).sum())
                if m.sum():
                    M[n, j] = (s_[m] == j).mean() / allshare if allshare else np.nan
                bs = []
                for b in boots:
                    hb = b[have[b]]
                    mb = hb[node[hb] == n]
                    sh = (s_[hb] == j).mean()
                    if len(mb) and sh > 0:
                        bs.append((s_[mb] == j).mean() / sh)
                if len(bs) > 20:
                    lo, hi = np.percentile(bs, [5, 95])
                    sig[n, j] = lo > 1 or hi < 1
        res["ratios"][str(L)] = {"ratio": np.round(M, 2).tolist(), "significant": sig.tolist(), "counts": cnt.tolist()}
        fig, ax = plt.subplots(figsize=(8.2, 0.55 * nn + 1.6))
        im = ax.imshow(M, cmap="PuOr_r", norm=matplotlib.colors.TwoSlopeNorm(1, 0.3, 2.2), aspect="auto")
        for n in range(nn):
            for j in range(9):
                if not np.isnan(M[n, j]):
                    ax.text(j, n, f"{M[n, j]:.1f}" + ("*" if sig[n, j] else ""), ha="center", va="center", fontsize=8, fontweight="bold" if sig[n, j] else "normal")
        ax.set_xticks(range(9))
        ax.set_xticklabels([f"MJO {s}" if s != "weak" else "weak" for s in STATES], fontsize=8)
        ax.set_yticks(range(nn))
        ax.set_yticklabels([f"node {n} (n={int((node == n).sum())})" for n in range(nn)], fontsize=8)
        fig.colorbar(im, label="share of node's days in the phase / share of all storm days\n(1 = no difference; * = 90% range excludes 1)")
        ax.set_title(f"MJO state {L} days before the storm day ({a.tag})", fontsize=10)
        fig.savefig(FIG / f"som_mjo_ratios_{a.tag}{suffix}_lag{L}.png", dpi=130, bbox_inches="tight")
        plt.close(fig)
    (OUT / f"som_mjo_{a.tag}{suffix}.json").write_text(json.dumps(res), encoding="utf-8")
    print("wrote", FIG / f"som_mjo_lags_{a.tag}{suffix}.png", "and som_mjo_ratios_* for lags", a.lags)


if __name__ == "__main__":
    sys.exit(main())
