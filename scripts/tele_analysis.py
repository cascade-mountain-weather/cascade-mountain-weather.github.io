"""Teleconnections vs. on-the-ground SNOTEL conditions, November-May (exploratory; run by hand).

    python scripts/tele_fetch.py            # once: downloads the records into data/teleconnections/cache
    python scripts/tele_analysis.py         # writes data/teleconnections/results/*.csv

What it measures, per station and per day of the cold season (Nov 1 - May 31):
  tanom   daily mean temperature minus that station's smoothed day-of-year mean (F)
  swe     daily SWE gain (in of water, increases only), "how snowy"
  precip  daily precipitation (in of water), from the accumulated gauge
  rain    precipitation that did not show up as new SWE (in), "how rainy"
  bigsnow day with SWE gain at or above the station's 90th percentile of snow days   (big snow storm)
  bigwet  day with precipitation at or above the station's 90th percentile of wet days (big storm, any phase)
Each is grouped by the state of an index `lag` days earlier: MJO phase (OMI, amplitude >= 1), PNA class (CPC daily
index, 5-day mean, quintile classes), ENSO class (ONI). Effects are reported against the station's own cold-season
average (a ratio for SWE, precip, rain and storm frequency; degrees F for temperature). Uncertainty is a bootstrap
over seasons (whole winters resampled, because days within a storm and a winter are not independent).
"""
import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "teleconnections" / "cache"
RES = ROOT / "data" / "teleconnections" / "results"
METRICS = ["tanom", "swe", "precip", "rain", "bigsnow", "bigwet"]
RATIO = {"swe", "precip", "rain", "bigsnow", "bigwet"}
rng = np.random.default_rng(7)


# ---------------------------------------------------------------- data
def load_station(sid):
    d = pd.read_csv(CACHE / "snotel" / f"{sid}.csv", index_col=0, parse_dates=True)
    d = d.reindex(pd.date_range("1980-10-01", "2026-09-30"))
    t = d["TAVG"].where(d["TAVG"].between(-20, 90))
    tm = (d["TMAX"].where(d["TMAX"].between(-20, 100)) + d["TMIN"].where(d["TMIN"].between(-25, 90))) / 2
    t = t.fillna(tm)
    t = t.where(~((d["TMAX"] < d["TMIN"]) | (d["TMAX"] == d["TMIN"])))                          # sensor stuck or swapped
    # precipitation: day-to-day change of the accumulated gauge, which resets each water year
    p = d["PREC"].diff()
    p = p.where((p >= 0) & (p < 12))
    swe = d["WTEQ"].diff()
    gain = swe.clip(lower=0)
    cap = (p.fillna(1.0) + 0.3).clip(upper=8)                                               # SWE cannot rise by more than fell, plus noise
    gain = gain.where(gain <= cap)
    gain = gain.where(~((gain > 0) & p.isna() & (gain > 3)))
    return pd.DataFrame({"temp": t, "precip": p, "swe": gain})


def anomaly(t):
    """Departure from the smoothed day-of-year mean, using the whole record."""
    mdoy = t.index.strftime("%m-%d")
    clim = t.groupby(mdoy).mean().reindex(sorted(set(mdoy)))
    ext = pd.concat([clim.iloc[-30:], clim, clim.iloc[:30]]).rolling(31, center=True).mean().iloc[30:-30]
    a = t - mdoy.map(ext.to_dict()).values.astype(float)
    return a.where(a.abs() < 35)


