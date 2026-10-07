"""Add the six 12 h snowfall periods to existing NBM snapshots (used to bring the 2025-26 backfill up to date).

    python scripts/add_periods.py data/evaluation/backfill/nbm_snapshot_2025-11-21.json ...
    python scripts/add_periods.py --all              # every snapshot in data/evaluation/backfill and data/forecasts
    python scripts/add_periods.py --all --force      # recompute periods that are already there

Reads each snapshot's own NBM cycle and first day, fetches only the 6 h snowfall windows needed (Herbie), and merges
`windows[<period>]` and `sites[<name>].snowfall_in[<period>]` into the same file. Nothing else in the snapshot
changes. Run in the cmw-herbie conda env.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nbm_snapshot as ns  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def add_periods(path, sites, force=False):
    snap = json.loads(path.read_text(encoding="utf-8"))
    if "fri_day" in snap["windows"] and not force:
        print(f"{path.name}: periods already there, skipped")
        return False
    cycle = pd.Timestamp(snap["source"]["cycle_utc"].rstrip("Z").replace("T", " "))
    p_start = pd.Timestamp(snap["source"]["first_day_local"] + " 12:00")
    names = [s["name"] for s in sites if s["name"] in snap["sites"]]
    use = [s for s in sites if s["name"] in names]
    grid = ns.Grid(use)
    t0 = time.time()
    for pid, (ps, pe, d) in ns.period_snowfall(cycle, p_start, grid, len(use), verbose=False).items():
        snap["windows"][pid] = {"start_utc": f"{ps:%Y-%m-%dT%H:%MZ}", "end_utc": f"{pe:%Y-%m-%dT%H:%MZ}",
                                "fxx": [int((ps - cycle).total_seconds() // 3600), int((pe - cycle).total_seconds() // 3600)]}
        for k, s in enumerate(use):
            snap["sites"][s["name"]]["snowfall_in"][pid] = {
                "method": d["method"], **{key: ns.r(d[key][k]) for key in ("p25", "p50", "p75", "deterministic") if key in d}}
    path.write_text(json.dumps(snap, indent=1), encoding="utf-8")
    print(f"{path.name}: periods added in {time.time() - t0:.0f}s", flush=True)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    files = [Path(f) for f in args.files]
    if args.all:
        files += sorted((ROOT / "data" / "evaluation" / "backfill").glob("nbm_snapshot_*.json"))
        files += sorted((ROOT / "data" / "forecasts").glob("nbm_snapshot_*.json"))
    sites = yaml.safe_load(ns.SITES_FILE.read_text(encoding="utf-8"))["sites"]
    for f in files:
        try:
            add_periods(f, sites, args.force)
        except Exception as exc:   # noqa: BLE001
            print(f"{f.name}: failed ({str(exc)[:100]})", flush=True)


if __name__ == "__main__":
    main()
