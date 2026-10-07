"""Pilot: how big was the storm when the high passes closed for the winter? (run by hand)

    python scripts/pass_seasonal_dates.py && python scripts/tele_fetch.py --only snotel && python scripts/pass_pilot.py

For each pass and winter-closing date (WSDOT's historic table), look at the nearest SNOTEL station in the cached long records
(data/teleconnections/cache): the new SWE in the 1, 3 and 7 days up to the closing date, the SWE on the ground, and where those
numbers rank among the same days of that fall (Oct 15 to Dec 31). A closure that follows a storm should sit high in that ranking.
Writes docs/passes/seasonal_pilot.csv and docs/passes/seasonal_pilot.png.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "teleconnections" / "cache" / "snotel"
OUT = ROOT / "docs" / "passes"
# nearest SNOTEL with a long record (Cayuse Pass SNOTEL only starts in 2006)
STATION = {"Chinook Pass SR 410": ("642", "Morse Lake 5,400 ft"), "Cayuse Pass SR 123": ("642", "Morse Lake 5,400 ft"),
           "North Cascades SR 20": ("711", "Rainy Pass 4,880 ft")}


def swe_series(sid):
    d = pd.read_csv(CACHE / f"{sid}.csv", index_col=0, parse_dates=True)
    d = d[~d.index.duplicated()].sort_index()
    return d["WTEQ"].asfreq("D").interpolate(limit=3)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    c = pd.read_csv(ROOT / "data" / "passes" / "seasonal_closures.csv", parse_dates=["closed"])
    rows = []
    for pas, (sid, label) in STATION.items():
        swe = swe_series(sid)
        for r in c[(c["pass"] == pas) & c["closed"].notna()].itertuples():
            y = r.closed.year
            if y < 1981 or r.closed.month < 10:
                continue
            gain = {k: (swe - swe.shift(k)).clip(lower=0) for k in (1, 3, 7)}
            row = {"pass": pas, "station": label, "closed": r.closed.date()}
            for k, g in gain.items():
                v = g.get(pd.Timestamp(r.closed))
                pool = g[f"{y}-10-15":f"{y}-12-31"].dropna()
                row[f"gain{k}d_in"] = None if v is None or np.isnan(v) else round(float(v), 2)
                row[f"gain{k}d_pctile"] = None if v is None or np.isnan(v) or not len(pool) else round(float((pool < v).mean() * 100))
            v = swe.get(pd.Timestamp(r.closed))
            row["swe_on_ground_in"] = None if v is None or np.isnan(v) else round(float(v), 1)
            row["max_gain_3d_prior_7d"] = round(float(gain[3][pd.Timestamp(r.closed) - pd.Timedelta(days=7):pd.Timestamp(r.closed)].max()), 2)
            rows.append(row)
    D = pd.DataFrame(rows)
    D.to_csv(OUT / "seasonal_pilot.csv", index=False)
    print(D.groupby("pass")[["gain1d_in", "gain3d_in", "gain7d_in", "swe_on_ground_in", "gain3d_pctile", "gain7d_pctile"]].median().round(2).to_string())
    print("\nshare of closures where the 3-day gain was above that fall's 80th percentile:",
          {p: round(float((g["gain3d_pctile"].dropna() >= 80).mean()), 2) for p, g in D.groupby("pass")})
    print("n:", D.groupby("pass").size().to_dict())
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.2))
    for ax, (p, g) in zip(axs, D.groupby("pass")):
        ax.hist(g["gain3d_pctile"].dropna(), bins=np.arange(0, 101, 10), color="#1e3c72", edgecolor="#fff")
        ax.axhline(len(g.dropna(subset=['gain3d_pctile'])) / 10, color="#c2410c", ls="--", lw=1)
        ax.set_title(f"{p}\n3-day new snow ranking on the closing date, {g['station'].iloc[0]}", fontsize=9)
        ax.set_xlabel("percentile among Oct 15 to Dec 31 days of that fall (dashed: what chance would give)")
    fig.tight_layout()
    fig.savefig(OUT / "seasonal_pilot.png", dpi=110)


if __name__ == "__main__":
    main()
