#!/usr/bin/env python3
"""Verify UW WRF forecast soundings against the Quillayute (UIL) radiosonde, by lead time and init time.

    python scripts/wrf_uil_verify.py

Every archived WRF run (data/cycles/uw_wrf/, written by scripts/uw_soundings.py) has a frame every 3 h out to 72 h.
Radiosondes launch at 00Z and 12Z, so a frame can be checked against an observation when its valid time is 00Z/12Z,
that is, at leads of 0, 12, 24, 36, 48, 60 and 72 h. The nearest WRF point to Quillayute is Olympex DOW (`dowlx`,
about 60 km away), so this is a check of the forecast for the Olympic coast, not of the model at the launch site.

Both sides go through the same derivation (`derive` in scripts/uw_soundings.py), so a freezing level or snow level
(0 C wet-bulb level) means the same thing in each. Levels are feet MSL. Pairs where either side's level falls below the
ground (extrapolated at 6.5 C/km and flagged) are left out of the scores.

Observations are fetched from IEM once and kept in data/wrf_verification/uil_obs.json (the radiosonde history file only
keeps about a week; the scores cover the whole season). Nothing is guessed: a launch that IEM does not have is skipped.

Output: assets/data/wrf_uil.json (bot-generated, do not hand-edit):
  recent  - the last ~8 days, one row per 00Z/12Z valid time: observed values and the WRF value from the run at each lead
  metrics - per season (September to August): n, bias (WRF - obs), MAE, RMSE and correlation by lead x init (00Z, 12Z, all),
            and the same pooled by week, for each variable
"""
import gzip
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_uw_vs_radiosonde import observed  # noqa: E402  (IEM profile -> uw_soundings.derive)

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "data" / "cycles" / "uw_wrf"
OBS_FILE = ROOT / "data" / "wrf_verification" / "uil_obs.json"
OUT = ROOT / "assets" / "data" / "wrf_uil.json"

WRF_SITE = "dowlx"
VARS = {   # key -> (label, unit, below-surface flag)
    "freezing_level_ft": ("Freezing level", "ft", "freezing_below_surface"),
    "snow_level_ft": ("Snow level (0 C wet-bulb)", "ft", "snow_below_surface"),
    "t850_c": ("850 hPa temperature", "C", None),
}
CHART_LEADS = [12, 24, 48, 72]
RECENT_DAYS = 8
RETRY_DAYS = 10   # IEM can post a launch late; keep asking about a missing one this long


def utc(s):
    return datetime.strptime(s, "%Y%m%d%H").replace(tzinfo=timezone.utc)


def season_of(dt):
    y = dt.year if dt.month >= 9 else dt.year - 1
    return f"{y}-{str(y + 1)[2:]}"


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_runs():
    """{init datetime: [frame, ...]} for the WRF point nearest Quillayute."""
    runs = {}
    for f in sorted(ARCHIVE.glob("*.json.gz")):
        try:
            data = json.loads(gzip.open(f, "rt", encoding="utf-8").read())
            frames = data["sites"][WRF_SITE]["frames"]
        except (OSError, KeyError, ValueError):
            continue
        runs[utc(data.get("init_utc") or f.name[:10])] = frames
    return runs


def update_obs(runs, now):
    store = load_json(OBS_FILE, {"station": "UIL", "obs": {}, "missing": {}})
    obs, missing = store.setdefault("obs", {}), store.setdefault("missing", {})
    first = min(runs)
    t = first
    while t <= now:
        key = t.strftime("%Y%m%d%H")
        if key not in obs and (key not in missing or now - t < timedelta(days=RETRY_DAYS)):
            try:
                d = observed(t)
            except Exception as exc:  # noqa: BLE001 -- one bad launch must not stop the run
                print(f"  {key}: fetch failed ({exc})", file=sys.stderr)
                d = None
            if d is None:
                missing[key] = True
            else:
                obs[key] = {k: d.get(k) for k in ("surface_ft", *VARS, "freezing_below_surface", "snow_below_surface")}
                missing.pop(key, None)
                print(f"  {key}: observed freezing {d.get('freezing_level_ft')} ft, snow {d.get('snow_level_ft')} ft")
        t += timedelta(hours=12)
    OBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    OBS_FILE.write_text(json.dumps(store, indent=1), encoding="utf-8")
    return obs


