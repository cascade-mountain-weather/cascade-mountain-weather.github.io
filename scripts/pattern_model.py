"""Everything the live pattern forecast needs from the ERA5 storm-day analysis, saved as two small files so the forecast script
does not need the ERA5 years (and can run on a GitHub runner later).

    python scripts/pattern_model.py                  # needs the cached ERA5 in data/era5 and data/storms from storm_idisp.py --k 6

Writes data/forecast_model/pattern_model.npz:
  lat, lon         the 1-degree ERA5 grid (20-65 N, 180-100 W)
  beta_z, beta_t   three-harmonic day-of-year fit (7 coefficients per grid point) of daily-mean 500 hPa height (m) and 850 hPa
                   temperature (K), fitted to Nov-May 1991-2026, so a forecast anomaly is forecast minus the fit
  zstd             standard deviation of the 500 hPa height anomaly at each grid point (m), to standardize it
  mu, sd           mean and spread of the IDISP features (intensity m, km east, km north) over the storm days
  centroids        the six cluster centres in those standardized features, cluster 0 = deepest low
  cutoff           distance (standardized units) to the own centre that 90% of the storm days are within; a forecast farther
                   from every centre than this is called "no good match"
and data/forecast_model/pattern_zones.json: for every pattern and zone, how often the zone beat (over) or fell short of (under)
what it usually gets for a storm of that size, the same for all storm days, and a verdict (over / under / average) from a
season-resampled 90% range on the difference (over rate minus under rate) from all storm days.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

sys.path.insert(0, str(Path(__file__).resolve().parent))
import storm_som as S  # noqa: E402
import storm_idisp as I  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "forecast_model"
K, PERIOD, NBOOT = 6, "nwac", 1000
CUT_PCT = 90
XGRID = np.round(np.arange(-1.5, 2.5001, 0.05), 2)     # inches of water vs expectation, for the curves on the page
KDE_BW = 0.12


def harmonic_beta(da):
    doy = da.time.dt.dayofyear.values
    beta, *_ = np.linalg.lstsq(I.harmonic_design(doy), da.values.reshape(len(doy), -1), rcond=None)
    return beta.astype("float32")


def density(a):
    """Smooth density (per inch) of storm-day anomalies on XGRID: a Gaussian kernel about KDE_BW inches wide."""
    g = np.linspace(-4, 6, 2000)
    return np.interp(XGRID, g, gaussian_kde(a, bw_method=KDE_BW / a.std())(g))


def spread(a):
    q = np.percentile(a, [25, 50, 75])
    return {"mean": round(float(a.mean()), 3), "q25": round(float(q[0]), 2), "q50": round(float(q[1]), 2), "q75": round(float(q[2]), 2), "f": [round(float(v), 3) for v in density(a)]}


def zone_table(lab, zt, names, sea, rng):
    """Per zone and pattern: P(over), P(under), and the verdict from net = P(over) - P(under) against all storm days."""
    useasons = np.unique(sea)
    boots = [np.concatenate([np.flatnonzero(sea == s) for s in rng.choice(useasons, len(useasons), replace=True)]) for _ in range(NBOOT)]
    out = {}
    for zn in names:
        have = zt[zn].notna().values
        over = zt[f"over_{zn}"].fillna(False).astype(bool).values
        under = zt[f"under_{zn}"].fillna(False).astype(bool).values
        net = over.astype(float) - under.astype(float)
        anom = zt[f"anom_{zn}"].values
        okn = have & ~np.isnan(anom)
        typical = float(zt[zn].values[okn].mean())                    # the zone's average storm-day water gain (in), the "usual storm"
        a0 = np.where(okn, anom, 0.0)
        base = dict(over=float(over[have].mean()), under=float(under[have].mean()))
        rows = []
        for n in range(K):
            m = (lab == n) & have
            diffs, mdiffs = [], []
            for idx in boots:
                ii = idx[(lab[idx] == n) & have[idx]]
                jj = idx[have[idx]]
                if len(ii):
                    diffs.append(net[ii].mean() - net[jj].mean())
                ik, jk = idx[(lab[idx] == n) & okn[idx]], idx[okn[idx]]
                if len(ik):
                    mdiffs.append(a0[ik].mean() - a0[jk].mean())
            lo, hi = np.percentile(diffs, [5, 95])
            verdict_tail = "over" if lo > 0 else "under" if hi < 0 else "average"
            mlo, mhi = np.percentile(mdiffs, [5, 95])
            mshift = float(a0[(lab == n) & okn].mean() - a0[okn].mean())          # mean extra water in this pattern vs all storms (in)
            verdict = "over" if mlo > 0 else "under" if mhi < 0 else "average"    # the 90% range of the mean shift excludes zero
            rows.append({"pattern": n, "days": int(m.sum()), "p_over": round(float(over[m].mean()), 3), "p_under": round(float(under[m].mean()), 3),
                         "net_diff": round(float(net[m].mean() - net[have].mean()), 3), "lo": round(float(lo), 3), "hi": round(float(hi), 3), "verdict": verdict, "verdict_tail": verdict_tail,
                         "shift_in": round(mshift, 3), "shift_pct": round(mshift / typical * 100, 1), "pct_lo": round(float(mlo) / typical * 100, 1), "pct_hi": round(float(mhi) / typical * 100, 1),
                         **spread(anom[m & ~np.isnan(anom)])})
        out[zn] = {"typical_in": round(typical, 2), "base_over": round(base["over"], 3), "base_under": round(base["under"], 3), "all": spread(anom[have & ~np.isnan(anom)]), "patterns": rows}
    return out


def main():
    rng = np.random.default_rng(0)
    seasons = S.seasons_available()
    z_abs = S.load_daily("z500", seasons) / S.G
    t_abs = S.load_daily("t850", seasons)
    z = S.anomalies(z_abs)
    zones = pd.read_csv(S.OUT / "zone_daily.csv", index_col=0, parse_dates=True)
    names = [c[5:] for c in zones.columns if c.startswith("over_")]
    days = pd.DatetimeIndex(z.time.values)
    zt = zones.reindex(days)
    storm = zt["storm"].fillna(False).astype(bool).values & S.in_period(days, PERIOD)
    sea = zt["season"].values[storm].astype(int)

    box = z.sel(latitude=slice(S.SOM_BOX["lat"][1], S.SOM_BOX["lat"][0]), longitude=slice(*S.SOM_BOX["lon"]))
    ibox = box.sel(longitude=slice(I.IDISP_LON_W, S.SOM_BOX["lon"][1]))
    Xraw, _ = I.idisp_features(ibox.values[storm], ibox.latitude.values, ibox.longitude.values)
    mu, sd = Xraw.mean(0), Xraw.std(0)
    X = (Xraw - mu) / sd

    res = json.loads((S.OUT / f"idisp_results_{PERIOD}_k{K}.json").read_text(encoding="utf-8"))
    cent = (np.array(res["centroids"]) - mu) / sd
    lab_csv = pd.read_csv(S.OUT / f"idisp_days_{PERIOD}_k{K}.csv", parse_dates=["date"]).set_index("date")["cluster"].reindex(days[storm])
    lab = lab_csv.values.astype(int)
    near, dist, _, _ = I.nearest(X, cent)
    print(f"{storm.sum()} storm days; nearest saved centre reproduces the saved cluster on {100 * (near == lab).mean():.1f}% of them")
    cutoff = float(np.percentile(dist, CUT_PCT))
    print(f"no-match cutoff (the {CUT_PCT}th percentile of the distance to the own centre): {cutoff:.2f}")

    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / "pattern_model.npz", lat=z_abs.latitude.values, lon=z_abs.longitude.values, beta_z=harmonic_beta(z_abs), beta_t=harmonic_beta(t_abs),
                        zstd=z.std("time").values.astype("float32"), mu=mu, sd=sd, centroids=cent, cutoff=cutoff, ilon_w=I.IDISP_LON_W)
    zl = np.full(len(days), -1)
    zl[np.flatnonzero(storm)] = lab
    table = zone_table(zl[storm], zt[storm], names, sea, rng)
    (OUT / "pattern_zones.json").write_text(json.dumps({"k": K, "period": PERIOD, "n_storm_days": int(storm.sum()), "n_per_pattern": np.bincount(lab, minlength=K).tolist(),
                                                        "centroids": res["centroids"], "grid": XGRID.tolist(), "threshold_in": 0.5, "zones": table}, indent=1), encoding="utf-8")
    for zn in names:
        print(f"{zn:16s}", " ".join(f"{r['verdict'][:5]:>5s}" for r in table[zn]["patterns"]))
    print("wrote", OUT / "pattern_model.npz", "and pattern_zones.json")


if __name__ == "__main__":
    sys.exit(main())
