"""Collect the monthly climate indices for the Teleconnections page: ENSO (ONI) and PDO.

    python scripts/collect_climate_indices.py            # writes assets/data/climate_indices.json
    python scripts/collect_climate_indices.py --out FILE

Sources (both update about once a month, so a daily run is cheap and only commits when a value changes):
  ONI  NOAA Climate Prediction Center, Oceanic Nino Index, version 6 (ERSSTv5 based; recent values are estimates):
       https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/   (an HTML table: year by rolling 3-month season)
  PDO  NOAA NCEI, ERSST v6 PDO index:
       https://www.ncei.noaa.gov/pub/data/cmb/ersst/v5/v6/index/ersst.v6.pdo.dat   (year by month; 99.99 means missing)

Output arrays are monthly, starting at the stated month, with null for missing:
  oni.values[i]  the 3-month ONI centered on month i (the DJF value is January's), from 1950-01
  pdo.values[i]  the PDO of month i, from 1850-01
Nothing is invented: a month the source does not have yet is left out (the arrays end at the latest value).
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ONI_URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/"
PDO_URL = "https://www.ncei.noaa.gov/pub/data/cmb/ersst/v5/v6/index/ersst.v6.pdo.dat"
HEADERS = {"User-Agent": "cascade-mountain-weather.github.io climate index page (dlhogan@uw.edu)"}
OUT = Path(__file__).resolve().parent.parent / "assets" / "data" / "climate_indices.json"
SEASONS = {"Year", "DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"}


def get(url):
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.text


def parse_oni(html):
    """{year: [12 or fewer values]} from the CPC table. The header row repeats every ten years, and the current
    year has only the seasons that exist so far."""
    text = re.sub(r"<[^>]+>", " ", html)
    start = text.find("NDJ")
    if start < 0:
        raise ValueError("ONI table header not found")
    rows, year = {}, None
    for tok in text[start + 3:].split():
        if re.fullmatch(r"(19|20)\d\d", tok):
            year = int(tok)
            rows[year] = []
        elif year is not None and re.fullmatch(r"-?\d+\.\d", tok):
            rows[year].append(float(tok))
        elif tok in SEASONS or tok in ("&nbsp;",):
            continue
        elif year is not None and rows[year]:
            break                      # the page footer
    return {y: v for y, v in rows.items() if v}


def monthly(rows, first_year):
    out = []
    for y in range(first_year, max(rows) + 1):
        vals = rows.get(y, [])
        out += vals + [None] * (12 - len(vals)) if y < max(rows) else vals
    return out


def parse_pdo(text):
    rows = {}
    for ln in text.splitlines():
        p = ln.split()
        if len(p) == 13 and p[0].isdigit():
            rows[int(p[0])] = [None if float(x) > 90 else float(x) for x in p[1:]]
    if not rows:
        raise ValueError("no PDO rows found")
    vals = []
    for y in range(min(rows), max(rows) + 1):
        vals += rows.get(y, [None] * 12)
    while vals and vals[-1] is None:
        vals.pop()
    return min(rows), vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out_path = Path(args.out)
    old = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}

    oni_rows = parse_oni(get(ONI_URL))
    oni_first = min(oni_rows)
    oni = monthly(oni_rows, oni_first)
    pdo_first, pdo = parse_pdo(get(PDO_URL))
    if len(oni) < 12 * 60 or len(pdo) < 12 * 100:
        sys.exit(f"parsed too little (ONI {len(oni)} months, PDO {len(pdo)} months); keeping the existing file")

    result = {
        "oni": {"source": ONI_URL, "name": "Oceanic Nino Index (ONI), version 6", "start": f"{oni_first}-01", "values": oni,
                "note": "Three-month running mean of the Nino 3.4 sea surface temperature anomaly, plotted at its center month. Recent values are estimates."},
        "pdo": {"source": PDO_URL, "name": "Pacific Decadal Oscillation (PDO), ERSST v6", "start": f"{pdo_first}-01", "values": pdo,
                "note": "Monthly index from the leading pattern of North Pacific sea surface temperature variability."},
    }
    if {k: v for k, v in old.items() if k != "generated_utc"} == result:
        print("no change")
        return
    result["generated_utc"] = f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out_path}: ONI {len(oni)} months from {oni_first} (latest {oni[-1]}), "
          f"PDO {len(pdo)} months from {pdo_first} (latest {pdo[-1]}), {out_path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
