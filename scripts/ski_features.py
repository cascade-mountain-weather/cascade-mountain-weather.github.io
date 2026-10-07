"""Build assets/data/ski_features.json for the ski tool from data/ski/destinations.yml and elevations.json.

    python scripts/ski_features.py --mock      # Phase 2: sample conditions so the scorer and page can be built and tested
    python scripts/ski_features.py --real      # Phase 3 beta: this week's NBM forecast (data/ski/nbm_extract.json from scripts/ski_nbm.py)

Phase 3 replaces the mock block with real extraction (NBM through Herbie, NWAC, WSDOT, SNOTEL). The output shape is the
contract with assets/ski-model.js: per zone the static fields (name, modes, access points, elevations, drive hours, pass
type) and a `days` list (one entry per forecast day) of the conditions the scorer uses. A mock file says so at the top
level (`"mock": true`) and the page shows a banner; nothing in it is a forecast.
"""
import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "ski" / "destinations.yml"
ELEV = ROOT / "data" / "ski" / "elevations.json"
EXTRACT = ROOT / "data" / "ski" / "nbm_extract.json"
OUT = ROOT / "assets" / "data" / "ski_features.json"


CURVE = ROOT / "assets" / "data" / "pass_risk_curve.json"


def delay_risk(curves, swe_in):
    """(chance of a weather delay that day, chance of one lasting 3 hours or more) from one day's new snow water equivalent, inches."""
    x = min(max(swe_in, 0.0), curves["max_swe_in"])
    out = []
    for k in ("delay", "long"):
        c = curves["curves"][k]
        v = math.sqrt(x) if c["shape"] == "sqrt" else x
        out.append(round(1 / (1 + math.exp(-(c["a"] + c["b"] * v))), 3))
    return out


def mock_days(zone, elev, start, curves):
    """Plausible-looking sample numbers, deterministic per zone and day, scaled by elevation. Not a forecast."""
    out = []
    for k in range(3):
        d = start + timedelta(days=k)
        r = random.Random(f"{zone['id']}-{d:%Y%m%d}")
        storm = random.Random(f"storm-{d:%Y%m%d}").random()               # the same storm hits every zone that day
        snow = max(0.0, round((storm * 14 - 2 + r.uniform(-2, 3)) * (0.7 + 0.1 * (elev["forecast_point"] or 4000) / 4000), 1))
        out.append({
            "date": f"{d:%Y-%m-%d}",
            "new_snow_in": snow,                                              # 07:00-16:00 local window, plus the preceding night
            "snow_level_ft": int(2500 + 3500 * (1 - storm) + r.uniform(-400, 400)),
            "snow_ratio": round(r.uniform(9, 16), 1),                         # snow-to-liquid, the powder proxy (NBM SNOWLR)
            "gust_mph": int(10 + 35 * storm + r.uniform(-5, 10)),
            "cloud_pct": int(30 + 60 * storm + r.uniform(-15, 10)),
            "vis_mi": round(max(0.3, 8 - 7 * storm + r.uniform(-1, 1)), 1),
            "temp_f": int(20 + 14 * (1 - storm) + r.uniform(-3, 3)),
            "avy_danger": min(5, max(1, int(1 + storm * 3 + r.uniform(0, 1.2)))),     # 1 low .. 5 extreme; -1 would mean no forecast
        })
        out[-1]["swe_in"] = round(snow / out[-1]["snow_ratio"], 2)         # forecast new snow (in) to water equivalent (in)
    return out


LIVE = ROOT / "assets" / "data" / "live_conditions.json"


def base_depths(cfg):
    """{zone id: {base_in, stations, asof}}: the deepest snow depth reported at the zone's stations (None if none report one).
    Depth reports in the off-season can be sensor noise, which is why the page compares them with a threshold, not with zero."""
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    areas = {a["id"]: a for a in live["areas"]}
    out = {}
    for z in cfg["zones"]:
        best, who = None, None
        for aid in z.get("live_areas", []):
            for s in areas.get(aid, {}).get("stations", []):
                d = s.get("snow_depth_in")
                if d is not None and (best is None or d > best):
                    best, who = d, f"{s['label']} ({s.get('network')})"
        out[z["id"]] = {"base_in": best, "base_station": who, "base_asof": live["generated_utc"]}
    return out


