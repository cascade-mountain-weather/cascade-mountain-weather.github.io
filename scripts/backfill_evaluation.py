"""Re-run the 2025-26 evaluation with the new method.

    python scripts/backfill_evaluation.py              # all weekends (resumes; skips finished ones)
    python scripts/backfill_evaluation.py --summary    # only rebuild the summary from existing scores

For every Thursday post of the 2025-26 season it:
  1. builds an NBM snapshot from the AWS archive with scripts/nbm_snapshot.py, using the 19Z cycle on the
     Thursday (about 11 am Pacific, the cycle available when the forecast was being written),
  2. scores it against SNOTEL snowfall and sounding-derived snow level (scripts/score_forecast.py),
  3. adds your own weekend-total range from data/forecasts/eval_forecast_<date>.json where it was saved.

What the archive does and does not give us:
  - The NBM side is rebuilt, not the exact numbers the old Selenium viewer saved. The viewer used whatever
    cycle was newest when it was run, which was not recorded. The 19Z cycle is a consistent stand-in.
  - Only the weekend total of your forecast was saved for each area, so your forecast is scored on that.
  - Four posts (2025-11-20, 11-27, 04-09, 04-23) have no saved ranges; they are scored for the NBM only.
  - Observations are recomputed with the new method, so these numbers are not comparable with the old
    reports (data/evaluation_reports/), which used a different snowfall estimate.

Output: data/evaluation/backfill/{nbm_snapshot,score}_<first-day>.json and summary.json.
Run it in the cmw-herbie conda env (it calls Herbie).
"""
import json
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_forecast import print_result, score_snapshot  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "evaluation" / "backfill"
FORECASTS = ROOT / "data" / "forecasts"

THURSDAYS = [
    "2025-11-20", "2025-11-27", "2025-12-04", "2025-12-11", "2025-12-18", "2025-12-25",
    "2026-01-01", "2026-01-08", "2026-01-15", "2026-01-22", "2026-01-29",
    "2026-02-05", "2026-02-12", "2026-02-19", "2026-02-26",
    "2026-03-05", "2026-03-12", "2026-03-19", "2026-03-26",
    "2026-04-02", "2026-04-09", "2026-04-16", "2026-04-23",
]


def saved_ours(thursday):
    """{area: {'total': [lo, hi]}} from the old evaluation file, or None."""
    path = FORECASTS / f"eval_forecast_{thursday}.json"
    if not path.exists():
        return None
    out = {}
    for name, area in json.loads(path.read_text(encoding="utf-8")).get("areas", {}).items():
        rng = ((area.get("accumulated_snowfall") or {}).get("our_forecast") or {}).get("range") if isinstance(area, dict) else None
        if rng and rng[0] is not None and rng[1] is not None:
            out[name] = {"total": [float(rng[0]), float(rng[1])]}
    return out or None


def make_snapshot(thursday, first_day):
    path = OUT / f"nbm_snapshot_{first_day}.json"
    if path.exists():
        return path
    cmd = [sys.executable, str(ROOT / "scripts" / "nbm_snapshot.py"), "--cycle", f"{thursday} 19:00",
           "--first-day", first_day, "--days", "3", "--out-dir", str(OUT)]
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    if res.returncode != 0 or not path.exists():
        print(f"  snapshot FAILED for {thursday}: {(res.stderr or res.stdout)[-300:]}")
        return None
    print(f"  snapshot done in {time.time() - t0:.0f}s")
    return path


