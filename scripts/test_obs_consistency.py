"""Step-0 test: do two consecutive 12 h SNOTEL estimates add up to the 24 h estimate?

    python scripts/test_obs_consistency.py [--steps 3 6 12]

An estimator that handles settling and sensor noise well should give day + night ~= the 24 h window
over the same hours. For each step size this compares the sum of the two 12 h periods with the 24 h
window (12Z-12Z) at the same step size, and with a 3 h-step 24 h window as a common reference.
Reuses the weekends and stations of scripts/test_obs_steps.py; nothing is written to evaluation data.
"""
import argparse
import pickle
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import snotel_obs as so  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PAIRS = [('fri', 0), ('sat', 24), ('sun', 48)]   # offsets of each 24 h window from Friday 12Z


def mid(res):
    sf = res.get('snowfall_in')
    return None if not sf else sf['mid']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--steps', type=int, nargs='+', default=[3, 6, 12])
    ap.add_argument('--cache', default='')
    args = ap.parse_args()

    sites = yaml.safe_load((ROOT / 'data' / 'nbm' / 'sites.yml').read_text())['sites']
    stations = sorted({t for s in sites for t in s['obs']})
    fridays = sorted(p.stem.split('_')[-1] for p in (ROOT / 'data' / 'evaluation' / 'backfill').glob('nbm_snapshot_*.json'))

    cache = Path(args.cache) if args.cache else None
    data = pickle.loads(cache.read_bytes()) if cache and cache.exists() else {}
    for fri in fridays:
        if fri in data:
            continue
        f0 = datetime.strptime(fri, '%Y-%m-%d').replace(hour=12, tzinfo=timezone.utc)
        try:
            data[fri] = so.fetch_hourly(stations, f0, f0 + timedelta(hours=72))[0]
        except Exception as e:   # noqa: BLE001
            print(fri, 'fetch failed', e)
    if cache:
        cache.write_bytes(pickle.dumps(data))

    ref = {}
    rows = []
    for fri, hourly in data.items():
        f0 = datetime.strptime(fri, '%Y-%m-%d').replace(hour=12, tzinfo=timezone.utc)
        for name, off in PAIRS:
            a, m, b = f0 + timedelta(hours=off), f0 + timedelta(hours=off + 12), f0 + timedelta(hours=off + 24)
            for trip in stations:
                h = hourly.get(trip, {})
                so.STEP_H = 3
                r3 = mid(so.station_window(h, a, b))
                for step in args.steps:
                    so.STEP_H = step
                    d, n, w = (mid(so.station_window(h, *x)) for x in ((a, m), (m, b), (a, b)))
                    if None in (d, n, w):
                        continue
                    rows.append((step, fri, name, trip, d + n, w, r3))

    print('step | pairs | with snow | mean|sum-24h| | >=2 in apart | mean|sum-24h(3h ref)|')
    for step in args.steps:
        rs = [r for r in rows if r[0] == step and (r[4] > 0 or r[5] > 0)]
        if not rs:
            continue
        md = sum(abs(r[4] - r[5]) for r in rs) / len(rs)
        big = sum(abs(r[4] - r[5]) >= 2 for r in rs)
        rr = [r for r in rs if r[6] is not None]
        mr = sum(abs(r[4] - r[6]) for r in rr) / max(1, len(rr))
        print(f'{step:>4} | {len([r for r in rows if r[0] == step]):>5} | {len(rs):>9} | {md:>13.2f} | {big:>12} | {mr:>10.2f}')


if __name__ == '__main__':
    main()
