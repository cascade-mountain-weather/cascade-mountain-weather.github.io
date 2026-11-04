"""The next 72 hours of ECMWF forecast, as scrollable anomaly maps and a storm-pattern call for each day, for the Tea Leaves page.

    python scripts/pattern_forecast.py                    # latest run, deterministic and ensemble: fetch (slow), then build
    python scripts/pattern_forecast.py --model det        # deterministic only (a few minutes)
    python scripts/pattern_forecast.py --no-fetch         # rebuild from the cached reads
    python scripts/pattern_forecast.py --init "2026-11-03 00:00" --workers 4

Needs data/forecast_model/pattern_model.npz (scripts/pattern_model.py), which carries the ERA5 baseline, so the ERA5 years themselves
are not needed.

Fetch: 500 hPa height and 850 hPa temperature every 12 h out to 120 h for the 50 ensemble members and the deterministic run, and
total precipitation over the Cascades at the start and end of each UTC day to be classified (a few steps). Reads are cached in
data/forecast_cache/ (gitignored).

Build: (1) one PNG per variable, model and 12-hour step in assets/forecast/frames/ for the scrolling viewer; (2) for every
UTC day with both its 00 and 12 UTC frames, each member's daily-mean 500 hPa height anomaly is turned into the same three IDISP
numbers as the storm days (depth and position of the lowest low west of Anchorage's longitude) and assigned to the nearest of the six
patterns, or to "no good match" if it is farther from every centre than 90% of the storm days are from their own; the share of members
per pattern, with the chance of a storm day (a member's mean precipitation over the Cascades box of at least STORM_MM) is written to
assets/forecast/pattern_forecast.json. The pattern-by-zone table is copied to assets/forecast/pattern_zones.json. Nothing in assets/forecast/
is committed: like the satellite looper, a workflow would force-push it as one commit on the forecast-data branch and the page reads it from there,
so the repository does not grow with the frames (the page falls back to the local assets/forecast/ when that branch is not reachable).
"""
import argparse
import json
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data" / "forecast_model"
CACHE = ROOT / "data" / "forecast_cache"
STEPS = list(range(0, 121, 12))
PRODUCT = {"det": "oper", "eps": "enfo"}
LABEL = {"det": "ECMWF HRES", "eps": "ECMWF ENS mean"}
BOX = (46.0, 49.0, -123.0, -120.5)         # Cascades and Olympics: lat min/max, lon min/max, for the precipitation
STORM_MM = 6.0                              # about a quarter inch of water, the storm-day threshold of the SNOTEL analysis
AGREE = 0.9
NPAT = 6


def design(doy):
    ang = 2 * np.pi * np.asarray(doy, float) / 366.0
    return np.column_stack([np.ones_like(ang)] + [f(k * ang) for k in (1, 2, 3) for f in (np.cos, np.sin)])


def cache_file(model, init, step, kind):
    return CACHE / f"{model}_{init:%Y%m%d%H}_{step:03d}_{kind}.npz"


# ------------------------------------------------------------------ fetch
def fetch_one(job):
    """Read one forecast time and cache it (a worker process). kind is 'zt' (height and temperature on the 1-degree grid) or 'tp' (box-mean precipitation)."""
    model, init, step, kind = job
    f = cache_file(model, init, step, kind)
    if f.exists():
        return f"cached {f.name}"
    from herbie import Herbie
    H = Herbie(init, model="ifs", product=PRODUCT[model], fxx=step, verbose=False)
    if kind == "zt":
        m = np.load(MODEL / "pattern_model.npz")
        ds = H.xarray(r":(gh|t):(500|850):").sel(latitude=m["lat"], longitude=m["lon"])
        z, t = ds["gh"].sel(isobaricInhPa=500).values, ds["t"].sel(isobaricInhPa=850).values
        if z.ndim == 2:
            z, t = z[None], t[None]
        np.savez_compressed(f, z=z.astype("float32"), t=t.astype("float32"))
    else:
        if step == 0:
            n = 50 if model == "eps" else 1
            np.savez_compressed(f, tp=np.zeros(n, "float32"))
        else:
            ds = H.xarray(r":tp:").sel(latitude=slice(BOX[1], BOX[0]), longitude=slice(BOX[2], BOX[3]))
            tp = ds["tp"].values * 1000.0
            tp = tp.reshape(tp.shape[0], -1) if tp.ndim == 3 else tp.reshape(1, -1)
            np.savez_compressed(f, tp=tp.mean(1).astype("float32"))
    return f"read {f.name}"