def summarize():
    """Season statistics from every score file, for the weekend-total window."""
    scores = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(OUT.glob("score_*.json"))]
    stats, snow_level = {}, {}
    for s in scores:
        for name, area in s["areas"].items():
            w = area["windows"].get("total")
            o = (w or {}).get("observed")
            if not w or not o:
                continue
            st = stats.setdefault(name, {"weekends": 0, "nbm": [], "ours": [], "both": []})
            st["weekends"] += 1
            sc = w["scores"]
            if "nbm_error_in" in sc:
                st["nbm"].append({"err": sc["nbm_error_in"], "hit": sc["nbm_iqr_hit"], "obs": o["mid"], "date": s["first_day_local"]})
            if "ours_error_in" in sc:
                st["ours"].append({"err": sc["ours_error_in"], "hit": sc["ours_hit"], "obs": (w.get("observed_for_ours") or o)["mid"], "date": s["first_day_local"]})
                if "nbm_error_in" in sc:
                    st["both"].append({"nbm_abs": abs(sc["nbm_error_in"]), "ours_abs": abs(sc["ours_error_in"])})
        for name, sl in (s.get("snow_level") or {}).items():
            agg = snow_level.setdefault(name, {"errors": [], "hits": [], "launches": 0})
            agg["launches"] += sl["n_launches"]
            for row in sl["launches"]:
                if row["scored"]:
                    agg["errors"].append(row["nbm_error_ft"])
                    agg["hits"].append(row["nbm_iqr_hit"])

    def mean(xs):
        return round(sum(xs) / len(xs), 1) if xs else None

    summary = {"weekends_scored": len(scores), "areas": {}, "snow_level": {}}
    for name, st in stats.items():
        entry = {"weekends": st["weekends"]}
        for key in ("nbm", "ours"):
            rows = st[key]
            entry[key] = {"n": len(rows), "bias_in": mean([r["err"] for r in rows]), "mae_in": mean([abs(r["err"]) for r in rows]),
                          "hit_rate": mean([r["hit"] for r in rows]) if rows else None}
            if rows:
                entry[key]["hit_rate"] = round(sum(r["hit"] for r in rows) / len(rows), 2)
        both = st["both"]
        entry["on_same_weekends"] = {"n": len(both), "nbm_mae_in": mean([b["nbm_abs"] for b in both]), "ours_mae_in": mean([b["ours_abs"] for b in both])}
        summary["areas"][name] = entry
    for name, agg in snow_level.items():
        summary["snow_level"][name] = {"launches": agg["launches"], "scored": len(agg["errors"]),
                                       "bias_ft": round(sum(agg["errors"]) / len(agg["errors"])) if agg["errors"] else None,
                                       "mae_ft": round(sum(abs(e) for e in agg["errors"]) / len(agg["errors"])) if agg["errors"] else None,
                                       "iqr_hit_rate": round(sum(agg["hits"]) / len(agg["hits"]), 2) if agg["hits"] else None}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def print_summary(sm):
    print(f"\nSEASON SUMMARY ({sm['weekends_scored']} weekends scored; weekend-total window)")
    print(f"{'area':16s} {'n':>3s} | {'NBM bias':>8s} {'MAE':>5s} {'IQR hit':>7s} | {'ours bias':>9s} {'MAE':>5s} {'range hit':>9s} | same-weekend MAE: NBM vs ours")
    for name, a in sm["areas"].items():
        n, o, b = a["nbm"], a["ours"], a["on_same_weekends"]
        print(f"{name:16s} {a['weekends']:>3d} | {str(n['bias_in']):>8s} {str(n['mae_in']):>5s} {str(n['hit_rate']):>7s} | "
              f"{str(o['bias_in']):>9s} {str(o['mae_in']):>5s} {str(o['hit_rate']):>9s} | {b['nbm_mae_in']} vs {b['ours_mae_in']} (n={b['n']})")
    print("\nSnow level vs sounding (near-saturated launches only)")
    for name, s in sm["snow_level"].items():
        print(f"  {name}: {s['scored']} of {s['launches']} launches scored, bias {s['bias_ft']} ft, MAE {s['mae_ft']} ft, within NBM 25-75 {s['iqr_hit_rate']}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if "--summary" not in sys.argv:
        for thursday in THURSDAYS:
            first_day = (date.fromisoformat(thursday) + timedelta(days=1)).isoformat()
            score_path = OUT / f"score_{first_day}.json"
            if score_path.exists():
                print(f"{thursday}: already scored")
                continue
            print(f"{thursday}: building snapshot for the weekend starting {first_day}")
            snap_path = make_snapshot(thursday, first_day)
            if snap_path is None:
                continue
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
            try:
                result = score_snapshot(snap, snap_path.name, saved_ours(thursday), verbose=False)
            except Exception as exc:  # noqa: BLE001 -- one bad weekend should not stop the season
                print(f"  scoring FAILED for {thursday}: {exc}")
                continue
            score_path.write_text(json.dumps(result, indent=1), encoding="utf-8")
            print(f"  scored ({'with' if result['our_forecast_found'] else 'without'} your ranges)")
    sm = summarize()
    print_summary(sm)
    print(f"\nwrote {(OUT / 'summary.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
