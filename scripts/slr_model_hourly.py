"""Can the 700 hPa temperature stand in for a missing depth sensor? Site, regional and pooled models, tested leave-one-season-out.

    python scripts/slr_model_hourly.py
    python scripts/slr_model_hourly.py --min-swe 0.75

Uses the storm runs of scripts/slr_analysis_hourly.py (same screens). Predictor: T700, the mean of the Quillayute and Salem 700 hPa
temperatures during the storm (the pair that did best for the west side, and the Cascade crest it feeds).

1. Does the relationship depend on where the station is? Per-station fits of SLR = a + b T700 (a is the SLR at 0 C is not meaningful, so
   a is reported as the fitted SLR at -10 C), then how the fitted SLR at -10 C, the slope and the correlation vary with elevation, latitude and
   longitude (Spearman across stations). A pooled regression with elevation, latitude and the east side shows which of them matter once T700 is in.
2. Prediction skill, leave-one-season-out (each winter is predicted from the other winters, so nothing is scored on data it was fitted to):
     global constant      the median SLR of the training storms
     T700 only            one line for every station
     region x T700        a line each for the Olympics, west Cascades and east Cascades (the crest split at 121.0 W)
     lat, elev, east      T700 plus latitude, elevation and an east-side flag
     station constant     each station's own median SLR
     station + global T   each station's own level, one shared slope on T700
     station x T700       each station's own line (falls back to station + global T for a station with under 20 training storms)
   Scored on the storms' depth, which is what the evaluation needs: depth predicted = observed SWE x predicted SLR. Reports the typical error in
   inches (MAE), in percent of the storm's depth (median absolute), the bias (total predicted depth over total observed), and R^2 of
   predicted against observed depth.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slr_plot_hourly import build  # noqa: E402
from slr_analysis import SLR  # noqa: E402

MIN_TRAIN = 20


def prepare(a):
    d = build(a)
    meta = pd.read_csv(SLR / "snotel_stations.csv").rename(columns={"triplet": "station"}).set_index("station")[["lat", "lon"]]
    d = d.join(meta, on="station")
    d["T"] = d[["UIL_700", "SLE_700"]].mean(axis=1)
    d = d.dropna(subset=["T", "elevation_ft", "lat", "lon"]).copy()
    d["elev"] = d["elevation_ft"] / 1000
    d["east"] = (d["lon"] >= -121.0).astype(float)
    d["region"] = np.where(d["lon"] < -122.6, "Olympics", np.where(d["lon"] < -121.0, "west Cascades", "east Cascades"))
    d["season"] = d["launch"].dt.year + (d["launch"].dt.month >= 7).astype(int)
    return d


def ols(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def station_fits(d):
    rows = []
    for st, g in d.groupby("station"):
        if len(g) < 30:
            continue
        b, a0 = np.polyfit(g["T"], g["slr"], 1)
        rows.append({"station": st, "name": g["name"].iloc[0], "n": len(g), "elev": g["elev"].iloc[0], "lat": g["lat"].iloc[0],
                     "lon": g["lon"].iloc[0], "r": g["T"].corr(g["slr"]), "slope": b, "slr_m10": a0 - 10 * b, "mean_slr": g["slr"].mean()})
    return pd.DataFrame(rows).set_index("station")


def design(df, kind):
    one = np.ones(len(df))
    t = df["T"].to_numpy()
    if kind == "T":
        return np.column_stack([one, t])
    if kind == "lat_elev_east":
        return np.column_stack([one, t, df["lat"] - 47.5, df["elev"] - 4.5, df["east"]])
    raise ValueError(kind)


def predict_all(tr, te):
    """{model name: predicted SLR for te} fitted on tr."""
    out = {}
    med = tr["slr"].median()
    out["global constant"] = np.full(len(te), med)
    b = ols(design(tr, "T"), tr["slr"].to_numpy())
    out["T700 only"] = design(te, "T") @ b
    p = np.full(len(te), np.nan)
    for reg in te["region"].unique():
        t_r = tr[tr["region"] == reg]
        m = (te["region"] == reg).to_numpy()
        if len(t_r) >= MIN_TRAIN:
            br = ols(design(t_r, "T"), t_r["slr"].to_numpy())
            p[m] = design(te[m], "T") @ br
        else:
            p[m] = design(te[m], "T") @ b
    out["region x T700"] = p
    bl = ols(design(tr, "lat_elev_east"), tr["slr"].to_numpy())
    out["lat, elev, east + T700"] = design(te, "lat_elev_east") @ bl
    # station level models
    smed = tr.groupby("station")["slr"].median()
    out["station constant"] = te["station"].map(smed).fillna(med).to_numpy()
    # station + global T: remove each station's mean of (slr - slope*T), shared slope from within-station variation
    dm = tr.copy()
    dm["slr_c"] = dm["slr"] - dm.groupby("station")["slr"].transform("mean")
    dm["T_c"] = dm["T"] - dm.groupby("station")["T"].transform("mean")
    bw = (dm["T_c"] * dm["slr_c"]).sum() / (dm["T_c"] ** 2).sum()
    lvl = (tr["slr"] - bw * tr["T"]).groupby(tr["station"]).mean()
    glob_lvl = float((tr["slr"] - bw * tr["T"]).mean())
    out["station + global T"] = te["station"].map(lvl).fillna(glob_lvl).to_numpy() + bw * te["T"].to_numpy()
    # station-specific line
    p = out["station + global T"].copy()
    for st, g in tr.groupby("station"):
        if len(g) >= MIN_TRAIN:
            bs = ols(design(g, "T"), g["slr"].to_numpy())
            m = (te["station"] == st).to_numpy()
            if m.any():
                p[m] = design(te[m], "T") @ bs
    out["station x T700"] = p
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-swe", type=float, default=0.5)
    ap.add_argument("--max-temp", type=float, default=34.0)
    ap.add_argument("--min-slr", type=float, default=2.0)
    ap.add_argument("--max-slr", type=float, default=25.0)
    a = ap.parse_args()
    d = prepare(a)
    print(f"{len(d):,} storms (SWE gain {a.min_swe:g} in or more), {d['station'].nunique()} stations, seasons {d['season'].min()}-{d['season'].max()}")

    f = station_fits(d)
    print("\n1. Per-station fit, SLR = a + b T700 (sorted by slope; slr_m10 is the fitted SLR at T700 = -10 C)")
    print(f.drop(columns=["name"]).assign(name=f["name"]).sort_values("slope").to_string(float_format=lambda v: f"{v:.2f}"))
    print("\nHow the station fits vary with location (Spearman across stations, n = %d)" % len(f))
    cors = pd.DataFrame({q: [f[q].corr(f[c], method="spearman") for c in ("elev", "lat", "lon")] for q in ("r", "slope", "slr_m10", "mean_slr")}, index=["elevation", "latitude", "longitude (east = larger)"])
    print(cors.to_string(float_format=lambda v: f"{v:.2f}"))
    print("\nBy region")
    d2 = d.copy()
    rg = []
    for reg, g in d2.groupby("region"):
        b, a0 = np.polyfit(g["T"], g["slr"], 1)
        rg.append({"region": reg, "stations": g["station"].nunique(), "storms": len(g), "r": g["T"].corr(g["slr"]), "slope": b, "slr_m10": a0 - 10 * b, "median_slr": g["slr"].median()})
    print(pd.DataFrame(rg).set_index("region").to_string(float_format=lambda v: f"{v:.2f}"))

    X = design(d, "lat_elev_east")
    y = d["slr"].to_numpy()
    beta = ols(X, y)
    res = y - X @ beta
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * (res @ res) / (len(y) - X.shape[1]))
    names = ["intercept", "T700 (per C)", "latitude (per deg N of 47.5)", "elevation (per 1,000 ft above 4,500)", "east side"]
    print("\nPooled regression, SLR on T700 and location (storm-level standard errors, which overstate the confidence because storms at one station are not independent)")
    print(pd.DataFrame({"coef": beta, "se": se, "t": beta / se}, index=names).to_string(float_format=lambda v: f"{v:.2f}"))

    # leave-one-season-out
    preds = {}
    for s in sorted(d["season"].unique()):
        te, tr = d[d["season"] == s], d[d["season"] != s]
        for k, v in predict_all(tr, te).items():
            preds.setdefault(k, pd.Series(np.nan, index=d.index)).loc[te.index] = v
    rows = []
    for k, p in preds.items():
        pred_depth = d["swe"] * p.clip(lower=1)
        err = pred_depth - d["depth"]
        rows.append({"model": k, "MAE depth (in)": err.abs().mean(), "median |error| (% of depth)": (err.abs() / d["depth"]).median() * 100,
                     "bias (pred/obs)": pred_depth.sum() / d["depth"].sum(), "R2 depth": 1 - (err ** 2).sum() / ((d["depth"] - d["depth"].mean()) ** 2).sum(),
                     "MAE SLR": (p - d["slr"]).abs().mean()})
    print("\n2. Leave-one-season-out skill on storm depth (observed SWE x predicted SLR). Mean storm depth %.1f in, mean SWE %.2f in" % (d["depth"].mean(), d["swe"].mean()))
    print(pd.DataFrame(rows).set_index("model").to_string(float_format=lambda v: f"{v:.2f}"))
    out = SLR / "slr_model_predictions.csv"
    d.assign(**{k: v for k, v in preds.items()}).drop(columns=["band"], errors="ignore").to_csv(out, index=False)
    print(f"\nwrote {out.relative_to(SLR.parent.parent)}")


if __name__ == "__main__":
    main()
