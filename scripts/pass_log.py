"""Log pass closures and road restrictions as they happen, so the delay-risk model can be calibrated for every pass (bot, three runs a day around the 7 to 8 am decision).

    python scripts/pass_log.py            # writes data/passes/log/*.jsonl and assets/data/pass_now.json

Sources (all public, no key):
  WSDOT   Travel Information road alerts, https://data.wsdot.wa.gov/arcgis/rest/services/TravelInformation/TravelInfoRoadAlerts/FeatureServer/0
          Current events only (there is no archive), so this log IS the archive. Kept when the alert sits on a pass corridor (PASSES below).
  NPS     Mount Rainier alerts, https://www.nps.gov/mora/park-alerts-mora.json (the feed behind https://www.nps.gov/mora/planyourvisit/conditions.htm),
          and the road status table on https://www.nps.gov/mora/planyourvisit/road-status.htm, which includes the Longmire to Paradise gate.
What it writes:
  data/passes/log/state.json       what is open right now (written only when something changed)
  data/passes/log/events.jsonl     one line per finished event: first seen, last seen, ended (the poll that noticed it was gone), text history
  data/passes/log/nps_gate.jsonl   one line each time the Longmire to Paradise status text changes
  assets/data/pass_now.json        current closures and restrictions by pass, for the ski tool, rewritten every run (its generated_utc says how fresh it is)
Times are the poll times: with three runs in the morning an event's start and end are only known to within hours, which is enough to say that a pass was closed that morning but not for how long.
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "passes" / "log"
NOW_JSON = ROOT / "assets" / "data" / "pass_now.json"
H = {"User-Agent": "cascade-mountain-weather.github.io pass log (dlhogan@uw.edu)"}
WSDOT = "https://data.wsdot.wa.gov/arcgis/rest/services/TravelInformation/TravelInfoRoadAlerts/FeatureServer/0/query"
NPS_ALERTS = "https://www.nps.gov/mora/park-alerts-mora.json"
NPS_ROADS = "https://www.nps.gov/mora/planyourvisit/road-status.htm"
# pass: (road name in the WSDOT feed, lon min, lon max, lat min, lat max). Boxes are generous around each pass corridor.
PASSES = {
    "snoqualmie": ("I-90", -121.85, -120.85, 47.20, 47.60),
    "stevens": ("US 2", -121.55, -120.45, 47.50, 47.90),
    "white": ("US 12", -121.80, -121.00, 46.45, 46.80),
    "chinook": ("SR 410", -121.75, -121.00, 46.80, 47.20),
    "cayuse": ("SR 123", -121.70, -121.40, 46.75, 47.00),
    "baker": ("SR 542", -122.05, -121.55, 48.70, 48.95),
    "washington": ("SR 20", -121.50, -120.15, 48.35, 48.75),
    "blewett": ("US 97", -120.85, -120.35, 47.20, 47.50),
    "rainier_706": ("SR 706", -122.20, -121.70, 46.70, 46.90),
}
ROAD_KEY = re.compile(r"(closed|closure|avalanche|chain|traction|restriction|spin|collision|blocked|reopen)", re.I)


def now_utc():
    return f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}"


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def pass_for(road, x, y):
    for name, (r, x0, x1, y0, y1) in PASSES.items():
        if road and road.replace(" ", "") == r.replace(" ", "") and x0 <= x <= x1 and y0 <= y <= y1:
            return name
    return None


def wsdot_items():
    p = {"where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": "4326", "f": "json", "resultRecordCount": 2000}
    r = requests.get(WSDOT, params=p, headers=H, timeout=60)
    r.raise_for_status()
    out = {}
    for f in r.json().get("features", []):
        a, g = f["attributes"], f.get("geometry") or {}
        if g.get("x") is None:
            continue
        tag = pass_for(a.get("Road"), g["x"], g["y"])
        if not tag:
            continue
        key = f"wsdot:{a['OBJECTID']}"
        out[key] = {"source": "wsdot", "pass": tag, "road": a.get("Road"), "direction": a.get("RoadDirection"), "category": a.get("EventCategoryDescription"),
                    "type": a.get("EventCategoryTypeDescription"), "closed": bool(a.get("RoadClosedFlag")), "text": (a.get("HeadlineMessage") or "").strip(),
                    "lon": round(g["x"], 4), "lat": round(g["y"], 4), "source_modified": a.get("LastModifiedDate")}
    return out


def nps_items():
    r = requests.get(NPS_ALERTS, headers=H, timeout=60)
    r.raise_for_status()
    out = {}
    for a in r.json():
        if not a.get("is_active"):
            continue
        txt = f"{a.get('title', '')}. {a.get('description', '')}".strip()
        road = bool(a.get("road_closure_name") or a.get("road_closure_road_names")) or re.search(r"\b(road|gate|paradise|longmire|nisqually|closed|closure)\b", txt, re.I)
        if not road:
            continue
        out["nps:" + a["id"]] = {"source": "nps", "pass": "paradise" if re.search(r"paradise|longmire|nisqually", txt, re.I) else "rainier", "road": a.get("road_closure_name") or "",
                                 "category": a.get("category"), "closed": a.get("category") == "Park Closure", "text": txt[:600], "url": a.get("url")}
    return out


def nps_roads():
    """{road name: status text} from the NPS road status table."""
    r = requests.get(NPS_ROADS, headers=H, timeout=60)
    r.raise_for_status()
    rows = {}
    for tr in re.findall(r"<tr.*?</tr>", r.text, flags=re.S):
        c = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
        if len(c) == 2 and c[0] and c[1] and c[1].upper() != "STATUS":
            rows[c[0][:80]] = c[1][:300]
    return rows


def main():
    LOG.mkdir(parents=True, exist_ok=True)
    now = now_utc()
    state = read_json(LOG / "state.json", {"open": {}, "nps_roads": {}})
    cur, errors = {}, []
    for name, fn in [("wsdot", wsdot_items), ("nps", nps_items)]:
        try:
            cur.update(fn())
        except Exception as e:
            errors.append(f"{name}: {e}")
    roads = None
    try:
        roads = nps_roads()
    except Exception as e:
        errors.append(f"nps road status: {e}")
    ok_sources = {s for s in ("wsdot", "nps") if not any(e.startswith(s) for e in errors)}
    changed = False
    # events that were open and are gone (only judged for a source that answered)
    for key in list(state["open"]):
        ev = state["open"][key]
        if ev["source"] in ok_sources and key not in cur:
            ev["ended_utc"] = now
            with open(LOG / "events.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(ev) + "\n")
            del state["open"][key]
            changed = True
    for key, it in cur.items():
        ev = state["open"].get(key)
        if ev and ev.get("road") == it.get("road") and ev["source"] == it["source"]:
            if it["text"] != ev["text"] or it["closed"] != ev["closed"]:
                ev.setdefault("history", []).append({"utc": now, "text": ev["text"], "closed": ev["closed"]})
                ev["history"] = ev["history"][-20:]
                ev.update({k: it[k] for k in ("text", "closed", "category", "type", "direction") if k in it})
                changed = True
        else:
            if ev:                                      # the id was reused for a different event
                ev["ended_utc"] = now
                with open(LOG / "events.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(ev) + "\n")
            state["open"][key] = dict(it, key=key, first_seen_utc=now)
            changed = True
    if roads is not None:
        for name, status in roads.items():
            if state["nps_roads"].get(name) != status:
                if name.startswith("Longmire to Paradise") or name.startswith("Nisqually"):
                    with open(LOG / "nps_gate.jsonl", "a", encoding="utf-8") as f:
                        f.write(json.dumps({"utc": now, "road": name, "status": status, "previous": state["nps_roads"].get(name)}) + "\n")
                state["nps_roads"][name] = status
                changed = True
    if changed:
        (LOG / "state.json").write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    # what the tool reads
    gate = (roads or state["nps_roads"]).get("Longmire to Paradise")
    by_pass = {}
    for ev in state["open"].values():
        if not (ev.get("closed") or (ROAD_KEY.search(ev.get("text", "")) and ev.get("category") not in ("Construction", "Rest Area", "Maintenance"))):
            continue                                   # routine roadwork stays in the log but is not shown to the tool
        by_pass.setdefault(ev["pass"], []).append({k: ev.get(k) for k in ("source", "road", "direction", "category", "closed", "text", "first_seen_utc")})
    now_doc = {"generated_utc": now, "errors": errors, "passes": by_pass,
               "paradise_gate": {"status": gate, "open": None if gate is None else gate.upper().startswith("OPEN"), "source": NPS_ROADS}}
    NOW_JSON.parent.mkdir(parents=True, exist_ok=True)
    NOW_JSON.write_text(json.dumps(now_doc, indent=1), encoding="utf-8")
    print(f"{now}: {len(cur)} items on pass corridors/NPS alerts, {len(state['open'])} open in the log, errors: {errors or 'none'}")
    if gate:
        print("  Longmire to Paradise:", gate[:100])
    return 1 if (errors and not cur and roads is None) else 0


if __name__ == "__main__":
    sys.exit(main())
