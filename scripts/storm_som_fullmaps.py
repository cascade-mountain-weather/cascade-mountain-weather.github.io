"""Per-node composite maps for the storm SOM: 500 hPa height (black contours, dam), its anomaly (shading), 850 hPa temperature
(red contours, C, heavy line at 0) and the moisture plume (green, IVT), on a cartopy map. Also writes data/storms/som_days_<tag>.csv
(the node of every storm day). Refits the same SOM as scripts/storm_som.py (same seeds, so the same nodes).

    python scripts/storm_som_fullmaps.py --grid 2 3 --pcs 2            # all four periods
    python scripts/storm_som_fullmaps.py --grid 2 3 --pcs 2 --period mid

Writes docs/storms/som_fullmaps_<period>_g<NX>x<NY>_pc<k>.png (--no-ivt drops the green lines). Check the printed days per node against som_results_*.json.
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
import cartopy.crs as ccrs
import cartopy.feature as cfeature

sys.path.insert(0, str(Path(__file__).resolve().parent))
import storm_som as S  # noqa: E402


def reconcile(node, zt, period, k, fields):
    """The refit can come out with the nodes numbered differently from the stats run. Relabel so that every node's days and
    over-performance days per zone match som_results_<tag>.json exactly (so maps line up with the heatmaps)."""
    tag = period if ((S.NX, S.NY) == (3, 3) and not S.ARGS_PCS) else f"{period}_g{S.NX}x{S.NY}_pc{k}"
    if fields != ["z500"]:
        tag += "_" + "+".join(fields)
    f = S.OUT / f"som_results_{tag}.json"
    if not f.exists():
        print("no", f.name, "- node numbers are not checked against the stats run")
        return node
    res = json.loads(f.read_text(encoding="utf-8"))
    names = list(res["zones"])
    want = [tuple((z["nodes"][n]["days"], z["nodes"][n]["over_days"]) for z in res["zones"].values()) for n in range(S.NX * S.NY)]
    have = []
    for n in range(S.NX * S.NY):
        sig = []
        for zn in names:
            d = zt[zn].notna().values & (node == n)
            sig.append((int(d.sum()), int(zt[f"over_{zn}"].fillna(False).astype(bool).values[d].sum())))
        have.append(tuple(sig))
    if sorted(have) != sorted(want) or len(set(want)) != len(want):
        print("WARNING: the refit does not reproduce", f.name, "- node numbers may not match the heatmap")
        return node
    remap = np.array([want.index(h) for h in have])
    print("relabelled nodes to match the stats run:", remap.tolist())
    return remap[node]


def draw_panels(panels, nrows, ncols, lon, lat, title, cbar_label, out):
    """One cartopy map per panel: standardized 500 hPa height anomaly (shading), 500 hPa height (black, dam), 850 hPa
    temperature (red, C, heavy at 0) and, when a panel has "iv", IVT 250 and 500 kg/m/s (green).
    Each panel is a dict with title, za (standardized anomaly), zs (height, m), tc (C) and iv (or None)."""
    proj = ccrs.PlateCarree()
    fig, axs = plt.subplots(nrows, ncols, figsize=(4.6 * ncols, 4.5 * nrows), subplot_kw={"projection": proj}, constrained_layout=True)
    flat = np.atleast_1d(axs).ravel()
    for ax in flat[len(panels):]:
        ax.set_visible(False)
    for ax, pn in zip(flat, panels):
        ax.set_extent([-150, -105, 33, 62], crs=proj)
        ax.set_aspect("auto")
        cf = ax.contourf(lon, lat, pn["za"], levels=np.arange(-2.4, 2.41, 0.3), cmap="RdBu_r", extend="both", transform=proj)
        cz = ax.contour(lon, lat, pn["zs"] / 10, levels=np.arange(480, 600, 6), colors="k", linewidths=0.9, transform=proj)
        ax.clabel(cz, fmt="%d", fontsize=7)
        lv = [l for l in np.arange(-24, 25, 3) if l]
        ct = ax.contour(lon, lat, pn["tc"], levels=lv, colors="#dc2626", linewidths=1.0, transform=proj)
        ct.set_linestyles(["dashed" if l < 0 else "solid" for l in ct.levels])
        ax.clabel(ct, fmt="%d", fontsize=7)
        ax.contour(lon, lat, pn["tc"], levels=[0], colors="#dc2626", linewidths=2.6, transform=proj)
        if pn.get("iv") is not None:
            add_plume(ax, lon, lat, pn["iv"], proj)
        if pn.get("stip") is not None:
            add_stipple(ax, lon, lat, pn["stip"], proj)
        add_map_features(ax, proj)
        ax.set_title(pn["title"], fontsize=11)
    fig.colorbar(cf, ax=axs, shrink=0.95, aspect=45, pad=0.02, ticks=np.arange(-2.4, 2.41, 0.6), label=cbar_label)
    has_iv = any(pn.get("iv") is not None for pn in panels)
    fig.suptitle(f"{title}   star = Cascades\n"
                 "black lines: 500 hPa height (dam)     red lines: 850 hPa temperature (C), every 3, dashed below 0, heavy line = 0 C"
                 + ("     green shading: IVT 250 / 500 / 750 kg/m/s" if has_iv else "")
                 + (f"     dots: {panels[0]['stip_note']}" if panels[0].get("stip") is not None else ""), fontsize=12)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)


def add_plume(ax, lon, lat, iv, proj):
    """Moisture plume: translucent green fill at IVT 250, 500 and 750 kg/m/s (darker = more) with a thin edge at each level."""
    ax.contourf(lon, lat, iv, levels=[250, 500, 750, 5000], colors=["#4ade80", "#16a34a", "#14532d"], alpha=0.38, transform=proj, zorder=3)
    ax.contour(lon, lat, iv, levels=[250, 500, 750], colors="#14532d", linewidths=[0.6, 0.9, 1.2], transform=proj, zorder=3)


def add_stipple(ax, lon, lat, mask, proj):
    """Dots where `mask` is True (used for 'most ensemble members agree on the sign of the anomaly')."""
    ax.contourf(lon, lat, mask.astype(float), levels=[0.5, 1.5], colors="none", hatches=["..."], transform=proj, zorder=4)


def add_map_features(ax, proj):
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), edgecolor="#64748b", linewidth=0.7)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), edgecolor="#94a3b8", linewidth=0.6)
    ax.add_feature(cfeature.STATES.with_scale("50m"), edgecolor="#94a3b8", linewidth=0.4)
    ax.plot([-121.7], [47.5], marker="*", color="orange", mec="k", ms=13, transform=proj, zorder=10)


# anchors for an NWS-style 850 hPa temperature chart: purples and blues below freezing, greens just above, yellow to red when warm
NWS_T850 = matplotlib.colors.LinearSegmentedColormap.from_list(
    "nws_t850", [(0.0, "#3b0a70"), (0.15, "#2b3a9a"), (0.30, "#3b8fd9"), (0.42, "#9fd8f2"), (0.50, "#e9f6fb"),
                 (0.56, "#b9e3a8"), (0.66, "#6cc66a"), (0.76, "#f5e65a"), (0.86, "#f2a03a"), (0.94, "#d9372b"), (1.0, "#8a0f1f")])


def draw_t850(panels, nrows, ncols, lon, lat, title, out, kind="abs"):
    """NWS-style 850 hPa temperature chart for each panel (kind="abs": filled isotherms every 3 C, heavy 0 C line, 500 hPa
    height in thin grey) or its anomaly (kind="anom": departure from the day-of-year mean, K). Panels need tc (C), ta (K), zs (m)
    and optionally iv for the translucent plume."""
    proj = ccrs.PlateCarree()
    fig, axs = plt.subplots(nrows, ncols, figsize=(4.6 * ncols, 4.5 * nrows), subplot_kw={"projection": proj}, constrained_layout=True)
    flat = np.atleast_1d(axs).ravel()
    for ax in flat[len(panels):]:
        ax.set_visible(False)
    lv = np.arange(-30, 31, 3) if kind == "abs" else np.arange(-8, 8.1, 1)
    for ax, pn in zip(flat, panels):
        ax.set_extent([-150, -105, 33, 62], crs=proj)
        ax.set_aspect("auto")
        if kind == "abs":
            cf = ax.contourf(lon, lat, pn["tc"], levels=lv, cmap=NWS_T850, extend="both", transform=proj)
            ci = ax.contour(lon, lat, pn["tc"], levels=lv, colors="#1e293b", linewidths=0.4, transform=proj)
            ax.contour(lon, lat, pn["tc"], levels=[0], colors="#1e293b", linewidths=2.2, transform=proj)
            ax.clabel(ci, levels=[l for l in lv if l % 6 == 0], fmt="%d", fontsize=7)
            ax.contour(lon, lat, pn["zs"] / 10, levels=np.arange(480, 600, 6), colors="#475569", linewidths=0.6, alpha=0.7, transform=proj)
        else:
            cf = ax.contourf(lon, lat, pn["ta"], levels=lv, cmap="RdBu_r", extend="both", transform=proj)
            ax.contour(lon, lat, pn["ta"], levels=[0], colors="#1e293b", linewidths=0.8, transform=proj)
            ax.contour(lon, lat, pn["tc"], levels=[0], colors="#1e293b", linewidths=2.0, linestyles="dashed", transform=proj)
        if pn.get("iv") is not None:
            add_plume(ax, lon, lat, pn["iv"], proj)
        if pn.get("stip_t") is not None and kind == "anom":
            add_stipple(ax, lon, lat, pn["stip_t"], proj)
        add_map_features(ax, proj)
        ax.set_title(pn["title"], fontsize=11)
    fig.colorbar(cf, ax=axs, shrink=0.95, aspect=45, pad=0.02, ticks=lv[::2] if kind == "abs" else lv[::2],
                 label="850 hPa temperature (C)" if kind == "abs" else "850 hPa temperature anomaly (K)")
    has_iv = any(pn.get("iv") is not None for pn in panels)
    sub = ("filled isotherms every 3 C, heavy line = 0 C, grey lines: 500 hPa height (dam)" if kind == "abs"
           else "anomaly from the day-of-year mean (K); dashed line = 0 C isotherm")
    note = f"     dots: {panels[0]['stip_note']}" if panels[0].get("stip_t") is not None and kind == "anom" else ""
    fig.suptitle(f"{title}   star = Cascades\n{sub}" + ("     green shading: IVT 250 / 500 / 750 kg/m/s" if has_iv else "") + note, fontsize=12)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)


def run(a, period):
    seasons = S.seasons_available()
    z_abs = S.load_daily("z500", seasons) / S.G
    z = S.anomalies(z_abs)
    t850_abs = S.load_daily("t850", seasons)
    t850 = S.anomalies(t850_abs)
    ivt = np.hypot(S.load_daily("ivt_u", seasons), S.load_daily("ivt_v", seasons))
    zones = pd.read_csv(S.OUT / "zone_daily.csv", index_col=0, parse_dates=True)
    days = pd.DatetimeIndex(z.time.values)
    storm = zones.reindex(days)["storm"].fillna(False).astype(bool).values & S.in_period(days, period)

    F = S.som_features(a.fields, z, t850, ivt, storm)
    mu = F.mean(0)
    U, Sv, Vt = np.linalg.svd(F - mu, full_matrices=False)
    k = a.pcs or int(np.searchsorted(np.cumsum(Sv ** 2) / np.sum(Sv ** 2), 0.90)) + 1
    X = (F - mu) @ Vt[:k].T
    best = min((S.fit_som(X, s) for s in range(a.seeds)), key=lambda m: m.quantization_error(X))
    node = S.assign(best, X)
    node = reconcile(node, zones.reindex(days)[storm], period, k, a.fields)
    print(period, "days per node:", np.bincount(node, minlength=S.NX * S.NY).tolist())

    # storm-day node assignments, for scripts/storm_som_mjo.py
    tag = f"{period}_g{S.NX}x{S.NY}_pc{k}" + ("" if a.fields == ["z500"] else "_" + "+".join(a.fields))
    pd.DataFrame({"date": days[storm], "node": node}).to_csv(S.OUT / f"som_days_{tag}.csv", index=False)

    lat, lon = z.latitude.values, z.longitude.values
    zstd = z.std("time").values                       # per-grid-point standard deviation over every day of the seasons used
    zs, za, iv = z_abs.values[storm], z.values[storm] / zstd, ivt.values[storm]
    tc = t850_abs.values[storm] - 273.15
    panels = []
    for n in range(S.NX * S.NY):
        m = node == n
        panels.append({"title": f"Node {n}: {m.sum()} storm days ({100 * m.mean():.0f}%)", "za": za[m].mean(0), "zs": zs[m].mean(0),
                       "tc": tc[m].mean(0), "iv": iv[m].mean(0) if a.ivt else None})
    span = f"{int(z.time.dt.year.min()) + 1}-{int(z.time.dt.year.max())}"
    when = {"nwac": "Nov 15-Apr 30", "all": "Nov-May", "early": "Nov-Dec", "mid": "Jan-Mar", "late": "Apr-May"}[period]
    out = S.FIG / f"som_fullmaps_{tag}.png"
    draw_panels(panels, S.NX, S.NY, lon, lat, f"500 hPa height patterns of Washington storm days, {when}, {S.NX}x{S.NY} SOM ({span}, ERA5)",
                "Mean standardized 500 hPa height anomaly on storm days (std. devs.)", out)
    print("wrote", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=list(S.PERIODS), nargs="+", default=list(S.PERIODS))
    ap.add_argument("--grid", type=int, nargs=2, default=[3, 3], metavar=("NX", "NY"))
    ap.add_argument("--pcs", type=int, default=0)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--ivt", action=argparse.BooleanOptionalAction, default=True, help="overlay IVT 250 and 500 kg/m/s (green)")
    ap.add_argument("--fields", nargs="+", choices=["z500", "t850", "ivt"], default=["z500"])
    a = ap.parse_args()
    S.NX, S.NY = a.grid
    S.ARGS_PCS = a.pcs
    for p in a.period:
        run(a, p)


if __name__ == "__main__":
    sys.exit(main())