def panel(first_season):
    st = pd.read_csv(CACHE / "stations.csv")
    frames = {}
    for _, s in st.iterrows():
        d = load_station(s["id"])
        d["tanom"] = anomaly(d["temp"])
        frames[s["id"]] = d
    idx = frames[st["id"].iloc[0]].index
    keep = (idx.month >= 11) | (idx.month <= 5)
    keep &= idx >= pd.Timestamp(first_season - 1, 11, 1)
    idx = idx[keep]
    season = np.where(idx.month >= 11, idx.year + 1, idx.year)        # a season is named for the year it ends in
    arr = {m: np.column_stack([frames[i].loc[idx, k].values for i in st["id"]]) for m, k in
           [("tanom", "tanom"), ("swe", "swe"), ("precip", "precip")]}
    arr["rain"] = np.where(np.isnan(arr["precip"]) | np.isnan(arr["swe"]), np.nan, np.clip(arr["precip"] - arr["swe"], 0, None))
    # station coverage: drop stations missing most of the days for a metric
    for m in list(arr):
        bad = np.isnan(arr[m]).mean(axis=0) > 0.35
        arr[m][:, bad] = np.nan
    snow_days = arr["swe"] >= 0.2
    wet_days = arr["precip"] >= 0.2
    arr["bigsnow"] = np.full(arr["swe"].shape, np.nan)
    arr["bigwet"] = np.full(arr["swe"].shape, np.nan)
    for j in range(arr["swe"].shape[1]):
        s = arr["swe"][:, j]
        p = arr["precip"][:, j]
        if snow_days[:, j].sum() > 200:
            thr = np.nanpercentile(s[snow_days[:, j]], 90)
            arr["bigsnow"][:, j] = np.where(np.isnan(s), np.nan, (s >= thr).astype(float))
        if wet_days[:, j].sum() > 200:
            thr = np.nanpercentile(p[wet_days[:, j]], 90)
            arr["bigwet"][:, j] = np.where(np.isnan(p), np.nan, (p >= thr).astype(float))
    return st, idx, season, arr