def real_days(zid, extract):
    """Per-day conditions for one zone from the NBM extract. A value the NBM could not give stays None; the page says so."""
    out = []
    for e in extract["zones"][zid]:
        snow = e["snow_p50_in"]
        ratio = e["snow_ratio"]
        swe = None if snow is None else round(snow / (ratio if ratio else 10.0), 2)         # forecast new snow (in) to water equivalent (in)
        out.append({
            "date": e["date"], "new_snow_in": snow, "new_snow_lo_in": e["snow_p25_in"], "new_snow_hi_in": e["snow_p75_in"], "liquid_in": e["liquid_in"],
            "snow_level_ft": None if e["snow_level_ft"] is None else int(round(e["snow_level_ft"])), "snow_ratio": ratio, "gust_mph": None if e["gust_mph"] is None else int(round(e["gust_mph"])),
            "cloud_pct": None if e["cloud_pct"] is None else int(round(e["cloud_pct"])), "vis_mi": e["vis_mi"], "temp_f": e["temp_f"],
            "avy_danger": -1,                                   # NWAC forecasts start in late November: -1 means no forecast, never "low"
            "swe_in": swe,
        })
    return out


def add_risk(zones, curves):
    """Road delay chance per zone and day: the zone's own pass (curve), plus the passes it is reached over (via); NPS gate rule for Paradise."""
    by_id = {z["id"]: z for z in zones}
    for z in zones:
        rr = z.get("road_risk") or {}
        for k, d in enumerate(z["days"]):
            parts = []
            if rr.get("model") in ("curve", "nps_gate"):
                parts.append((rr["route"], *delay_risk(curves, d["swe_in"] or 0.0)))
            for vid in rr.get("via", []):
                v = by_id[vid]
                parts.append((v["road_risk"]["route"], *delay_risk(curves, v["days"][k]["swe_in"] or 0.0)))
            if not parts:
                d["road_risk"] = 0.0
                continue
            d["risk_parts"] = [{"route": r, "p": p} for r, p, _ in parts]
            d["delay_risk"] = round(1 - math.prod(1 - p for _, p, _ in parts), 3)
            d["delay_risk_3h"] = round(1 - math.prod(1 - q for _, _, q in parts), 3)
            d["gate_hold"] = bool(rr.get("model") == "nps_gate" and d["avy_danger"] >= 4)     # NPS matrix: High or Extreme danger holds the Paradise gate
            d["road_risk"] = 0.9 if d["gate_hold"] else d["delay_risk"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if not (a.mock or a.real):
        raise SystemExit("choose --mock or --real")
    extract = json.loads(EXTRACT.read_text(encoding="utf-8")) if a.real else None
    cfg = yaml.safe_load(SRC.read_text(encoding="utf-8"))
    elev = json.loads(ELEV.read_text(encoding="utf-8"))["zones"]
    curves = json.loads(CURVE.read_text(encoding="utf-8"))
    start = datetime.now(timezone.utc).date() + timedelta(days=1)
    zones = []
    bases = base_depths(cfg) if a.real else {}
    for z in cfg["zones"]:
        e = elev[z["id"]]
        zones.append({
            "id": z["id"], "name": z["name"], "modes": z["modes"], "nwac_zone": z["nwac_zone"],
            "top_ft": z["top_ft"], "access_ft": e["winter_access"], "forecast_ft": e["forecast_point"],
            "pass": z["pass"], "url": z.get("url"), "grooming_url": z.get("grooming_url"),
            "drive_hours": z["drive_hours"], "road_risk": z.get("road_risk"),
            "access_points": [{"id": p["id"], "name": p["name"], "type": p["type"], "modes": p["modes"], "ft": e.get("ap:" + p["id"])} for p in z["access_points"]],
            **bases.get(z["id"], {}),
            "days": real_days(z["id"], extract) if a.real else mock_days(z, e, start, curves),
        })
    add_risk(zones, curves)
    out = {"mock": not a.real, "risk_source": curves["source"], "generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",
           "note": "Sample numbers to build and test the scorer. Not a forecast." if not a.real else "Beta: NBM forecast, not yet checked against what happened.",
           "forecast": ({"model": extract["model"], "cycle_utc": extract["cycle_utc"], "generated_utc": extract["generated_utc"], "notes": extract["notes"]} if a.real else None),
           "origins": {k: v["name"] for k, v in cfg["origins"].items()}, "zones": zones}
    Path(a.out).write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print("wrote", a.out, len(zones), "zones")


if __name__ == "__main__":
    main()
