"""Zone storm table for the synoptic regime (storm-type) analysis: daily SWE gain per forecast zone and over-performance days.

    python scripts/storm_zones.py            # writes data/storms/zone_daily.csv

Zones are the nine forecast areas. Each is the mean daily SWE gain (in of water) of its SNOTEL stations, taken from the cached
records in data/teleconnections/cache/snotel (scripts/tele_fetch.py), through the same cleaning as the teleconnection analysis
(tele_analysis.load_station). Wells Creek (909, record from 1995) and Waterhole (974, from 1999) are fetched here when missing;
they are not in the 36-station teleconnection panel, whose stations all began by 1990.

An OVER-PERFORMANCE day for a zone is a day when its SWE gain is at least OVER_IN (0.5 in of water, roughly 4 to 6 in of snow)
above what the zone usually gets for the amount the other zones got: zone SWE minus RATIO x (mean of the other zones), where RATIO
is the zone's least-squares ratio to the other-zone mean over days when the others got more than 0.05 in. UNDER-performance is the
same with -0.5. A STORM day is a day when the mean over all zones is at least STORM_IN (0.25 in), or STORM_IN_SPRING (0.10 in) in April and May.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tele_analysis as ta  # noqa: E402
import tele_fetch as tf  # noqa: E402

ROOT = ta.ROOT
OUT = ROOT / "data" / "storms"
OVER_IN, STORM_IN, MIN_OTHERS_IN = 0.5, 0.25, 0.05
STORM_IN_SPRING = 0.10                           # April-May: smaller storms count, spring snow is lighter
FIRST_SEASON, LAST_SEASON = 1992, 2026          # a season is named for the year it ends in (Nov of the year before to May)
# Baker and Hurricane Ridge: the one station with a long record (Easy Pass starts in 2008, and a station that appears part
# way through would change the zone's usual level).
ZONE_STATIONS = {"Mt. Baker": [909], "Washington Pass": [515], "Stevens Pass": [791], "Hurricane Ridge": [974],
                 "Blewett Pass": [352], "Snoqualmie Pass": [672], "Crystal": [418], "Paradise": [679], "White Pass": [692]}


def ensure_records():
    need = [s for v in ZONE_STATIONS.values() for s in v if not (ta.CACHE / "snotel" / f"{s}.csv").exists()]
    if need:
        rows = [{"triplet": f"{s}:WA:SNTL", "id": str(s), "name": str(s)} for s in need]
        tf.snotel(pd.DataFrame(rows), "1978-10-01")


def build():
    ensure_records()
    sites = yaml.safe_load((ROOT / "data" / "nbm" / "sites.yml").read_text(encoding="utf-8"))["sites"]
    names = {s["name"] for s in sites}
    assert set(ZONE_STATIONS) <= names | {"Snoqualmie Pass"}, set(ZONE_STATIONS) - names
    series = {z: pd.concat([ta.load_station(str(s))["swe"] for s in ids], axis=1).mean(axis=1, skipna=True) for z, ids in ZONE_STATIONS.items()}
    df = pd.DataFrame(series)
    keep = ((df.index.month >= 11) | (df.index.month <= 5)) & (df.index >= pd.Timestamp(FIRST_SEASON - 1, 11, 1)) & (df.index <= pd.Timestamp(LAST_SEASON, 5, 31))
    df = df[keep]
    df.insert(0, "season", np.where(df.index.month >= 11, df.index.year + 1, df.index.year))
    zones = list(ZONE_STATIONS)
    A = df[zones].values
    df["all_mean"] = np.nanmean(A, axis=1)
    df["storm"] = df["all_mean"] >= np.where(df.index.month.isin([4, 5]), STORM_IN_SPRING, STORM_IN)
    ratios = {}
    for k, z in enumerate(zones):
        others = np.nanmean(np.delete(A, k, axis=1), axis=1)
        y = A[:, k]
        m = np.isfinite(others) & np.isfinite(y) & (others > MIN_OTHERS_IN)
        ratios[z] = float(np.sum(others[m] * y[m]) / np.sum(others[m] ** 2))
        anom = y - ratios[z] * others
        df[f"anom_{z}"] = anom
        df[f"over_{z}"] = anom >= OVER_IN
        df[f"under_{z}"] = anom <= -OVER_IN
    return df, ratios


if __name__ == "__main__":
    df, ratios = build()
    OUT.mkdir(parents=True, exist_ok=True)
    df.rename_axis("date").to_csv(OUT / "zone_daily.csv", float_format="%.3f")
    print(f"{len(df)} days, {df.season.min()}-{df.season.max()}; storm days {int(df.storm.sum())}")
    print("zone               ratio   with data   over   under   over-days that are storm days")
    for z, r in ratios.items():
        n = int(df[z].notna().sum()); o = int(df[f"over_{z}"].sum()); u = int(df[f"under_{z}"].sum()); so = int((df[f"over_{z}"] & df.storm).sum())
        print(f"{z:17s} {r:6.2f} {n:9d} {o:6d} {u:7d} {so:8d}")
    print("days with at least one zone over-performing:", int(df[[f'over_{z}' for z in ZONE_STATIONS]].any(axis=1).sum()))
