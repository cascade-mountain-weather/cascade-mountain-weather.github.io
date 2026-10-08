"""Typical weekend-morning drive times from each starting area to each ski-tool zone, from the Google Maps Routes API.

    python scripts/ski_traffic.py --count            # how many requests a run would make, no calls
    python scripts/ski_traffic.py --day sat          # (run it once a day until it says 0 left: the demo key allows about 100 requests a day)
    # Saturday morning, 05:30, 06:00, 06:30, 07:00 and 07:30 local (13 origins x 12 zones x 5 = 780 requests)
    python scripts/ski_traffic.py --day sun

The key is read from the GOOGLE_MAPS_KEY environment variable or from data/traffic/.google_key (git-ignored). Never commit it.

Google does not give historical traffic. A request with a future departure time returns the *typical* travel time for that day and
hour (their historical average), which is the "normal backup" this wants. Each request also returns the static (no traffic) time.
It does not know about storms, closures or a powder-day surge. Results go to data/traffic/typical_<day>.json and the script resumes
from that file, so a run can be stopped and restarted without paying for the same request twice.

Destination: each zone's first access point (the main lot). Departure date: a mid-winter Saturday/Sunday (the API accepts far-future dates).
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "ski" / "destinations.yml"
OUT_DIR = ROOT / "data" / "traffic"
PT = ZoneInfo("America/Los_Angeles")
URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# Starting areas: neighborhoods of Seattle plus the surrounding cities. Coordinates are a point in each, not a street address.
ORIGINS = {
    "seattle_nw": ("NW Seattle (Ballard)", 47.668, -122.384), "seattle_n": ("N Seattle (Northgate)", 47.708, -122.325),
    "seattle_ne": ("NE Seattle (Lake City)", 47.719, -122.295), "seattle_c": ("Central Seattle (Capitol Hill)", 47.623, -122.320),
    "seattle_sw": ("SW Seattle (West Seattle)", 47.561, -122.386), "seattle_s": ("S Seattle (Columbia City)", 47.560, -122.286),
    "seattle_se": ("SE Seattle (Rainier Beach)", 47.522, -122.262), "bellevue": ("Bellevue", 47.610, -122.201),
    "everett": ("Everett", 47.979, -122.202), "tacoma": ("Tacoma", 47.253, -122.444), "olympia": ("Olympia", 47.038, -122.900),
    "bellingham": ("Bellingham", 48.752, -122.479), "portland": ("Portland", 45.515, -122.679),
}
SKIP_ZONES = {"whistler"}      # out of the country and out of the weekend-drive range
FIRST_DATE = {"sat": "2027-01-16", "sun": "2027-01-17"}     # mid-winter weekend; the API gives the typical value for that weekday and time
SLOTS = [(5, 30), (6, 0), (6, 30), (7, 0), (7, 30)]      # the departure times the tool offers; --slots overrides


def key():
    k = os.environ.get("GOOGLE_MAPS_KEY")
    if not k and (OUT_DIR / ".google_key").exists():
        k = (OUT_DIR / ".google_key").read_text().strip()
    if not k:
        raise SystemExit("No key: set GOOGLE_MAPS_KEY or put it in data/traffic/.google_key")
    return k


def request(k, o, d, when_utc):
    body = {"origin": {"location": {"latLng": {"latitude": o[1], "longitude": o[2]}}},
            "destination": {"location": {"latLng": {"latitude": d[0], "longitude": d[1]}}},
            "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE", "departureTime": when_utc}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {
        "Content-Type": "application/json", "X-Goog-Api-Key": k,
        "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.distanceMeters"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rt = json.load(r)["routes"][0]
    return int(rt["duration"].rstrip("s")), int(rt["staticDuration"].rstrip("s")), rt["distanceMeters"]


def apply_drive_hours():
    """Replace the hand-estimated drive_hours and origins in destinations.yml with the typical Saturday 07:00 times (hours, one decimal). The other leave times are read by ski_features.py from typical_sat.json."""
    import re
    res = json.loads((OUT_DIR / "typical_sat.json").read_text())
    text = DEST.read_text(encoding="utf-8")
    zid, out, missing = None, [], []
    for line in text.splitlines(keepends=True):
        m = re.match(r"  - id: (\w+)", line)
        if m:
            zid = m.group(1)
        if zid and line.startswith("    drive_hours:"):
            vals = {o: res.get(f"{o}|{zid}|07:00") for o in ORIGINS}
            if all(vals.values()):
                line = "    drive_hours: {" + ", ".join(f"{o}: {round(v['min'] / 60, 1)}" for o, v in vals.items()) + "}" + chr(10)
            else:
                missing.append(zid)
        out.append(line)
    if missing:
        raise SystemExit(f"not applied: no complete 07:00 set yet for {missing}")
    text = "".join(out)
    nl = chr(10)
    block = "origins:" + nl + "".join(f"  {k}: {{name: {v[0]}, lat: {v[1]}, lon: {v[2]}}}" + nl for k, v in ORIGINS.items())
    text = re.sub("origins:" + nl + "(?:  .*" + nl + ")+", lambda _: block, text, count=1)
    DEST.write_text(text, encoding="utf-8")
    print("updated", DEST)



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", choices=["sat", "sun"], default="sat")
    ap.add_argument("--slots", help='comma-separated departure times to use instead of the five defaults, e.g. "07:00"')
    ap.add_argument("--apply", action="store_true", help="write the 07:00 times into data/ski/destinations.yml (origins and drive_hours), then stop")
    ap.add_argument("--count", action="store_true", help="print the number of requests and stop")
    ap.add_argument("--limit", type=int, help="stop after this many new requests (to test)")
    a = ap.parse_args()
    if a.apply:
        return apply_drive_hours()
    slots = [tuple(map(int, t.split(":"))) for t in a.slots.split(",")] if a.slots else SLOTS
    zones = [z for z in yaml.safe_load(DEST.read_text(encoding="utf-8"))["zones"] if z["id"] not in SKIP_ZONES]
    dests = {z["id"]: (z["access_points"][0]["lat"], z["access_points"][0]["lon"]) for z in zones}
    y, m, dd = map(int, FIRST_DATE[a.day].split("-"))
    path = OUT_DIR / f"typical_{a.day}.json"
    res = json.loads(path.read_text()) if path.exists() else {}
    todo = [(o, z, s) for o in ORIGINS for z in dests for s in slots if f"{o}|{z}|{s[0]:02d}:{s[1]:02d}" not in res]
    print(f"{len(ORIGINS)} origins x {len(dests)} zones x {len(slots)} times = {len(ORIGINS) * len(dests) * len(slots)} requests; {len(todo)} not yet done")
    if a.count:
        return
    k = key()
    n = 0
    for o, z, (h, mi) in todo:
        if a.limit is not None and n >= a.limit:
            break
        when = datetime(y, m, dd, h, mi, tzinfo=PT).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            dur, static, dist = request(k, ORIGINS[o], dests[z], when)
        except urllib.error.HTTPError as e:
            print("HTTP", e.code, e.read()[:300].decode(errors="replace"), file=sys.stderr)
            if e.code in (403, 429):
                break
            continue
        res[f"{o}|{z}|{h:02d}:{mi:02d}"] = {"min": round(dur / 60, 1), "free_min": round(static / 60, 1), "km": round(dist / 1000, 1)}
        n += 1
        if n % 50 == 0:
            path.write_text(json.dumps(res))
            print(f"  {n} done", flush=True)
        time.sleep(0.05)
    path.write_text(json.dumps(res))
    print(f"wrote {path} ({len(res)} entries, {n} new requests this run)")


if __name__ == "__main__":
    main()
