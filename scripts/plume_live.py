"""Write the live data for the interactive plume map on the precipitation tools page.

    python scripts/plume_live.py              # next 4 forecast days, starting with the current one
    python scripts/plume_live.py --days 3

Output: assets/data/plume_live.json (bot-generated, do not hand-edit). Same format as the frozen plume_data.json that
scripts/post_plume.py writes for a forecast post (assets/post-plume-map.js draws both), but rebuilt from the current
assets/data/nbm_plumes.json and assets/data/hires_plumes.json every time model_data.yml runs. A forecast day runs
12Z to 12Z (4 am Pacific), so the window starts at the latest 12Z at or before now. Needs only pandas and PyYAML.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
NBM = ROOT / "assets" / "data" / "nbm_plumes.json"
HIRES = ROOT / "assets" / "data" / "hires_plumes.json"
OUT = ROOT / "assets" / "data" / "plume_live.json"
TZ = "America/Los_Angeles"
MODELS = ("hrrr", "rrfs", "hrdps")


def rnd(v):
    return [None if x is None else round(float(x), 3) for x in v]


def build(nbm, hires, days, now):
    cfg = yaml.safe_load((ROOT / "data" / "nbm" / "sites.yml").read_text(encoding="utf-8"))
    coords = {s["name"]: (s["lat"], s["lon"]) for s in cfg["sites"] + cfg.get("plume_only_sites", [])}
    t0u = now.floor("D") + pd.Timedelta(hours=12)
    if t0u > now:
        t0u -= pd.Timedelta(days=1)
    t1u = t0u + pd.Timedelta(days=days)
    ends_all = pd.DatetimeIndex(pd.to_datetime(nbm["window_end_utc"], utc=True))
    keep = (ends_all - pd.Timedelta(hours=6) >= t0u) & (ends_all <= t1u)
    ends_utc = [e for e, k in zip(nbm["window_end_utc"], keep) if k]

    def pick(model_ends, values):
        by_end = dict(zip(model_ends, values))
        return [by_end.get(e) for e in ends_utc]

    sites = {}
    for name, s in nbm["sites"].items():
        if name not in coords:
            continue
        sel = lambda key: [v for v, k in zip(s[key], keep) if k]  # noqa: E731
        site = {"lat": coords[name][0], "lon": coords[name][1],
                "nbm": {k: rnd(sel(k)) for k in ("p25", "p50", "p75", "det", "precip")}}
        for key in MODELS:
            md = hires["models"].get(key)
            st = md and md["sites"].get(name)
            if st:
                site[key] = {"snow": rnd(pick(md["window_end_utc"], st["snow"])),
                             "precip": rnd(pick(md["window_end_utc"], st["precip"]))}
        sites[name] = site
    return {"schema": 1, "tz": TZ, "live": True,
            "window_start_local": str(t0u.tz_convert(TZ)), "window_end_local": str(t1u.tz_convert(TZ)),
            "generated_utc": nbm["generated_utc"],
            "cycles": {"nbm": nbm["cycle_utc"], **{k: v["cycle_utc"] for k, v in hires["models"].items() if k in MODELS}},
            "ends_utc": ends_utc, "sites": sites}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=4)
    args = ap.parse_args()
    nbm = json.loads(NBM.read_text(encoding="utf-8"))
    hires = json.loads(HIRES.read_text(encoding="utf-8"))
    data = build(nbm, hires, args.days, pd.Timestamp(datetime.now(timezone.utc)))
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print("wrote", OUT, f"({len(data['sites'])} sites, {len(data['ends_utc'])} windows)")


if __name__ == "__main__":
    main()
