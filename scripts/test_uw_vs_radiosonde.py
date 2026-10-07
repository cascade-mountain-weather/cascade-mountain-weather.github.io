"""Quick intercomparison: UW WRF forecast soundings vs observed radiosondes.

    python scripts/test_uw_vs_radiosonde.py [--first 2026100300] [--last 2026100612]

Quillayute (UIL) is the only launch site near a UW sounding point (Olympex DOW, about 60 km away), so this
compares the two, run by run and lead by lead, using the same derived quantities for both (the `derive`
function of scripts/uw_soundings.py applied to the observed IEM RAOB profile). Launch times are 00Z and 12Z.
This is a spot check over a few days, not a verification: sample size is small and the site is not the same.
"""
import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import uw_soundings as u  # noqa: E402

IEM = "https://mesonet.agron.iastate.edu/json/raob.py"
KT_TO_MS = 0.514444
FIELDS = ("freezing_level_ft", "wet_bulb_zero_ft", "snow_level_ft", "t850_c", "t700_c", "pw_mm", "ivt_kgms")


def observed(valid):
    r = requests.get(IEM, params={"ts": valid.strftime("%Y%m%d%H%M"), "station": "UIL"}, headers=u.HEADERS, timeout=30)
    profs = r.json().get("profiles") or []
    if not profs or not profs[0].get("profile"):
        return None
    rows = [x for x in profs[0]["profile"] if None not in (x.get("pres"), x.get("hght"), x.get("tmpc"), x.get("dwpc"), x.get("drct"), x.get("sknt"))]
    rows.sort(key=lambda x: -x["pres"])
    if len(rows) < 8:
        return None
    col = lambda k: np.array([float(x[k]) for x in rows])  # noqa: E731
    sknt = col("sknt")
    c = {"PRES": col("pres"), "TMPC": col("tmpc"), "DWPC": col("dwpc"), "HGTM": col("hght"), "DRCT": col("drct"),
         "SKNT": sknt, "SPED": sknt * KT_TO_MS}
    return u.derive({}, c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", default="2026100300")
    ap.add_argument("--last", default="2026100612")
    ap.add_argument("--leads", type=int, nargs="+", default=[0, 12, 24, 36, 48])
    args = ap.parse_args()

    t = datetime.strptime(args.first, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    last = datetime.strptime(args.last, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    inits = []
    while t <= last:
        inits.append(t)
        t += timedelta(hours=12)

    obs_cache, pairs = {}, []
    for init in inits:
        for lead in args.leads:
            valid = init + timedelta(hours=lead)
            if valid > last + timedelta(hours=12):
                continue
            if valid not in obs_cache:
                obs_cache[valid] = observed(valid)
            ob = obs_cache[valid]
            if ob is None:
                continue
            html = u.fetch_frame(init.strftime("%Y%m%d%H"), lead, "dowlx")
            meta, cols = u.parse_frame(html) if html else (None, None)
            time.sleep(0.7)
            if cols is None:
                continue
            pairs.append((init, lead, valid, u.derive(meta, cols), ob))
    print(f"{len(pairs)} forecast/observation pairs from {len(obs_cache)} launches ({sum(v is not None for v in obs_cache.values())} with data)\n")

    print("observed Quillayute launches:")
    for v, ob in sorted(obs_cache.items()):
        if ob:
            print(f"  {v:%m-%d %HZ}  frz {ob['freezing_level_ft']}  wbz {ob['wet_bulb_zero_ft']}  snow {ob['snow_level_ft']}  T850 {ob.get('t850_c')}  PW {ob['pw_mm']}  IVT {ob['ivt_kgms']}")

    print("\nforecast minus observed, by lead (bias / MAE / n):")
    print("lead  " + "  ".join(f"{f:>26s}" for f in FIELDS))
    for lead in args.leads:
        cells = []
        for f in FIELDS:
            d = [p[3].get(f) - p[4].get(f) for p in pairs if p[1] == lead and p[3].get(f) is not None and p[4].get(f) is not None]
            cells.append(f"{np.mean(d):+8.1f} /{np.mean(np.abs(d)):7.1f} /{len(d):3d}" if d else "-".rjust(26))
        print(f"{lead:>4}h " + "  ".join(f"{c:>26s}" for c in cells))


if __name__ == "__main__":
    main()
