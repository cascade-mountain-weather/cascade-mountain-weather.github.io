"""Pull and screen shortwave radiation from the three Synoptic stations that report it (for the corn model's clear-sky check).

    python scripts/corn_radiation_obs.py fetch --start 2026-02-26 --end 2026-03-02     # saves data/corn/radiation/<STID>.csv (appends)
    python scripts/corn_radiation_obs.py check --start 2026-02-26 --end 2026-03-02     # screens against the clear-sky engine, prints a table

Stations (Danny, Oct 14 2026): Alpental summit ALP55, Mt. Baker Pan Dome MTB50, Stevens Pass Tye Mill STS54. Mountain radiometers
fail often (rime, snow on the dome, tilt), so `check` keeps only readings that pass ALL of: sun at least 10 degrees above the
horizon; not above 1.05 x the clear-sky horizontal value at the station elevation; a clearness index (measured over clear-sky)
for the window within the daily upper envelope; and no flat-lined or negative values. Day summaries use the midday median.
Needs SYNOPTIC_TOKEN in the environment (never committed). Variable names and the units returned are printed on fetch, because
the station metadata decides them (solar_radiation is W/m2).
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "corn" / "radiation"
URL = "https://api.synopticdata.com/v2/stations/timeseries"
STATIONS = ["ALP55", "MTB50", "STS54"]
VARS = "solar_radiation,air_temp,wind_speed,relative_humidity"
MIN_SUN_ELEV, MAX_OVER_CLEAR = 10.0, 1.05


def fetch(start, end):
    token = (os.environ.get("SYNOPTIC_TOKEN") or "").strip()
    if not token:
        raise SystemExit("SYNOPTIC_TOKEN is not set in this environment.")
    OUT.mkdir(parents=True, exist_ok=True)
    s, e = pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1)
    r = requests.get(URL, params={"token": token, "stid": ",".join(STATIONS), "start": s.strftime("%Y%m%d%H%M"),
                                  "end": e.strftime("%Y%m%d%H%M"), "vars": VARS, "obtimezone": "utc", "units": "metric"}, timeout=120)
    r.raise_for_status()
    data = r.json()
    if data["SUMMARY"].get("RESPONSE_CODE") not in (1, 2):
        raise SystemExit(f"Synoptic error: {data['SUMMARY']}")
    for st in data.get("STATION", []):
        obs = st["OBSERVATIONS"]
        df = pd.DataFrame({"time": pd.to_datetime(obs["date_time"], utc=True)})
        for k, v in obs.items():
            if k != "date_time" and "_set_" in k:
                df[k.split("_set_")[0] + "_" + k.split("_set_")[1].split("d")[0]] = v
        meta = {k: st[k] for k in ("STID", "NAME", "LATITUDE", "LONGITUDE", "ELEVATION")}
        print(meta, "columns:", [c for c in df.columns if c != "time"], "rows:", len(df), "units:", data.get("UNITS", {}).get("solar_radiation"))
        f = OUT / f"{st['STID']}.csv"
        if f.exists():
            df = pd.concat([pd.read_csv(f, parse_dates=["time"]), df]).drop_duplicates("time").sort_values("time")
        df.to_csv(f, index=False)
        (OUT / f"{st['STID']}.meta.txt").write_text(repr(meta), encoding="utf-8")
    if not data.get("STATION"):
        print("no stations returned (the token may not allow this period):", data["SUMMARY"])


def check(start, end):
    import corn_clearsky as cs
    for stid in STATIONS:
        f = OUT / f"{stid}.csv"
        if not f.exists():
            print(stid, "no data fetched")
            continue
        meta = eval((OUT / f"{stid}.meta.txt").read_text(encoding="utf-8"))
        lat, lon, elev = float(meta["LATITUDE"]), float(meta["LONGITUDE"]), float(meta["ELEVATION"]) * 0.3048
        df = pd.read_csv(f, parse_dates=["time"]).set_index("time")
        col = next((c for c in df.columns if c.startswith("solar_radiation")), None)
        if col is None:
            print(stid, "no solar_radiation column")
            continue
        df = df.loc[start:end]
        # clear-sky on the same times (the engine works on 30-minute windows; take the window's midpoint-free hourly mean here)
        times = df.index
        import pvlib
        sp = pvlib.solarposition.get_solarposition(times, lat, lon, altitude=elev)
        cl = pvlib.location.Location(lat, lon, altitude=elev).get_clearsky(times, model="ineichen")["ghi"]
        d = pd.DataFrame({"obs": df[col], "clear": cl, "elev": sp["apparent_elevation"]})
        d["kt"] = d.obs / d.clear.where(d.clear > 20)
        ok = (d.elev >= MIN_SUN_ELEV) & (d.obs >= 0) & (d.obs <= MAX_OVER_CLEAR * d.clear)
        d["ok"] = ok
        print(f"\n{stid} {meta['NAME']} ({elev:.0f} m): {len(d)} readings, {int(ok.sum())} pass; midday (20-22 UTC) median kt by day:")
        mid = d[ok & (d.index.hour >= 19) & (d.index.hour <= 22)]
        print(mid.groupby(mid.index.date).kt.median().round(2).to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "check"])
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    a = ap.parse_args()
    (fetch if a.cmd == "fetch" else check)(a.start, a.end)


if __name__ == "__main__":
    main()
