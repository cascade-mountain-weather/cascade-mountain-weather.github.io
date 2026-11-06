"""Estimate new-snow depth from SWE when a SNOTEL depth sensor is out.

    python scripts/slr_depth_model.py 418:WA:SNTL 1.2 -9          # station, SWE gain in inches, 700 hPa temperature in C
    python scripts/slr_depth_model.py 418:WA:SNTL 1.2 2026-11-06T12:00 2026-11-09T12:00   # SWE gain, then a window (UTC): fetches the soundings

depth = SWE x clip(level + b (T700 - t0) + c (SWE - 1), 2, 25), from data/slr_model/depth_model.json (built by
scripts/slr_model_swe.py --export; the file is committed, the hourly data behind it is not). `level` is the station's own SLR at -10 C for a
1 in storm; `b` (about -0.29 per C) and `c` (about -0.37 per inch of SWE) are shared by every station. T700 is the mean of the Quillayute and
Salem 700 hPa temperatures at the 00Z and 12Z launches inside the window.

The range is the model's own error: the 10th and 90th percentile of observed over predicted depth in the leave-one-season-out test (about 0.6
and 1.5 times the estimate), so it says how far a working sensor would typically have read from the estimate, not just a rounding band.

What the estimate means: the depth a working SNOTEL depth sensor would have read, which is a lower bound on true new-snow depth (settling and
compaction). That is consistent with the sensors it replaces and with the other stations in the evaluation, but it is not a board measurement.

Used by scripts/snotel_obs.py (the `fill` argument) when a station's depth series is mostly missing. A station with fewer than MIN_STATION_STORMS
storms in the fit, or one that is not in it, gets the east- or west-side average level (east of 121.0 W is east).
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_FILE = ROOT / "data" / "slr_model" / "depth_model.json"
MIN_STATION_STORMS = 40
SOUNDING_SITES = ("UIL", "SLE")   # Quillayute and Salem
_model = None
_t700_cache = {}


def model():
    global _model
    if _model is None:
        _model = json.loads(MODEL_FILE.read_text(encoding="utf-8"))
    return _model


def station_level(trip, lon=None):
    """(level, how): the station's own level, or the regional average when it has too few storms or is not in the fit."""
    m = model()
    st = m["stations"].get(trip)
    if st and st["storms"] >= MIN_STATION_STORMS:
        return st["level"], "station"
    if lon is not None:
        return (m["level_default_east"] if lon >= m["east_lon"] else m["level_default_west"]), "region"
    return m["level_default"], "default"


def estimate(trip, swe_in, t700_c=None, lon=None):
    """{low, mid, high, slr, method} for one station. t700_c None uses the average storm temperature (no temperature information)."""
    m = model()
    level, how = station_level(trip, lon)
    t_used = m["t700_default_c"] if t700_c is None else t700_c
    slr = level + m["b_per_c"] * (t_used - m["t0_c"]) + m["c_per_in_swe"] * (swe_in - 1.0)
    slr = min(max(slr, m["slr_min"]), m["slr_max"])
    mid = swe_in * slr
    q = m["obs_over_pred_quantiles"]
    label = f"swe + depth model (sensor out; {how} level" + ("" if t700_c is not None else ", no 700 hPa temperature") + ")"
    return {"low": round(mid * q["p10"], 1), "mid": round(mid, 1), "high": round(mid * q["p90"], 1), "slr": round(slr, 1), "method": label}


def t700_window(start, end):
    """Mean Quillayute and Salem 700 hPa temperature (C) at the launches in [start, end] (UTC datetimes), or None when none are available."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from slr_pull_soundings import fetch   # IEM raob, with retries; a row has status ok and t700_c
    t = start.replace(minute=0, second=0, microsecond=0)
    while t.hour not in (0, 12) or t < start:
        t += timedelta(hours=1)
    vals = []
    while t <= end:
        for site in SOUNDING_SITES:
            key = (site, t)
            if key not in _t700_cache:
                row = fetch(site, t.replace(tzinfo=None))
                _t700_cache[key] = row.get("t700_c") if row.get("status") == "ok" else None
            if _t700_cache[key] is not None:
                vals.append(_t700_cache[key])
        t += timedelta(hours=12)
    return sum(vals) / len(vals) if vals else None


def make_fill():
    """A callable for snotel_obs.combine: fill(trip, swe_gain_in, start, end, lon) -> snowfall dict."""
    def fill(trip, swe_in, start, end, lon=None):
        return estimate(trip, swe_in, t700_window(start, end), lon)
    return fill


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    trip, swe = sys.argv[1], float(sys.argv[2])
    if len(sys.argv) >= 5:
        t = t700_window(datetime.strptime(sys.argv[3], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc),
                        datetime.strptime(sys.argv[4], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc))
        print(f"mean Quillayute and Salem 700 hPa temperature in the window: {t}")
    else:
        t = float(sys.argv[3])
    print(estimate(trip, swe, t))
