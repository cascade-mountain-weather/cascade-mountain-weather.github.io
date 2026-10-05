"""Collect "percent of normal" numbers for the homepage bar plots.

For each forecast area's SNOTEL station (see _data/areas.yml), compares this water
year (starting Oct 1) with normal over three windows (last 7 days, last 30 days, water
year to date):
  - precipitation vs the NRCS median over the same window
  - snow water equivalent (SWE): level vs median for the water year; change vs median
    change for 7/30 days
  - temperature anomaly vs the station's 1991-2020 average

NRCS publishes median/average for PREC and WTEQ through AWDB but not for air
temperature, so temperature normals are computed here from each station's own
1991-2020 daily TAVG record. That climatology is slow to build and never changes,
so it is cached in data/snotel/tavg_climo.json (excluded from the Jekyll build):

    python scripts/collect_normals.py --rebuild-climo   # once, or when areas.yml gains a SNOTEL station
    python scripts/collect_normals.py                   # the daily run

Writes assets/data/normals.json. Missing values are null; the page shows an en dash.
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

REPO = Path(__file__).resolve().parent.parent
AREAS_FILE = REPO / '_data' / 'areas.yml'
CLIMO_FILE = REPO / 'data' / 'snotel' / 'tavg_climo.json'
OUT_FILE = REPO / 'assets' / 'data' / 'normals.json'
AWDB_URL = 'https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1'

CLIMO_YEARS = (1991, 2020)
MIN_CLIMO_YEARS = 10         # fewer years of record than this -> no temperature anomaly
SMOOTH_DAYS = 3              # climatology is averaged over +/- this many days
MIN_NORMAL_PRECIP_IN = 0.5   # percent of a tiny normal is noise
TIMEFRAMES = {'7': 7, '30': 30, 'wy': None}   # days; None = water year to date
MIN_NORMAL_SWE_IN = 0.5
MIN_TEMP_DAYS = 5            # need at least this many daily temps in a window
SERIES_MIN_DAYS = 35         # daily series for the mini charts covers at least this many days


def load_stations():
    """One SNOTEL station per area: (area id, area name, station dict)."""
    out = []
    for area in yaml.safe_load(AREAS_FILE.read_text(encoding='utf8'))['areas']:
        sntl = [s for s in area['stations'] if s['network'] == 'SNOTEL']
        sntl = [s for s in sntl if s.get('normals', True)]
        if sntl:
            out.append((area['id'], area['name'], next((s for s in sntl if s.get('primary')), sntl[0])))
    return out


def awdb_data(triplets, elements, begin, end, central=False):
    params = {
        'stationTriplets': ','.join(triplets), 'elements': ','.join(elements),
        'duration': 'DAILY', 'beginDate': begin.isoformat(), 'endDate': end.isoformat(),
    }
    if central:
        params['centralTendencyType'] = 'ALL'
    resp = requests.get(f'{AWDB_URL}/data', params=params, timeout=120)
    resp.raise_for_status()
    result = {}
    for station in resp.json():
        by_element = {}
        for block in station.get('data', []):
            by_element[block['stationElement']['elementCode']] = block.get('values', [])
        result[station['stationTriplet']] = by_element
    return result


def awdb_meta(triplets):
    """Station name, latitude, longitude and elevation (ft). Best effort: the map on the homepage
    needs it, but the charts do not, so a failure here must not stop the daily update."""
    try:
        resp = requests.get(f'{AWDB_URL}/stations', params={'stationTriplets': ','.join(triplets)}, timeout=60)
        resp.raise_for_status()
        return {r['stationTriplet']: r for r in resp.json()}
    except Exception as exc:
        print(f'Station metadata unavailable ({exc}); coordinates left out.', file=sys.stderr)
        return {}


def md_key(d):
    return f'{d.month:02d}-{d.day:02d}'


def quantile(sorted_vals, q):
    """Linear-interpolated quantile of an already sorted list."""
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


MIN_POOL = 20   # need at least this many daily values (years x window days) for a percentile


def rebuild_climo(stations):
    """Per-station mean TAVG for each month-day over CLIMO_YEARS, lightly smoothed, plus the median and
    25th/75th percentiles. The percentiles pool every daily value within +/-SMOOTH_DAYS of the date
    across all years, so each is computed from about 7 x (number of years) values."""
    climo = {}
    for _, _, st in stations:
        triplet = st['id']
        try:
            series = awdb_data([triplet], ['TAVG'], date(CLIMO_YEARS[0], 1, 1), date(CLIMO_YEARS[1], 12, 31)
                               ).get(triplet, {}).get('TAVG', [])
        except requests.RequestException as e:
            print(f'  {triplet}: fetch failed ({e})', file=sys.stderr)
            continue
        sums, counts, years, vals = {}, {}, set(), {}
        for row in series:
            if row.get('value') is None:
                continue
            d = date.fromisoformat(row['date'])
            k = md_key(d)
            sums[k] = sums.get(k, 0.0) + row['value']
            counts[k] = counts.get(k, 0) + 1
            vals.setdefault(k, []).append(row['value'])
            years.add(d.year)
        if len(years) < MIN_CLIMO_YEARS:
            print(f'  {triplet} ({st["label"]}): only {len(years)} years of TAVG, no temperature normal')
            climo[triplet] = {'years': len(years), 'mean': {}, 'p25': {}, 'p50': {}, 'p75': {}}
            continue
        raw = {k: sums[k] / counts[k] for k in sums}
        mean, p25, p50, p75 = {}, {}, {}, {}
        for k in raw:
            if k == '02-29':   # leap day: no normal, those observations are skipped
                continue
            m, dd = int(k[:2]), int(k[3:])
            neighbours, pool = [], []
            for off in range(-SMOOTH_DAYS, SMOOTH_DAYS + 1):
                nk = md_key(date(2001, m, dd) + timedelta(days=off))   # non-leap year
                if nk in raw:
                    neighbours.append(raw[nk])
                    pool.extend(vals[nk])
            mean[k] = round(sum(neighbours) / len(neighbours), 2)
            if len(pool) >= MIN_POOL:
                pool.sort()
                p25[k], p50[k], p75[k] = (round(quantile(pool, q), 1) for q in (0.25, 0.5, 0.75))
        climo[triplet] = {'years': len(years), 'mean': mean, 'p25': p25, 'p50': p50, 'p75': p75}
        print(f'  {triplet} ({st["label"]}): {len(years)} years')
    CLIMO_FILE.parent.mkdir(parents=True, exist_ok=True)
    CLIMO_FILE.write_text(json.dumps({'period': list(CLIMO_YEARS), 'stations': climo},
                                     separators=(',', ':')), encoding='utf8')
    print(f'Wrote {CLIMO_FILE.relative_to(REPO)}')


def water_year_start(today):
    return date(today.year if today.month >= 10 else today.year - 1, 10, 1)


def last_with(values, key='value'):
    for row in reversed(values):
        if row.get(key) is not None:
            return row
    return None


def pct_of(value, normal, minimum):
    if value is None or normal is None or normal < minimum:
        return None
    return round(100.0 * value / normal)


def mean_anomaly(series, climo_mean, start, end):
    """Mean of (observed - normal) over dated TAVG rows in [start, end]."""
    diffs = []
    for row in series:
        if row.get('value') is None:
            continue
        d = date.fromisoformat(row['date'])
        if start <= d <= end:
            normal = climo_mean.get(md_key(d))
            if normal is not None:
                diffs.append(row['value'] - normal)
    if len(diffs) < MIN_TEMP_DAYS:
        return None
    return round(sum(diffs) / len(diffs), 1)


def daily_series(prec_rows, swe_rows, tavg_rows, climo_st, start, end):
    """Parallel daily arrays from start to end for the mini charts on the homepage.

    precip_obs / precip_med: the day's precipitation (inches), the change in the water-year running
        total. On Oct 1 the total restarts, so that day's value is the total itself. Small negative
        changes (sensor corrections, or dips in the smoothed median) are clamped to 0. The chart
        adds these up over its window.
    swe_obs / swe_med: snow water equivalent level (inches), observed and NRCS median.
    temp_f: daily mean temperature (F). temp_p25 / temp_p50 / temp_p75: the 25th, 50th and 75th
        percentiles of that day's 1991-2020 temperatures (F), the "normal range" drawn behind it.
    A missing day is None (it counts as 0 when precipitation is added up).
    """
    def by_date(rows):
        return {r['date']: r for r in rows if r.get('value') is not None}
    prec, swe, tavg = by_date(prec_rows), by_date(swe_rows), by_date(tavg_rows)

    def increment(table, d, key):
        row = table.get(d.isoformat())
        if row is None or row.get(key) is None:
            return None
        if d.month == 10 and d.day == 1:
            return max(0.0, row[key])
        prev = table.get((d - timedelta(days=1)).isoformat())
        if prev is None or prev.get(key) is None:
            return None
        return max(0.0, row[key] - prev[key])

    def rnd(x, nd=2):
        return None if x is None else round(x, nd)

    out = {k: [] for k in ('precip_obs', 'precip_med', 'swe_obs', 'swe_med', 'temp_f', 'temp_p25', 'temp_p50', 'temp_p75')}
    d = start
    while d <= end:
        key = d.isoformat()
        out['precip_obs'].append(rnd(increment(prec, d, 'value')))
        out['precip_med'].append(rnd(increment(prec, d, 'median')))
        s = swe.get(key)
        out['swe_obs'].append(rnd(s['value']) if s else None)
        out['swe_med'].append(rnd(s.get('median')) if s else None)
        t, mk = tavg.get(key), md_key(d)
        out['temp_f'].append(rnd(t['value'], 1) if t else None)
        for name in ('p25', 'p50', 'p75'):
            out['temp_' + name].append(climo_st.get(name, {}).get(mk))
        d += timedelta(days=1)
    return {'start': start.isoformat(), **out}


def row_on_or_before(rows, d, max_back=3):
    """Latest row dated d or up to max_back days earlier (SNOTEL has occasional gaps)."""
    by_date = {r['date']: r for r in rows if r.get('value') is not None}
    for back in range(max_back + 1):
        row = by_date.get((d - timedelta(days=back)).isoformat())
        if row:
            return row
    return None


def accumulation(rows, end_row, days, wy_start, min_normal, accumulating):
    """Observed vs normal over a window ending at end_row.

    days=None means the whole water year. Precipitation (accumulating=True) is a running
    total that restarts at 0 on Oct 1, so a window is end minus the total `days` earlier
    (0 if that is before Oct 1). SWE is a level, not a total: the water-year figure is the
    current level against the median level, and a 7/30-day window is the CHANGE in SWE
    against the median change over the same days.
    Returns {obs, normal, pct} in inches, or None without data.
    """
    if not end_row or end_row.get('value') is None:
        return None
    end = date.fromisoformat(end_row['date'])
    obs, normal = end_row['value'], end_row.get('median')
    if days is not None:
        start = end - timedelta(days=days)
        base = row_on_or_before(rows, start)
        if base is None:
            return None
        carry_obs, carry_norm = 0.0, 0.0
        if accumulating and start < wy_start:
            # The running total restarted at Oct 1: add the tail of the previous water year.
            last_prev = row_on_or_before(rows, wy_start - timedelta(days=1))
            if last_prev is None:
                return None
            carry_obs = last_prev['value'] - base['value']
            carry_norm = None if last_prev.get('median') is None or base.get('median') is None                 else last_prev['median'] - base['median']
            base = {'value': 0.0, 'median': 0.0}
        obs = obs - base['value'] + carry_obs
        normal = None if normal is None or base.get('median') is None or carry_norm is None             else normal - base['median'] + carry_norm
    return {
        'obs': round(obs, 2),
        'normal': None if normal is None else round(normal, 2),
        'pct': pct_of(obs, normal, min_normal),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rebuild-climo', action='store_true')
    args = parser.parse_args()
    stations = load_stations()

    if args.rebuild_climo:
        rebuild_climo(stations)
        return 0
    if not CLIMO_FILE.exists():
        print(f'{CLIMO_FILE.relative_to(REPO)} is missing; run with --rebuild-climo first.', file=sys.stderr)
        return 1
    climo = json.loads(CLIMO_FILE.read_text(encoding='utf8'))['stations']

    today = datetime.now(timezone.utc).date()
    wy_start = water_year_start(today)
    triplets = [st['id'] for _, _, st in stations]
    # Start early enough that 7- and 30-day windows are complete in early October.
    fetch_start = min(wy_start, today - timedelta(days=SERIES_MIN_DAYS))
    raw = awdb_data(triplets, ['PREC', 'WTEQ', 'TAVG'], fetch_start, today, central=True)

    meta = awdb_meta(triplets)
    areas = []
    for area_id, area_name, st in stations:
        el = raw.get(st['id'], {})
        m = meta.get(st['id'], {})
        prec_rows, swe_rows, tavg_rows = el.get('PREC', []), el.get('WTEQ', []), el.get('TAVG', [])
        mean = climo.get(st['id'], {}).get('mean', {})
        prec_end, swe_end, temp_end = last_with(prec_rows), last_with(swe_rows), last_with(tavg_rows)

        metrics = {'precip': {}, 'swe': {}, 'temp': {}}
        for tf, days in TIMEFRAMES.items():
            metrics['precip'][tf] = accumulation(prec_rows, prec_end, days, wy_start, MIN_NORMAL_PRECIP_IN, accumulating=True)
            metrics['swe'][tf] = accumulation(swe_rows, swe_end, days, wy_start, MIN_NORMAL_SWE_IN, accumulating=False)
            if temp_end and mean:
                end = date.fromisoformat(temp_end['date'])
                start = wy_start if days is None else end - timedelta(days=days - 1)
                metrics['temp'][tf] = mean_anomaly(tavg_rows, mean, max(start, wy_start) if days is None else start, end)
            else:
                metrics['temp'][tf] = None

        areas.append({
            'id': area_id,
            'name': area_name,
            'station': st['label'],
            'resort': st.get('resort'),
            'triplet': st['id'],
            'lat': m.get('latitude'),
            'lon': m.get('longitude'),
            'elev_ft': None if m.get('elevation') is None else round(m['elevation']),
            'metrics': metrics,
            'series': daily_series(prec_rows, swe_rows, tavg_rows, climo.get(st['id'], {}), fetch_start, date.fromisoformat((prec_end or swe_end or temp_end)['date'])) if (prec_end or swe_end or temp_end) else None,
            'data_through': (prec_end or swe_end or temp_end or {}).get('date'),
        })

    areas.sort(key=lambda a: -(a['lat'] if a['lat'] is not None else -90))  # north to south

    if not any(a['metrics']['precip']['wy'] or a['metrics']['swe']['wy'] for a in areas):
        print('No SNOTEL data returned; leaving the existing normals.json untouched.', file=sys.stderr)
        return 1

    OUT_FILE.write_text(json.dumps({
        'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'water_year_start': wy_start.isoformat(),
        'climo_period': list(CLIMO_YEARS),
        'areas': areas,
    }, separators=(',', ':')), encoding='utf8')
    print(f'Wrote {OUT_FILE.relative_to(REPO)}: {len(areas)} areas')
    return 0


if __name__ == '__main__':
    sys.exit(main())
