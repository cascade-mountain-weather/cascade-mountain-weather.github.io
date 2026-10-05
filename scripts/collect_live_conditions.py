"""Collect live station conditions for the homepage/live-conditions map.

Reads _data/areas.yml, pulls the last ~3 days of hourly data for every station
(NWAC via Synoptic, SNOTEL via NRCS AWDB), derives 24h/72h changes and
data-trust flags, and writes assets/data/live_conditions.json.

Run from the repo root:  python scripts/collect_live_conditions.py
"""
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

REPO = Path(__file__).resolve().parent.parent
AREAS_FILE = REPO / '_data' / 'areas.yml'
OUT_FILE = REPO / 'assets' / 'data' / 'live_conditions.json'

# Never commit the token: it comes from the SYNOPTIC_TOKEN secret (Actions) or the environment.
SYNOPTIC_TOKEN = (os.environ.get('SYNOPTIC_TOKEN') or '').strip()  # a pasted secret often carries a trailing newline
if not SYNOPTIC_TOKEN:
    raise SystemExit('SYNOPTIC_TOKEN is not set. Add it as a repository secret (Actions) or export it locally.')
SYNOPTIC_URL = 'https://api.synopticdata.com/v2/stations/timeseries'
AWDB_URL = 'https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1'

LOOKBACK_HOURS = 72
FETCH_HOURS = 24 * 30        # Synoptic's max; keeps long-dead stations visible, flagged
STALE_HOURS = 6              # last report older than this -> flagged stale

# Checklist thresholds
SNOW_DEPTH_RISE_IN = 2.0     # 72h net depth increase counted as "recent snow"
SWE_RISE_IN = 0.25           # 72h SWE increase counted as "recent snow"
PRECIP_72H_IN = 0.10
HUMID_RH = 90
FOG_SPREAD_F = 3.0           # air temp minus dew point at or below this -> visibility flag

# Data-trust flags (caution only, the data is still shown)
DEPTH_SWING_IN = 36.0        # depth range within 24h larger than this is suspect
OFFSEASON_MONTHS = {7, 8, 9, 10}   # any snow depth reported now is flagged
DEPTH_VS_REF_IN = 24.0       # depth this far above every SNOTEL in the area is suspect

now = datetime.now(timezone.utc)


# --- small series helpers -------------------------------------------------

def last_value(series):
    """(time, value) of the newest non-null point, or (None, None)."""
    for t, v in reversed(series):
        if v is not None:
            return t, v
    return None, None


def value_at(series, when, tolerance_h=6):
    """Newest non-null value at or before `when`, if within tolerance."""
    best = None
    for t, v in series:
        if v is None or t > when:
            continue
        best = (t, v)
    if best and (when - best[0]) <= timedelta(hours=tolerance_h):
        return best[1]
    return None


def in_window(series, hours):
    cutoff = now - timedelta(hours=hours)
    return [(t, v) for t, v in series if v is not None and t >= cutoff]


def net_change(series, hours, tolerance_h=6):
    cur_t, cur = last_value(series)
    if cur is None:
        return None
    past = value_at(series, cur_t - timedelta(hours=hours), tolerance_h)
    return None if past is None else round(cur - past, 2)


def accum_change(series, hours):
    """Change in a running accumulation (e.g. SNOTEL PREC, which reports sparsely); resets clamp to 0."""
    change = net_change(series, hours, tolerance_h=12)
    return None if change is None else max(change, 0.0)


def summed(series, hours):
    vals = [v for _, v in in_window(series, hours)]
    return round(sum(vals), 2) if vals else None


def dew_point_f(temp_f, rh):
    if temp_f is None or rh is None or rh <= 0:
        return None
    t_c = (temp_f - 32) * 5 / 9
    a, b = 17.625, 243.04
    g = math.log(rh / 100.0) + a * t_c / (b + t_c)
    return round((b * g / (a - g)) * 9 / 5 + 32, 1)


def r(x, n=1):
    return None if x is None else round(x, n)


# --- fetchers -------------------------------------------------------------

