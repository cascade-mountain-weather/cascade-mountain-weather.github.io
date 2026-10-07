"""Download the long records for the teleconnection analysis (run by hand; results are cached, not committed).

    python scripts/tele_fetch.py                 # everything
    python scripts/tele_fetch.py --only indices  # just the indices

Writes to data/teleconnections/cache/ (git-ignored; the derived results are what get committed):
  stations.csv          Washington SNOTEL stations with a record that began on or before --first-year
  snotel/<n>.csv        daily TMAX, TMIN, TAVG (F), PREC (water-year accumulated precip, in), WTEQ (SWE, in), SNWD (in)
  pna_daily.csv         CPC daily PNA index, 1950-
  rmm.csv               BoM RMM1, RMM2, phase, amplitude, 1974-
  omi.csv               NOAA PSL OLR MJO index (OMI), PC1, PC2, amplitude
  oni.csv               monthly ONI from assets/data/climate_indices.json
Sources: NRCS AWDB REST API; CPC daily PNA; Bureau of Meteorology RMM; NOAA PSL OMI.
"""
import argparse
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "teleconnections" / "cache"
H = {"User-Agent": "cascade-mountain-weather.github.io teleconnection analysis (dlhogan@uw.edu)"}
AWDB = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/"
ELEMENTS = ["TMAX", "TMIN", "TAVG", "PREC", "WTEQ", "SNWD"]


def get(url, headers=H, **kw):
    for a in range(4):
        try:
            r = requests.get(url, headers=headers, timeout=180, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            print("   retry", a, e)
            time.sleep(5 * (a + 1))
    raise SystemExit("could not fetch " + url)


def stations(first_year):
    r = get(AWDB + "stations", params={"stationTriplets": "*:WA:SNTL", "activeOnly": "false"}).json()
    rows = []
    for s in r:
        begin = s["beginDate"][:10]
        if int(begin[:4]) <= first_year and s.get("endDate", "2100")[:4] >= "2100":
            rows.append({"triplet": s["stationTriplet"], "id": s["stationTriplet"].split(":")[0], "name": s["name"],
                         "elev_ft": round(s["elevation"]), "lat": s["latitude"], "lon": s["longitude"], "begin": begin})
    df = pd.DataFrame(rows).sort_values("id", key=lambda x: x.astype(int))
    df.to_csv(CACHE / "stations.csv", index=False)
    return df


def snotel(df, begin):
    (CACHE / "snotel").mkdir(parents=True, exist_ok=True)
    for _, s in df.iterrows():
        out = CACHE / "snotel" / f"{s['id']}.csv"
        if out.exists():
            continue
        frames = []
        for el in ELEMENTS:
            js = get(AWDB + "data", params={"stationTriplets": s["triplet"], "elements": el, "duration": "DAILY",
                                            "beginDate": begin, "endDate": "2026-09-30", "periodRef": "END",
                                            "centralTendencyType": "NONE", "returnFlags": "false",
                                            "returnOriginalValues": "false", "returnSuppressedValues": "false"}).json()
            vals = js[0]["data"][0]["values"] if js and js[0].get("data") else []
            frames.append(pd.Series({v["date"][:10]: v["value"] for v in vals if "value" in v}, name=el, dtype=float))
        pd.concat(frames, axis=1).rename_axis("date").to_csv(out)
        print(f"  {s['id']} {s['name']}: {out.stat().st_size // 1024} KB")


def indices():
    r = get("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.index.b500101.current.ascii").text
    rows = []
    for l in r.splitlines():
        m = re.match(r"\s*(\d{4})\s+(\d+)\s+(\d+)\s*(-?\d+\.\d+)", l)       # a few rows run the value into the day ("26-99.000")
        if m and float(m.group(4)) > -90:
            rows.append((f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", float(m.group(4))))
    pd.DataFrame(rows, columns=["date", "pna"]).to_csv(CACHE / "pna_daily.csv", index=False)
    r = get("http://www.bom.gov.au/climate/mjo/graphics/rmm.74toRealtime.txt", headers={"User-Agent": "Mozilla/5.0"}).text   # BoM refuses non-browser agents
    out = []
    for l in r.splitlines()[2:]:
        p = l.split()
        if len(p) >= 7 and p[0].isdigit():
            y, m, d, r1, r2, ph, amp = int(p[0]), int(p[1]), int(p[2]), float(p[3]), float(p[4]), int(p[5]), float(p[6])
            if amp < 900:
                out.append((f"{y:04d}-{m:02d}-{d:02d}", r1, r2, ph, amp))
    pd.DataFrame(out, columns=["date", "rmm1", "rmm2", "phase", "amp"]).to_csv(CACHE / "rmm.csv", index=False)
    r = get("https://psl.noaa.gov/mjo/mjoindex/omi.1x.txt").text
    out = []
    for l in r.splitlines():
        p = l.split()
        if len(p) >= 6 and p[0].isdigit():
            v = [float(x) for x in p[3:6]]
            if abs(v[0]) < 900:
                out.append((f"{int(p[0]):04d}-{int(p[1]):02d}-{int(p[2]):02d}", *v))
    pd.DataFrame(out, columns=["date", "pc1", "pc2", "amp"]).to_csv(CACHE / "omi.csv", index=False)
    ci = json.loads((ROOT / "assets" / "data" / "climate_indices.json").read_text(encoding="utf-8"))["oni"]
    y0 = int(ci["start"][:4])
    pd.DataFrame({"month": [f"{y0 + i // 12}-{i % 12 + 1:02d}" for i in range(len(ci["values"]))], "oni": ci["values"]}).to_csv(CACHE / "oni.csv", index=False)
    print("  indices written")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["indices", "snotel"])
    ap.add_argument("--first-year", type=int, default=1990, help="keep stations whose record began on or before this year")
    ap.add_argument("--begin", default="1978-10-01")
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    if a.only != "snotel":
        indices()
    if a.only != "indices":
        df = stations(a.first_year)
        print(len(df), "stations")
        snotel(df, a.begin)
