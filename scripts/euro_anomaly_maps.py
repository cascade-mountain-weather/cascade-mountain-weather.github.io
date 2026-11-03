"""ECMWF forecast anomalies over the same region and in the same style as the storm-regime maps (for the Tea Leaves page).

    python scripts/euro_anomaly_maps.py                      # both: the deterministic run and the ensemble mean
    python scripts/euro_anomaly_maps.py --model det          # deterministic (HRES) only: quick, a few minutes
    python scripts/euro_anomaly_maps.py --model eps          # ensemble (ENS, 50 members) only: slow, about half an hour
    python scripts/euro_anomaly_maps.py --days 1 2 3 4 5 6 --init "2026-11-02 00:00"

Reads the 500 hPa height and 850 hPa temperature of ECMWF's open-data forecasts through Herbie, averages the valid times of each
forecast day (a UTC day, as in the ERA5 daily means used for the regimes: 00, 06, 12 and 18 UTC for the deterministic run, 00 and
12 UTC for the ensemble because each ensemble read takes minutes), and subtracts the same three-harmonic day-of-year mean the
storm-regime maps use (fitted to ERA5 Nov-May, 1991-2026, so this is only meaningful for valid dates inside that window). The
height anomaly is standardized per grid point with the ERA5 standard deviation. For the ensemble each member is turned into an
anomaly and the maps show the mean of the 50 members, with dots where at least 80% of the members agree on the sign of the
anomaly. Writes euro_det_height_anom.png, euro_det_t850_anom.png, euro_eps_height_anom.png and euro_eps_t850_anom.png to --out
(default assets/images/tea-leaves/). Moisture transport (IVT) is not in the open-data pressure-level fields, so there is no plume.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import storm_som as S  # noqa: E402
import storm_som_fullmaps as FM  # noqa: E402
import storm_idisp as I  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
AGREE = 0.8


def latest_init(product):
    from herbie import Herbie
    now = pd.Timestamp.utcnow().tz_localize(None).floor("12h")
    for back in range(0, 8):
        t = now - pd.Timedelta(hours=12 * back)
        if Herbie(t, model="ifs", product=product, fxx=24, verbose=False).grib is not None:
            return t
    raise SystemExit(f"no ECMWF open-data {product} run found in the last four days")


def read_fields(init, valid, product, lat, lon):
    """500 hPa height (m) and 850 hPa temperature (K) at one valid time, as (members, lat, lon); one member for the deterministic run."""
    from herbie import Herbie
    step = int((valid - init) / pd.Timedelta(hours=1))
    H = Herbie(init, model="ifs", product=product, fxx=step, verbose=False)
    ds = H.xarray(r":(gh|t):(500|850):").sel(latitude=lat, longitude=lon)
    z, t = ds["gh"].sel(isobaricInhPa=500).values, ds["t"].sel(isobaricInhPa=850).values
    return (z, t) if z.ndim == 3 else (z[None], t[None])


def forecast_days(init, dates, product, hours, lat, lon):
    zs, ts = [], []
    for d in dates:
        pairs = [read_fields(init, d + pd.Timedelta(hours=h), product, lat, lon) for h in hours]
        zs.append(np.mean([p[0] for p in pairs], 0))
        ts.append(np.mean([p[1] for p in pairs], 0))
        print("  read", d.date(), flush=True)
    return np.array(zs), np.array(ts)           # (days, members, lat, lon)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["det", "eps", "both"], default="both")
    ap.add_argument("--init", default=None, help='run time UTC, e.g. "2026-11-02 00:00" (default: the latest available 00 or 12 UTC run)')
    ap.add_argument("--days", type=int, nargs="+", default=[1, 2, 3, 5, 7, 9], help="forecast days after the run date (UTC days)")
    ap.add_argument("--out", default=str(ROOT / "assets" / "images" / "tea-leaves"))
    a = ap.parse_args()

    seasons = S.seasons_available()
    z_abs = S.load_daily("z500", seasons) / S.G
    t_abs = S.load_daily("t850", seasons)
    zstd = S.anomalies(z_abs).std("time").values
    lat, lon = z_abs.latitude.values, z_abs.longitude.values
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    for model in (["det", "eps"] if a.model == "both" else [a.model]):
        product, hours, label = ("oper", (0, 6, 12, 18), "ECMWF HRES (deterministic)") if model == "det" else ("enfo", (0, 12), "ECMWF ENS mean")
        init = pd.Timestamp(a.init) if a.init else latest_init(product)
        print(f"{label}: run {init}", flush=True)
        dates = [init.normalize() + pd.Timedelta(days=d) for d in a.days]
        for d in dates:
            if not (d.month >= 11 or d.month <= 5):
                print(f"WARNING: {d.date()} is outside the Nov-May window the baseline was fitted to")
        zf, tf = forecast_days(init, dates, product, hours, lat, lon)
        zc, tc_ = I.climatology(z_abs, dates), I.climatology(t_abs, dates)
        za, ta = zf - zc[:, None], tf - tc_[:, None]                       # anomalies per member
        n = za.shape[1]
        print("  members:", n, "| domain-mean height anomaly by day (m):", np.round(za.mean((1, 2, 3))).astype(int).tolist())
        panels = []
        for i, d in enumerate(dates):
            zam, tam = za[i].mean(0), ta[i].mean(0)
            pn = {"title": f"{d.strftime('%a %b %d')}  (day +{a.days[i]})", "za": zam / zstd, "zs": zf[i].mean(0), "tc": tf[i].mean(0) - 273.15, "ta": tam, "iv": None}
            if n > 1:
                fz, ft = (za[i] > 0).mean(0), (ta[i] > 0).mean(0)
                pn["stip"] = np.maximum(fz, 1 - fz) >= AGREE
                pn["stip_t"] = np.maximum(ft, 1 - ft) >= AGREE
                pn["stip_note"] = f"{AGREE:.0%} or more of the {n} members agree on the sign"
            panels.append(pn)
        nr = int(np.ceil(len(panels) / 3))
        run = f"{label}, run {init.strftime('%Y-%m-%d %H')} UTC"
        FM.draw_panels(panels, nr, 3, lon, lat, f"{run}: 500 hPa height", "Standardized 500 hPa height anomaly (std. devs.)", out / f"euro_{model}_height_anom.png")
        FM.draw_t850(panels, nr, 3, lon, lat, f"{run}: 850 hPa temperature anomaly", out / f"euro_{model}_t850_anom.png", "anom")
        print("  wrote", out / f"euro_{model}_height_anom.png", out / f"euro_{model}_t850_anom.png", flush=True)


if __name__ == "__main__":
    sys.exit(main())