def pairs(runs, obs):
    """Every (init, lead) frame that has an observation at its valid time, with a value for each variable (or None)."""
    out = []
    for init, frames in runs.items():
        for fr in frames:
            lead = fr["hour"]
            if lead % 12:
                continue
            valid = init + timedelta(hours=lead)
            o = obs.get(valid.strftime("%Y%m%d%H"))
            if o is None:
                continue
            row = {"init": init, "valid": valid, "lead": lead, "obs": {}, "wrf": {}}
            for k, (_, _, flag) in VARS.items():
                bad = flag and (o.get(flag) or fr.get(flag))
                row["obs"][k] = None if bad else o.get(k)
                row["wrf"][k] = None if bad else fr.get(k)
            out.append(row)
    return out


def score(rows, k):
    d = np.array([r["wrf"][k] - r["obs"][k] for r in rows if r["wrf"][k] is not None and r["obs"][k] is not None], float)
    if d.size == 0:
        return None
    w = np.array([r["wrf"][k] for r in rows if r["wrf"][k] is not None and r["obs"][k] is not None], float)
    o = np.array([r["obs"][k] for r in rows if r["wrf"][k] is not None and r["obs"][k] is not None], float)
    r_ = float(np.corrcoef(w, o)[0, 1]) if d.size >= 5 and w.std() > 0 and o.std() > 0 else None
    rd = lambda x: None if x is None else round(float(x), 2)  # noqa: E731
    return {"n": int(d.size), "bias": rd(d.mean()), "mae": rd(np.abs(d).mean()), "rmse": rd(np.sqrt((d ** 2).mean())), "r": rd(r_)}


def build_metrics(prs):
    seasons = {}
    for season in sorted({season_of(p["valid"]) for p in prs}):
        rows = [p for p in prs if season_of(p["valid"]) == season]
        overall, weekly = {}, {}
        for k in VARS:
            cells = []
            for lead in sorted({p["lead"] for p in rows}):
                for init in ("all", "00", "12"):
                    sel = [p for p in rows if p["lead"] == lead and (init == "all" or f"{p['init'].hour:02d}" == init)]
                    s = score(sel, k)
                    if s:
                        cells.append({"lead": lead, "init": init, **s})
            overall[k] = cells
            wk = []
            for week in sorted({(p["valid"] - timedelta(days=p["valid"].weekday())).date() for p in rows}):
                for lead in sorted({p["lead"] for p in rows}):
                    sel = [p for p in rows if p["lead"] == lead and (p["valid"] - timedelta(days=p["valid"].weekday())).date() == week]
                    s = score(sel, k)
                    if s:
                        wk.append({"week": week.isoformat(), "lead": lead, **s})
            weekly[k] = wk
        seasons[season] = {"overall": overall, "weekly": weekly}
    return seasons


def build_recent(runs, obs, now):
    start = now - timedelta(days=RECENT_DAYS)
    rows = []
    t = (start.replace(hour=0, minute=0, second=0, microsecond=0))
    while t <= now:
        for h in (0, 12):
            valid = t + timedelta(hours=h)
            if not (start <= valid <= now):
                continue
            o = obs.get(valid.strftime("%Y%m%d%H"))
            row = {"valid": valid.strftime("%Y-%m-%dT%H:%MZ"),
                   "obs": None if o is None else {k: o.get(k) for k in VARS},
                   "wrf": {}}
            for lead in CHART_LEADS:
                fr = next((f for f in runs.get(valid - timedelta(hours=lead), []) if f["hour"] == lead), None)
                if fr is not None:
                    row["wrf"][str(lead)] = {k: fr.get(k) for k in VARS}
            rows.append(row)
        t += timedelta(days=1)
    return rows


def main():
    runs = load_runs()
    if not runs:
        print("no archived WRF runs", file=sys.stderr)
        return
    now = datetime.now(timezone.utc)
    obs = update_obs(runs, now)
    prs = pairs(runs, obs)
    surface = next((o["surface_ft"] for o in reversed(list(obs.values())) if o.get("surface_ft") is not None), None)
    out = {
        "updated": now.strftime("%Y-%m-%dT%H:%MZ"),
        "notes": [
            "WRF point: Olympex DOW (about 60 km from the Quillayute launch site). Levels are feet MSL; bias is WRF minus observed.",
            "Observed and WRF values use the same derivation. Pairs with a level below the ground are excluded from the scores.",
        ],
        "uil_surface_ft": surface,
        "variables": {k: {"label": v[0], "unit": v[1]} for k, v in VARS.items()},
        "chart_leads": CHART_LEADS,
        "recent": build_recent(runs, obs, now),
        "metrics": build_metrics(prs),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT}: {len(runs)} runs, {len(obs)} observations, {len(prs)} pairs")


if __name__ == "__main__":
    main()
