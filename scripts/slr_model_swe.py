"""Add SWE to the depth model: depth = SWE x (station level + b T700 + c SWE), fitted on depth directly.

    python scripts/slr_model_swe.py
    python scripts/slr_model_swe.py --min-swe 0.75

Builds on scripts/slr_model_hourly.py (same storm runs, same leave-one-season-out test, same T700). Depth is mostly the water that fell, so SWE
carries most of the answer; the question is how much the other pieces add on top of it and whether SLR itself changes with storm size (the
median fell from 7.3 to 6.5 as the minimum SWE rose from 0.5 to 2 in).

Models, each tested leave-one-season-out on storm depth in inches:
    constant SLR           depth = SWE x one SLR for everyone (the median of the training storms)
    station level          depth = SWE x the station's own median SLR
    SLR fit (previous)     each station's level + one shared T700 slope, fitted to SLR (what scripts/slr_model_hourly.py chose)
    depth fit: level       SWE x station level, fitted by least squares on depth
    depth fit: level + T   adds b T700, fitted on depth
    depth fit: level + SWE adds c SWE (SLR changes with storm size)
    depth fit: level + T + SWE      all three
Fitting on depth, not on SLR, weights each storm by how much snow it brought, which is what the depth error counts, and removes the bias that
comes from small storms dominating an SLR fit. The error is also broken out by storm size. Prints the final table (station levels, the shared
temperature slope, the SWE term) fitted on all the storms.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slr_model_hourly import prepare  # noqa: E402
from slr_analysis import SLR  # noqa: E402

MIN_TRAIN = 20
T0 = -10.0   # the temperature the station levels refer to, so they read as "SLR at -10 C"


def fit_depth(tr, use_t, use_swe):
    """Least squares on depth. Returns (station levels, b, c)."""
    st = sorted(tr["station"].unique())
    idx = {s: i for i, s in enumerate(st)}
    swe = tr["swe"].to_numpy()
    cols = np.zeros((len(tr), len(st)))
    cols[np.arange(len(tr)), tr["station"].map(idx).to_numpy()] = swe
    parts = [cols]
    if use_t:
        parts.append((swe * (tr["T"].to_numpy() - T0))[:, None])
    if use_swe:
        parts.append((swe * (swe - 1.0))[:, None])   # centred at 1 in so station levels read as SLR for a 1 in storm
    X = np.hstack(parts)
    beta, *_ = np.linalg.lstsq(X, tr["depth"].to_numpy(), rcond=None)
    levels = dict(zip(st, beta[:len(st)]))
    k = len(st)
    b = beta[k] if use_t else 0.0
    c = beta[k + (1 if use_t else 0)] if use_swe else 0.0
    return levels, b, c


def predict_depth(levels, b, c, te):
    mean_level = float(np.mean(list(levels.values())))
    lvl = te["station"].map(levels).fillna(mean_level).to_numpy()
    swe = te["swe"].to_numpy()
    slr = lvl + b * (te["T"].to_numpy() - T0) + c * (swe - 1.0)
    return swe * np.clip(slr, 2.0, 25.0)


def old_models(tr, te):
    med = tr["slr"].median()
    out = {"constant SLR": te["swe"].to_numpy() * med}
    smed = tr.groupby("station")["slr"].median()
    out["station level"] = te["swe"].to_numpy() * te["station"].map(smed).fillna(med).to_numpy()
    dm = tr.copy()
    dm["slr_c"] = dm["slr"] - dm.groupby("station")["slr"].transform("mean")
    dm["T_c"] = dm["T"] - dm.groupby("station")["T"].transform("mean")
    bw = (dm["T_c"] * dm["slr_c"]).sum() / (dm["T_c"] ** 2).sum()
    lvl = (tr["slr"] - bw * tr["T"]).groupby(tr["station"]).mean()
    g = float((tr["slr"] - bw * tr["T"]).mean())
    slr = te["station"].map(lvl).fillna(g).to_numpy() + bw * te["T"].to_numpy()
    out["SLR fit (previous)"] = te["swe"].to_numpy() * np.clip(slr, 2.0, 25.0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-swe", type=float, default=0.5)
    ap.add_argument("--max-temp", type=float, default=34.0)
    ap.add_argument("--min-slr", type=float, default=2.0)
    ap.add_argument("--max-slr", type=float, default=25.0)
    ap.add_argument("--export", action="store_true", help="write data/slr_model/depth_model.json (committed; used by scripts/slr_depth_model.py)")
    a = ap.parse_args()
    d = prepare(a)
    print(f"{len(d):,} storms (SWE gain {a.min_swe:g} in or more), {d['station'].nunique()} stations; mean depth {d['depth'].mean():.1f} in, mean SWE {d['swe'].mean():.2f} in")

    print("\nHow much does SWE alone explain? R^2 of depth against SWE, one line through the origin per fit")
    ratio = d["depth"].sum() / d["swe"].sum()
    r2 = 1 - ((d["depth"] - ratio * d["swe"]) ** 2).sum() / ((d["depth"] - d["depth"].mean()) ** 2).sum()
    print(f"  depth = {ratio:.2f} x SWE: R^2 {r2:.2f};  correlation of depth with SWE {d['depth'].corr(d['swe']):.2f}")

    names = ["constant SLR", "station level", "SLR fit (previous)", "depth fit: level", "depth fit: level + T", "depth fit: level + SWE", "depth fit: level + T + SWE"]
    flags = {"depth fit: level": (False, False), "depth fit: level + T": (True, False), "depth fit: level + SWE": (False, True), "depth fit: level + T + SWE": (True, True)}
    preds = {n: pd.Series(np.nan, index=d.index) for n in names}
    for s in sorted(d["season"].unique()):
        te, tr = d[d["season"] == s], d[d["season"] != s]
        for n, p in old_models(tr, te).items():
            preds[n].loc[te.index] = p
        for n, (ut, us) in flags.items():
            lv, b, c = fit_depth(tr, ut, us)
            preds[n].loc[te.index] = predict_depth(lv, b, c, te)

    rows = []
    sst = ((d["depth"] - d["depth"].mean()) ** 2).sum()
    for n in names:
        err = preds[n] - d["depth"]
        rows.append({"model": n, "MAE depth (in)": err.abs().mean(), "RMSE (in)": np.sqrt((err ** 2).mean()), "median |error| (%)": (err.abs() / d["depth"]).median() * 100,
                     "bias (pred/obs)": preds[n].sum() / d["depth"].sum(), "R2": 1 - (err ** 2).sum() / sst})
    print("\nLeave-one-season-out skill on storm depth")
    print(pd.DataFrame(rows).set_index("model").to_string(float_format=lambda v: f"{v:.2f}"))

    d["size"] = pd.cut(d["swe"], [0, 0.75, 1.0, 1.5, 2.5, 100], labels=["0.5-0.75 in", "0.75-1 in", "1-1.5 in", "1.5-2.5 in", "over 2.5 in"])
    rows = []
    for sz, g in d.groupby("size", observed=True):
        row = {"storm SWE": sz, "storms": len(g), "mean depth (in)": g["depth"].mean()}
        for n in ("constant SLR", "SLR fit (previous)", "depth fit: level + T + SWE"):
            e = preds[n].loc[g.index] - g["depth"]
            row[f"MAE {n}"] = e.abs().mean()
        row["bias new"] = preds["depth fit: level + T + SWE"].loc[g.index].sum() / g["depth"].sum()
        rows.append(row)
    print("\nError by storm size (MAE in inches; bias = predicted over observed depth for the new model)")
    print(pd.DataFrame(rows).set_index("storm SWE").to_string(float_format=lambda v: f"{v:.2f}"))

    lv, b, c = fit_depth(d, True, True)
    print(f"\nFinal model on all storms: depth = SWE x (level + {b:.3f} x (T700 - ({T0:g})) + {c:.3f} x (SWE - 1)), SLR clipped to 2-25")
    print(f"  each degree C warmer lowers SLR by {-b:.2f}; each extra inch of SWE changes SLR by {c:+.2f}")
    t = pd.DataFrame({"name": d.groupby("station")["name"].first(), "elev_ft": d.groupby("station")["elevation_ft"].first(), "lat": d.groupby("station")["lat"].first(),
                      "lon": d.groupby("station")["lon"].first(), "storms": d.groupby("station").size(), "SLR at -10C, 1 in storm": pd.Series(lv)})
    print(t.sort_values("SLR at -10C, 1 in storm").to_string(float_format=lambda v: f"{v:.2f}"))
    t.to_csv(SLR / "slr_station_levels.csv")
    print("\nwrote data/slr/slr_station_levels.csv")

    if a.export:
        import json
        from datetime import date
        ratio = (d["depth"] / preds["depth fit: level + T + SWE"]).replace([np.inf, -np.inf], np.nan).dropna()
        q = {k: round(float(ratio.quantile(v)), 3) for k, v in (("p10", .10), ("p25", .25), ("p50", .50), ("p75", .75), ("p90", .90))}
        err = preds["depth fit: level + T + SWE"] - d["depth"]
        east = t["lon"] >= -121.0
        model = {
            "about": "Fills in observed snowfall when a SNOTEL depth sensor is out: depth = SWE x clip(level + b (T700 - t0) + c (SWE - 1), slr_min, slr_max). "
                     "Built by scripts/slr_model_swe.py --export from hourly SNOTEL storms (SWE gain >= min_swe) and Quillayute and Salem 700 hPa temperatures. "
                     "The depth it predicts is what a working SNOTEL depth sensor would have read, a lower bound on true new snow.",
            "built": f"{date.today():%Y-%m-%d}", "seasons": [int(d["season"].min()), int(d["season"].max())], "storms": int(len(d)), "min_swe_in": a.min_swe,
            "t700_default_c": round(float(d["T"].mean()), 1), "t0_c": T0, "b_per_c": round(float(b), 4), "c_per_in_swe": round(float(c), 4), "slr_min": 2.0, "slr_max": 25.0,
            "level_default": round(float(t["SLR at -10C, 1 in storm"].mean()), 3),
            "level_default_east": round(float(t.loc[east, "SLR at -10C, 1 in storm"].mean()), 3),
            "level_default_west": round(float(t.loc[~east, "SLR at -10C, 1 in storm"].mean()), 3),
            "east_lon": -121.0,
            "obs_over_pred_quantiles": q,
            "skill_leave_one_season_out": {"mae_depth_in": round(float(err.abs().mean()), 2), "median_abs_error_pct": round(float((err.abs() / d["depth"]).median() * 100), 1),
                                           "r2": round(float(1 - (err ** 2).sum() / sst), 2), "bias": round(float(preds["depth fit: level + T + SWE"].sum() / d["depth"].sum()), 3)},
            "stations": {k: {"name": r["name"], "elev_ft": int(r["elev_ft"]), "storms": int(r["storms"]), "level": round(float(r["SLR at -10C, 1 in storm"]), 3)} for k, r in t.iterrows()},
        }
        dest = SLR.parent / "slr_model" / "depth_model.json"
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(json.dumps(model, indent=1), encoding="utf-8")
        print(f"wrote {dest.relative_to(SLR.parent.parent)} ({len(model['stations'])} stations; obs/pred quantiles {q})")


if __name__ == "__main__":
    main()
