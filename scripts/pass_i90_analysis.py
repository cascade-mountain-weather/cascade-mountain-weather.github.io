"""I-90 Snoqualmie Pass delays versus storm size at the nearest SNOTEL stations (run by hand).

    python scripts/pass_i90_analysis.py

Data: data/passes/i90_snoqualmie_closures_2017_2024.csv, transcribed from Figure 4 ("Closure Map") of a Snoqualmie Pass study of
I-90 closures and delays, November 2017 to March 2024 (printed total 458 h 7 min, $13.6 million). Each row is a delay with its
date, weather, cause and length. The figure gives no start times, so the unit here is the DAY.
Storm size: Meadows Pass SNOTEL (3,230 ft, 1993-, the closest in elevation to the 3,022 ft summit), with Stampede Pass (3,850 ft) and
Olallie Meadows (4,010 ft) as checks. Measures: new SWE (inches of water) in the day and the two days up to it.
Question: how does the chance of a delay day rise with storm size, and is a forecast of it useful?
Writes docs/passes/i90_*.png and data/passes/i90_risk_table.csv.
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
STATIONS = {"897": "Meadows Pass 3,230 ft", "788": "Stampede Pass 3,850 ft", "672": "Olallie Meadows 4,010 ft"}


def load(sid):
    d = pd.read_csv(CACHE / f"{sid}.csv", index_col=0, parse_dates=True)
    d = d[~d.index.duplicated()].sort_index().asfreq("D")
    swe = d["WTEQ"].interpolate(limit=3)
    prec = d["PREC"].diff().where(lambda x: (x >= 0) & (x < 12))
    gain = (swe - swe.shift(1)).clip(lower=0)
    cap = (prec.fillna(1.0) + 0.3).clip(upper=8)
    gain = gain.where(gain <= cap)
    return pd.DataFrame({"swe1": gain, "swe2": gain.rolling(2, min_periods=2).sum(), "prec1": prec, "tavg": d["TAVG"].where(d["TAVG"].between(-20, 90))})


def auc(y, s):
    ok = np.isfinite(s)
    y, s = y[ok], s[ok]
    pos, neg = s[y == 1], s[y == 0]
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ev = pd.read_csv(ROOT / "data" / "passes" / "i90_snoqualmie_closures_2017_2024.csv", parse_dates=["date"])
    clear = ev["weather"].isin(["CLEAR", "OVERCAST", "OVERCAST SKIES", "FOG"])
    days = pd.date_range("2017-11-01", "2024-04-30")
    days = days[(days.month >= 11) | (days.month <= 4)]
    days = days[~((days > "2018-04-30") & (days < "2018-11-01"))]
    base = pd.DataFrame(index=days)
    base["any"] = base.index.isin(ev["date"]).astype(int)
    base["storm"] = base.index.isin(ev.loc[~clear, "date"]).astype(int)
    big = ev.groupby("date")["delay_min"].max()
    base["long"] = base.index.map(lambda d: int(big.get(d, 0) >= 180))
    base["mins"] = base.index.map(lambda d: float(ev.loc[ev["date"] == d, "delay_min"].max()) if d in big.index else 0.0)
    print(f"{len(base)} winter days (Nov-Apr, Nov 2017 to Apr 2024), {int(base['any'].sum())} with a delay ({int(base['storm'].sum())} in snowing weather, {int(base['long'].sum())} with a delay of 3 hours or more)")
    res = []
    for sid, name in STATIONS.items():
        s = load(sid).reindex(base.index)
        for m in ["swe1", "swe2"]:
            res.append((name, m, auc(base["storm"].values, s[m].values), auc(base["long"].values, s[m].values)))
    R = pd.DataFrame(res, columns=["station", "measure", "AUC_storm_delay_day", "AUC_3h_delay_day"]).round(2)
    print("\nHow well storm size ranks delay days (AUC: 0.5 = no skill, 1 = perfect):")
    print(R.to_string(index=False))

    # risk table by storm size at the best station
    s = load("897").reindex(base.index)
    b = base.join(s)
    bins = [-0.01, 0.05, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 99]
    labels = ["under 0.05", "0.05-0.25", "0.25-0.5", "0.5-0.75", "0.75-1.0", "1.0-1.5", "1.5-2.0", "2.0 or more"]
    b["bin"] = pd.cut(b["swe1"], bins=bins, labels=labels)
    T = b.groupby("bin", observed=True).agg(days=("any", "size"), delay_days=("storm", "sum"), long_days=("long", "sum"), median_delay_min=("mins", lambda x: x[x > 0].median() if (x > 0).any() else np.nan))
    T["P_delay"] = (T["delay_days"] / T["days"]).round(2)
    T["P_delay_3h"] = (T["long_days"] / T["days"]).round(2)
    T.to_csv(ROOT / "data" / "passes" / "i90_risk_table.csv")
    print("\nChance of a weather delay by the day's new SWE at Meadows Pass (inches of water):")
    print(T.to_string())
    # temperature matters: the same SWE as rain or heavy snow
    b["warm"] = b["tavg"] > 33
    print("\nDelay-day rate with 0.5 in or more of new SWE, by temperature:")
    print(b[b["swe1"] >= 0.5].groupby("warm").agg(days=("any", "size"), P_delay=("storm", "mean")).round(2).to_string())
    # snow-free days with delays (collisions, ice)
    print("\nDelay days with under 0.05 in SWE:", int(((b["swe1"] < 0.05) & (b["any"] == 1)).sum()), "of", int(b["any"].sum()))

    fig, axs = plt.subplots(1, 2, figsize=(13, 4.6))
    ax = axs[0]
    x = np.arange(len(T))
    ax.bar(x, T["P_delay"], color="#1e3c72", label="any weather delay")
    ax.bar(x, T["P_delay_3h"], color="#c2410c", label="delay of 3 hours or more")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{i}\n(n={n})" for i, n in zip(T.index, T["days"])], fontsize=7)
    ax.set_xlabel("new snow water equivalent that day at Meadows Pass SNOTEL (inches)")
    ax.set_ylabel("share of winter days (Nov-Apr, 2017-24)")
    ax.legend(fontsize=8)
    ax.set_title("I-90 Snoqualmie Pass delay chance by storm size", fontsize=10)
    ax = axs[1]
    ev2 = ev.copy()
    ev2["swe1"] = ev2["date"].map(s["swe1"])
    ax.scatter(ev2["swe1"], ev2["delay_min"] / 60, c=np.where(ev2["cause"].str.contains("AVALANCHE"), "#7c3aed", "#1e3c72"), s=24, alpha=0.8)
    ax.set_xlabel("new SWE that day, Meadows Pass (in)")
    ax.set_ylabel("delay (hours)")
    ax.set_yscale("symlog", linthresh=1)
    ax.set_title("Each delay: size of the storm vs. how long it lasted (purple: avalanche control)", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "i90_delay_vs_storm.png", dpi=110)


if __name__ == "__main__":
    main()
