"""Compare the step-based SNOTEL estimator with the original, on the cached 2025-26 hourly data.

    python scripts/test_obs_consistency.py --cache FILE     # builds the cache first
    python scripts/test_obs_new.py FILE

Checks (1) additivity: day + night vs the 24 h window, and the three 24 h windows vs the weekend total;
(2) how much the 12 h periods change relative to the original method, and where.
"""
import pickle
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import snotel_obs as so  # noqa: E402

BINS = (0.5, 1, 3, 6, 12)
cat = lambda x: sum(x >= b for b in BINS)  # noqa: E731
mid = lambda r: None if not r.get('snowfall_in') else r['snowfall_in']['mid']  # noqa: E731

data = pickle.loads(Path(sys.argv[1]).read_bytes())
add, vs, tot_add = [], [], []
for fri, hourly in data.items():
    f0 = datetime.strptime(fri, '%Y-%m-%d').replace(hour=12, tzinfo=timezone.utc)
    for trip, h in ((t, hourly.get(t, {})) for t in hourly):
        H = lambda x: f0 + timedelta(hours=x)  # noqa: E731
        per = [mid(so.station_window(h, H(o), H(o + 12))) for o in range(0, 72, 12)]
        day24 = [mid(so.station_window(h, H(o), H(o + 24))) for o in (0, 24, 48)]
        wk = mid(so.station_window(h, H(0), H(72)))
        if None in per or None in day24 or wk is None:
            continue
        for i in range(3):
            add.append((per[2 * i] + per[2 * i + 1], day24[i]))
        tot_add.append((sum(per), wk))
        so.STEP_H = 6
        old = [mid(so.station_window_v1(h, H(o), H(o + 12))) for o in range(0, 72, 12)]
        for a, b in zip(per, old):
            if b is not None:
                vs.append((fri, trip, a, b))

active = [p for p in add if p[0] > 0 or p[1] > 0]
print(f'new method, day+night vs 24 h: {len(active)} pairs with snow, mean |diff| {sum(abs(a - b) for a, b in active) / len(active):.2f} in, '
      f'{sum(abs(a - b) >= 2 for a, b in active)} differ by >=2 in')
ta = [p for p in tot_add if p[0] > 0 or p[1] > 0]
print(f'six 12 h periods vs weekend total: {len(ta)} cases, mean |diff| {sum(abs(a - b) for a, b in ta) / len(ta):.2f} in, max {max(abs(a - b) for a, b in ta):.1f}')
act = [v for v in vs if v[2] > 0 or v[3] > 0]
print(f'new vs old, 12 h periods: {len(vs)} station-periods, {len(act)} with snow in either; '
      f'{sum(cat(v[2]) != cat(v[3]) for v in act)} change category; '
      f'total new {sum(v[2] for v in vs):.0f} in vs old {sum(v[3] for v in vs):.0f} in; '
      f'new zero where old >=1: {sum(v[2] == 0 and v[3] >= 1 for v in act)}; old zero where new >=1: {sum(v[3] == 0 and v[2] >= 1 for v in act)}')
