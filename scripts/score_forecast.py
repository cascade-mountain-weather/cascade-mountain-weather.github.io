"""Score a saved forecast snapshot against what was observed.

    python scripts/score_forecast.py                                      # newest snapshot
    python scripts/score_forecast.py data/forecasts/nbm_snapshot_2026-10-03.json

Reads the NBM snapshot written at forecast time (scripts/nbm_snapshot.py), gets observed snowfall for
each window from SNOTEL (scripts/snotel_obs.py; stations from data/nbm/sites.yml), and writes
data/evaluation/score_<first-day>.json. Run it after the last window has ended. Other scripts call
score_snapshot() directly (scripts/backfill_evaluation.py).

Your own forecast
-----------------
If a post carries a `forecast:` block in its front matter with `snapshot: <first-day>`, the author's own
ranges are scored too:

    forecast:
      snapshot: 2026-10-03
      areas:
        Mt. Baker: {total: [1, 6]}        # inches, low and high; day1, day2, day3 are allowed too

Your weekend total is scored against what fell over YOUR forecast period, 4 pm Thursday to 4 am Monday
(local time), not the NBM window (Friday 12Z to Monday 12Z), so Thursday-evening snow counts for you.

What is scored, per area and window
-----------------------------------
  nbm_error_in   NBM median minus the observed estimate (positive = NBM too high)
  nbm_iqr_hit    observed estimate inside the NBM 25th-75th range (plus slack: 1 in or 10% of the observed amount, whichever is larger)
  ours_error_in  middle of your range minus the observed estimate
  ours_hit       observed estimate inside your range (plus slack: 1 in or 10% of the observed amount, whichever is larger)
  hrrr_error_in  HRRR minus the observed estimate, and the same for hrdps (only for windows the models reach,
                 normally Friday; see scripts/hires_models.py). Both are single values, not ranges.
  obs_overlaps_* the observed range (wide, because new-snow density is unknown) overlaps the forecast
                 range. A weaker test than the hit, reported next to it.

Snow level
----------
Scored at the radiosonde sites in the snapshot (Quillayute, Salem): for each 00Z and 12Z launch, the snow
level computed from the actual sounding (collect_radiosonde_history.py, via IEM's archive) against the NBM
snow level at the same place and time (median, with the 25th-75th range). Only launches where the column
is near saturation are scored: with dry air the melting-layer calculation gives a snow level that says
nothing about a precipitation forecast. A hit allows 500 ft of slack.
"""
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_radiosonde_history import compute_melting_layer, fetch_profile  # noqa: E402
import cocorahs_obs  # noqa: E402
from draft_forecast_tables import is_pdt  # noqa: E402
from snotel_obs import utc, windows_obs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITES_FILE = ROOT / "data" / "nbm" / "sites.yml"
POSTS = ROOT / "_posts"
OUT_DIR = ROOT / "data" / "evaluation"
SLACK_IN = 1.0               # floor on the slack for a snowfall hit, inches
SLACK_FRAC = 0.10            # slack grows with the amount: 10% of the observed value, so a big storm is held to a range, not a point
SLACK_FT = 500.0
SATURATED_WITHIN_M = 300.0   # actual and fully saturated snow levels this close = column is near saturation
M_TO_FT = 3.28084


# ---------------------------------------------------------------- your forecast

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


def local_to_utc(d, hour):
    """Pacific local time on date d at `hour` o'clock, as a UTC datetime."""
    return datetime(d.year, d.month, d.day, hour, tzinfo=timezone.utc) + timedelta(hours=7 if is_pdt(d) else 8)


def our_period(first_day):
    """Your forecast period: 4 pm Thursday (the day before the first day) to 4 am the Monday after."""
    first = date.fromisoformat(first_day)
    return local_to_utc(first - timedelta(days=1), 16), local_to_utc(first + timedelta(days=3), 4)


# ---------------------------------------------------------------- scoring helpers

def slack_in(amount):
    """Slack on each side of a forecast range: the larger of SLACK_IN and 10% of the observed amount."""
    return max(SLACK_IN, SLACK_FRAC * amount)


def within(value, lo, hi):
    k = slack_in(value)
    return lo - k <= value <= hi + k


def overlaps(a_lo, a_hi, b_lo, b_hi):
    k = slack_in(max(a_hi, b_hi))
    return a_lo <= b_hi + k and b_lo <= a_hi + k


def score_nbm(nbm, obs):
    if not obs or not nbm or nbm.get("p50") is None:
        return {}
    return {"nbm_error_in": round(nbm["p50"] - obs["mid"], 1),
            "nbm_iqr_hit": within(obs["mid"], nbm["p25"], nbm["p75"]),
            "obs_overlaps_nbm_iqr": overlaps(obs["low"], obs["high"], nbm["p25"], nbm["p75"])}


def score_ours(ours, obs):
    if not obs or not ours:
        return {}
    lo, hi = ours
    return {"ours_error_in": round((lo + hi) / 2 - obs["mid"], 1),
            "ours_hit": within(obs["mid"], lo, hi),
            "obs_overlaps_ours": overlaps(obs["low"], obs["high"], lo, hi)}


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


