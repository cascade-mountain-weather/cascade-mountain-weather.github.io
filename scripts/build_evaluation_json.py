"""Build assets/data/evaluation.json for the evaluation page from the scored weekends.

    python scripts/build_evaluation_json.py

Reads every data/evaluation/backfill/score_*.json (season rebuild) and data/evaluation/score_*.json (live
weekends, once the Monday workflow writes them), plus data/nbm/sites.yml for the map coordinates, and writes
one tidy file the page reads in the browser. All statistics are computed in the browser from the records, so
a new product (HRRR, HRDPS) is just another field on each record; nothing here needs to change for it except
adding the field.

Seasons run September to August and are named by their two years (2025-26). Each weekend is tagged with its
season so the page can filter. `SEASONS` lists every season the page offers, including the current one before it
has any weekends. Test weekends from before a season's first real forecast go in PRESEASON and are left out.

Record fields (inches), per weekend and area:
  obs       [low, mid, high]   observed snowfall estimate over the NBM window (Friday 12Z to Monday 12Z)
  obs_ours  [low, mid, high]   the same over the author's own period (4 pm Thursday to 4 am Monday); only
                               present when it differs, i.e. when the author's forecast was saved
  nbm       [p25, p50, p75]
  ours      [low, high] or null
  days      {day1|day2|day3: {obs: [...], nbm: [...], hrrr: x, hrdps: x, coco: {...}}}  for the per-day view and the
            Friday comparison (HRRR and HRDPS run 48 hours, so they have a value for day1 only; HRDPS only for weekends
            scored live, since it is not archived)
  coco      CoCoRaHS cross-check (volunteer stations within 25 km): {n, nr, full, med, max, top: [name, elev_ft, in]}
            for the weekend total, and the same under days. Not part of any score.
"""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCORE_DIRS = [ROOT / "data" / "evaluation" / "backfill", ROOT / "data" / "evaluation"]
SITES = ROOT / "data" / "nbm" / "sites.yml"
OUT = ROOT / "assets" / "data" / "evaluation.json"

SEASONS = [
    {"id": "2026-27", "label": "2026–27", "note": ""},
    {"id": "2025-26", "label": "2025–26", "note": "Rebuilt with the new method from the model archive. These are not the numbers the original evaluation showed."},
]
PRESEASON = {"2026-10-03"}   # first-day dates of test weekends before the 2026-27 forecasts began


def season_of(first_day):
    d = date.fromisoformat(first_day)
    start = d.year if d.month >= 9 else d.year - 1
    return f"{start}-{str(start + 1)[2:]}"


def coco(w, a=None, wid=None):
    """Compact CoCoRaHS summary of a scored window, with each station's value so the page can filter, or None."""
    c = (w or {}).get("cocorahs")
    if not c:
        return None
    h = c.get("highest") or {}
    out = {"n": c["n"], "nr": c["n_reporting"], "full": bool(c["complete"]), "med": c["median_in"], "max": c["max_in"],
           "top": [h.get("name"), h.get("elev_ft"), h.get("snow_in")]}
    stations = []
    for st in (a or {}).get("cocorahs_stations") or []:
        v = (st.get("windows") or {}).get(wid)
        if v and v.get("snow_in") is not None:
            stations.append([st["name"], st["elev_ft"], st["km"], v["snow_in"], bool(v["complete"])])
    if stations:
        out["st"] = stations    # [name, elevation ft, km from the site, snow in, reported every day]
    return out


def triple(d, keys):
    if not d or any(d.get(k) is None for k in keys):
        return None
    return [d[k] for k in keys]


def main():
    sites = yaml.safe_load(SITES.read_text(encoding="utf-8"))["sites"]
    coords = {s["name"]: (s["lat"], s["lon"]) for s in sites}
    files = {}
    for d in SCORE_DIRS:                      # later directories win when a weekend appears twice
        for p in sorted(d.glob("score_*.json")):
            files[p.stem.replace("score_", "")] = p
    weekends, areas, records, snow = [], {}, [], []
    for first_day, path in sorted(files.items()):
        if first_day in PRESEASON:
            continue
        s = json.loads(path.read_text(encoding="utf-8"))
        first = date.fromisoformat(first_day)
        wi = len(weekends)
        weekends.append({"id": first_day, "season": season_of(first_day), "label": f"{first:%b} {first.day}–{(first + timedelta(days=2)).day}",
                         "thursday": (first - timedelta(days=1)).isoformat(), "nbm_cycle": s["nbm_cycle_utc"],
                         "has_ours": bool(s.get("our_forecast_found"))})
        for name, a in s["areas"].items():
            areas.setdefault(name, {"id": name, "name": name, "lat": coords.get(name, (None, None))[0], "lon": coords.get(name, (None, None))[1],
                                    "obs_stations": a.get("obs_stations"), "forecast_elev_ft": a.get("forecast_elev_ft")})
            tot = a["windows"].get("total")
            if not tot:
                continue
            rec = {"w": wi, "a": name,
                   "obs": triple(tot.get("observed"), ("low", "mid", "high")),
                   "nbm": triple(tot.get("nbm"), ("p25", "p50", "p75")),
                   "ours": tot.get("ours")}
            if tot.get("observed_for_ours"):
                rec["obs_ours"] = triple(tot["observed_for_ours"], ("low", "mid", "high"))
            days = {}
            for wid, w in a["windows"].items():
                if wid.startswith("day"):
                    days[wid] = {"obs": triple(w.get("observed"), ("low", "mid", "high")), "nbm": triple(w.get("nbm"), ("p25", "p50", "p75"))}
            for wid, w in a["windows"].items():
                if wid.startswith("day"):
                    for model in ("hrrr", "hrdps"):
                        if w.get(model) and w[model].get("snowfall_in") is not None:
                            days[wid][model] = w[model]["snowfall_in"]
                    c = coco(w, a, wid)
                    if c:
                        days[wid]["coco"] = c
                    if isinstance(w.get("ours"), list):          # a day-level forecast of ours, when one was saved
                        days[wid]["ours"] = w["ours"]
            rec["days"] = days
            if coco(tot, a, "total"):
                rec["coco"] = coco(tot, a, "total")
            records.append(rec)
        for site, sl in (s.get("snow_level") or {}).items():
            for r in sl["launches"]:
                snow.append({"w": wi, "site": site, "valid": r["valid_utc"], "sonde": r["sounding_snow_level_ft"],
                             "freezing": r.get("sounding_freezing_level_ft"), "sat": bool(r["column_saturated"]),
                             "nbm": triple(r["nbm"], ("p25", "p50", "p75"))})
    out = {
        "generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",
        "seasons": SEASONS,
        "products": [
            {"id": "nbm", "label": "NBM", "long": "NBM median, with the 25th–75th percentile range", "kind": "range", "available": True},
            {"id": "ours", "label": "Our forecast", "long": "Our forecast range (weekend total)", "kind": "range", "available": True},
            {"id": "hrrr", "label": "HRRR", "long": "HRRR (single value, first 48 hours: Friday)", "kind": "point", "available": True},
            {"id": "hrdps", "label": "HRDPS", "long": "HRDPS (single value, first 48 hours: Friday; assumes 10:1 snow ratio)", "kind": "point", "available": True},
        ],
        "areas": list(areas.values()),
        "weekends": weekends,
        "records": records,
        "snow_level": snow,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(weekends)} weekends, {len(areas)} areas, {len(records)} records, "
          f"{len(snow)} launches, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
