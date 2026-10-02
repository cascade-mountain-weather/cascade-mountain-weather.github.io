"""Collect "percent of normal" numbers for the homepage bar plots.

For each forecast area's SNOTEL station (see _data/areas.yml), compares this water
year (starting Oct 1) with normal:
  - accumulated precipitation vs the NRCS median for the same day of year
  - snow water equivalent (SWE) vs the NRCS median for the same day of year
  - temperature anomaly for the last 7 days and for the water year to date

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
MIN_NORMAL_PRECIP_IN = 1.0   # percent of a tiny early-season normal is noise
MIN_NORMAL_SWE_IN = 0.5
MIN_TEMP_DAYS = 5            # need at least this many daily temps in a window


def load_stations():
    """One SNOTEL station per area: (area id, area name, station dict)."""
    out = []
    for area in yaml.safe_load(AREAS_FILE.read_text(encoding='utf8'))['areas']:
        sntl = [s for s in area['stations'] if s['network'] == 'SNOTEL']
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


def md_key(d):
    return f'{d.month:02d}-{d.day:02d}'


def rebuild_climo(stations):
    """Per-station mean TAVG for each month-day over CLIMO_YEARS, lightly smoothed."""
    climo = {}
    for _, _, st in stations:
        triplet = st['id']
        try:
            series = awdb_data([triplet], ['TAVG'], date(CLIMO_YEARS[0], 1, 1), date(CLIMO_YEARS[1], 12, 31)
                               ).get(triplet, {}).get('TAVG', [])
        except requests.RequestException as e:
            print(f'  {triplet}: fetch failed ({e})', file=sys.stderr)
            continue
        sums, counts, years = {}, {}, set()
        for row in series:
            if row.get('value') is None:
                continue
            d = date.fromisoformat(row['date'])
            k = md_key(d)
            sums[k] = sums.get(k, 0.0) + row['value']
            counts[k] = counts.get(k, 0) + 1
            years.add(d.year)
        if len(years) < MIN_CLIMO_YEARS:
            print(f'  {triplet} ({st["label"]}): only {len(years)} years of TAVG, no temperature normal')
            climo[triplet] = {'years': len(years), 'mean': {}}
            continue
        raw = {k: sums[k] / counts[k] for k in sums}
        mean = {}
        for k in raw:
            if k == '02-29':   # leap day: no normal, those observations are skipped
                continue
            m, dd = int(k[:2]), int(k[3:])
            neighbours = []
            for off in range(-SMOOTH_DAYS, SMOOTH_DAYS + 1):
                nk = md_key(date(2001, m, dd) + timedelta(days=off))   # non-leap year
                if nk in raw:
                    neighbours.append(raw[nk])
            mean[k] = round(sum(neighbours) / len(neighbours), 2)
        climo[triplet] = {'years': len(years), 'mean': mean}
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
    # Start early enough that the 7-day temperature window is complete in early October.
    raw = awdb_data(triplets, ['PREC', 'WTEQ', 'TAVG'], min(wy_start, today - timedelta(days=10)), today, central=True)

    areas = []
    for area_id, area_name, st in stations:
        el = raw.get(st['id'], {})
        prec = last_with(el.get('PREC', []))
        swe = last_with(el.get('WTEQ', []))
        tavg_rows = el.get('TAVG', [])
        mean = climo.get(st['id'], {}).get('mean', {})
        last_temp = last_with(tavg_rows)
        end = date.fromisoformat(last_temp['date']) if last_temp else today
        areas.append({
            'id': area_id,
            'name': area_name,
            'station': st['label'],
            'resort': st.get('resort'),
            'triplet': st['id'],
            'precip_in': prec['value'] if prec else None,
            'precip_median_in': prec.get('median') if prec else None,
            'precip_pct': pct_of(prec['value'], prec.get('median'), MIN_NORMAL_PRECIP_IN) if prec else None,
            'swe_in': swe['value'] if swe else None,
            'swe_median_in': swe.get('median') if swe else None,
            'swe_pct': pct_of(swe['value'], swe.get('median'), MIN_NORMAL_SWE_IN) if swe else None,
            'temp_anom_7d_f': mean_anomaly(tavg_rows, mean, end - timedelta(days=6), end) if mean else None,
            'temp_anom_wy_f': mean_anomaly(tavg_rows, mean, wy_start, end) if mean else None,
            'data_through': (prec or swe or last_temp or {}).get('date'),
        })

    if not any(a['precip_in'] is not None or a['swe_in'] is not None for a in areas):
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