def snow_level_scores(snap, start, end, verbose=True):
    """Sounding-derived snow level against the NBM at each sounding site."""
    times = snap["series_times_utc"]
    result = {}
    for name, vp in (snap.get("verification_points") or {}).items():
        rows = []
        if verbose:
            print(f"  {name} ({vp['station']}): soundings")
        for t in launches(start, end):
            stamp = f"{t:%Y-%m-%dT%H:%MZ}"
            if stamp not in times:
                continue
            profile = fetch_profile(vp["station"], t)
            if profile is None:
                continue
            heights, temps, dews = profile
            actual = compute_melting_layer(heights, temps, dews)
            saturated = compute_melting_layer(heights, temps, temps)   # same column, fully saturated
            if actual.get("snow_level_m") is None:
                continue
            i = times.index(stamp)
            sl = vp["snow_level_ft"]
            obs_ft = round(actual["snow_level_m"] * M_TO_FT)
            nbm = {k: sl[k][i] for k in ("p25", "p50", "p75", "deterministic")}
            is_sat = (saturated.get("snow_level_m") is not None
                      and abs(actual["snow_level_m"] - saturated["snow_level_m"]) <= SATURATED_WITHIN_M)
            row = {"valid_utc": stamp, "sounding_snow_level_ft": obs_ft,
                   "sounding_snow_level_saturated_ft": None if saturated.get("snow_level_m") is None else round(saturated["snow_level_m"] * M_TO_FT),
                   "sounding_freezing_level_ft": None if actual.get("freezing_level_m") is None else round(actual["freezing_level_m"] * M_TO_FT),
                   "column_saturated": is_sat, "scored": bool(is_sat and nbm["p50"] is not None), "nbm": nbm}
            if row["scored"]:
                row["nbm_error_ft"] = round(nbm["p50"] - obs_ft)
                row["nbm_iqr_hit"] = nbm["p25"] - SLACK_FT <= obs_ft <= nbm["p75"] + SLACK_FT
            rows.append(row)
        scored = [r for r in rows if r["scored"]]
        errs = [r["nbm_error_ft"] for r in scored]
        result[name] = {
            "station": vp["station"], "km_to_grid_point": vp["km_to_grid_point"], "launches": rows,
            "n_launches": len(rows), "n_scored": len(scored),
            "bias_ft": round(sum(errs) / len(errs)) if errs else None,
            "mae_ft": round(sum(abs(e) for e in errs) / len(errs)) if errs else None,
            "iqr_hit_rate": round(sum(r["nbm_iqr_hit"] for r in scored) / len(scored), 2) if scored else None,
        }
    return result


# ---------------------------------------------------------------- the scoring itself

