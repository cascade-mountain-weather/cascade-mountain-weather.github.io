"""Add HRRR (and HRDPS, where it exists) to the saved NBM snapshots, so the evaluation can score them.

    python scripts/backfill_hires.py                 # snapshots in data/evaluation/backfill without a "hires" section
    python scripts/backfill_hires.py --force         # recompute all
    python scripts/backfill_hires.py --dir data/forecasts

For each snapshot it takes the newest 00/06/12/18Z HRRR cycle at or before the NBM cycle the snapshot used (the
Thursday 19Z run gives the 18Z HRRR) and records the snowfall and liquid precipitation for the windows the model
reaches in its 48 hours, which is normally Friday (day 1). HRRR comes from the AWS archive. HRDPS is not archived
beyond a few weeks, so old weekends have none. Then run `python scripts/backfill_evaluation.py --rescore` and
`python scripts/build_evaluation_json.py`.
Run it in the cmw-herbie conda env.
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hires_models  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "data" / "nbm" / "sites.yml"


def main():
    force = "--force" in sys.argv
    folder = ROOT / "data" / "evaluation" / "backfill"
    if "--dir" in sys.argv:
        folder = Path(sys.argv[sys.argv.index("--dir") + 1])
    sites = yaml.safe_load(SITES.read_text(encoding="utf-8"))["sites"]
    for path in sorted(folder.glob("nbm_snapshot_*.json")):
        snap = json.loads(path.read_text(encoding="utf-8"))
        if snap.get("hires") and not force:
            print(f"{path.name}: already has hires")
            continue
        t0 = time.time()
        spans = {wid: (pd.Timestamp(w["start_utc"].rstrip("Z")), pd.Timestamp(w["end_utc"].rstrip("Z"))) for wid, w in snap["windows"].items()}
        print(f"{path.name}:")
        snap["hires"] = hires_models.for_snapshot(pd.Timestamp(snap["source"]["cycle_utc"].rstrip("Z")), spans, sites)
        path.write_text(json.dumps(snap, indent=1), encoding="utf-8")
        print(f"  done in {time.time() - t0:.0f}s ({', '.join(snap['hires']) or 'nothing available'})")


if __name__ == "__main__":
    main()
