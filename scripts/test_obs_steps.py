"""Step-0 test: how sensitive is the SNOTEL snowfall estimate to the sampling step on 12-hour periods?

    python scripts/test_obs_steps.py [--steps 3 6 12] [--out docs/obs_step_test.json]

For every weekend in data/evaluation/backfill (the Friday date is in the file name) and every
station in data/nbm/sites.yml, this scores the six 12-hour periods (Fri day through Sun night, day
12Z-0Z, night 0Z-12Z) with snotel_obs.station_window at each step size and reports how often the
answer changes. Nothing is written to the evaluation data.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import snotel_obs as so  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PERIODS = [('fri_day', 0), ('fri_night', 12), ('sat_day', 24), ('sat_night', 36), ('sun_day', 48), ('sun_night', 60)]
BINS = (0.5, 1, 3, 6, 12)   # snowfall category edges (inches); the design's thresholds plus a near-zero edge


def category(x):
    return sum(x >= b for b in BINS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--steps', type=int, nargs='+', default=[3, 6, 12])
    ap.add_argument('--out', default=str(ROOT / 'docs' / 'obs_step_test.json'))
    args = ap.parse_args()

    sites = yaml.safe_load((ROOT / 'data' / 'nbm' / 'sites.yml').read_text())['sites']
    stations = {t: s['name'] for s in sites for t in s['obs']}
    fridays = sorted(p.stem.split('_')[-1] for p in (ROOT / 'data' / 'evaluation' / 'backfill').glob('nbm_snapshot_*.json'))

    rows = []
    for fri in fridays:
        f0 = datetime.strptime(fri, '%Y-%m-%d').replace(hour=12, tzinfo=timezone.utc)
        try:
            hourly, _ = so.fetch_hourly(list(stations), f0, f0 + timedelta(hours=72))
        except Exception as e:   # noqa: BLE001
            print(f'{fri}: fetch failed ({e})')
            continue
        for pid, off in PERIODS:
            s, e = f0 + timedelta(hours=off), f0 + timedelta(hours=off + 12)
            for trip, name in stations.items():
                rec = {'friday': fri, 'period': pid, 'station': trip, 'area': name}
                for step in args.steps:
                    so.STEP_H = step
                    r = so.station_window(hourly.get(trip, {}), s, e)
                    sf = r.get('snowfall_in')
                    rec[f'mid_{step}'] = None if not sf else sf['mid']
                    rec[f'gate_{step}'] = r.get('gate')
                    rec['precip_in'] = r.get('precip_in')
                rows.append(rec)
        print(fri, 'done', flush=True)

    Path(args.out).write_text(json.dumps(rows))
    base = args.steps[1] if len(args.steps) > 1 else args.steps[0]
    for step in args.steps:
        if step == base:
            continue
        both = [r for r in rows if r[f'mid_{step}'] is not None and r[f'mid_{base}'] is not None]
        flips = [r for r in both if category(r[f'mid_{step}']) != category(r[f'mid_{base}'])]
        big = [r for r in both if abs(r[f'mid_{step}'] - r[f'mid_{base}']) >= 2]
        active = [r for r in both if r[f'mid_{step}'] > 0 or r[f'mid_{base}'] > 0]
        print(f'step {step}h vs {base}h: {len(both)} station-periods, {len(active)} with snow in either; '
              f'{len(flips)} change category ({100 * len(flips) / max(1, len(both)):.1f}%), '
              f'{len(big)} differ by >=2 in')
    print('missing data at each step:', {s: sum(r[f"mid_{s}"] is None for r in rows) for s in args.steps}, 'of', len(rows))


if __name__ == '__main__':
    main()
