"""CoCoRaHS snowfall reports near each forecast site, as a cross-check on the SNOTEL estimate.

    python scripts/cocorahs_obs.py 2026-01-30T12:00 2026-02-02T12:00        # print stations and reports near each site

CoCoRaHS (Community Collaborative Rain, Hail and Snow Network) volunteers measure new snow once a day, usually
around 7 am local time, and report it to cocorahs.org, which offers open CSV exports:
  stations  https://data.cocorahs.org/cocorahs/export/exportstations.aspx   (location and elevation)
  reports   https://data.cocorahs.org/cocorahs/export/exportreports.aspx    (daily reports)

What is reported, per station and window
  A daily report is the new snow (in) over the 24 hours before the observation time. A window's total is the
  sum of the reports whose observation time falls in (start + 3 h, end + 3 h] local time, which lines the
  7 am reports up with a window that starts at 4 am Pacific. Days without a snow value are counted as missing
  and the station is marked incomplete for that window. The window summary uses the stations that reported
  every day; when none did it uses what was reported and says so (`complete: false`, a floor, not a total). A "T" (trace) counts as 0. Observers often leave the
  snow box empty on days without snow, so a day with no snow value and no precipitation counts as 0, while a
  day with no snow value but some precipitation is treated as missing (rain, or snow they did not measure).

Limits (the page says the same): stations are volunteers' backyards, mostly in valleys and towns, so few sit
anywhere near ski terrain (and none within 25 km of Stevens, Crystal or Paradise in the 2025-26 season). Their
elevation is saved next to each value, and a lowland station is a weak check on a mountain forecast. The
observation time is not exactly the window boundary. New-snow depth is measured on a board and settles.
This is a cross-check, not the score; the score uses SNOTEL (scripts/snotel_obs.py).
"""
import csv
import io
import json
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from draft_forecast_tables import is_pdt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cocorahs" / "stations_WA.json"
STATIONS_URL = "https://data.cocorahs.org/cocorahs/export/exportstations.aspx"
REPORTS_URL = "https://data.cocorahs.org/cocorahs/export/exportreports.aspx"
HEADERS = {"User-Agent": "cascade-mountain-weather (+https://github.com/cascade-mountain-weather)"}
RADIUS_KM = 25.0
OBS_OFFSET_H = 3          # a 7 am report belongs to the window that ends about 4 am the same day


def get_csv(url, params, tries=3, timeout=120):
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(io.StringIO(r.text))]
        except requests.RequestException as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"CoCoRaHS request failed: {str(last)[:100]}")


def num(v):
    if v is None:
        return None
    v = v.strip()
    if v.upper() == "T":
        return 0.0
    try:
        return float(v)
    except ValueError:
        return None


def km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    h = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def stations(refresh=False):
    """Washington CoCoRaHS stations: id, name, lat, lon, elev_ft. Cached because they change slowly."""
    if CACHE.exists() and not refresh:
        return json.loads(CACHE.read_text(encoding="utf-8"))["stations"]
    rows = get_csv(STATIONS_URL, {"State": "WA", "Format": "CSV"})
    out = []
    for r in rows:
        lat, lon, elev = num(r.get("Latitude")), num(r.get("Longitude")), num(r.get("Elevation"))
        if lat is None or lon is None:
            continue
        out.append({"id": r["StationNumber"], "name": r["StationName"], "lat": lat, "lon": lon,
                    "elev_ft": None if elev is None else int(elev), "status": r.get("StationStatus", "")})
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({"fetched_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}", "stations": out}, indent=0), encoding="utf-8")
    return out


def stations_near(sites, radius_km=RADIUS_KM):
    """{site name: [station dicts within radius, nearest first]} for sites given as dicts with name, lat, lon."""
    allst = stations()
    out = {}
    for s in sites:
        near = []
        for st in allst:
            d = km(s["lat"], s["lon"], st["lat"], st["lon"])
            if d <= radius_km:
                near.append(dict(st, km=round(d, 1)))
        out[s["name"]] = sorted(near, key=lambda x: x["km"])
    return out


def to_local(utc_dt):
    return utc_dt - timedelta(hours=7 if is_pdt(utc_dt.date()) else 8)


