"""Pull hourly SWE, snow depth, precipitation and air temperature for 28 Cascade and Olympic SNOTEL stations.

    python scripts/slr_pull_snotel_hourly.py                    # 28 stations, Nov-Apr, 2005-06 season to now (resumable)
    python scripts/slr_pull_snotel_hourly.py --stations 606:WA:SNTL --years 2012

Why: daily depth changes are blurred by settling and by the depth sensor's inch resolution (scripts/slr_analysis.py found no
signal). Hourly values let a storm be measured as it falls: the depth gain and the SWE gain over hours when both rise.

Stations: crest and flanks (3,000 ft and up) of the Cascades plus the Olympics, with hourly SWE and depth since before
the 2005-06 winter, chosen by how well depth rises with SWE in the daily record (December to March since 2005: share of SWE gains of
0.4 in or more where the depth also rose 1 in or more; at least 150 such events and under 2% impossible densities).
Source: NRCS AWDB REST API, HOURLY duration, in the station's local standard time (no daylight shift, PST).

Output, git-ignored with the rest of data/slr:
    data/slr/snotel_hourly/<triplet>_<season>.csv     season = the year it ends in (2020 = Nov 2019 to Apr 2020)
    columns: time (local standard, YYYY-MM-DD HH:MM), wteq_in, snwd_in, prec_in (running total since Oct 1), tobs_f
A missing hour is simply absent from the file (not filled), and a sensor missing for an hour leaves that field empty.
"""
import argparse
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import requests

BASE = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "slr" / "snotel_hourly"
ELEMENTS = {"WTEQ": "wteq_in", "SNWD": "snwd_in", "PREC": "prec_in", "TOBS": "tobs_f"}
STATIONS = {
    "841:WA:SNTL": "Upper Wheeler", "832:WA:SNTL": "Trough", "502:WA:SNTL": "Green Lake", "507:WA:SNTL": "Grouse Camp",
    "599:WA:SNTL": "Lost Horse", "941:WA:SNTL": "Mowich", "606:WA:SNTL": "Lyman Lake", "734:WA:SNTL": "Sasse Ridge",
    "648:WA:SNTL": "Mount Crag", "375:WA:SNTL": "Bumping Ridge", "478:WA:SNTL": "Fish Lake", "974:WA:SNTL": "Waterhole",
    "899:WA:SNTL": "Tinkham Creek", "692:WA:SNTL": "Pigtail Peak", "863:WA:SNTL": "White Pass E.S.", "352:WA:SNTL": "Blewett Pass",
    "699:WA:SNTL": "Pope Ridge", "748:WA:SNTL": "Sheep Canyon", "642:WA:SNTL": "Morse Lake", "910:WA:SNTL": "Elbow Lake",
    "711:WA:SNTL": "Rainy Pass", "942:WA:SNTL": "Burnt Mountain", "788:WA:SNTL": "Stampede Pass", "515:WA:SNTL": "Harts Pass",
    "420:WA:SNTL": "Cougar Mountain",
    "1085:WA:SNTL": "Cayuse Pass", "679:WA:SNTL": "Paradise", "418:WA:SNTL": "Corral Pass",   # Rainier; hourly records start in autumn 2006
    # the stations the forecast evaluation scores against (data/nbm/sites.yml) that are not in the list above, so the depth model has them too
    "909:WA:SNTL": "Wells Creek", "998:WA:SNTL": "Easy Pass", "791:WA:SNTL": "Stevens Pass", "672:WA:SNTL": "Olallie Meadows",
}


def fetch(triplet, year, tries=4):
    """{time: {column: value}} for one station and one cold season, or None after repeated failures."""
    for attempt in range(tries):
        try:
            r = requests.get(BASE, params={"stationTriplets": triplet, "elements": ",".join(ELEMENTS), "duration": "HOURLY",
                                           "beginDate": f"{year - 1}-11-01", "endDate": f"{year}-04-30"}, timeout=180)
            r.raise_for_status()
            rows = {}
            for blk in r.json():
                for el in blk.get("data", []):
                    col = ELEMENTS.get(el["stationElement"]["elementCode"])
                    for v in el.get("values", []):
                        if col and v.get("value") is not None:
                            rows.setdefault(v["date"], {})[col] = v["value"]
            return rows
        except Exception:   # noqa: BLE001 -- retry on any network or server error
            time.sleep(2 * (attempt + 1))
    return None


def job(args):
    triplet, year = args
    path = OUT / f"{triplet.replace(':', '_')}_{year}.csv"
    if path.exists():
        return triplet, year, None, "have"
    rows = fetch(triplet, year)
    if rows is None:
        return triplet, year, None, "error"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time"] + list(ELEMENTS.values()))
        for t in sorted(rows):
            w.writerow([t] + [rows[t].get(c, "") for c in ELEMENTS.values()])
    return triplet, year, len(rows), "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", nargs="+", default=list(STATIONS))
    ap.add_argument("--years", nargs="+", type=int, help="seasons by the year they end in (default 2006 to the current season)")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    today = date.today()
    last = today.year + 1 if today.month >= 10 else today.year
    years = args.years or list(range(2006, last + 1))
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = [(s, y) for s in args.stations for y in years]
    done = bad = 0
    with ThreadPoolExecutor(args.workers) as ex:
        for triplet, year, n, status in ex.map(job, tasks):
            done += 1
            if status == "error":
                bad += 1
                print(f"[{done}/{len(tasks)}] {triplet} {STATIONS.get(triplet, '')} {year}: FAILED (not saved; rerun to retry)", flush=True)
            elif status == "ok":
                print(f"[{done}/{len(tasks)}] {triplet} {STATIONS.get(triplet, '')} {year}: {n} hours", flush=True)
    print(f"done, {bad} failed")


if __name__ == "__main__":
    sys.exit(main())
