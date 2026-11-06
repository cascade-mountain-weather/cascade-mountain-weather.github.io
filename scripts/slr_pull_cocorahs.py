"""Pull CoCoRaHS new-snow reports for Washington: a direct measurement of snow-to-liquid ratio.

    python scripts/slr_pull_cocorahs.py                       # Nov-Apr, 2008 season to now (resumable)
    python scripts/slr_pull_cocorahs.py --years 2020 2021

Why: SNOTEL daily depth change is a lower bound on new-snow depth (settling), so its ratios came out near 6. A CoCoRaHS
volunteer measures the new snow on a board AND melts a core to get its water content (NewSnowDepth and NewSnowSWE, inches),
once a day around 7 am. Depth over water content is the ratio of the snow that fell, with little time to settle.
The cost: stations are volunteers' backyards, mostly valleys and towns, so few sit at ski-terrain elevation, and each
report is one observer's measurement.

Source: https://data.cocorahs.org/cocorahs/export/exportreports.aspx (statewide, so it is asked for in 10-day chunks, the same as
scripts/cocorahs_obs.py). Only reports with a numeric new-snow depth above zero and a numeric new-snow water content are kept.
Coverage grows through the 2010s: a 10-day window in January 2008 has almost no reports, January 2013 has dozens of
stations and January 2020 well over a hundred.

Output, git-ignored with the rest of data/slr:
    data/slr/cocorahs/<season>.csv    season = the year it ends in (2020 = Nov 2019 to Apr 2020)
    columns: obs_date, obs_time, station, name, lat, lon, new_snow_in, new_snow_swe_in, precip_in
obs_date and obs_time are the observer's local date and time (Pacific). Station elevations come from the stations export when
the analysis needs them (scripts/cocorahs_obs.py caches it).
"""
import argparse
import csv
import io
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

URL = "https://data.cocorahs.org/cocorahs/export/exportreports.aspx"
HEADERS = {"User-Agent": "cascade-mountain-weather (+https://github.com/cascade-mountain-weather)"}
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "slr" / "cocorahs"
COLS = ["obs_date", "obs_time", "station", "name", "lat", "lon", "new_snow_in", "new_snow_swe_in", "precip_in"]


def fetch_text(params, tries=3):
    """The CSV text. Python's TLS handshake is sometimes dropped by this server, so fall back to curl."""
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(URL, params=params, headers=HEADERS, timeout=180)
            r.raise_for_status()
            return r.text
        except requests.RequestException as exc:
            last = exc
            try:
                q = "&".join(f"{k}={v}" for k, v in params.items())
                p = subprocess.run(["curl", "-s", "-m", "180", "-A", HEADERS["User-Agent"], f"{URL}?{q}"], capture_output=True, text=True, timeout=200)
                if p.returncode == 0 and p.stdout.startswith("ObservationDate"):
                    return p.stdout
            except (OSError, subprocess.SubprocessError):
                pass
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"CoCoRaHS request failed: {str(last)[:100]}")


def num(v):
    try:
        return float(v.strip())
    except (ValueError, AttributeError):
        return None


def chunk(start, stop):
    text = fetch_text({"ReportType": "Daily", "dtf": 1, "Format": "CSV", "State": "WA", "ReportDateType": "reportdate",
                       "StartDate": f"{start.month}/{start.day}/{start.year}", "EndDate": f"{stop.month}/{stop.day}/{stop.year}",
                       "TimesInGMT": "False"})
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        r = {k.strip(): (v or "").strip() for k, v in r.items()}
        depth, swe = num(r.get("NewSnowDepth")), num(r.get("NewSnowSWE"))
        if depth is None or swe is None or depth <= 0 or swe <= 0:
            continue
        rows.append({"obs_date": r["ObservationDate"], "obs_time": r["ObservationTime"], "station": r["StationNumber"],
                     "name": r["StationName"], "lat": r["Latitude"], "lon": r["Longitude"], "new_snow_in": depth,
                     "new_snow_swe_in": swe, "precip_in": num(r.get("TotalPrecipAmt"))})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, help="seasons by the year they end in (default 2008 to the current season)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    today = date.today()
    last = today.year + 1 if today.month >= 10 else today.year
    years = args.years or list(range(2008, last + 1))
    OUT.mkdir(parents=True, exist_ok=True)
    for year in years:
        path = OUT / f"{year}.csv"
        if path.exists() and not args.force:
            continue
        rows, day, end = [], date(year - 1, 11, 1), min(date(year, 4, 30), today)
        while day <= end:
            stop = min(day + timedelta(days=9), end)
            rows.extend(chunk(day, stop))
            day = stop + timedelta(days=1)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            w.writerows(rows)
        print(f"{year - 1}-{year}: {len(rows):,} snow reports with a water content, {len({r['station'] for r in rows})} stations")


if __name__ == "__main__":
    sys.exit(main())
