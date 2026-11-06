"""Score the most recent forecast weekend and rebuild the evaluation page data. Run by the Monday workflow.

    python scripts/weekly_evaluation.py                 # the weekend that just ended
    python scripts/weekly_evaluation.py --first-day 2026-11-06

What it does, in order:
  1. Finds the Friday that starts the most recent weekend (or --first-day).
  2. Looks for the snapshot saved when the forecast was written (data/forecasts/nbm_snapshot_<Friday>.json,
     from scripts/nbm_snapshot.py). No snapshot means nothing can be scored: it says so and stops. The workflow
     turns that into a GitHub issue so the missed Thursday step is not lost.
  3. Skips a weekend that already has data/evaluation/score_<Friday>.json (a re-run changes nothing).
  4. Scores it (scripts/score_forecast.py: SNOTEL snowfall and precipitation, sounding freezing level, your call from
     assets/images/<Thursday>_fx/ours.json) and rebuilds assets/data/evaluation.json.

Under GitHub Actions it writes `status` (scored, already-scored, missing-snapshot, not-finished) and `first_day` to
$GITHUB_OUTPUT. Needs only requests, numpy and pyyaml, no Herbie: the model numbers are already in the snapshot.
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_evaluation_json  # noqa: E402
import score_forecast as sf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS = ROOT / "data" / "forecasts"


def last_friday(today):
    """The Friday that began the most recent weekend: this week's if it is Saturday or later, else last week's."""
    back = (today.weekday() - 4) % 7
    return today - timedelta(days=back or 7)


def emit(status, first_day):
    print(f"status: {status} ({first_day})")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"status={status}\nfirst_day={first_day}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--first-day", help="the Friday of the weekend to score, YYYY-MM-DD (default: the most recent Friday)")
    args = ap.parse_args()

    first = args.first_day or last_friday(datetime.now(timezone.utc).date()).isoformat()
    date.fromisoformat(first)   # fail early on a typo
    snap_path = SNAPSHOTS / f"nbm_snapshot_{first}.json"
    score_path = sf.OUT_DIR / f"score_{first}.json"

    if score_path.exists():
        return emit("already-scored", first)
    if not snap_path.exists():
        return emit("missing-snapshot", first)

    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    ours = sf.load_our_forecast(first) or sf.load_ours_json(first)
    try:
        result = sf.score_snapshot(snap, snap_path.name, ours)
    except RuntimeError as exc:   # the last window has not ended yet
        print(exc)
        return emit("not-finished", first)
    sf.OUT_DIR.mkdir(parents=True, exist_ok=True)
    score_path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    sf.print_result(result)
    print("our forecast found:", bool(ours))
    build_evaluation_json.main()
    emit("scored", first)


if __name__ == "__main__":
    main()