def indices(idx, lag):
    """Index classes aligned to `idx`, each a pandas Series of labels, using the index value `lag` days earlier."""
    src = idx - pd.Timedelta(days=lag)
    omi = pd.read_csv(CACHE / "omi.csv", index_col=0, parse_dates=True)
    ang = (np.degrees(np.arctan2(omi["pc2"], omi["pc1"])) + 360) % 360
    phase = (((ang - 180) % 360) // 45 + 1).astype(int)                 # PHASE_OFFSET is applied in main()
    phase = ((phase - 1 + PHASE_SHIFT) % 8 + 1).where(omi["amp"] >= 1, 0)
    mjo = pd.Series(phase.reindex(src).values, index=idx).fillna(-1).astype(int)
    pna = pd.read_csv(CACHE / "pna_daily.csv", index_col=0, parse_dates=True)["pna"].rolling(5, center=True, min_periods=3).mean()
    v = pna.reindex(src).values
    cold = pna[(pna.index.month >= 11) | (pna.index.month <= 5)].dropna()
    q = np.nanquantile(cold, [0.1, 0.3, 0.7, 0.9])
    cls = np.select([np.isnan(v), v <= q[0], v <= q[1], v < q[2], v < q[3]], [-9, -2, -1, 0, 1], 2)
    pnac = pd.Series(cls, index=idx)
    oni = pd.read_csv(CACHE / "oni.csv", index_col=0)["oni"]
    oni.index = pd.PeriodIndex(oni.index, freq="M")
    o = oni.reindex(pd.PeriodIndex(src.to_period("M"))).values
    en = pd.Series(np.select([np.isnan(o), o >= 1.0, o >= 0.5, o <= -1.0, o <= -0.5], [-9, 2, 1, -2, -1], 0), index=idx)
    return {"mjo": mjo, "pna": pnac, "enso": en}, q


PHASE_SHIFT = 0


def phase_check():
    """OMI phase labels versus the BoM RMM phases over their common years: pick the rotation that agrees most."""
    omi = pd.read_csv(CACHE / "omi.csv", index_col=0, parse_dates=True)
    rmm = pd.read_csv(CACHE / "rmm.csv", index_col=0, parse_dates=True)
    j = omi.join(rmm, how="inner", lsuffix="_x", rsuffix="_y")
    j = j[(j["amp_x"] >= 1) & (j["amp_y"] >= 1)]
    ang = (np.degrees(np.arctan2(j["pc2"], j["pc1"])) + 360) % 360
    base = (((ang - 180) % 360) // 45).astype(int)
    best = max(range(8), key=lambda s: ((base + s) % 8 + 1 == j["phase"]).mean())
    ok = ((base + best) % 8 + 1 == j["phase"]).mean()
    near = (np.abs(((base + best) % 8 + 1 - j["phase"] + 4) % 8 - 4) <= 1).mean()
    return best, ok, near, len(j)


# ---------------------------------------------------------------- composites
def composites(arr, season, labels, cats, nboot=400):
    """Return tidy rows: metric, category, station index, value, lo, hi, n_days. Ratios are category mean / all-day mean."""
    years = np.unique(season)
    yi = np.searchsorted(years, season)
    S = arr["swe"].shape[1]
    rows = []
    draws = rng.integers(0, len(years), size=(nboot, len(years)))
    for m in METRICS:
        X = arr[m]
        ok = ~np.isnan(X)
        Xz = np.where(ok, X, 0.0)
        tot_sum = np.zeros((len(years), S))
        tot_n = np.zeros((len(years), S))
        np.add.at(tot_sum, yi, Xz)
        np.add.at(tot_n, yi, ok.astype(float))
        for c in cats:
            msk = (labels.values == c)[:, None] & ok
            cs = np.zeros((len(years), S))
            cn = np.zeros((len(years), S))
            np.add.at(cs, yi, np.where(msk, Xz, 0.0))
            np.add.at(cn, yi, msk.astype(float))

            def stat(ys):
                a = cs[ys].sum(axis=0) / np.maximum(cn[ys].sum(axis=0), 1)
                b = tot_sum[ys].sum(axis=0) / np.maximum(tot_n[ys].sum(axis=0), 1)
                return (a / b if m in RATIO else a - b)

            v = stat(np.arange(len(years)))
            bs = np.array([stat(d) for d in draws])
            lo, hi = np.nanpercentile(bs, [5, 95], axis=0)
            n = cn.sum(axis=0)
            for j in range(S):
                if n[j] >= 30 and np.isfinite(v[j]):
                    rows.append((m, c, j, v[j], lo[j], hi[j], int(n[j])))
    return pd.DataFrame(rows, columns=["metric", "cat", "st", "value", "lo", "hi", "n"])


def main():
    global PHASE_SHIFT
    ap = argparse.ArgumentParser()
    ap.add_argument("--first-season", type=int, default=1992, help="first season (named for the year it ends); OMI starts in 1991")
    ap.add_argument("--lags", default="0,2,4,6,8,10,12,14")
    ap.add_argument("--boot", type=int, default=300)
    a = ap.parse_args()
    RES.mkdir(parents=True, exist_ok=True)
    PHASE_SHIFT, agree, near, n = phase_check()
    print(f"OMI phase rotation vs RMM: shift {PHASE_SHIFT}, exact agreement {agree:.0%}, within one phase {near:.0%} over {n} days")
    st, idx, season, arr = panel(a.first_season)
    print(f"{len(idx)} cold-season days, {len(np.unique(season))} seasons, {len(st)} stations")
    for m in METRICS:
        print(f"  {m}: stations with data {int((~np.isnan(arr[m]).all(axis=0)).sum())}, mean {np.nanmean(arr[m]):.3f}")
    st.to_csv(RES / "stations.csv", index=False)
    np.savez_compressed(RES / "panel.npz", idx=idx.values.astype("datetime64[D]"), season=season, **arr)
    out = []
    for lag in [int(x) for x in a.lags.split(",")]:
        ind, q = indices(idx, lag)
        for name, cats in [("mjo", [0, 1, 2, 3, 4, 5, 6, 7, 8]), ("pna", [-2, -1, 0, 1, 2]), ("enso", [-2, -1, 0, 1, 2])]:
            df = composites(arr, season, ind[name], cats, a.boot)
            df.insert(0, "lag", lag)
            df.insert(0, "index", name)
            out.append(df)
        print(f"lag {lag} done")
    res = pd.concat(out)
    res["station"] = st["id"].values[res["st"].values]
    res.drop(columns="st").to_csv(RES / "composites.csv", index=False)
    print("PNA class cut points (5-day mean):", np.round(q, 2))
    print("wrote", RES / "composites.csv", len(res), "rows")


if __name__ == "__main__":
    main()
