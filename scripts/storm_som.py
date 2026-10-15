"""Synoptic regimes of Washington storms: a 3x3 self-organizing map (SOM) of ERA5 500 hPa height anomalies on storm days,
then which regimes go with a zone over-performing (see scripts/storm_zones.py and PLAN.md, "Storm-type analysis").

    python scripts/storm_som.py                 # all four periods, every cold season for which all ERA5 files exist (scripts/era5_fetch.py)
    python scripts/storm_som.py --period mid    # one period: all (Nov-May), early (Nov-Dec), mid (Jan-Mar) or late (Apr-May)
    python scripts/storm_som.py --seeds 20      # more restarts when judging stability

Each period gets its own SOM, fit only on that period's storm days (the anomalies are still against the whole-season
day-of-year mean, so they are comparable). Writes data/storms/som_results_<period>.json and docs/storms/som_*_<period>.png.

Steps: daily means of z500, t850 and IVT from the 6-hourly ERA5 files; anomalies against a smoothed day-of-year mean (three
harmonics, fitted to the seasons used); storm days from the zone table; the SOM input is z500 anomaly over SOM_BOX, weighted by
sqrt(cos latitude) and reduced to the principal components that hold 90% of the variance. For each node and zone: the share of
the node's storm days on which the zone over-performed, divided by that zone's share over all storm days (1 = no difference),
with a 90% range from resampling whole seasons. Stability: the SOM is refit on resampled seasons and every storm day is assigned
by the refit; the adjusted Rand index against the main fit says how much the grouping changes (1 = identical).

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
import xarray as xr
from minisom import MiniSom

ROOT = Path(__file__).resolve().parent.parent
ERA = ROOT / "data" / "era5"
OUT = ROOT / "data" / "storms"
FIG = ROOT / "docs" / "storms"
G = 9.80665
SOM_BOX = dict(lat=(30, 60), lon=(-170, -115))       # south, north; west, east
NX, NY = 3, 3
PERIODS = {"all": [11, 12, 1, 2, 3, 4, 5], "early": [11, 12], "mid": [1, 2, 3], "late": [4, 5]}
FIELDS = {"z500": "z", "t850": "t", "ivt_u": "viwve", "ivt_v": "viwvn"}


def seasons_available():
    have = {f: {int(p.stem.rsplit("_", 1)[1]) for p in ERA.glob(f"{f}_*.nc")} for f in FIELDS}
    ok = set.intersection(*have.values())
    return sorted(s for s in range(1992, 2027) if s - 1 in ok and s in ok)


def load_daily(field, seasons):
    """Daily means (UTC) for the cold-season days of `seasons`, as a DataArray (time, latitude, longitude)."""
    parts = []
    for y in sorted({s - 1 for s in seasons} | set(seasons)):
        ds = xr.open_dataset(ERA / f"{field}_{y}.nc")
        da = ds[FIELDS[field]]
        da = da.drop_vars([c for c in da.coords if c not in da.dims and c != "valid_time"], errors="ignore")
        da = da.squeeze(drop=True).rename({"valid_time": "time"})
        parts.append(da.resample(time="1D").mean().dropna("time", how="all"))
    da = xr.concat(parts, "time").sortby("time")
    da = da.sel(time=da.time.dt.month.isin([11, 12, 1, 2, 3, 4, 5]))
    season = xr.where(da.time.dt.month >= 11, da.time.dt.year + 1, da.time.dt.year)
    return da.sel(time=season.isin(seasons))


def anomalies(da):
    """Subtract a smoothed day-of-year mean (mean plus three harmonics over the Nov-May days that exist)."""
    doy = da.time.dt.dayofyear.values.astype(float)
    ang = 2 * np.pi * doy / 366.0
    X = np.column_stack([np.ones_like(ang)] + [f(k * ang) for k in (1, 2, 3) for f in (np.cos, np.sin)])
    Y = da.values.reshape(len(doy), -1)
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    return da - xr.DataArray((X @ beta).reshape(da.shape), coords=da.coords, dims=da.dims)


def ari(a, b):
    """Adjusted Rand index of two labelings (label-order free)."""
    a, b = np.unique(a, return_inverse=True)[1], np.unique(b, return_inverse=True)[1]
    n = len(a)
    ct = np.zeros((a.max() + 1, b.max() + 1))
    np.add.at(ct, (a, b), 1)
    c2 = lambda x: x * (x - 1) / 2  # noqa: E731
    sij, sa, sb = c2(ct).sum(), c2(ct.sum(1)).sum(), c2(ct.sum(0)).sum()
    exp = sa * sb / c2(n)
    return float((sij - exp) / (0.5 * (sa + sb) - exp)) if (0.5 * (sa + sb) - exp) else 1.0


def fit_som(X, seed, iters=20000):
    som = MiniSom(NX, NY, X.shape[1], sigma=1.0, learning_rate=0.5, neighborhood_function="gaussian", random_seed=seed)
    som.pca_weights_init(X)
    som.train(X, iters, random_order=True)
    return som


def assign(som, X):
    out = []
    for x in X:
        i, j = som.winner(x)
        out.append(i * NY + j)
    return np.array(out)


def run(a, period):
    seasons = seasons_available()
    print(f"\n=== period {period} (months {PERIODS[period]}); seasons with all four ERA5 fields: {seasons[0]}-{seasons[-1]} ({len(seasons)}) ===")

    z = anomalies(load_daily("z500", seasons)) / G
    t850 = anomalies(load_daily("t850", seasons))
    ivt = np.hypot(load_daily("ivt_u", seasons), load_daily("ivt_v", seasons))
    zones = pd.read_csv(OUT / "zone_daily.csv", index_col=0, parse_dates=True)
    names = [c[5:] for c in zones.columns if c.startswith("over_")]
    days = pd.DatetimeIndex(z.time.values)
    zt = zones.reindex(days)
    storm = zt["storm"].fillna(False).astype(bool).values & days.month.isin(PERIODS[period])
    print(f"storm days in these seasons: {storm.sum()} of {len(days)}")

    box = z.sel(latitude=slice(SOM_BOX["lat"][1], SOM_BOX["lat"][0]), longitude=slice(*SOM_BOX["lon"]))
    w = np.sqrt(np.cos(np.deg2rad(box.latitude.values)))[:, None]
    F = (box.values * w).reshape(len(days), -1)[storm]
    mu = F.mean(0)
    U, S, Vt = np.linalg.svd(F - mu, full_matrices=False)
    k = int(np.searchsorted(np.cumsum(S ** 2) / np.sum(S ** 2), 0.90)) + 1
    X = (F - mu) @ Vt[:k].T
    print(f"SOM input: {F.shape[1]} grid points -> {k} principal components (90% of variance)")
    sea = zt["season"].values[storm].astype(int)

    best = min((fit_som(X, s) for s in range(a.seeds)), key=lambda m: m.quantization_error(X))
    node = assign(best, X)
    print("quantization error", round(best.quantization_error(X), 3), "| storm days per node:", np.bincount(node, minlength=NX * NY).tolist())

    # stability: refit on resampled seasons, assign every storm day, compare with the main grouping
    rng = np.random.default_rng(0)
    useasons = np.unique(sea)
    aris = []
    for r in range(a.refits):
        pick = rng.choice(useasons, len(useasons), replace=True)
        idx = np.concatenate([np.flatnonzero(sea == s) for s in pick])
        aris.append(ari(node, assign(fit_som(X[idx], 100 + r, 8000), X)))
    print(f"stability (adjusted Rand vs the main fit, {a.refits} season resamples): median {np.median(aris):.2f}, 10th percentile {np.percentile(aris, 10):.2f}")

    # zones: over-performance share by node, relative to the zone's overall share, bootstrap over seasons
    res = {"period": period, "months": PERIODS[period], "seasons": [int(seasons[0]), int(seasons[-1])], "n_storm_days": int(storm.sum()), "n_per_node": np.bincount(node, minlength=NX * NY).tolist(),
           "stability_ari_median": float(np.median(aris)), "zones": {}}
    boots = [np.concatenate([np.flatnonzero(sea == s) for s in rng.choice(useasons, len(useasons), replace=True)]) for _ in range(a.boot)]
    for zn in names:
        over = zt[f"over_{zn}"].fillna(False).astype(bool).values[storm]
        have = zt[zn].notna().values[storm]
        base = over[have].mean()
        row = []
        for n in range(NX * NY):
            m = (node == n) & have
            rate = over[m].mean() / base if m.sum() else np.nan
            bs = []
            for idx in boots:
                ii = idx[(node[idx] == n) & have[idx]]
                bb = over[idx[have[idx]]].mean()
                if len(ii) and bb > 0:
                    bs.append(over[ii].mean() / bb)
            lo, hi = (np.percentile(bs, [5, 95]) if len(bs) > 20 else (np.nan, np.nan))
            row.append({"node": n, "days": int(m.sum()), "over_days": int(over[m].sum()), "ratio": None if np.isnan(rate) else round(float(rate), 2),
                        "lo": None if np.isnan(lo) else round(float(lo), 2), "hi": None if np.isnan(hi) else round(float(hi), 2)})
        res["zones"][zn] = {"over_share_all_storm_days": round(float(base), 3), "nodes": row}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"som_results_{period}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")

    # figures: composites per node, and the zone ratios
    FIG.mkdir(parents=True, exist_ok=True)
    fig, axs = plt.subplots(NX, NY, figsize=(11, 8.5), sharex=True, sharey=True)
    lat, lon = z.latitude.values, z.longitude.values
    zs, ivs = z.values[storm], ivt.values[storm]
    for n, ax in enumerate(axs.ravel()):
        m = node == n
        zc = zs[m].mean(0) if m.any() else np.zeros((len(lat), len(lon)))
        cf = ax.contourf(lon, lat, zc, levels=np.arange(-150, 151, 15), cmap="RdBu_r", extend="both")
        ic = ivs[m].mean(0) if m.any() else np.zeros_like(zc)
        ax.contour(lon, lat, ic, levels=[250, 500], colors=["#15803d", "#14532d"], linewidths=[0.8, 1.4])
        ax.plot([-121.7], [47.5], marker="*", color="k", ms=8)
        ax.set_title(f"{period} node {n}: {m.sum()} days ({100 * m.mean():.0f}%)", fontsize=9)
        ax.set_xlim(-170, -115)
        ax.set_ylim(30, 62)
    fig.colorbar(cf, ax=axs, shrink=0.7, label="500 hPa height anomaly (m); green: mean IVT 250 and 500 kg/m/s; star: the Cascades")
    fig.savefig(FIG / f"som_nodes_{period}.png", dpi=130, bbox_inches="tight")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    M = np.array([[r["ratio"] if r["ratio"] is not None else np.nan for r in res["zones"][zn]["nodes"]] for zn in names])
    im = ax.imshow(M, cmap="PuOr_r", norm=matplotlib.colors.TwoSlopeNorm(1, 0, max(2.5, np.nanmax(M))), aspect="auto")
    for i, zn in enumerate(names):
        for j, r in enumerate(res["zones"][zn]["nodes"]):
            sig = r["lo"] is not None and (r["lo"] > 1 or r["hi"] < 1)
            ax.text(j, i, (f"{r['ratio']:.1f}" + ("*" if sig else "")) if r["ratio"] is not None else "", ha="center", va="center", fontsize=8, fontweight="bold" if sig else "normal")
    ax.set_xticks(range(NX * NY))
    ax.set_xticklabels([f"node {n}\n(n={c})" for n, c in enumerate(res["n_per_node"])], fontsize=8)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=9)
    fig.colorbar(im, label="over-performance share vs the zone's overall share (1 = no difference); * = 90% range excludes 1")
    fig.savefig(FIG / f"som_zones_{period}.png", dpi=130, bbox_inches="tight")
    print("wrote", OUT / f"som_results_{period}.json", FIG / f"som_nodes_{period}.png", FIG / f"som_zones_{period}.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=list(PERIODS), nargs="+", default=list(PERIODS))
    ap.add_argument("--seeds", type=int, default=8, help="SOM restarts for the main fit (the best by quantization error is kept)")
    ap.add_argument("--boot", type=int, default=500, help="season resamples for the zone ranges")
    ap.add_argument("--refits", type=int, default=30, help="season-resampled refits for the stability check")
    a = ap.parse_args()
    for period in a.period:
        run(a, period)


if __name__ == "__main__":
    sys.exit(main())