def forecast_days(init):
    """UTC days with both a 00 and a 12 UTC frame in the 120 hours: [(date, step at 00 UTC, step at 12 UTC, step at the next 00 UTC)]."""
    out = []
    for d in sorted({(init + pd.Timedelta(hours=s)).normalize() for s in STEPS}):
        s0 = int((d - init) / pd.Timedelta(hours=1))
        if s0 in STEPS and s0 + 12 in STEPS:
            out.append((d, s0, s0 + 12, s0 + 24))
    return out


def fetch(models, init, workers):
    days = forecast_days(init)
    jobs = []
    for model in models:
        jobs += [(model, init, s, "zt") for s in STEPS]
        jobs += [(model, init, s, "tp") for s in sorted({x for d in days for x in (d[1], d[3]) if x > 0})]
    jobs = [j for j in jobs if not cache_file(*j[:3], j[3]).exists()]
    print(f"fetching {len(jobs)} reads with {workers} workers (an ensemble height/temperature read is about 3 minutes each)", flush=True)
    if not jobs:
        return
    with ProcessPoolExecutor(workers) as ex:
        for msg in ex.map(fetch_one, jobs):
            print(" ", msg, flush=True)


def load_model(model, init):
    zs, ts = [], []
    for s in STEPS:
        d = np.load(cache_file(model, init, s, "zt"))
        zs.append(d["z"]), ts.append(d["t"])
    return np.array(zs), np.array(ts)            # (steps, members, lat, lon)