def daily_reports(start_utc, end_utc, ids):
    """Daily reports for the given station ids with observation dates around [start, end]: {id: [(local datetime, snow, swe, precip)]}."""
    a, b = to_local(start_utc) - timedelta(days=1), to_local(end_utc) + timedelta(days=2)
    wanted, out = set(ids), {}
    day = a
    while day <= b:                                  # the export is state-wide, so ask in chunks of up to 10 days
        stop = min(day + timedelta(days=9), b)
        rows = get_csv(REPORTS_URL, {"ReportType": "Daily", "dtf": 1, "Format": "CSV", "State": "WA", "ReportDateType": "reportdate",
                                     "StartDate": f"{day.month}/{day.day}/{day.year}", "EndDate": f"{stop.month}/{stop.day}/{stop.year}",
                                     "TimesInGMT": "False"})
        for r in rows:
            if r["StationNumber"] not in wanted:
                continue
            try:
                t = datetime.strptime(f"{r['ObservationDate']} {r['ObservationTime']}", "%Y-%m-%d %I:%M %p")
            except ValueError:
                continue
            out.setdefault(r["StationNumber"], []).append((t, num(r["NewSnowDepth"]), num(r["NewSnowSWE"]), num(r["TotalPrecipAmt"])))
        day = stop + timedelta(days=1)
    return out


def window_obs(near, windows):
    """near: {site: [stations]}; windows: {window id: (start_utc, end_utc)}.
    Returns {site: {"radius_km", "stations": [...with per-window values], "windows": {wid: summary}}}."""
    ids = {st["id"] for sts in near.values() for st in sts}
    if not ids:
        return {name: {"radius_km": RADIUS_KM, "stations": [], "windows": {}} for name in near}
    first = min(s for s, _ in windows.values())
    last = max(e for _, e in windows.values())
    reports = daily_reports(first, last, ids)
    result = {}
    for name, sts in near.items():
        rows, per_window = [], {wid: [] for wid in windows}
        for st in sts:
            reps = reports.get(st["id"], [])
            row = {"id": st["id"], "name": st["name"], "elev_ft": st["elev_ft"], "km": st["km"], "windows": {}}
            for wid, (s, e) in windows.items():
                ls, le = to_local(s).replace(tzinfo=None) + timedelta(hours=OBS_OFFSET_H), to_local(e).replace(tzinfo=None) + timedelta(hours=OBS_OFFSET_H)
                hit = [r for r in reps if ls < r[0] <= le]
                expected = max(1, round((le - ls).total_seconds() / 86400))
                # no snow value with no precipitation that day means nothing fell; no snow value with precipitation is unknown
                have = [(r[0], r[1] if r[1] is not None else 0.0, r[2], r[3]) for r in hit if r[1] is not None or not r[3]]
                if not hit:
                    continue                           # the station did not report at all in this window
                entry = {"snow_in": round(sum(r[1] for r in have), 1) if have else None, "days": len(have), "expected_days": expected,
                         "complete": len(have) >= expected}
                swe = [r[2] for r in have if r[2] is not None]
                if swe and len(swe) == len(have):
                    entry["swe_in"] = round(sum(swe), 2)
                row["windows"][wid] = entry
                if entry["snow_in"] is not None:
                    per_window[wid].append((entry["snow_in"], st, entry["complete"]))
            if row["windows"]:
                rows.append(row)
        summary = {}
        for wid, vals in per_window.items():
            if not vals:
                continue
            full = [v for v in vals if v[2]]
            use = full or vals                       # stations that reported every day, else whatever was reported (a floor)
            snow = sorted(v[0] for v in use)
            top = max(use, key=lambda x: (x[1]["elev_ft"] or 0))
            mid = snow[len(snow) // 2] if len(snow) % 2 else round((snow[len(snow) // 2 - 1] + snow[len(snow) // 2]) / 2, 1)
            summary[wid] = {"n": len(use), "n_reporting": len(vals), "complete": bool(full), "min_in": snow[0], "median_in": mid, "max_in": snow[-1],
                            "highest": {"name": top[1]["name"], "elev_ft": top[1]["elev_ft"], "km": top[1]["km"], "snow_in": top[0]}}
        result[name] = {"radius_km": RADIUS_KM, "stations": rows, "windows": summary}
    return result


def main():
    import yaml
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    s = datetime.fromisoformat(sys.argv[1]).replace(tzinfo=timezone.utc)
    e = datetime.fromisoformat(sys.argv[2]).replace(tzinfo=timezone.utc)
    sites = yaml.safe_load((ROOT / "data" / "nbm" / "sites.yml").read_text(encoding="utf-8"))["sites"]
    res = window_obs(stations_near(sites), {"total": (s, e)})
    for name, r in res.items():
        print(f"{name}: {len(r['stations'])} stations reporting; {r['windows'].get('total')}")


if __name__ == "__main__":
    main()
