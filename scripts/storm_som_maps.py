"""500 hPa height maps of the storm-type SOM nodes, on a map with state, provincial and country outlines.

    python scripts/storm_som_maps.py

Refits the 3x3 SOM exactly as scripts/storm_som.py does (same seasons rule, same input, same seeds), then draws, for each node, the
mean 500 hPa height ANOMALY on storm days as filled contours (m, blue = lower than normal) with the mean 500 hPa HEIGHT as black
contour lines (dam), over the outlines of US states, Canadian provinces and the coast. Writes docs/storms/som_height_maps.png.
"""
import argparse
import sys
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import storm_som as ss  # noqa: E402

LEVELS_ANOM = np.arange(-150, 151, 15)
STATES = cfeature.NaturalEarthFeature("cultural", "admin_1_states_provinces_lines", "50m", edgecolor="#6b7280", facecolor="none", linewidth=0.6)
COUNTRIES = cfeature.NaturalEarthFeature("cultural", "admin_0_boundary_lines_land", "50m", edgecolor="#6b7280", facecolor="none", linewidth=1.1)
COAST = cfeature.NaturalEarthFeature("physical", "coastline", "50m", edgecolor="#6b7280", facecolor="none", linewidth=0.8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-heights", action="store_true", help="leave the mean 500 hPa height lines off")
    args = ap.parse_args()
    seasons = ss.seasons_available()
    z_raw = ss.load_daily("z500", seasons) / ss.G
    z = ss.anomalies(ss.load_daily("z500", seasons)) / ss.G
    t850 = ss.load_daily("t850", seasons) - 273.15           # mean 850 hPa temperature, C
    days = pd.DatetimeIndex(z.time.values)
    zt = pd.read_csv(ss.OUT / "zone_daily.csv", index_col=0, parse_dates=True).reindex(days)
    storm = zt["storm"].fillna(False).astype(bool).values

    box = z.sel(latitude=slice(ss.SOM_BOX["lat"][1], ss.SOM_BOX["lat"][0]), longitude=slice(*ss.SOM_BOX["lon"]))
    w = np.sqrt(np.cos(np.deg2rad(box.latitude.values)))[:, None]
    F = (box.values * w).reshape(len(days), -1)[storm]
    mu = F.mean(0)
    _, S, Vt = np.linalg.svd(F - mu, full_matrices=False)
    k = int(np.searchsorted(np.cumsum(S ** 2) / np.sum(S ** 2), 0.90)) + 1
    X = (F - mu) @ Vt[:k].T
    seeds = 4
    best = min((ss.fit_som(X, s) for s in range(seeds)), key=lambda m: m.quantization_error(X))
    node = ss.assign(best, X)
    print(f"{len(seasons)} seasons ({seasons[0]}-{seasons[-1]}), {storm.sum()} storm days, node sizes {np.bincount(node, minlength=9).tolist()}")

    lat, lon = z.latitude.values, z.longitude.values
    za, zr, tr = z.values[storm], z_raw.values[storm], t850.values[storm]
    proj = ccrs.Mercator(central_longitude=-139)    # a lon/lat rectangle stays a rectangle, so the data fill the panel
    fig, axs = plt.subplots(ss.NX, ss.NY, figsize=(15, 11.5), subplot_kw={"projection": proj})
    cf = None
    for n, ax in enumerate(axs.ravel()):
        m = node == n
        ax.set_extent([-168, -110, 28, 62], crs=ccrs.PlateCarree())
        cf = ax.contourf(lon, lat, za[m].mean(0), levels=LEVELS_ANOM, cmap="RdBu_r", extend="both", transform=ccrs.PlateCarree())
        tm = tr[m].mean(0)
        ct = ax.contour(lon, lat, tm, levels=[v for v in range(-30, 31, 3) if v != 0], colors="#dc2626", linewidths=0.9, linestyles=["--" if v < 0 else "-" for v in range(-30, 31, 3) if v != 0], transform=ccrs.PlateCarree(), zorder=4)
        ax.clabel(ct, fmt="%d", fontsize=7, inline=True, colors="#b91c1c")
        ax.contour(lon, lat, tm, levels=[0], colors="#dc2626", linewidths=2.2, linestyles="-", transform=ccrs.PlateCarree(), zorder=4)
        if not args.no_heights:
            ch = ax.contour(lon, lat, zr[m].mean(0) / 10.0, levels=np.arange(480, 600, 6), colors="k", linewidths=0.8, transform=ccrs.PlateCarree(), zorder=3)
            ax.clabel(ch, fmt="%d", fontsize=7, inline=True)
        ax.add_feature(COAST, zorder=5)
        ax.add_feature(STATES, zorder=5)
        ax.add_feature(COUNTRIES, zorder=5)
        gl = ax.gridlines(draw_labels=False, linewidth=0.3, color="#94a3b8", alpha=0.6, linestyle=":")
        ax.plot([-121.7], [47.5], marker="*", color="#f59e0b", markeredgecolor="k", ms=12, transform=ccrs.PlateCarree(), zorder=10)
        ax.set_title(f"Node {n}: {m.sum()} storm days ({100 * m.mean():.0f}%)", fontsize=11)
    fig.subplots_adjust(hspace=0.12, wspace=0.04, top=0.93)
    cb = fig.colorbar(cf, ax=axs, shrink=0.6, pad=0.02, label="Mean 500 hPa height anomaly on storm days (m)")
    cb.ax.tick_params(labelsize=9)
    fig.suptitle(f"500 hPa height patterns of Washington storm days, 3x3 SOM ({seasons[0]}-{seasons[-1]}, ERA5)   star = Cascades", fontsize=13, y=0.985)
    fig.text(0.5, 0.955, "black lines: mean 500 hPa height (dam)     red lines: mean 850 hPa temperature (C), every 3, dashed below 0, heavy line = 0 C", ha="center", fontsize=10.5)
    out = ss.FIG / "som_height_maps.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    print("wrote", out)


if __name__ == "__main__":
    sys.exit(main())