# ------------------------------------------------------------------ maps
def draw_frame(kind, lon, lat, za, zs, tc, ta, stip, title, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import cartopy.crs as ccrs
    import storm_som_fullmaps as FM
    proj = ccrs.PlateCarree()
    fig, ax = plt.subplots(figsize=(7.4, 5.4), subplot_kw={"projection": proj}, constrained_layout=True)
    ax.set_extent([-150, -105, 33, 62], crs=proj)
    ax.set_aspect("auto")
    if kind == "height_anom":
        cf = ax.contourf(lon, lat, za, levels=np.arange(-2.4, 2.41, 0.3), cmap="RdBu_r", extend="both", transform=proj)
        cz = ax.contour(lon, lat, zs / 10, levels=np.arange(480, 600, 6), colors="k", linewidths=0.9, transform=proj)
        ax.clabel(cz, fmt="%d", fontsize=7)
        ax.contour(lon, lat, tc, levels=[0], colors="#dc2626", linewidths=2.2, transform=proj)
        cb = "500 hPa height anomaly (std. devs.)"
        ticks = np.arange(-2.4, 2.41, 0.6)
    else:
        lv = np.arange(-8, 8.1, 1)
        cf = ax.contourf(lon, lat, ta, levels=lv, cmap="RdBu_r", extend="both", transform=proj)
        ax.contour(lon, lat, ta, levels=[0], colors="#1e293b", linewidths=0.8, transform=proj)
        ax.contour(lon, lat, tc, levels=[0], colors="#1e293b", linewidths=2.0, linestyles="dashed", transform=proj)
        ax.contour(lon, lat, zs / 10, levels=np.arange(480, 600, 6), colors="#475569", linewidths=0.6, alpha=0.7, transform=proj)
        cb = "850 hPa temperature anomaly (K)"
        ticks = lv[::2]
    if stip is not None:
        FM.add_stipple(ax, lon, lat, stip, proj)
    FM.add_map_features(ax, proj)
    ax.set_title(title, fontsize=12)
    fig.colorbar(cf, ax=ax, shrink=0.95, aspect=30, pad=0.02, ticks=ticks, label=cb)
    fig.savefig(out, dpi=100, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ pattern call
def call_patterns(za_day, lat, lon, m):
    """za_day: (members, lat, lon) daily-mean height anomaly (m). Returns per-member pattern (-1 = no good match) and distance."""
    import storm_idisp as I
    lm = (lat >= 30) & (lat <= 60)
    om = (lon >= m["ilon_w"]) & (lon <= -115)
    X, _ = I.idisp_features(za_day[:, lm][:, :, om], lat[lm], lon[om])
    Xs = (X - m["mu"]) / m["sd"]
    near, dist, near2, _ = I.nearest(Xs, m["centroids"])
    return np.where(dist > float(m["cutoff"]), -1, near), dist, near, near2, X


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["det", "eps", "both"], default="both")
    ap.add_argument("--init", default=None, help='run time UTC, e.g. "2026-11-03 00:00" (default: the latest available run of the ensemble)')
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--fetch-only", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "assets" / "forecast"), help="frames/ and the two JSON files go here (gitignored; published to the forecast-data branch)")
    a = ap.parse_args()
    models = ["det", "eps"] if a.model == "both" else [a.model]
    CACHE.mkdir(parents=True, exist_ok=True)
    if a.init:
        init = pd.Timestamp(a.init)
    else:
        import euro_anomaly_maps as E
        init = E.latest_init(PRODUCT[models[-1]])
    print("run:", init, flush=True)
    if not a.no_fetch:
        fetch(models, init, a.workers)
    if a.fetch_only:
        return

    m = np.load(MODEL / "pattern_model.npz")
    lat, lon, zstd = m["lat"], m["lon"], m["zstd"]
    valid = [init + pd.Timedelta(hours=s) for s in STEPS]
    doy = np.array([v.dayofyear + v.hour / 24 for v in valid])
    clim_z = (design(doy) @ m["beta_z"]).reshape(len(STEPS), len(lat), len(lon))
    clim_t = (design(doy) @ m["beta_t"]).reshape(len(STEPS), len(lat), len(lon))
    data = Path(a.out)
    img = data / "frames"
    img.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    days = forecast_days(init)
    out = {"init": f"{init:%Y-%m-%d %H}Z", "steps": STEPS, "valid": [f"{v:%a %b %d %H}Z" for v in valid], "models": {}}

    for model in models:
        Z, T = load_model(model, init)
        n = Z.shape[1]
        za, ta = Z - clim_z[:, None], T - clim_t[:, None]
        print(f"{model}: {n} member(s); domain-mean height anomaly by step (m):", np.round(za.mean((1, 2, 3))).astype(int).tolist(), flush=True)
        for i, s in enumerate(STEPS):
            zam, tam = za[i].mean(0), ta[i].mean(0)
            stip_z = stip_t = None
            if n > 1:
                fz, ft = (za[i] > 0).mean(0), (ta[i] > 0).mean(0)
                stip_z, stip_t = np.maximum(fz, 1 - fz) >= AGREE, np.maximum(ft, 1 - ft) >= AGREE
            title = f"{LABEL[model]}  {valid[i]:%a %b %d %H}Z  (+{s} h)"
            for kind, st in (("height_anom", stip_z), ("t850_anom", stip_t)):
                draw_frame(kind, lon, lat, zam / zstd, Z[i].mean(0), T[i].mean(0) - 273.15, tam, st, title, img / f"{model}_{kind}_{s:03d}.png")
        print("  wrote", len(STEPS) * 2, "frames", flush=True)

        rows = []
        for d, s0, s12, s24 in days:
            i0, i12 = STEPS.index(s0), STEPS.index(s12)
            zday = (Z[i0] + Z[i12]) / 2
            clim_d = (design([d.dayofyear]) @ m["beta_z"]).reshape(len(lat), len(lon))
            lab, dist, near, near2, X = call_patterns(zday - clim_d, lat, lon, m)
            tp = np.load(cache_file(model, init, s24, "tp"))["tp"] - np.load(cache_file(model, init, s0, "tp"))["tp"]
            votes = {str(p): int((lab == p).sum()) for p in range(NPAT)}
            votes["none"] = int((lab == -1).sum())
            row = {"date": f"{d:%Y-%m-%d}", "label": f"{d:%a %b %d}", "members": n, "votes": votes, "pattern": int(np.bincount(near, minlength=NPAT).argmax()),
                   "median_distance": round(float(np.median(dist)), 2), "p_storm": round(float((tp >= STORM_MM).mean()), 2),
                   "precip_mm": [round(float(x), 1) for x in np.percentile(tp, [25, 50, 75])],
                   "lowest_low": {"intensity_m": round(float(np.median(X[:, 0]))), "km_east": round(float(np.median(X[:, 1]))), "km_north": round(float(np.median(X[:, 2])))}}
            row["call"] = max(votes, key=votes.get)
            rows.append(row)
            print(f"  {d:%a %b %d}: votes {votes}  p(storm) {row['p_storm']:.2f}  precip {row['precip_mm']} mm  low {row['lowest_low']}", flush=True)
        out["models"][model] = {"label": LABEL[model], "days": rows}

    (data / "pattern_forecast.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    shutil.copy(MODEL / "pattern_zones.json", data / "pattern_zones.json")
    print("wrote", data / "pattern_forecast.json")


if __name__ == "__main__":
    sys.exit(main())
