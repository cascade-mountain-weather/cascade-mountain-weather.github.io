"""Pull daily snow water equivalent and snow depth for every Washington SNOTEL station with both sensors.

    python scripts/slr_pull_snotel.py                       # all stations, whole record (resumable)
    python scripts/slr_pull_snotel.py --stations 791:WA:SNTL 898:WA:SNTL --start 2010-10-01
    python scripts/slr_pull_snotel.py --force               # re-download stations already saved

First step of the snow-to-liquid-ratio (SLR) study: does the 700 hPa temperature in a storm say anything about the
density of the snow that fell? This script only gathers the observations; scripts/slr_pull_soundings.py gathers the
temperatures.

Source: NRCS AWDB REST API (the same one scripts/snotel_obs.py uses), DAILY duration. The stations are found from the
station metadata: network SNTL, state WA, with both WTEQ (snow water equivalent) and SNWD (snow depth) listed at the
daily duration. Output, git-ignored with the rest of data/slr:

    data/slr/snotel_daily/<triplet>.csv     one file per station (so an interrupted run resumes)
    data/slr/snotel_stations.csv            station, name, elevation, lat, lon, first and last date

Columns of a daily file:
    date      the day the reading is stamped with (a daily value is the station's midnight reading, Pacific standard
              time; check this against the AWDB documentation before relying on it for timing)
    wteq_in   snow water equivalent, inches
    snwd_in   snow depth, inches (whole inches: the depth sensor reports to the inch)
    prec_in   accumulated precipitation since the start of the water year, inches (a running total that resets in October, so
              it is only useful as a difference between two days)
    tavg_f    daily mean air temperature, F

Only November to April is kept (the rest is dropped before saving). Nothing is cleaned or screened here; the screening (cold days, spikes, minimum SWE gain, settling) belongs in the SLR
analysis, where it can be changed without downloading again.
"""
import argparse
import csv
import sys
import time
from datetime import date
from pathlib import Path

import requests

BASE = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "slr"
ELEMENTS = {"WTEQ": "wteq_in", "SNWD": "snwd_in", "PREC": "prec_in", "TAVG": "tavg_f"}
EARLIEST = "1980-10-01"   # before any Washington SNOTEL station had both sensors; the station's own start is used if later


def get_json(path, params, tries=4, timeout=180):
    for attempt in range(tries):
        try:
            r = requests.get(f"{BASE}/{path}", params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:   # noqa: BLE001 -- retry on any network or server error
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{path} failed: {str(last)[:120]}")


def washington_stations():
    """Washington SNOTEL stations that list daily WTEQ and SNWD, from the AWDB metadata."""
    meta = get_json("stations", {"stationTriplets": "*:WA:SNTL", "activeOnly": "false", "returnStationElements": "true"})
    out = []
    for s in meta:
        have = {(e["elementCode"], e["durationName"]) for e in (s.get("stationElements") or [])}
        if ("WTEQ", "DAILY") in have and ("SNWD", "DAILY") in have:
            out.append(s)
    return out


def pull_station(station, start, end):
    """{date: {column: value}} for one station."""
    triplet = station["stationTriplet"]
    first = max(start, station["beginDate"][:10])
    last = min(end, station["endDate"][:10]) if station["endDate"][:4] != "2100" else end
    days = {}
    for code, col in ELEMENTS.items():
        blocks = get_json("data", {"stationTriplets": triplet, "elements": code, "duration": "DAILY",
                                    "beginDate": first, "endDate": last})
        for blk in blocks:
            for el in blk.get("data", []):
                for v in el.get("values", []):
                    if v.get("value") is not None:
                        days.setdefault(v["date"][:10], {})[col] = v["value"]
    return days


SEASON = (11, 12, 1, 2, 3, 4)   # November to April only: the study is about snow falling in the cold season


def write_station(path, days):
    cols = list(ELEMENTS.values())
    days = {d: v for d, v in days.items() if int(d[5:7]) in SEASON}
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date"] + cols)
        for d in sorted(days):
            w.writerow([d] + [days[d].get(c, "") for c in cols])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", nargs="+", help="station triplets (default: every Washington SNOTEL station with both sensors)")
    ap.add_argument("--start", default=EARLIEST, help="first date, YYYY-MM-DD")
    ap.add_argument("--end", default=date.today().isoformat(), help="last date, YYYY-MM-DD")
    ap.add_argument("--force", action="store_true", help="download again even if the station's file exists")
    args = ap.parse_args()

    stations = washington_stations()
    if args.stations:
        stations = [s for s in stations if s["stationTriplet"] in args.stations]
    print(f"{len(stations)} stations with daily WTEQ and SNWD")
    folder = OUT / "snotel_daily"
    folder.mkdir(parents=True, exist_ok=True)

    summary = []
    for k, s in enumerate(sorted(stations, key=lambda x: x["stationTriplet"]), 1):
        triplet = s["stationTriplet"]
        path = folder / f"{triplet.replace(':', '_')}.csv"
        if path.exists() and not args.force:
            days = {r["date"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}
            print(f"[{k}/{len(stations)}] {triplet} {s['name']}: have {len(days)} days")
        else:
            days = pull_station(s, args.start, args.end)
            write_station(path, days)
            both = sum(1 for d in days.values() if "wteq_in" in d and "snwd_in" in d)
            print(f"[{k}/{len(stations)}] {triplet} {s['name']}: {len(days)} days, {both} with both SWE and depth")
        ds = sorted(days)
        summary.append([triplet, s["name"], s.get("elevation"), s.get("latitude"), s.get("longitude"),
                        ds[0] if ds else "", ds[-1] if ds else "", len(ds)])

    with open(OUT / "snotel_stations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["triplet", "name", "elevation_ft", "lat", "lon", "first_date", "last_date", "days"])
        w.writerows(summary)
    print("wrote", (OUT / "snotel_stations.csv").relative_to(ROOT))


if __name__ == "__main__":
    sys.exit(main())
