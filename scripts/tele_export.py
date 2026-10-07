"""Export the composite table for the on-site explorer: assets/data/tele_composites.json (run by hand after tele_analysis.py).

    python scripts/tele_analysis.py --lags 0,1,2,...,14 --boot 200
    python scripts/tele_export.py

Shape: stations (id, name, lat, lon, elev_ft) and, for each index (mjo, pna, enso), each metric, each lag, a 2-D list
[station][class] of values (null where the station had too few days), with the classes listed under `classes`.
Values are ratios to the station's normal (snowfall, rain, big-snow days) or degrees F (temperature anomaly).
`sig` holds the same shape as 0/1: the 90% season-bootstrap interval excludes "no change".
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "data" / "teleconnections" / "results"
OUT = ROOT / "assets" / "data" / "tele_composites.json"
CLASSES = {"mjo": [1, 2, 3, 4, 5, 6, 7, 8], "pna": [-2, -1, 0, 1, 2], "enso": [-2, -1, 0, 1, 2]}
METRICS = ["swe", "tanom", "rain", "bigsnow", "precip", "bigwet"]


def main():
    c = pd.read_csv(RES / "composites.csv", dtype={"station": str})
    st = pd.read_csv(RES / "stations.csv", dtype={"id": str}).sort_values("lat", ascending=False).reset_index(drop=True)
    sid = {s: i for i, s in enumerate(st["id"])}
    out = {"generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",
           "period": "Nov-May, seasons 1992-2026", "source": "NRCS SNOTEL; NOAA PSL OMI; CPC PNA; CPC ONI",
           "stations": [{"id": r.id, "name": r.name, "lat": round(r.lat, 3), "lon": round(r.lon, 3), "elev_ft": int(r.elev_ft)} for r in st.itertuples()],
           "classes": CLASSES, "data": {}}
    for index, cats in CLASSES.items():
        out["data"][index] = {}
        for m in METRICS:
            out["data"][index][m] = {}
            for lag, g in c[(c["index"] == index) & (c["metric"] == m)].groupby("lag"):
                v = np.full((len(st), len(cats)), np.nan)
                s = np.zeros((len(st), len(cats)), dtype=int)
                base = 0 if m == "tanom" else 1
                for r in g.itertuples():
                    if r.cat in cats and r.station in sid:
                        i, j = sid[r.station], cats.index(r.cat)
                        v[i, j] = r.value
                        s[i, j] = int(r.lo > base or r.hi < base)
                out["data"][index][m][str(int(lag))] = {
                    "v": [[None if np.isnan(x) else round(float(x), 3) for x in row] for row in v],
                    "sig": s.tolist()}
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print("wrote", OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
