"""Second pass of the teleconnection analysis: modes of variability, harmonic MJO fit, month and elevation/latitude effects.

    python scripts/tele_analysis.py && python scripts/tele_modes.py [--lag 8]

Reads data/teleconnections/results/panel.npz; writes tables there and figures to docs/teleconnections/.
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

ROOT = ta.ROOT
RES, OUT = ta.RES, ROOT / "docs" / "teleconnections"


def zscore(X):
    mu, sd = np.nanmean(X, axis=0), np.nanstd(X, axis=0)
    return np.where(np.isnan(X), 0.0, (X - mu) / sd), sd


def ols(y, cols, names):
    """Plain least squares with standard errors; returns a printable DataFrame and R^2."""
    ok = np.isfinite(y)
    X = np.column_stack([np.ones(ok.sum())] + [(c[ok] - c[ok].mean()) / c[ok].std() for c in cols])
    b, *_ = np.linalg.lstsq(X, y[ok], rcond=None)
    res = y[ok] - X @ b
    s2 = res @ res / (len(res) - X.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    r2 = 1 - res @ res / ((y[ok] - y[ok].mean()) @ (y[ok] - y[ok].mean()))
    return pd.DataFrame({"term": ["intercept"] + names, "coef_per_sd": b, "t": b / se}).round(3), r2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lag", type=int, default=8)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    z = np.load(RES / "panel.npz")
    idx = pd.DatetimeIndex(z["idx"])
    st = pd.read_csv(RES / "stations.csv", dtype={"id": str})
    ind, _ = ta.indices(idx, a.lag)
    ta.PHASE_SHIFT = ta.phase_check()[0]
    ind, _ = ta.indices(idx, a.lag)
    lines = []

    # --- 1. harmonic MJO fit: response = a*PC1 + b*PC2 on days with amplitude >= 1 -------------------
    omi = pd.read_csv(ta.CACHE / "omi.csv", index_col=0, parse_dates=True)
    src = idx - pd.Timedelta(days=a.lag)
    pc1 = omi["pc1"].reindex(src).values
    pc2 = omi["pc2"].reindex(src).values
    amp = omi["amp"].reindex(src).values
    use = amp >= 1
    rows = []
    for m in ["swe", "tanom", "rain", "bigsnow"]:
        X = z[m]
        for j, sid in enumerate(st["id"]):
            y = X[:, j]
            ok = use & np.isfinite(y)
            if ok.sum() < 300:
                continue
            yy = y[ok] / np.nanmean(y) - 1 if m != "tanom" else y[ok]
            A = np.column_stack([np.ones(ok.sum()), pc1[ok], pc2[ok]])
            b, *_ = np.linalg.lstsq(A, yy, rcond=None)
            fit = A @ b
            r2 = 1 - ((yy - fit) ** 2).sum() / ((yy - yy.mean()) ** 2).sum()
            ang = (np.degrees(np.arctan2(b[2], b[1])) + 360) % 360       # direction in the PC1/PC2 plane where the response is largest
            # same phase numbering as the composites
            ph = ((int(((ang - 180) % 360) // 45) + ta.PHASE_SHIFT) % 8) + 1
            rows.append((m, sid, np.hypot(b[1], b[2]), ang, ph, r2))
    H = pd.DataFrame(rows, columns=["metric", "station", "per_unit_amp", "angle_deg", "peak_phase", "r2"])
    H.to_csv(RES / "mjo_harmonic.csv", index=False)
    lines.append("MJO harmonic fit (lag %d): peak phase by metric (median over stations) and explained variance" % a.lag)
    lines.append(H.groupby("metric").agg(peak_phase=("peak_phase", lambda s: s.mode().iloc[0]), r2=("r2", "median"), amp=("per_unit_amp", "median")).round(3).to_string())

    # --- 2. what explains the differences between stations ---------------------------------------
    stn = st.set_index("id")
    y = {}
    res = pd.read_csv(RES / "composites.csv", dtype={"station": str})
    def eff(index, lag, metric, cat):
        d = res[(res["index"] == index) & (res["lag"] == lag) & (res["metric"] == metric) & (res["cat"] == cat)].set_index("station")["value"]
        return d.reindex(stn.index).values
    tests = {
        f"MJO phase 2 snowfall ratio (lag {a.lag})": eff("mjo", a.lag, "swe", 2),
        f"MJO phase 7 snowfall ratio (lag {a.lag})": eff("mjo", a.lag, "swe", 7),
        f"MJO phase 5 temp anomaly F (lag {a.lag})": eff("mjo", a.lag, "tanom", 5),
        f"MJO phase 3 temp anomaly F (lag {a.lag})": eff("mjo", a.lag, "tanom", 3),
        "strong +PNA snowfall ratio": eff("pna", 0, "swe", 2),
        "strong -PNA snowfall ratio": eff("pna", 0, "swe", -2),
        "strong +PNA temp anomaly F": eff("pna", 0, "tanom", 2),
        "El Nino snowfall ratio": eff("enso", 0, "swe", 2),
        "La Nina snowfall ratio": eff("enso", 0, "swe", -2),
        "La Nina temp anomaly F": eff("enso", 0, "tanom", -2),
    }
    reg = []
    for k, v in tests.items():
        t, r2 = ols(v, [stn["elev_ft"].values, stn["lat"].values, stn["lon"].values], ["elevation", "latitude", "longitude"])
        reg.append((k, r2, *t["coef_per_sd"].values[1:], *t["t"].values[1:], np.nanstd(v)))
    R = pd.DataFrame(reg, columns=["effect", "R2", "elev", "lat", "lon", "t_elev", "t_lat", "t_lon", "spread"]).round(3)
    R.to_csv(RES / "station_gradients.csv", index=False)
    lines.append("\nWhat explains the differences between stations (OLS on standardized elevation, latitude, longitude; coefficients are the effect of +1 sd; |t|>2 notable)")
    lines.append(R.to_string(index=False))

    # --- 3. EOFs of daily snowfall and temperature anomalies ----------------------------------------
    fig, axs = plt.subplots(2, 4, figsize=(17, 8))
    basins = None
    for r, m in enumerate(["swe", "tanom"]):
        X, _ = zscore(z[m])
        X = X[:, np.isfinite(z[m]).mean(axis=0) > 0.6]
        keep = np.isfinite(z[m]).mean(axis=0) > 0.6
        U, s, Vt = np.linalg.svd(X - X.mean(axis=0), full_matrices=False)
        var = s ** 2 / (s ** 2).sum()
        lines.append(f"\nEOF of daily {m}: variance explained by modes 1-4 = {np.round(var[:4] * 100, 1)} %")
        pcs = U[:, :3] * s[:3]
        pcs = pcs / pcs.std(axis=0)
        sub = st[keep].reset_index(drop=True)
        for k in range(2):
            ax = axs[r, k]
            sc = ax.scatter(sub["lon"], sub["lat"], c=Vt[k], cmap="RdBu_r", vmin=-0.4, vmax=0.4, s=70, edgecolor="k", linewidth=0.4)
            ax.set_title(f"{m} EOF{k + 1} loadings ({var[k] * 100:.0f}% of variance)", fontsize=9)
            ax.set_aspect(1 / np.cos(np.radians(47)))
            fig.colorbar(sc, ax=ax, fraction=0.04)
            corr_e = np.corrcoef(Vt[k], sub["elev_ft"])[0, 1]
            corr_l = np.corrcoef(Vt[k], sub["lat"])[0, 1]
            lines.append(f"   EOF{k + 1}: correlation of loadings with elevation {corr_e:+.2f}, latitude {corr_l:+.2f}")
        # how the leading PC varies with MJO phase and PNA class
        for c, (name, labels, cats) in enumerate([("MJO phase", ind["mjo"], range(1, 9)), ("PNA class", ind["pna"], [-2, -1, 0, 1, 2])]):
            ax = axs[r, 2 + c]
            for k in range(2):
                ax.plot([str(q) for q in cats], [pcs[labels.values == q, k].mean() for q in cats], "-o", label=f"PC{k + 1}")
            ax.axhline(0, color="#94a3b8", lw=0.8)
            ax.set_title(f"{m}: mean PC score by {name}" + (f" (lag {a.lag})" if c == 0 else ""), fontsize=9)
            ax.legend(fontsize=7)
        lines.append(f"   mean PC1 score by MJO phase: " + ", ".join(f"{q}:{pcs[ind['mjo'].values == q, 0].mean():+.2f}" for q in range(1, 9)))
    fig.suptitle("Leading modes of daily variability across the 36 stations", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "eofs.png", dpi=110)
    plt.close(fig)

    # --- 4. month dependence: regional snowfall ratio by month and class ----------------------------
    swe = np.nanmean(z["swe"] / np.nanmean(z["swe"], axis=0), axis=1)
    tan = np.nanmean(z["tanom"], axis=1)
    mon = idx.month.values
    fig, axs = plt.subplots(2, 2, figsize=(13, 8))
    order = [11, 12, 1, 2, 3, 4, 5]
    name = {11: "Nov", 12: "Dec", 1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May"}
    for r, (nm, arr_, base, cmap) in enumerate([("snowfall ratio", swe, 1, "BrBG"), ("temperature anomaly F", tan, 0, "RdYlBu_r")]):
        for c, (iname, cats) in enumerate([("mjo", range(1, 9)), ("pna", [-2, -1, 0, 1, 2])]):
            M = np.array([[np.nanmean(arr_[(mon == mo) & (ind[iname].values == q)]) / (np.nanmean(arr_[mon == mo]) if base == 1 else 1) - (0 if base == 1 else np.nanmean(arr_[mon == mo]) * 0)
                           for q in cats] for mo in order])
            ax = axs[r, c]
            lim = np.nanmax(np.abs(M - base))
            im = ax.imshow(M, cmap=cmap, vmin=base - lim, vmax=base + lim, aspect="auto")
            ax.set_yticks(range(7))
            ax.set_yticklabels([name[m] for m in order])
            ax.set_xticks(range(len(list(cats))))
            ax.set_xticklabels([str(q) for q in cats])
            for i in range(M.shape[0]):
                for j in range(M.shape[1]):
                    ax.text(j, i, f"{M[i, j]:.2f}" if base == 1 else f"{M[i, j]:+.1f}", ha="center", va="center", fontsize=7)
            ax.set_title(f"regional {nm} by month and {iname.upper()} {'phase (lag %d d)' % a.lag if iname == 'mjo' else 'class'}", fontsize=9)
            fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(OUT / "month_by_class.png", dpi=110)
    plt.close(fig)

    # --- 5. the harmonic fit on a map: where is each station's snowiest MJO phase? ------------------
    fig, axs = plt.subplots(1, 2, figsize=(12, 6))
    for ax, m in zip(axs, ["swe", "tanom"]):
        h = H[H["metric"] == m].set_index("station").reindex(stn.index)
        sc = ax.scatter(stn["lon"], stn["lat"], c=h["angle_deg"], cmap="twilight", vmin=0, vmax=360, s=40 + 3000 * h["per_unit_amp"].fillna(0) / (h["per_unit_amp"].max() if m == "swe" else 1.5), edgecolor="k", linewidth=0.4)
        ax.set_title(f"Direction in the MJO plane where {'snowfall' if m == 'swe' else 'temperature'} peaks (color) and its size per unit amplitude", fontsize=8)
        ax.set_aspect(1 / np.cos(np.radians(47)))
        fig.colorbar(sc, ax=ax, label="angle (deg) in PC1/PC2 plane", fraction=0.04)
    fig.tight_layout()
    fig.savefig(OUT / "mjo_harmonic_map.png", dpi=110)
    plt.close(fig)

    text = "\n".join(lines)
    (RES / "modes_summary.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
