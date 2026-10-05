"""Score a saved forecast snapshot against what SNOTEL observed.

    python scripts/score_forecast.py                                      # newest snapshot
    python scripts/score_forecast.py data/forecasts/nbm_snapshot_2026-10-03.json

Reads the NBM snapshot written at forecast time (scripts/nbm_snapshot.py), gets the observed
snowfall for each window from SNOTEL (scripts/snotel_obs.py, stations from data/nbm/sites.yml), and
writes data/evaluation/score_<first-day>.json. Runs after the last window has ended.

If a post carries a `forecast:` block in its front matter with `snapshot: <first-day>`, the author's
own ranges are scored too:

    forecast:
      snapshot: 2026-10-03
      areas:
        Mt. Baker: {day1: [0, 2], day2: [1, 4], total: [1, 6]}     # inches, low and high

What is scored, per area and window:
  nbm_error_in   NBM median minus the observed estimate (positive = NBM too high)
  nbm_iqr_hit    observed estimate inside the NBM 25th-75th range (plus 0.5 in of slack)
  ours_error_in  middle of the author's range minus the observed estimate
  ours_hit       observed estimate inside the author's range (plus 0.5 in of slack)
  obs_overlaps_* the observed range (which is wide, because new-snow density is unknown) overlaps the
                 forecast range. A weaker test than the hit, reported next to it.

Snow level is scored separately, at the radiosonde sites (Quillayute, Spokane, Salem): for each 00Z and
12Z launch in the period, the snow level computed from the actual sounding is compared with the NBM
snow level at the same place and time (median, with the 25th-75th range). The snapshot saves the NBM
side under `verification_points`. Soundings come from IEM's archive via collect_radiosonde_history.py,
so any past weekend can be scored. A hit allows 500 ft of slack.
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from snotel_obs import utc, windows_obs  # noqa: E402
from collect_radiosonde_history import compute_melting_layer, fetch_profile  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITES_FILE = ROOT / "data" / "nbm" / "sites.yml"
POSTS = ROOT / "_posts"
OUT_DIR = ROOT / "data" / "evaluation"
SLACK_IN = 0.5
SLACK_FT = 500.0
M_TO_FT = 3.28084


def load_our_forecast(first_day):
    """The `forecast:` block of the post written against this snapshot, or None."""
    for post in sorted(POSTS.glob("*.html")):
        m = re.match(r"---\n(.*?)\n---\n", post.read_text(encoding="utf-8").replace("\r\n", "\n"), re.S)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        fc = fm.get("forecast")
        if isinstance(fc, dict) and str(fc.get("snapshot")) == first_day:
            return fc.get("areas") or {}
    return None


def within(value, lo, hi):
    return lo - SLACK_IN <= value <= hi + SLACK_IN


def overlaps(a_lo, a_hi, b_lo, b_hi):
    return a_lo <= b_hi + SLACK_IN and b_lo <= a_hi + SLACK_IN


def score_window(nbm, obs, ours):
    out = {}
    if not obs:
        return {"note": "no observation available"}
    mid = obs["mid"]
    if nbm and nbm.get("p50") is not None:
        out["nbm_error_in"] = round(nbm["p50"] - mid, 1)
        out["nbm_iqr_hit"] = within(mid, nbm["p25"], nbm["p75"])
        out["obs_overlaps_nbm_iqr"] = overlaps(obs["low"], obs["high"], nbm["p25"], nbm["p75"])
    if ours:
        lo, hi = ours
        out["ours_error_in"] = round((lo + hi) / 2 - mid, 1)
        out["ours_hit"] = within(mid, lo, hi)
        out["obs_overlaps_ours"] = overlaps(obs["low"], obs["high"], lo, hi)
    return out


def launches(start, end):
    """The 00Z and 12Z launch times inside [start, end]."""
    t = start.replace(minute=0, second=0, microsecond=0)
    while t.hour not in (0, 12) or t < start:
        t += timedelta(hours=1)
    out = []
    while t <= end:
        out.append(t)
        t += timedelta(hours=12)
    return out


def snow_level_scores(snap, start, end):
    """Sounding-derived snow level against the NBM at each sounding site."""
    times = snap["series_times_utc"]
    result = {}
    for name, vp in (snap.get("verification_points") or {}).items():
        rows = []
        print(f"  {name} ({vp['station']}): soundings")
        for t in launches(start, end):
            stamp = f"{t:%Y-%m-%dT%H:%MZ}"
            if stamp not in times:
                continue
            profile = fetch_profile(vp["station"], t)
            if profile is None:
                continue
            d = compute_melting_layer(*profile)
            if d.get("snow_level_m") is None:
                continue
            i = times.index(stamp)
            sl = vp["snow_level_ft"]
            obs_ft = round(d["snow_level_m"] * M_TO_FT)
            nbm = {k: sl[k][i] for k in ("p25", "p50", "p75", "deterministic")}
            row = {"valid_utc": stamp, "sounding_snow_level_ft": obs_ft,
                   "sounding_freezing_level_ft": None if d.get("freezing_level_m") is None else round(d["freezing_level_m"] * M_TO_FT),
                   "nbm": nbm}
            if nbm["p50"] is not None:
                row["nbm_error_ft"] = round(nbm["p50"] - obs_ft)
                row["nbm_iqr_hit"] = nbm["p25"] - SLACK_FT <= obs_ft <= nbm["p75"] + SLACK_FT
            rows.append(row)
        errs = [r["nbm_error_ft"] for r in rows if "nbm_error_ft" in r]
        result[name] = {
            "station": vp["station"], "km_to_grid_point": vp["km_to_grid_point"], "launches": rows,
            "n": len(errs),
            "bias_ft": round(sum(errs) / len(errs)) if errs else None,
            "mae_ft": round(sum(abs(e) for e in errs) / len(errs)) if errs else None,
            "iqr_hit_rate": round(sum(r["nbm_iqr_hit"] for r in rows if "nbm_iqr_hit" in r) / len(errs), 2) if errs else None,
        }
    return result


def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        found = sorted((ROOT / "data" / "forecasts").glob("nbm_snapshot_*.json"))
        if not found:
            sys.exit("no nbm_snapshot_*.json in data/forecasts")
        path = found[-1]
    snap = json.loads(path.read_text(encoding="utf-8"))
    first_day = snap["source"]["first_day_local"]
    windows = {wid: (utc(w["start_utc"].rstrip("Z")), utc(w["end_utc"].rstrip("Z"))) for wid, w in snap["windows"].items()}
    last_end = max(e for _, e in windows.values())
    if last_end > datetime.now(timezone.utc):
        sys.exit(f"The last window ends {last_end:%Y-%m-%d %H:%MZ}, which has not happened yet.")

    sites = {s["name"]: s for s in yaml.safe_load(SITES_FILE.read_text(encoding="utf-8"))["sites"]}
    ours_all = load_our_forecast(first_day)
    result = {
        "snapshot": path.name, "first_day_local": first_day, "nbm_cycle_utc": snap["source"]["cycle_utc"],
        "scored_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",
        "our_forecast_found": ours_all is not None,
        "notes": [
            "Observed snowfall is an estimate from SNOTEL snow water equivalent and snow depth; see scripts/snotel_obs.py.",
            "SNOTEL stations sit at their own elevation, not the 5000 ft forecast elevation (elevations are recorded per area).",
            f"A hit allows {SLACK_IN} in of slack on each side.",
        ],
        "windows": {wid: {"start_utc": snap["windows"][wid]["start_utc"], "end_utc": snap["windows"][wid]["end_utc"]} for wid in windows},
        "areas": {},
    }
    for name, site_snap in snap["sites"].items():
        trips = sites.get(name, {}).get("obs")
        if not trips:
            print(f"  {name}: no obs stations in sites.yml, skipped")
            continue
        print(f"  {name}: fetching {', '.join(trips)}")
        obs = windows_obs(trips, windows)
        area = {"obs_stations": {t: {"name": s["name"], "elev_ft": s["elev_ft"]} for t, s in next(iter(obs.values()))["stations"].items()},
                "forecast_elev_ft": (site_snap.get("elevation_ft") or {}).get("site"), "windows": {}}
        for wid in windows:
            nbm = site_snap["snowfall_in"].get(wid)
            ours = ((ours_all or {}).get(name) or {}).get(wid)
            o = obs[wid]["snowfall_in"]
            area["windows"][wid] = {
                "nbm": {k: nbm.get(k) for k in ("p25", "p50", "p75", "deterministic", "method")} if nbm else None,
                "ours": ours, "observed": o,
                "observed_inputs": {t: {k: s[k] for k in ("swe_gain_in", "depth_gain_in", "precip_in", "temp_mean_f", "coverage")}
                                    for t, s in obs[wid]["stations"].items()},
                "scores": score_window(nbm, o, ours),
            }
        result["areas"][name] = area

    result["snow_level"] = snow_level_scores(snap, min(s for s, _ in windows.values()), last_end)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"score_{first_day}.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")

    print(f"\nNBM cycle {result['nbm_cycle_utc']}; windows {', '.join(windows)}")
    print(f"{'area':16s} {'window':6s} {'NBM p25/p50/p75':17s} {'obs low/mid/high':20s} {'NBM err':>8s}  IQR hit")
    for name, a in result["areas"].items():
        for wid, w in a["windows"].items():
            n, o, sc = w["nbm"], w["observed"], w["scores"]
            nb = f"{n['p25']}/{n['p50']}/{n['p75']}" if n else "-"
            ob = f"{o['low']}/{o['mid']}/{o['high']}" if o else "-"
            print(f"{name:16s} {wid:6s} {nb:17s} {ob:20s} {str(sc.get('nbm_error_in', '-')):>8s}  {sc.get('nbm_iqr_hit', '-')}")
    print("\nSnow level at the sounding sites (sounding-derived vs NBM median, ft)")
    for name, sl in result["snow_level"].items():
        print(f"  {name} ({sl['station']}): {sl['n']} launches, bias {sl['bias_ft']} ft, MAE {sl['mae_ft']} ft, within NBM 25-75 range {sl['iqr_hit_rate']}")
        for row in sl["launches"]:
            n = row["nbm"]
            print(f"    {row['valid_utc']}  sounding {row['sounding_snow_level_ft']:>6}  NBM {n['p25']}/{n['p50']}/{n['p75']}  err {row.get('nbm_error_ft', '-')}")
    print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
