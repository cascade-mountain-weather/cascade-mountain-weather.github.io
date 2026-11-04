"""Storm regimes in intensity-displacement (IDISP) space, and where particular days fall.

    python scripts/storm_idisp.py                       # k = 9 clusters, storm days Nov 15 - Apr 30, plus the default test days
    python scripts/storm_idisp.py --k 6 --days 2026-09-12 2026-10-27

Each storm day is described by three numbers taken from its 500 hPa height anomaly field over the search region (SOM_BOX cut off at 150 W, the longitude of Anchorage): the intensity of the lowest
low (minus the minimum anomaly, m) and its displacement from the Cascades (km east and north, from the position of that minimum).
These are standardized and clustered with k-means (50 restarts, best by inertia; clusters numbered by decreasing intensity).
Known limits of the method, which the output reports where it can: the minimum can jump between two lows, and it loses information
when the low sits at the edge of the region (share of days with the minimum within 2 degrees of the box edge is printed).

Compared with the SOM (scripts/storm_som.py) by stability (season-resampled refits, adjusted Rand index), by the zone
over-performance ratios of each cluster, and by the adjusted Rand index against the SOM nodes (data/storms/som_days_nwac_g3x3_pc6.csv).

Test days: GFS analyses (00, 06, 12, 18 UTC, 0.25 degree, read with Herbie and cached in data/era5/gfs_testdays.nc) are averaged to a
daily mean, put on the ERA5 1-degree grid, turned into anomalies with the same three-harmonic day-of-year fit as the SOM
(EXTENDED beyond the Nov-May days the fit was made from: for September and October this is an extrapolation, see the printed
domain-mean anomaly as a check), then assigned to the nearest IDISP cluster, to the SOM node, and correlated with every composite.
Writes data/storms/idisp_*.json/csv and docs/storms/idisp_*.png and som_testdays.png.
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
from scipy.cluster.vq import kmeans2

sys.path.insert(0, str(Path(__file__).resolve().parent))
import storm_som as S  # noqa: E402
import storm_som_fullmaps as FM  # noqa: E402

CASCADES = (47.5, -121.7)
KM = 111.2
GFS_CACHE = S.ERA / "gfs_testdays.nc"
IDISP_LON_W = -150.0          # the lowest-low search stops at the longitude of Anchorage (149.9 W): lows farther west do not steer Washington storms
DEFAULT_DAYS = ["2026-09-11", "2026-09-12", "2026-09-13"] + [f"2026-10-{d}" for d in range(23, 31)]


# ------------------------------------------------------------------ IDISP features and clustering
def idisp_features(anom, lat, lon):
    """(n, 3): intensity (m, minus the minimum anomaly), km east and km north of the Cascades; and a flag for a minimum at the box edge."""
    a = np.asarray(anom)
    n = a.shape[0]
    flat = a.reshape(n, -1)
    i = flat.argmin(1)
    iy, ix = np.divmod(i, a.shape[2])
    la, lo = lat[iy], lon[ix]
    X = np.column_stack([-flat[np.arange(n), i], (lo - CASCADES[1]) * KM * np.cos(np.deg2rad(CASCADES[0])), (la - CASCADES[0]) * KM])
    edge = (iy <= 2) | (iy >= len(lat) - 3) | (ix <= 2) | (ix >= len(lon) - 3)
    return X, edge


def kmeans(X, k, restarts, seed=0):
    best = None
    for r in range(restarts):
        c, lab = kmeans2(X, k, minit="++", seed=seed + r, iter=50)
        if len(np.unique(lab)) < k:
            continue
        inertia = ((X - c[lab]) ** 2).sum()
        if best is None or inertia < best[0]:
            best = (inertia, c, lab)
    return best[1], best[2]


def nearest(X, c):
    d = ((X[:, None, :] - c[None]) ** 2).sum(2)
    o = np.argsort(d, 1)
    return o[:, 0], np.sqrt(d[np.arange(len(X)), o[:, 0]]), o[:, 1], np.sqrt(d[np.arange(len(X)), o[:, 1]])


def order_by_intensity(c):
    """Permutation so cluster 0 is the deepest low."""
    return np.argsort(-c[:, 0])


# ------------------------------------------------------------------ extended day-of-year fit
def harmonic_design(doy):
    ang = 2 * np.pi * np.asarray(doy, float) / 366.0
    return np.column_stack([np.ones_like(ang)] + [f(k * ang) for k in (1, 2, 3) for f in (np.cos, np.sin)])


def climatology(da, dates):
    """The same fit as storm_som.anomalies, evaluated on any dates (including ones outside the days it was fitted to)."""
    doy = da.time.dt.dayofyear.values
    beta, *_ = np.linalg.lstsq(harmonic_design(doy), da.values.reshape(len(doy), -1), rcond=None)
    return (harmonic_design(pd.DatetimeIndex(dates).dayofyear) @ beta).reshape((len(dates),) + da.shape[1:])


# ------------------------------------------------------------------ GFS test days
def fetch_gfs(days, lat, lon):
    from herbie import Herbie
    have = xr.open_dataset(GFS_CACHE).load() if GFS_CACHE.exists() else None
    keep = [] if have is None else [pd.Timestamp(t) for t in have.time.values]
    new = []
    for d in days:
        d = pd.Timestamp(d)
        if d in keep:
            continue
        zs, ts = [], []
        for hh in (0, 6, 12, 18):
            H = Herbie(d + pd.Timedelta(hours=hh), model="gfs", product="pgrb2.0p25", fxx=0, verbose=False)
            ds = H.xarray(r":(HGT|TMP):(500|850) mb")
            ds = ds.sel(latitude=lat, longitude=lon % 360)
            zs.append(ds["gh"].sel(isobaricInhPa=500).values)
            ts.append(ds["t"].sel(isobaricInhPa=850).values)
        new.append(xr.Dataset({"z500": (("time", "latitude", "longitude"), np.mean(zs, 0)[None]), "t850": (("time", "latitude", "longitude"), np.mean(ts, 0)[None])},
                              coords={"time": [d], "latitude": lat, "longitude": lon}))
        print("fetched GFS analyses for", d.date())
    if new:
        allds = xr.concat(([have] if have is not None else []) + new, "time").sortby("time")
        have = None
        allds.to_netcdf(GFS_CACHE)
    out = xr.open_dataset(GFS_CACHE).load()
    return out.sel(time=[pd.Timestamp(d) for d in days])


def weighted_corr(a, b, w):
    a, b = a - np.average(a, weights=w), b - np.average(b, weights=w)
    return float(np.sum(w * a * b) / np.sqrt(np.sum(w * a * a) * np.sum(w * b * b)))


# ------------------------------------------------------------------ zone ratios
def zone_ratios(node, nn, zt, names, sea, nboot, rng):
    useasons = np.unique(sea)
    boots = [np.concatenate([np.flatnonzero(sea == s) for s in rng.choice(useasons, len(useasons), replace=True)]) for _ in range(nboot)]
    out = {}
    for zn in names:
        over = zt[f"over_{zn}"].fillna(False).astype(bool).values
        have = zt[zn].notna().values
        base = over[have].mean()
        row = []
        for n in range(nn):
            m = (node == n) & have
            rate = over[m].mean() / base if m.sum() else np.nan
            bs = []
            for idx in boots:
                ii = idx[(node[idx] == n) & have[idx]]
                bb = over[idx[have[idx]]].mean()
                if len(ii) and bb > 0:
                    bs.append(over[ii].mean() / bb)
            lo, hi = np.percentile(bs, [5, 95]) if len(bs) > 20 else (np.nan, np.nan)
            row.append({"node": n, "days": int(m.sum()), "over_days": int(over[m].sum()), "ratio": None if np.isnan(rate) else round(float(rate), 2),
                        "lo": None if np.isnan(lo) else round(float(lo), 2), "hi": None if np.isnan(hi) else round(float(hi), 2)})
        out[zn] = {"over_share_all_storm_days": round(float(base), 3), "nodes": row}
    return out


def zone_heatmap(res, names, counts, out, label):
    fig, ax = plt.subplots(figsize=(1.0 * len(counts) + 3.5, 4.8))
    M = np.array([[r["ratio"] if r["ratio"] is not None else np.nan for r in res[zn]["nodes"]] for zn in names])
    im = ax.imshow(M, cmap="PuOr_r", norm=matplotlib.colors.TwoSlopeNorm(1, 0, max(2.5, np.nanmax(M))), aspect="auto")
    for i, zn in enumerate(names):
        for j, r in enumerate(res[zn]["nodes"]):
            sig = r["lo"] is not None and (r["lo"] > 1 or r["hi"] < 1)
            ax.text(j, i, (f"{r['ratio']:.1f}" + ("*" if sig else "")) if r["ratio"] is not None else "", ha="center", va="center", fontsize=8, fontweight="bold" if sig else "normal")
    ax.set_xticks(range(len(counts)))
    ax.set_xticklabels([f"{label} {n}\n(n={c})" for n, c in enumerate(counts)], fontsize=8)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=9)
    fig.colorbar(im, label="over-performance share vs the zone's\noverall share (1 = no difference)\n* = 90% range excludes 1")
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)


def plot_lows(Xraw, lab, k, out):
    """Where the lowest low sat on every storm day, coloured by cluster (the box the search ran over is outlined)."""
    import cartopy.crs as ccrs
    lon = CASCADES[1] + Xraw[:, 1] / (KM * np.cos(np.deg2rad(CASCADES[0])))
    lat = CASCADES[0] + Xraw[:, 2] / KM
    dist = np.hypot(Xraw[:, 1], Xraw[:, 2])
    print(f"lowest low within 500 km of the Cascades on {100 * np.mean(dist < 500):.0f}% of storm days, within 1000 km on {100 * np.mean(dist < 1000):.0f}%, "
          f"within 1500 km on {100 * np.mean(dist < 1500):.0f}%; median {np.median(dist):.0f} km")
    proj = ccrs.PlateCarree()
    fig, ax = plt.subplots(figsize=(10, 6.2), subplot_kw={"projection": proj})
    ax.set_extent([-158, -108, 26, 64], crs=proj)
    FM.add_map_features(ax, proj)
    b = S.SOM_BOX
    w_ = IDISP_LON_W
    ax.plot([w_, b["lon"][1], b["lon"][1], w_, w_], [b["lat"][0], b["lat"][0], b["lat"][1], b["lat"][1], b["lat"][0]], color="k", lw=1, ls="--", transform=proj)
    cm = plt.get_cmap("tab10" if k <= 10 else "tab20")
    rng = np.random.default_rng(1)
    for n in range(k):
        m = lab == n
        ax.scatter(lon[m] + rng.normal(0, 0.25, m.sum()), lat[m] + rng.normal(0, 0.25, m.sum()), s=9, color=cm(n % cm.N), alpha=0.6, transform=proj, label=f"cluster {n} ({m.sum()})")
    ax.legend(fontsize=7, loc="lower left", ncol=2, frameon=True)
    ax.set_title("Position of the lowest 500 hPa height anomaly on each storm day (dashed: the search box; star: the Cascades)", fontsize=10)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=9)
    ap.add_argument("--scan", type=int, nargs=2, default=[3, 12], metavar=("KMIN", "KMAX"))
    ap.add_argument("--refits", type=int, default=30)
    ap.add_argument("--boot", type=int, default=500)
    ap.add_argument("--days", nargs="+", default=DEFAULT_DAYS)
    ap.add_argument("--period", default="nwac")
    ap.add_argument("--skip-scan", action="store_true", help="skip the stability scan over k (the slow part)")
    ap.add_argument("--skip-test", action="store_true", help="skip the GFS test days and the SOM refit")
    a = ap.parse_args()
    S.NX, S.NY = 3, 3
    FM.S.ARGS_PCS = 0
    rng = np.random.default_rng(0)

    seasons = S.seasons_available()
    z_abs = S.load_daily("z500", seasons) / S.G
    z = S.anomalies(z_abs)
    t850_abs = S.load_daily("t850", seasons)
    t850 = S.anomalies(t850_abs)
    ivt = np.hypot(S.load_daily("ivt_u", seasons), S.load_daily("ivt_v", seasons))
    zones = pd.read_csv(S.OUT / "zone_daily.csv", index_col=0, parse_dates=True)
    names = [c[5:] for c in zones.columns if c.startswith("over_")]
    days = pd.DatetimeIndex(z.time.values)
    zt = zones.reindex(days)
    storm = zt["storm"].fillna(False).astype(bool).values & S.in_period(days, a.period)
    sea = zt["season"].values[storm].astype(int)
    lat, lon = z.latitude.values, z.longitude.values
    box = z.sel(latitude=slice(S.SOM_BOX["lat"][1], S.SOM_BOX["lat"][0]), longitude=slice(*S.SOM_BOX["lon"]))
    blat, blon = box.latitude.values, box.longitude.values
    ibox = box.sel(longitude=slice(IDISP_LON_W, S.SOM_BOX["lon"][1]))       # search region for the lowest low
    ilat, ilon = ibox.latitude.values, ibox.longitude.values
    Xraw, edge = idisp_features(ibox.values[storm], ilat, ilon)
    mu, sd = Xraw.mean(0), Xraw.std(0)
    X = (Xraw - mu) / sd
    print(f"{storm.sum()} storm days ({a.period}); IDISP features: intensity {Xraw[:, 0].mean():.0f} +/- {sd[0]:.0f} m, "
          f"dx {Xraw[:, 1].mean():.0f} +/- {sd[1]:.0f} km, dy {Xraw[:, 2].mean():.0f} +/- {sd[2]:.0f} km")
    print(f"minimum within 2 degrees of the box edge on {100 * edge.mean():.0f}% of storm days")

    # stability scan
    useasons = np.unique(sea)
    print("k   inertia   stability (median ARI, 10th pct)")
    scan = {}
    for k in ([] if a.skip_scan else range(a.scan[0], a.scan[1] + 1)):
        c, lab = kmeans(X, k, 20)
        aris = []
        for r in range(a.refits):
            pick = rng.choice(useasons, len(useasons), replace=True)
            idx = np.concatenate([np.flatnonzero(sea == s) for s in pick])
            c2, _ = kmeans(X[idx], k, 4, seed=1000 + 10 * r)
            aris.append(S.ari(lab, nearest(X, c2)[0]))
        scan[k] = (float(np.median(aris)), float(np.percentile(aris, 10)))
        print(f"{k:2d}  {((X - c[lab]) ** 2).sum():8.0f}   {scan[k][0]:.2f}  {scan[k][1]:.2f}")

    k = a.k
    c, lab = kmeans(X, k, 50)
    perm = order_by_intensity(c)
    c, lab = c[perm], np.argsort(perm)[lab]
    print(f"\nk = {k}; days per cluster:", np.bincount(lab, minlength=k).tolist())
    for n in range(k):
        r = c[n] * sd + mu
        print(f"  cluster {n}: intensity {r[0]:4.0f} m, {r[1]:+5.0f} km east, {r[2]:+5.0f} km north of the Cascades, {np.sum(lab == n)} days")
    tag = f"{a.period}_k{k}"
    pd.DataFrame({"date": days[storm], "cluster": lab}).to_csv(S.OUT / f"idisp_days_{tag}.csv", index=False)

    # zones, SOM comparison, composite maps
    res = {"period": a.period, "k": k, "n_storm_days": int(storm.sum()), "n_per_cluster": np.bincount(lab, minlength=k).tolist(),
           "stability_ari_scan": {str(kk): v for kk, v in scan.items()}, "edge_share": float(edge.mean()),
           "centroids": (c * sd + mu).round(1).tolist(), "zones": zone_ratios(lab, k, zt[storm], names, sea, a.boot, rng)}
    (S.OUT / f"idisp_results_{tag}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    zone_heatmap(res["zones"], names, res["n_per_cluster"], S.FIG / f"idisp_zones_{tag}.png", "cluster")
    nsig = sum(1 for zn in names for r in res["zones"][zn]["nodes"] if r["lo"] is not None and (r["lo"] > 1 or r["hi"] < 1))
    print(f"zone/cluster cells whose 90% range excludes 1: {nsig} of {len(names) * k}")
    somf = S.OUT / "som_days_nwac_g3x3_pc6.csv"
    if somf.exists():
        sd_ = pd.read_csv(somf, parse_dates=["date"]).set_index("date")["node"].reindex(days[storm])
        ok = sd_.notna().values
        print("adjusted Rand index, IDISP clusters vs SOM nodes:", round(S.ari(lab[ok], sd_.values[ok].astype(int)), 2))
    zstd = z.std("time").values
    zs, za, tc = z_abs.values[storm], z.values[storm] / zstd, t850_abs.values[storm] - 273.15
    ta, iv = t850.values[storm], ivt.values[storm]
    panels = []
    for n in range(k):
        m = lab == n
        r = c[n] * sd + mu
        panels.append({"title": f"Cluster {n}: {m.sum()} days ({100 * m.mean():.0f}%)\nlow {r[0]:.0f} m, {r[1]:+.0f} km E, {r[2]:+.0f} km N", "za": za[m].mean(0),
                       "zs": zs[m].mean(0), "tc": tc[m].mean(0), "ta": ta[m].mean(0), "iv": iv[m].mean(0)})
    nr = int(np.ceil(k / 3))
    FM.draw_panels(panels, nr, 3, lon, lat, f"500 hPa height patterns of Washington storm days by IDISP cluster (k={k}), Nov 15-Apr 30 (1992-2026, ERA5)",
                   "Mean standardized 500 hPa height anomaly on storm days (std. devs.)", S.FIG / f"idisp_maps_{tag}.png")
    ttl = f"850 hPa temperature on Washington storm days by IDISP cluster (k={k}), Nov 15-Apr 30 (1992-2026, ERA5)"
    tpan = [{**p_, "iv": None} for p_ in panels]            # no plume on the temperature charts: the NWS colour scale already uses green
    FM.draw_t850(tpan, nr, 3, lon, lat, ttl, S.FIG / f"idisp_t850_{tag}.png", "abs")
    FM.draw_t850(tpan, nr, 3, lon, lat, ttl.replace("temperature", "temperature anomaly"), S.FIG / f"idisp_t850anom_{tag}.png", "anom")
    plot_lows(Xraw, lab, k, S.FIG / f"idisp_lows_{tag}.png")
    cen = {n: (za[lab == n].mean(0) * zstd) for n in range(k)}             # composite anomaly in m, for the pattern correlations

    if a.skip_test:
        return

    # SOM refit for assigning the test days
    Fs = S.som_features(["z500"], z, t850, ivt, storm)
    mus = Fs.mean(0)
    _, Ssv, Vt = np.linalg.svd(Fs - mus, full_matrices=False)
    ks = int(np.searchsorted(np.cumsum(Ssv ** 2) / np.sum(Ssv ** 2), 0.90)) + 1
    Xs = (Fs - mus) @ Vt[:ks].T
    som = min((S.fit_som(Xs, s) for s in range(8)), key=lambda m: m.quantization_error(Xs))
    raw = S.assign(som, Xs)
    rel = FM.reconcile(raw.copy(), zt[storm], a.period, ks, ["z500"])
    remap = np.zeros(S.NX * S.NY, int)
    remap[raw] = rel
    somcomp = {n: z.values[storm][rel == n].mean(0) for n in range(S.NX * S.NY)}

    # test days
    td = pd.DatetimeIndex(a.days)
    g = fetch_gfs(td, lat, lon)
    zt_abs = g["z500"].values
    zt_anom = zt_abs - climatology(z_abs, td)
    gbox = xr.DataArray(zt_anom, coords={"time": td, "latitude": lat, "longitude": lon}, dims=("time", "latitude", "longitude")).sel(
        latitude=slice(S.SOM_BOX["lat"][1], S.SOM_BOX["lat"][0]), longitude=slice(*S.SOM_BOX["lon"]))
    Xt_raw, edge_t = idisp_features(gbox.sel(longitude=slice(IDISP_LON_W, S.SOM_BOX["lon"][1])).values, ilat, ilon)
    cl, d1, cl2, d2 = nearest((Xt_raw - mu) / sd, c)
    w = np.sqrt(np.cos(np.deg2rad(blat)))[:, None]
    Ft = (gbox.values * w).reshape(len(td), -1)
    sn = remap[S.assign(som, (Ft - mus) @ Vt[:ks].T)]
    wf = np.broadcast_to(np.sqrt(np.cos(np.deg2rad(blat)))[:, None], gbox.shape[1:]).ravel()
    def in_box(field):
        return xr.DataArray(field, coords={"latitude": lat, "longitude": lon}, dims=("latitude", "longitude")).sel(
            latitude=slice(S.SOM_BOX["lat"][1], S.SOM_BOX["lat"][0]), longitude=slice(*S.SOM_BOX["lon"])).values.ravel()

    somb = {n: in_box(somcomp[n]) for n in range(S.NX * S.NY)}
    idb = {n: in_box(cen[n]) for n in range(k)}
    rows = []
    for i, d in enumerate(td):
        a_i = gbox.values[i].ravel()
        som_r = {n: weighted_corr(a_i, somb[n], wf) for n in somb}
        idisp_r = {n: weighted_corr(a_i, idb[n], wf) for n in idb}
        bs = max(som_r, key=som_r.get)
        bi = max(idisp_r, key=idisp_r.get)
        rows.append({"date": d.date().isoformat(), "low_depth_m": round(float(Xt_raw[i, 0])), "dx_km": round(float(Xt_raw[i, 1])), "dy_km": round(float(Xt_raw[i, 2])),
                     "near_box_edge": bool(edge_t[i]), "idisp_cluster": int(cl[i]), "idisp_dist": round(float(d1[i]), 2), "idisp_2nd": int(cl2[i]), "idisp_2nd_dist": round(float(d2[i]), 2),
                     "som_node": int(sn[i]), "som_best_pattern_corr_node": int(bs), "som_pattern_corr": round(som_r[bs], 2), "idisp_best_pattern_corr_cluster": int(bi),
                     "idisp_pattern_corr": round(idisp_r[bi], 2), "domain_mean_anomaly_m": round(float(np.nanmean(zt_anom[i])))})
    tab = pd.DataFrame(rows)
    tab.to_csv(S.OUT / "idisp_testdays.csv", index=False)
    print("\n" + tab.to_string(index=False))

    tpan = []
    for i, d in enumerate(td):
        r = rows[i]
        tpan.append({"title": f"{d.strftime('%b %d')}: SOM node {r['som_node']}, IDISP cluster {r['idisp_cluster']}\nlow {r['low_depth_m']} m ({r['dx_km']:+d}E, {r['dy_km']:+d}N km)",
                     "za": zt_anom[i] / zstd, "zs": zt_abs[i], "tc": g["t850"].values[i] - 273.15, "iv": None})
    FM.draw_panels(tpan, int(np.ceil(len(td) / 3)), 3, lon, lat, "GFS daily-mean analyses for the requested days (anomalies from the extended fit)",
                   "Standardized 500 hPa height anomaly (std. devs.)", S.FIG / "som_testdays.png")
    print("wrote", S.FIG / "som_testdays.png")


if __name__ == "__main__":
    sys.exit(main())
