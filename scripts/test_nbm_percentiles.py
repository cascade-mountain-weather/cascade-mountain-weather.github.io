"""Step-0 test: how should NBM snowfall percentiles for a 12 h period be built from 6 h windows?

    python scripts/test_nbm_percentiles.py [--first-day 2026-01-23 ...] [--out docs/nbm_percentile_test.json]

The NBM has real percentiles for 6 h and 24 h snowfall windows (ending 0/6/12/18Z in 3-hourly files)
but not for 12 h. A 24 h window can be built from four 6 h windows, and the real 24 h percentiles are
the answer key. For each weekend this takes the 19Z Thursday cycle (the one the backfill uses), the 24 h
window ending Monday 12Z, fetches the real p25/p50/p75 for it and for its four 6 h windows, and compares:

  sum_median      p25/p75 of the 24 h window = sum of the 6 h p25/p75 values; p50 = sum of p50 (perfectly correlated)
  quadrature      p50 = sum of p50; the spread around it adds in quadrature (independent 6 h windows)
  fitted rho      spread = sqrt(sum_ij rho * w_i * w_j); rho is fitted to minimize error (reported, one value)

Run in the cmw-herbie conda env (needs Herbie, cfgrib, ecCodes). Nothing here writes evaluation data.
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nbm_snapshot as ns  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
THURSDAYS = [
    "2025-11-20", "2025-11-27", "2025-12-04", "2025-12-11", "2025-12-18", "2025-12-25",
    "2026-01-01", "2026-01-08", "2026-01-15", "2026-01-22", "2026-01-29",
    "2026-02-05", "2026-02-12", "2026-02-19", "2026-02-26",
    "2026-03-05", "2026-03-12", "2026-03-19", "2026-03-26",
    "2026-04-02", "2026-04-09", "2026-04-16", "2026-04-23",
]


def one_case(thursday, grid, n):
    first = date.fromisoformat(thursday) + timedelta(days=1)
    cycle = pd.Timestamp(f"{thursday} 19:00")
    end = pd.Timestamp(first.isoformat() + " 12:00") + pd.Timedelta(days=3)   # Monday 12Z
    start = end - pd.Timedelta(hours=24)
    real = ns.snowfall_window(cycle, start, end, grid, n)
    parts = []
    for k in range(4):
        s = start + pd.Timedelta(hours=6 * k)
        parts.append(ns.snowfall_window(cycle, s, s + pd.Timedelta(hours=6), grid, n))
    return real, parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--thursday', nargs='+', default=THURSDAYS)
    ap.add_argument('--out', default=str(ROOT / 'docs' / 'nbm_percentile_test.json'))
    args = ap.parse_args()

    sites = yaml.safe_load(ns.SITES_FILE.read_text(encoding='utf-8'))['sites']
    n = len(sites)
    grid = ns.Grid(sites)
    rows = []
    for th in args.thursday:
        try:
            real, parts = one_case(th, grid, n)
        except Exception as e:   # noqa: BLE001
            print(th, 'failed:', str(e)[:100], flush=True)
            continue
        methods = [real['method']] + [p['method'] for p in parts]
        if any(m != 'percentile' for m in methods) or any(k not in real for k in ('p25', 'p50', 'p75')):
            print(th, 'skipped, methods', methods, flush=True)
            continue
        for i, s in enumerate(sites):
            rows.append({'thursday': th, 'site': s['name'],
                         'real': [float(real[k][i]) for k in ('p25', 'p50', 'p75')],
                         'parts': [[float(p[k][i]) for k in ('p25', 'p50', 'p75')] for p in parts]})
        print(th, 'done', flush=True)
    Path(args.out).write_text(json.dumps(rows))
    report(rows)


def predict(parts, method, rho=None):
    """(p25, p50, p75) of the 24 h window from four 6 h (p25, p50, p75) triples."""
    a = np.array(parts)
    med = a[:, 1].sum()
    if method == 'sum_median':
        return a[:, 0].sum(), med, a[:, 2].sum()
    lo_w, hi_w = a[:, 1] - a[:, 0], a[:, 2] - a[:, 1]
    r = 0.0 if method == 'quadrature' else rho
    cov = lambda w: np.sqrt(max(0.0, (w ** 2).sum() + r * (w.sum() ** 2 - (w ** 2).sum()))) if r is not None else None  # noqa: E731
    return max(0.0, med - cov(lo_w)), med, med + cov(hi_w)


def report(rows):
    snowy = [r for r in rows if r['real'][2] >= 1.0]
    print(f'\n{len(rows)} site-weekends, {len(snowy)} with real 24 h p75 >= 1 in')
    if not snowy:
        return
    def err(method, rho=None):
        e = np.array([np.array(predict(r['parts'], method, rho)) - np.array(r['real']) for r in snowy])
        return e
    print('method         |  bias p25  p50  p75   |  MAE p25  p50  p75')
    for name, rho in (('sum_median', None), ('quadrature', None)):
        e = err(name, rho)
        print(f'{name:14s} | {e.mean(0)[0]:+8.2f} {e.mean(0)[1]:+5.2f} {e.mean(0)[2]:+5.2f}  | {abs(e).mean(0)[0]:8.2f} {abs(e).mean(0)[1]:5.2f} {abs(e).mean(0)[2]:5.2f}')
    best = min(np.linspace(0, 1, 21), key=lambda q: abs(err('rho', q)[:, [0, 2]]).mean())
    e = err('rho', best)
    print(f'fitted rho={best:.2f} | {e.mean(0)[0]:+8.2f} {e.mean(0)[1]:+5.2f} {e.mean(0)[2]:+5.2f}  | {abs(e).mean(0)[0]:8.2f} {abs(e).mean(0)[1]:5.2f} {abs(e).mean(0)[2]:5.2f}')
    # how wide is the real 24 h band relative to the 6 h bands
    ratio = [(r['real'][2] - r['real'][0]) / max(1e-6, sum(p[2] - p[0] for p in r['parts'])) for r in snowy if sum(p[2] - p[0] for p in r['parts']) > 0.5]
    print(f'real 24 h IQR / sum of 6 h IQRs: median {np.median(ratio):.2f} (1 = fully correlated, ~0.5 = independent), n={len(ratio)}')


if __name__ == '__main__':
    main()