def parse_iso(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(timezone.utc)


def fetch_synoptic(stids):
    resp = requests.get(SYNOPTIC_URL, params={
        'token': SYNOPTIC_TOKEN,
        'stid': ','.join(stids),
        # Fetch a wider window than the 72 h we summarize so a station that went
        # quiet still appears (flagged stale) instead of vanishing from the map.
        'recent': FETCH_HOURS * 60,
        'obtimezone': 'utc',
        'units': 'english,speed|mph',
    }, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if data['SUMMARY'].get('RESPONSE_CODE') not in (1, 2):
        raise RuntimeError(f"Synoptic error: {data['SUMMARY']}")
    out = {}
    for st in data.get('STATION', []):
        obs = st['OBSERVATIONS']
        times = [parse_iso(t) for t in obs.get('date_time', [])]

        def var(name):
            key = next((k for k in obs if k.startswith(name + '_set_1')), None)
            return list(zip(times, obs[key])) if key else []

        out[st['STID']] = {
            'name': st['NAME'],
            'lat': float(st['LATITUDE']),
            'lon': float(st['LONGITUDE']),
            'elev_ft': float(st['ELEVATION']),
            'temp': var('air_temp'),
            'rh': var('relative_humidity'),
            'dew': var('dew_point_temperature'),
            'wind': var('wind_speed'),
            'gust': var('wind_gust'),
            'depth': var('snow_depth'),
            'swe': [],
            'precip_hourly': var('precip_accum_one_hour'),
            'precip_accum': [],
        }
    return out


def fetch_awdb(triplets):
    meta = requests.get(f'{AWDB_URL}/stations', params={'stationTriplets': ','.join(triplets)}, timeout=60)
    meta.raise_for_status()
    meta = {m['stationTriplet']: m for m in meta.json()}

    begin = (now - timedelta(hours=LOOKBACK_HOURS + 30)).strftime('%Y-%m-%d')
    end = (now + timedelta(days=1)).strftime('%Y-%m-%d')
    resp = requests.get(f'{AWDB_URL}/data', params={
        'stationTriplets': ','.join(triplets),
        'elements': 'SNWD,WTEQ,PREC,TOBS,RHUM,WSPDV,WSPDX',
        'duration': 'HOURLY',
        'beginDate': begin,
        'endDate': end,
    }, timeout=90)
    resp.raise_for_status()

    out = {}
    for entry in resp.json():
        trip = entry['stationTriplet']
        m = meta.get(trip, {})
        tz_h = float(m.get('dataTimeZone', -8.0))
        series = {}
        for el in entry.get('data', []):
            code = el['stationElement']['elementCode']
            pts = []
            for p in el.get('values', []):
                # AWDB times are naive station-local standard time.
                t = datetime.strptime(p['date'], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc) - timedelta(hours=tz_h)
                pts.append((t, p.get('value')))
            series[code] = pts
        out[trip] = {
            'name': m.get('name', trip),
            'lat': m.get('latitude'),
            'lon': m.get('longitude'),
            'elev_ft': m.get('elevation'),
            'temp': series.get('TOBS', []),
            'rh': series.get('RHUM', []),
            'dew': [],
            'wind': series.get('WSPDV', []),
            'gust': series.get('WSPDX', []),
            'depth': series.get('SNWD', []),
            'swe': series.get('WTEQ', []),
            'precip_hourly': [],
            'precip_accum': series.get('PREC', []),
        }
    return out


# --- per-station summary --------------------------------------------------

def summarize(cfg, raw):
    obs_t, temp = last_value(raw['temp'])
    _, rh = last_value(raw['rh'])
    _, dew = last_value(raw['dew'])
    if dew is None:
        dew = dew_point_f(temp, rh)
    _, wind = last_value(raw['wind'])
    _, gust = last_value(raw['gust'])
    d_t, depth = last_value(raw['depth'])
    s_t, swe = last_value(raw['swe'])
    newest = max([t for t in (obs_t, d_t, s_t) if t], default=None)

    if raw['precip_accum']:
        p24 = accum_change(raw['precip_accum'], 24)
        p72 = accum_change(raw['precip_accum'], 72)
    else:
        p24 = summed(raw['precip_hourly'], 24)
        p72 = summed(raw['precip_hourly'], 72)

    depth_window = [v for _, v in in_window(raw['depth'], 24)]
    return {
        'id': cfg['id'],
        'label': cfg.get('label') or raw['name'],
        'network': cfg['network'],
        'primary': bool(cfg.get('primary')),
        'lat': raw['lat'],
        'lon': raw['lon'],
        'elev_ft': round(raw['elev_ft']) if raw['elev_ft'] is not None else None,
        'obs_time': newest.strftime('%Y-%m-%dT%H:%M:%SZ') if newest else None,
        'temp_f': r(temp),
        'rh': r(rh, 0),
        'dewpoint_f': r(dew),
        'wind_mph': r(wind),
        'gust_mph': r(gust),
        'snow_depth_in': r(depth),
        'swe_in': r(swe, 1) if swe is not None else None,
        'precip_24h_in': r(p24, 2),
        'precip_72h_in': r(p72, 2),
        'depth_change_24h_in': net_change(raw['depth'], 24),
        'depth_change_72h_in': net_change(raw['depth'], 72),
        'swe_change_72h_in': net_change(raw['swe'], 72),
        '_depth_range_24h': (max(depth_window) - min(depth_window)) if depth_window else None,
        'has_swe': bool(raw['swe']),
        'trust': {'ok': True, 'reasons': []},
    }


def apply_trust_flags(stations):
    """Add caution reasons. Never drops data, just marks it questionable."""
    refs = [s for s in stations if s['network'] == 'SNOTEL' and s['snow_depth_in'] is not None]
    ref_max_depth = max((s['snow_depth_in'] for s in refs), default=None)

    for s in stations:
        reasons = []
        depth = s['snow_depth_in']

        if s['obs_time'] is None:
            reasons.append('No recent data')
        elif now - parse_iso(s['obs_time']) > timedelta(hours=STALE_HOURS):
            hrs = int((now - parse_iso(s['obs_time'])).total_seconds() // 3600)
            age = f'{hrs} h' if hrs < 48 else f'{hrs // 24} days'
            reasons.append(f'No report in {age}')

        if s['temp_f'] is not None and not -35 <= s['temp_f'] <= 115:
            reasons.append('Implausible temperature reading')

        if depth is not None:
            if depth < 0:
                reasons.append('Negative snow depth')
            if now.month in OFFSEASON_MONTHS and depth > 0:
                reasons.append('Snow depth reported in the off-season, may be sensor error')
            if s['_depth_range_24h'] is not None and s['_depth_range_24h'] > DEPTH_SWING_IN:
                reasons.append(f'Snow depth swung {s["_depth_range_24h"]:.0f} in within 24 h')
            if s['has_swe'] and s['swe_in'] is not None and depth > 3 and s['swe_in'] <= 0:
                reasons.append('Snow depth with zero SWE')
            if (s['network'] != 'SNOTEL' and ref_max_depth is not None
                    and depth > ref_max_depth + DEPTH_VS_REF_IN):
                reasons.append('Snow depth far above nearby SNOTEL')

        s['trust'] = {'ok': not reasons, 'reasons': reasons}
        del s['_depth_range_24h']
        del s['has_swe']


def build_checklist(stations):
    def is_unusable(s):
        return any(x.startswith(('No ', 'Implausible')) for x in s['trust']['reasons'])

    usable = [s for s in stations if s['obs_time'] and not is_unusable(s)]
    trusted = [s for s in stations if s['trust']['ok']]
    primary = next((s for s in usable if s['primary']), None) or (usable[0] if usable else None)

    def best(key):
        """Largest value among trusted stations; if none of them report this
        metric, fall back to flagged-but-live stations and mark it unverified."""
        for pool, unverified in ((trusted, False), (usable, True)):
            vals = [s[key] for s in pool if s[key] is not None]
            if vals:
                return max(vals), unverified
        return None, False

    snow_depth, u1 = best('depth_change_72h_in')
    swe_rise, u2 = best('swe_change_72h_in')
    precip72, u3 = best('precip_72h_in')
    precip24, u4 = best('precip_24h_in')
    snow_tag = ' (unverified)' if (snow_depth is not None and u1) or (swe_rise is not None and u2) else ''
    precip_tag = ' (unverified)' if (precip72 is not None and u3) else ''

    def flag(known, hit):
        return 'unknown' if not known else ('yes' if hit else 'no')

    items = [{
        'key': 'snow_72h',
        'label': 'Snow in the last 72 h',
        'status': flag(snow_depth is not None or swe_rise is not None,
                       (snow_depth or 0) >= SNOW_DEPTH_RISE_IN or (swe_rise or 0) >= SWE_RISE_IN),
        'detail': (', '.join(x for x in (
            f'depth {snow_depth:+.1f} in' if snow_depth is not None else '',
            f'SWE {swe_rise:+.2f} in' if swe_rise is not None else '') if x) + snow_tag) or None,
    }, {
        'key': 'precip_72h',
        'label': 'Precipitation in the last 72 h',
        'status': flag(precip72 is not None, (precip72 or 0) >= PRECIP_72H_IN),
        'detail': (f'{precip72:.2f} in' + (f' ({precip24:.2f} in in 24 h)' if precip24 is not None else '') + precip_tag)
                  if precip72 is not None else None,
    }]

    temp = primary['temp_f'] if primary else None
    items.append({
        'key': 'temp',
        'label': 'Below freezing',
        'status': flag(temp is not None, (temp or 99) <= 32),
        'detail': f'{temp:.0f}°F at {primary["label"]}' if temp is not None else None,
    })

    rh = primary['rh'] if primary else None
    items.append({
        'key': 'humidity',
        'label': 'High humidity',
        'status': flag(rh is not None, (rh or 0) >= HUMID_RH),
        'detail': f'{rh:.0f}% RH' if rh is not None else None,
    })

    spread = None
    if primary and primary['temp_f'] is not None and primary['dewpoint_f'] is not None:
        spread = primary['temp_f'] - primary['dewpoint_f']
    items.append({
        'key': 'visibility',
        'label': 'Possible low visibility (fog/cloud)',
        'status': flag(spread is not None, (spread if spread is not None else 99) <= FOG_SPREAD_F),
        'detail': f'temp and dew point {spread:.1f}°F apart' if spread is not None else None,
    })
    return items


# --- main -----------------------------------------------------------------

def main():
    areas = yaml.safe_load(AREAS_FILE.read_text(encoding='utf-8'))['areas']

    nwac_ids = sorted({s['id'] for a in areas for s in a['stations'] if s['network'] == 'NWAC'})
    snotel_ids = sorted({s['id'] for a in areas for s in a['stations'] if s['network'] == 'SNOTEL'})

    raw = {}
    errors = []
    for name, ids, fetch in (('Synoptic', nwac_ids, fetch_synoptic), ('AWDB', snotel_ids, fetch_awdb)):
        try:
            raw.update(fetch(ids))
        except Exception as exc:  # keep going so one outage doesn't blank the map
            errors.append(f'{name}: {exc}')
            print(f'WARNING: {name} fetch failed: {exc}', file=sys.stderr)

    if not raw:
        print('No data from any source; leaving existing JSON untouched.', file=sys.stderr)
        sys.exit(1)

    out_areas = []
    for area in areas:
        stations = []
        for cfg in area['stations']:
            if cfg['id'] in raw:
                stations.append(summarize(cfg, raw[cfg['id']]))
            else:
                print(f'WARNING: no data returned for {cfg["id"]}', file=sys.stderr)
        if not stations:
            continue
        apply_trust_flags(stations)
        stations.sort(key=lambda s: s['elev_ft'] or 0, reverse=True)
        out_areas.append({
            'id': area['id'],
            'name': area['name'],
            'basin': area.get('basin'),
            'basins': area.get('basins') or [area.get('basin')],
            'page': area.get('page'),
            'note': area.get('note'),
            'webcams': area.get('webcams', []),
            'lat': round(sum(s['lat'] for s in stations) / len(stations), 5),
            'lon': round(sum(s['lon'] for s in stations) / len(stations), 5),
            'stations': stations,
            'checklist': build_checklist(stations),
        })

    payload = {
        'generated_utc': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'sources': {'NWAC': 'Synoptic Data API', 'SNOTEL': 'NRCS AWDB'},
        'errors': errors,
        'areas': out_areas,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, indent=1), encoding='utf-8')
    n_st = sum(len(a['stations']) for a in out_areas)
    print(f'Wrote {OUT_FILE.relative_to(REPO)}: {len(out_areas)} areas, {n_st} stations.')


if __name__ == '__main__':
    main()
