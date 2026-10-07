"""Fit the pass-delay risk curve from the I-90 history and export it for the ski tool (run by hand).

    python scripts/pass_i90_parse.py && python scripts/pass_i90_analysis.py && python scripts/pass_risk.py

Model: logistic regression of "a weather delay on I-90 at Snoqualmie Pass that day" (Nov-Apr 2017-2024, WSDOT's Snoqualmie
Winter Operations Study, Figure 4) on the day's new snow water equivalent at the Meadows Pass SNOTEL, with a second curve for a delay
of 3 hours or more. The shape (SWE or its square root) is picked by leave-one-winter-out log loss. The result is written to
assets/data/pass_risk_curve.json and is used by scripts/ski_features.py for every highway pass (US 2, US 12, SR 410, SR 542 ...) on the
assumption, which Danny accepted for now, that other Cascade passes behave like I-90. It is a daily chance for one day's snow, not a forecast of a
closure at a given hour, and it says nothing about collisions on clear days (about 1% of days).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pass_i90_analysis import ROOT, load  # noqa: E402


def fit_logistic(x, y, iters=60, ridge=1e-4):
    X = np.column_stack([np.ones(len(x)), x])
    b = np.zeros(2)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ b))
        W = p * (1 - p) + 1e-9
        g = X.T @ (y - p) - ridge * b
        H = X.T @ (X * W[:, None]) + ridge * np.eye(2)
        step = np.linalg.solve(H, g)
        b += step
        if np.abs(step).max() < 1e-8:
            break
    return b


def logloss(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def main():
    ev = pd.read_csv(ROOT / "data" / "passes" / "i90_snoqualmie_closures_2017_2024.csv", parse_dates=["date"])
    clear = ev["weather"].isin(["CLEAR", "OVERCAST", "OVERCAST SKIES", "FOG"])
    days = pd.date_range("2017-11-01", "2024-04-30")
    days = days[(days.month >= 11) | (days.month <= 4)]
    days = days[~((days > "2018-04-30") & (days < "2018-11-01"))]
    s = load("897").reindex(days)["swe1"]
    d = pd.DataFrame({"swe": s})
    d["delay"] = d.index.isin(ev.loc[~clear, "date"]).astype(int)
    longest = ev.groupby("date")["delay_min"].max()
    d["long"] = d.index.map(lambda t: int(longest.get(t, 0) >= 180))
    d["season"] = [t.year + 1 if t.month >= 10 else t.year for t in d.index]
    d = d.dropna(subset=["swe"])
    d["swe"] = d["swe"].clip(upper=3.0)          # the curve is flat beyond what was observed (5 days above 2 in)
    out = {"source": "WSDOT Snoqualmie Winter Operations Study (Dec 2024), Figure 4; SNOTEL Meadows Pass (897)", "n_days": int(len(d)),
           "n_delay_days": int(d["delay"].sum()), "n_long_days": int(d["long"].sum()), "max_swe_in": 3.0, "curves": {}}
    for target, label in [("delay", "any weather delay"), ("long", "delay of 3 hours or more")]:
        best = None
        for shape, f in [("linear", lambda v: v), ("sqrt", np.sqrt)]:
            ll = []
            for sn in sorted(d["season"].unique()):
                tr, te = d[d["season"] != sn], d[d["season"] == sn]
                b = fit_logistic(f(tr["swe"].values), tr[target].values)
                ll.append(logloss(te[target].values, 1 / (1 + np.exp(-(b[0] + b[1] * f(te["swe"].values))))))
            score = float(np.mean(ll))
            print(f"{label}: {shape} leave-one-winter-out log loss {score:.4f}")
            if best is None or score < best[0]:
                best = (score, shape, f)
        _, shape, f = best
        b = fit_logistic(f(d["swe"].values), d[target].values)
        grid = [0, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
        pts = {str(g): round(float(1 / (1 + np.exp(-(b[0] + b[1] * f(np.array([g]))[0])))), 3) for g in grid}
        print(f"  chosen {shape}; a={b[0]:.3f} b={b[1]:.3f};", pts)
        out["curves"][target] = {"label": label, "shape": shape, "a": round(float(b[0]), 4), "b": round(float(b[1]), 4), "at": pts}
    out["generated_utc"] = f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}"
    dest = ROOT / "assets" / "data" / "pass_risk_curve.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", dest)


if __name__ == "__main__":
    main()
