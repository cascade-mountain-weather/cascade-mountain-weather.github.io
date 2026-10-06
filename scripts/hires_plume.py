"""Write the HRRR and HRDPS 6-hour snowfall and liquid precipitation the precipitation page overlays on the NBM plume.

    python scripts/hires_plume.py                  # newest 48-hour cycle of each model
    python scripts/hires_plume.py --models hrrr    # one model only

Output: assets/data/hires_plumes.json (bot-generated, do not hand-edit). Same sites and the same 6-hour windows
(ending 00, 06, 12 and 18Z) as scripts/nbm_plume.py, so the page can draw the models on one axis. Each model has
its own cycle and runs 48 hours. See scripts/hires_models.py for what each field is (HRDPS snowfall assumes
a 10:1 snow-to-liquid ratio).
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hires_models as hm  # noqa: E402
import nbm_snapshot as nbm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "hires_plumes.json"
LABELS = {"hrrr": "HRRR (NOAA, 3 km)", "hrdps": "HRDPS (Environment Canada, 2.5 km)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["hrrr", "hrdps"], choices=["hrrr", "hrdps"])
    ap.add_argument("--out", help="output path (default assets/data/hires_plumes.json)")
    args = ap.parse_args()

    cfg = yaml.safe_load(nbm.SITES_FILE.read_text(encoding="utf-8"))
    sites = cfg["sites"] + cfg.get("plume_only_sites", [])
    t0 = time.time()
    out = {"schema": 1, "generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",
           "window_hours": 6, "units": "inches of snow and of liquid precipitation per 6-hour window",
           "notes": [
               "Deterministic model output at the nearest grid point to each site; not corrected for elevation.",
               "HRRR snowfall is its ASNOW field. HRDPS snowfall is its water equivalent of snow times 10 (an assumed 10:1 ratio).",
           ],
           "models": {}}
    for model in args.models:
        cycle = hm.newest_cycle(model)
        if cycle is None:
            print(f"{model}: no complete 48-hour cycle found, skipped", file=sys.stderr)
            continue
        print(f"{model}: cycle {cycle:%Y-%m-%d %H}Z")
        grid = nbm.Grid(sites)
        ends = [cycle + pd.Timedelta(hours=h) for h in range(6, hm.MAX_HOURS + 1, 6)]
        res = hm.windows(model, cycle, ends, grid)
        per_site = {}
        for k, s in enumerate(sites):
            per_site[s["name"]] = {
                "km_to_grid_point": grid.km[k],
                "snow": [nbm.r(res[e][0][k], 2) for e in ends],
                "precip": [nbm.r(res[e][1][k], 2) for e in ends],
            }
        out["models"][model] = {"label": LABELS[model], "cycle_utc": f"{cycle:%Y-%m-%dT%H:%MZ}",
                                "window_end_utc": [f"{e:%Y-%m-%dT%H:%MZ}" for e in ends], "sites": per_site}
    path = Path(args.out) if args.out else OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {path} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
