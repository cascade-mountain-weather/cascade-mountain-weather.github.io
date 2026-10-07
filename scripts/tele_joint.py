"""Separate the overlap between PNA, ENSO (ONI), PDO and the MJO with one joint regression (run by hand).

    python scripts/tele_analysis.py && python scripts/tele_joint.py [--lag 8]

For each response (all-station mean, three elevation tiers, and every station) it fits, over the cold-season days,
    response = intercept + b1 PNA + b2 ONI + b3 PDO + sum_k c_k [MJO phase k, `lag` days earlier] + error
PNA is the CPC 5-day mean (same day), ONI and PDO are the month's value, all standardized, so b is the change per one
standard deviation. The MJO enters as phase indicators relative to a weak MJO (amplitude < 1). Responses are temperature
anomaly (F), and snowfall, rain and big-snow days as a ratio to the station's normal (so b = 0.10 means +10%).
Uncertainty: 90% bootstrap over whole seasons. Single-index fits are saved next to the joint ones, so the change from
"alone" to "together" shows where one index was only standing in for another.
Writes data/teleconnections/results/joint_*.csv and docs/teleconnections/joint_*.png.
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
import tele_analysis as ta  # noqa: E402

RES, OUT = ta.RES, ta.ROOT / "docs" / "teleconnections"
TIERS = {"all stations": lambda e: e > 0, "low (<4000 ft)": lambda e: e < 4000,
         "mid (4000-5000 ft)": lambda e: (e >= 4000) & (e < 5000), "high (>=5000 ft)": lambda e: e >= 5000}


def predictors(idx, lag):
    ta.PHASE_SHIFT = ta.phase_check()[0]
    ind, _ = ta.indices(idx, lag)
    pna = pd.read_csv(ta.CACHE / "pna_daily.csv", index_col=0, parse_dates=True)["pna"].rolling(5, center=True, min_periods=3).mean()
    pna = pna.reindex(idx).values
    oni = pd.read_csv(ta.CACHE / "oni.csv", index_col=0)["oni"]
    oni.index = pd.PeriodIndex(oni.index, freq="M")
    oni = oni.reindex(pd.PeriodIndex(idx.to_period("M"))).values
    import json
    pj = json.load(open(ta.ROOT / "assets" / "data" / "climate_indices.json"))["pdo"]
    y0 = int(pj["start"][:4])
    pdo = pd.Series(pj["values"], index=pd.period_range(f"{y0}-01", periods=len(pj["values"]), freq="M"))
    pdo = pdo.reindex(pd.PeriodIndex(idx.to_period("M"))).values
    z = lambda v: (v - np.nanmean(v)) / np.nanstd(v)
    stats = {k: {"mean": float(np.nanmean(v)), "sd": float(np.nanstd(v))} for k, v in [("PNA", pna), ("ONI", oni), ("PDO", pdo)]}
    X = {"PNA": z(pna), "ONI": z(oni), "PDO": z(pdo)}
    for k in range(1, 9):
        X[f"MJO{k}"] = (ind["mjo"].values == k).astype(float)
    df = pd.DataFrame(X, index=idx)
    df.attrs["stats"] = stats
    return df


def fit_boot(X, y, season, terms, nboot, rng):
    """OLS coefficients for `terms` (intercept added) and a season-bootstrap 90% interval. X is a DataFrame."""
    A = np.column_stack([np.ones(len(X))] + [X[t].values for t in terms])
    ok = np.isfinite(y) & np.isfinite(A).all(axis=1)
    A, y, sn = A[ok], y[ok], season[ok]
    years = np.unique(sn)
    P = A.shape[1]
    xtx = np.zeros((len(years), P, P))
    xty = np.zeros((len(years), P))
    for i, yr in enumerate(years):
        a, b = A[sn == yr], y[sn == yr]
        xtx[i], xty[i] = a.T @ a, a.T @ b
    solve = lambda sel: np.linalg.lstsq(xtx[sel].sum(axis=0), xty[sel].sum(axis=0), rcond=None)[0]
    b = solve(np.arange(len(years)))
    bs = np.array([solve(rng.integers(0, len(years), len(years))) for _ in range(nboot)])
    lo, hi = np.percentile(bs, [5, 95], axis=0)
    return b, lo, hi          # the first entry is the intercept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lag", type=int, default=8)
    ap.add_argument("--boot", type=int, default=300)
    a = ap.parse_args()
    z = np.load(RES / "panel.npz")
    idx = pd.DatetimeIndex(z["idx"])
    season = z["season"]
    st = pd.read_csv(RES / "stations.csv", dtype={"id": str})
    X = predictors(idx, a.lag)
    import json
    (RES / "joint_stats.json").write_text(json.dumps({"lag": a.lag, "stats": X.attrs["stats"]}, indent=1), encoding="utf-8")
    rng = np.random.default_rng(11)
    print("daily correlation between PNA, ONI and PDO (cold season):")
    print(X[["PNA", "ONI", "PDO"]].corr().round(2).to_string())
    X[["PNA", "ONI", "PDO"]].corr().round(3).to_csv(RES / "joint_predictor_corr.csv")

    norm = {m: z[m] / np.nanmean(z[m], axis=0) - (0 if m == "tanom" else 0) for m in ["swe", "rain", "bigsnow"]}
    resp = {"tanom": z["tanom"], **{m: norm[m] for m in norm}}
    elev = st["elev_ft"].values
    rows = []
    jt = ["PNA", "ONI", "PDO"] + [f"MJO{k}" for k in range(1, 9)]
    for m, M in resp.items():
        units = {}
        for tier, f in TIERS.items():
            cols = f(elev) & (np.isfinite(M).mean(axis=0) > 0.6)
            units[tier] = np.nanmean(M[:, cols], axis=1)
        for j, sid in enumerate(st["id"]):
            if np.isfinite(M[:, j]).mean() > 0.6:
                units["st:" + sid] = M[:, j]
        for name, y in units.items():
            for model, terms in [("joint", jt), ("PNA alone", ["PNA"]), ("ONI alone", ["ONI"]), ("PDO alone", ["PDO"])]:
                if name.startswith("st:") and model != "joint":
                    continue
                b, lo, hi = fit_boot(X, y, season, terms, a.boot if not name.startswith("st:") else 60, rng)
                for t, bb, l, h in zip(["intercept"] + terms, b, lo, hi):
                    rows.append((m, name, model, t, bb, l, h))
        print("done", m)
    R = pd.DataFrame(rows, columns=["metric", "unit", "model", "term", "coef", "lo", "hi"])
    R.to_csv(RES / "joint_coefs.csv", index=False)

    # ---- figure 1: alone vs together for PNA, ONI, PDO, by tier
    fig, axs = plt.subplots(2, 4, figsize=(17, 8), sharey="row")
    for r, m in enumerate(["swe", "tanom"]):
        for c, tier in enumerate(TIERS):
            ax = axs[r, c]
            for k, t in enumerate(["PNA", "ONI", "PDO"]):
                for dx, model, col in [(-0.15, f"{t} alone", "#94a3b8"), (0.15, "joint", "#1e3c72")]:
                    d = R[(R["metric"] == m) & (R["unit"] == tier) & (R["model"] == model) & (R["term"] == t)].iloc[0]
                    ax.errorbar(k + dx, d["coef"], yerr=[[d["coef"] - d["lo"]], [d["hi"] - d["coef"]]], fmt="o", color=col, capsize=3,
                                label=("alone" if dx < 0 else "together") if k == 0 else None)
            ax.axhline(0, color="#94a3b8", lw=0.8)
            ax.set_xticks(range(3))
            ax.set_xticklabels(["PNA", "ONI", "PDO"])
            ax.set_title(f"{tier}: {'snowfall (ratio per 1 sd)' if m == 'swe' else 'temperature (F per 1 sd)'}", fontsize=9)
            if r == 0 and c == 0:
                ax.legend(fontsize=8)
    fig.suptitle("Each index alone vs. all together (with MJO phases), 90% season-bootstrap intervals", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "joint_alone_vs_together.png", dpi=110)
    plt.close(fig)

    # ---- figure 2: MJO phase effect after removing PNA/ONI/PDO, vs the raw composite
    comp = pd.read_csv(RES / "composites.csv", dtype={"station": str})
    fig, axs = plt.subplots(2, 2, figsize=(13, 7))
    for r, m in enumerate(["swe", "tanom"]):
        for c, tier in enumerate(["all stations", "low (<4000 ft)"]):
            ax = axs[r, c]
            ph = range(1, 9)
            j = [R[(R["metric"] == m) & (R["unit"] == tier) & (R["model"] == "joint") & (R["term"] == f"MJO{k}")].iloc[0] for k in ph]
            ax.errorbar(list(ph), [x["coef"] for x in j], yerr=[[x["coef"] - x["lo"] for x in j], [x["hi"] - x["coef"] for x in j]], fmt="-o", color="#1e3c72", capsize=3, label="joint model (vs weak MJO)")
            ax.axhline(0, color="#94a3b8", lw=0.8)
            ax.set_title(f"{tier}: MJO phase effect on {'snowfall ratio' if m == 'swe' else 'temperature F'} (lag {a.lag} d)", fontsize=9)
            ax.set_xlabel("MJO phase")
    fig.tight_layout()
    fig.savefig(OUT / "joint_mjo_phases.png", dpi=110)
    plt.close(fig)

    # ---- figure 3: sore thumbs, station coefficients minus the all-station coefficient (in standard errors)
    fig, axs = plt.subplots(2, 3, figsize=(16, 10))
    base = R[(R["model"] == "joint") & (R["unit"] == "all stations")].set_index(["metric", "term"])
    thumbs = []
    for r, m in enumerate(["swe", "tanom"]):
        for c, t in enumerate(["PNA", "ONI", "PDO"]):
            ax = axs[r, c]
            d = R[(R["metric"] == m) & (R["model"] == "joint") & (R["term"] == t) & R["unit"].str.startswith("st:")].copy()
            d["id"] = d["unit"].str[3:]
            d = d.merge(st, on="id")
            d["se"] = (d["hi"] - d["lo"]) / 3.29
            d["dev"] = (d["coef"] - base.loc[(m, t), "coef"]) / d["se"]
            for _, x in d.iterrows():
                if abs(x["dev"]) > 2.5:
                    thumbs.append((m, t, x["name"], x["elev_ft"], round(x["coef"], 3), round(base.loc[(m, t), "coef"], 3), round(x["dev"], 1)))
            sc = ax.scatter(d["lon"], d["lat"], c=d["coef"], cmap="BrBG" if m == "swe" else "RdBu_r", s=70, edgecolor=np.where(d["dev"].abs() > 2.5, "k", "#cbd5e1"), linewidth=1.6)
            fig.colorbar(sc, ax=ax, fraction=0.04)
            ax.set_aspect(1 / np.cos(np.radians(47)))
            ax.set_title(f"{t} (joint), {'snowfall ratio' if m == 'swe' else 'temp F'} per 1 sd; black ring = differs from the state mean by >2.5 SE", fontsize=7.5)
    fig.tight_layout()
    fig.savefig(OUT / "joint_station_maps.png", dpi=110)
    plt.close(fig)
    T = pd.DataFrame(thumbs, columns=["metric", "term", "station", "elev_ft", "station_coef", "state_coef", "dev_SE"]).sort_values("dev_SE", key=abs, ascending=False)
    T.to_csv(RES / "joint_sore_thumbs.csv", index=False)
    print("\nJoint coefficients, all stations:")
    print(R[(R["unit"] == "all stations") & (R["model"] == "joint")].pivot(index="term", columns="metric", values="coef").round(3).to_string())
    print("\nAlone vs joint for PNA/ONI/PDO, all stations (snowfall ratio and temp F per 1 sd):")
    for m in ["swe", "tanom"]:
        for t in ["PNA", "ONI", "PDO"]:
            al = R[(R["metric"] == m) & (R["unit"] == "all stations") & (R["model"] == f"{t} alone") & (R["term"] == t)].iloc[0]
            jo = R[(R["metric"] == m) & (R["unit"] == "all stations") & (R["model"] == "joint") & (R["term"] == t)].iloc[0]
            print(f"  {m:6s} {t}: alone {al['coef']:+.3f} [{al['lo']:+.3f},{al['hi']:+.3f}]  together {jo['coef']:+.3f} [{jo['lo']:+.3f},{jo['hi']:+.3f}]")
    print("\nSore thumbs (station coefficient differs from the state mean by more than 2.5 SE):")
    print(T.head(25).to_string(index=False))


if __name__ == "__main__":
    main()