def score_snapshot(snap, snap_name, ours_all=None, verbose=True, snow_level=None):
    """Score one snapshot (a loaded dict) and return the result dict. `ours_all` is {area: {window: [lo, hi]}}.
    `snow_level`, if given, is reused instead of fetching soundings again (a rescore of the snowfall only)."""
    first_day = snap["source"]["first_day_local"]
    windows = {wid: (utc(w["start_utc"].rstrip("Z")), utc(w["end_utc"].rstrip("Z"))) for wid, w in snap["windows"].items()}
    last_end = max(e for _, e in windows.values())
    if last_end > datetime.now(timezone.utc):
        raise RuntimeError(f"The last window ends {last_end:%Y-%m-%d %H:%MZ}, which has not happened yet.")

    obs_windows = dict(windows)
    ours_start, ours_end = our_period(first_day)
    if ours_all:
        obs_windows["ours_period"] = (ours_start, ours_end)

    site_list = yaml.safe_load(SITES_FILE.read_text(encoding="utf-8"))["sites"]
    sites = {s["name"]: s for s in site_list}
    # CoCoRaHS volunteer reports within 25 km of each site: a cross-check next to the SNOTEL estimate, not part of the score
    try:
        coco = cocorahs_obs.window_obs(cocorahs_obs.stations_near(site_list), windows)
    except Exception as exc:  # noqa: BLE001 -- the cross-check must not stop the scoring
        print(f"  CoCoRaHS skipped: {str(exc)[:100]}")
        coco = {}
    hires = snap.get("hires") or {}
    result = {
        "snapshot": snap_name, "first_day_local": first_day, "nbm_cycle_utc": snap["source"]["cycle_utc"],
        "scored_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",
        "our_forecast_found": bool(ours_all),
        "our_period_utc": [f"{ours_start:%Y-%m-%dT%H:%MZ}", f"{ours_end:%Y-%m-%dT%H:%MZ}"] if ours_all else None,
        "notes": [
            "Observed snowfall is an estimate from SNOTEL snow water equivalent and snow depth; see scripts/snotel_obs.py.",
            "SNOTEL stations sit at their own elevation, not the 5000 ft forecast elevation (elevations are recorded per area).",
            f"A hit allows slack on each side of the range: {SLACK_IN} in or {int(SLACK_FRAC * 100)}% of the observed amount, whichever is larger.",
            "The author's weekend total is scored against the author's own period (4 pm Thursday to 4 am Monday), not the NBM window.",
            "HRRR and HRDPS cover 48 hours, so they are scored on the windows inside that (normally Friday). HRDPS snowfall assumes a 10:1 ratio.",
            "CoCoRaHS reports are a cross-check from volunteer stations within 25 km, mostly lowland; they are not part of the score.",
        ],
        "windows": {wid: {"start_utc": snap["windows"][wid]["start_utc"], "end_utc": snap["windows"][wid]["end_utc"]} for wid in windows},
        "areas": {},
    }
    for name, site_snap in snap["sites"].items():
        trips = sites.get(name, {}).get("obs")
        if not trips:
            continue
        if verbose:
            print(f"  {name}: fetching {', '.join(trips)}")
        obs = windows_obs(trips, obs_windows)
        area = {"obs_stations": {t: {"name": s["name"], "elev_ft": s["elev_ft"]} for t, s in next(iter(obs.values()))["stations"].items()},
                "forecast_elev_ft": (site_snap.get("elevation_ft") or {}).get("site"), "windows": {}}
        if coco.get(name):
            area["cocorahs_stations"] = coco[name]["stations"]
        for wid in windows:
            nbm = site_snap["snowfall_in"].get(wid)
            ours = ((ours_all or {}).get(name) or {}).get(wid)
            o_nbm = obs[wid]["snowfall_in"]
            use_ours_period = wid == "total" and "ours_period" in obs
            o_ours = obs["ours_period"]["snowfall_in"] if use_ours_period else o_nbm
            scores = score_nbm(nbm, o_nbm)
            scores.update(score_ours(ours, o_ours))
            models = {}
            for model, md in hires.items():
                sf = ((md["sites"].get(name) or {}).get("snowfall_in") or {}).get(wid)
                if sf is None:
                    continue
                models[model] = {"snowfall_in": sf, "liquid_in": ((md["sites"][name].get("liquid_in") or {}).get(wid)), "cycle_utc": md["cycle_utc"]}
                if o_nbm:
                    scores[f"{model}_error_in"] = round(sf - o_nbm["mid"], 1)
            entry = {
                "nbm": {k: nbm.get(k) for k in ("p25", "p50", "p75", "deterministic", "method")} if nbm else None,
                "ours": ours, "observed": o_nbm,
                "observed_inputs": {t: {k: s[k] for k in ("swe_gain_in", "depth_gain_in", "precip_in", "temp_mean_f", "gate", "coverage")}
                                    for t, s in obs[wid]["stations"].items()},
                "scores": scores,
            }
            entry.update(models)
            if (coco.get(name) or {}).get("windows", {}).get(wid):
                entry["cocorahs"] = coco[name]["windows"][wid]
            if use_ours_period and ours:
                entry["observed_for_ours"] = o_ours
            area["windows"][wid] = entry
        result["areas"][name] = area

    result["snow_level"] = snow_level if snow_level is not None else snow_level_scores(snap, min(s for s, _ in windows.values()), last_end, verbose)
    return result


def print_result(result):
    print(f"\nNBM cycle {result['nbm_cycle_utc']}; windows {', '.join(result['windows'])}")
    print(f"{'area':16s} {'window':6s} {'NBM p25/p50/p75':17s} {'obs low/mid/high':20s} {'NBM err':>8s}  IQR hit")
    for name, a in result["areas"].items():
        for wid, w in a["windows"].items():
            n, o, sc = w["nbm"], w["observed"], w["scores"]
            nb = f"{n['p25']}/{n['p50']}/{n['p75']}" if n else "-"
            ob = f"{o['low']}/{o['mid']}/{o['high']}" if o else "-"
            print(f"{name:16s} {wid:6s} {nb:17s} {ob:20s} {str(sc.get('nbm_error_in', '-')):>8s}  {sc.get('nbm_iqr_hit', '-')}")
    print("\nSnow level at the sounding sites (only near-saturated launches are scored)")
    for name, sl in result["snow_level"].items():
        print(f"  {name} ({sl['station']}): {sl['n_scored']} of {sl['n_launches']} launches scored, bias {sl['bias_ft']} ft, "
              f"MAE {sl['mae_ft']} ft, within NBM 25-75 range {sl['iqr_hit_rate']}")
        for row in sl["launches"]:
            n = row["nbm"]
            tag = "" if row["scored"] else "  (dry column, not scored)"
            print(f"    {row['valid_utc']}  sounding {row['sounding_snow_level_ft']:>6}  NBM {n['p25']}/{n['p50']}/{n['p75']}  err {row.get('nbm_error_ft', '-')}{tag}")


def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        found = sorted((ROOT / "data" / "forecasts").glob("nbm_snapshot_*.json"))
        if not found:
            sys.exit("no nbm_snapshot_*.json in data/forecasts")
        path = found[-1]
    snap = json.loads(path.read_text(encoding="utf-8"))
    ours = load_our_forecast(snap["source"]["first_day_local"])
    try:
        result = score_snapshot(snap, path.name, ours)
    except RuntimeError as exc:
        sys.exit(str(exc))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"score_{result['first_day_local']}.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print_result(result)
    print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
