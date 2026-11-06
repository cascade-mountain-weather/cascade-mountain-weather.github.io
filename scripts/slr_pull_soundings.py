"""Pull the 00Z and 12Z radiosonde temperatures aloft (700 hPa and neighbours) from the IEM archive.

    python scripts/slr_pull_soundings.py                           # UIL, OTX, SLE, Nov-Apr, 1997 season to now (resumable)
    python scripts/slr_pull_soundings.py --stations UIL --years 2020 2021
    python scripts/slr_pull_soundings.py --months 12 1 2 --workers 8

Second step of the snow-to-liquid-ratio (SLR) study (the first is scripts/slr_pull_snotel.py). For each station and
launch time it records the temperature and height at 925, 850, 700 and 500 hPa. Only 700 hPa is the question; the
others are kept so the choice of level can be tested without downloading again.

Stations (IEM raob ids): UIL Quillayute (upwind, on the coast), OTX Spokane (east of the Cascades), SLE Salem (south).
Source: https://mesonet.agron.iastate.edu/json/raob.py, one request per launch (the same call scripts/collect_radiosonde_history.py
uses). About 362 launches a year per station for Nov-Apr, so the full run is roughly 30,000 requests: it runs in parallel,
saves one file per station and year as it goes, and skips files that exist, so it can be stopped and restarted.
A launch with no sounding is recorded as a row with an empty status so it is not asked for again.

Output, git-ignored with the rest of data/slr:
    data/slr/soundings/<station>_<year>.csv    year = the year the cold season ENDS in (2020 = Nov 2019 to Apr 2020)
    columns: station, valid_utc, status (ok | none | error), t925_c, t850_c, t700_c, t500_c, h925_m, h850_m, h700_m, h500_m

Launch times are 00Z and 12Z. SNOTEL daily values are midnight Pacific readings (08Z), so a SNOTEL day contains the 12Z
launch and the following 00Z launch; the analysis pairs them that way.
"""
import argparse
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

URL = "https://mesonet.agron.iastate.edu/json/raob.py"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "slr" / "soundings"
LEVELS = (925, 850, 700, 500)
STATIONS = ("UIL", "OTX", "SLE")
COLS = ["station", "valid_utc", "status"] + [f"t{p}_c" for p in LEVELS] + [f"h{p}_m" for p in LEVELS]
SEASON = (11, 12, 1, 2, 3, 4)   # November to April


def fetch(station, t, tries=3):
    """One launch: a row of values, status 'ok', 'none' (no sounding) or 'error' (network failure)."""
    row = {"station": station, "valid_utc": f"{t:%Y-%m-%dT%H:%MZ}", "status": "error"}
    for attempt in range(tries):
        try:
            r = requests.get(URL, params={"ts": f"{t:%Y%m%d%H%M}", "station": station}, timeout=40)
            r.raise_for_status()
            profiles = r.json().get("profiles") or []
            if not profiles or not profiles[0].get("profile"):
                row["status"] = "none"
                return row
            by = {}
            for lev in profiles[0]["profile"]:
                p = lev.get("pres")
                if p is not None and int(p) == p and int(p) in LEVELS and lev.get("tmpc") is not None:
                    by[int(p)] = lev
            for p in LEVELS:
                if p in by:
                    row[f"t{p}_c"] = by[p]["tmpc"]
                    row[f"h{p}_m"] = by[p].get("hght")
            row["status"] = "ok" if 700 in by else "none"   # a sounding without a 700 hPa temperature is no use here
            return row
        except Exception:   # noqa: BLE001 -- retry, then record the error so a rerun asks again
            time.sleep(1.5 * (attempt + 1))
    return row


def launches(year):
    """Every 00Z and 12Z launch from Nov 1 of year-1 to Apr 30 of year."""
    t, end = datetime(year - 1, 11, 1), datetime(year, 5, 1)
    while t < end:
        if t.month in SEASON:
            yield t
        t += timedelta(hours=12)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", nargs="+", default=list(STATIONS))
    ap.add_argument("--years", nargs="+", type=int, help="cold seasons by the year they end in (default 1997 to the current season)")
    ap.add_argument("--months", nargs="+", type=int, help="limit to these months, e.g. 12 1 2 (default Nov-Apr)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true", help="download again even if the station-year file exists")
    args = ap.parse_args()

    today = date.today()
    last = today.year + 1 if today.month >= 10 else today.year
    years = args.years or list(range(1997, last + 1))   # SNOTEL depth and SWE both start in 1996
    OUT.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(args.workers) as ex:
        for station in args.stations:
            for year in years:
                path = OUT / f"{station}_{year}.csv"
                if path.exists() and not args.force:
                    continue
                times = [t for t in launches(year) if t <= datetime.utcnow() and (not args.months or t.month in args.months)]
                rows = list(ex.map(lambda t: fetch(station, t), times))
                ok = sum(r["status"] == "ok" for r in rows)
                err = sum(r["status"] == "error" for r in rows)
                print(f"{station} {year - 1}-{year}: {ok} of {len(rows)} launches have a 700 hPa temperature" + (f", {err} errors (not saved)" if err else ""))
                if err:   # leave no file, so the next run asks again
                    continue
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=COLS)
                    w.writeheader()
                    w.writerows(rows)
    print("done")


if __name__ == "__main__":
    sys.exit(main())
