"""Observed snowfall for a time window from SNOTEL hourly data (NRCS AWDB).

    python scripts/snotel_obs.py 2026-03-13T12:00 2026-03-16T12:00 679:WA:SNTL 692:WA:SNTL

Times are UTC. The forecast windows run 12Z to 12Z, so hourly data is used and aligned to them.
AWDB hourly timestamps are in the station's local standard time (PST for Washington); they are
converted to UTC with the station's reported offset.

Method (deliberately simple; every input is saved so the estimate can be audited):
  - The hourly series is sampled every 6 hours from the window start to its end (a missing hour falls
    back to an earlier one, up to 3 hours back). 6-hourly steps limit the loss from settling that a
    daily sum suffers, without chasing hourly sensor noise.
  - swe_gain_in   = sum of the positive 6-hour changes in snow water equivalent (WTEQ), COLD STEPS ONLY.
  - depth_gain_in = sum of the positive 6-hour changes in snow depth (SNWD, whole inches), COLD STEPS ONLY.
  - precip_in     = change in accumulated precipitation (PREC). This is rain plus melted snow.
  - A step is cold if the station's mean air temperature (TOBS) over it is at or below 35 F. Rain falling on
    the snowpack raises SWE and gets absorbed, so gains during warm steps are rain, not snowfall, and are
    ignored (the amount ignored is saved as `swe_gain_warm_ignored_in`).
  - Snowfall is estimated from depth when it agrees with SWE, otherwise from SWE at a typical Cascade
    new-snow density (11%). The range runs from SWE at 20% density (low) to SWE at 7% density (high),
    widened to include depth only when depth agrees with SWE (a depth spike that SWE rejects is noise).
  - A window with no cold-step SWE gain and no cold-step depth gain is 0 snowfall.
  - Sanity checks, because SNOTEL sensors are noisy (snow depth flickers by an inch in warm, dry weather):
      * under 0.2 in of precipitation in the window is TRACE: snowfall is 0, with the high end of the
        range set to what that much water could make at 7% density (0.1 in gives at most 1.4 in);
      * a window averaging 45 F or warmer at the station means no snowfall;
      * a SWE gain under 0.1 in is noise, and cannot exceed 1.3 x the precipitation;
      * snow depth steps under 2 in are ignored unless SWE confirms new snow (then 1 in).
    The saved inputs show which check fired in `gate`.

Limits: SNOTEL sensors are accurate to about 0.1 in of SWE and 1 in of depth, the precipitation gauge reads
in 0.1 in steps, wind moves snow, and the stations sit at their own elevation, not the forecast elevation.
A cold-step rule cannot see snow that fell while a station was a little warm (marginal storms).
"""
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

AWDB_URL = 'https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1'
STEP_H = 6
DENSITY_LOW, DENSITY_TYPICAL, DENSITY_HIGH = 0.20, 0.11, 0.07   # fraction water; low density = high snowfall
SWE_NOISE_IN = 0.09          # WTEQ resolves 0.1 in; ignore changes smaller than that
TRACE_PRECIP_IN = 0.2        # less precipitation than this in the window is trace: no snowfall
PRECIP_CAP = 1.3             # SWE gain cannot exceed this times the precipitation (wind loading allows some excess)
SNOW_T_MAX_F = 35.0          # a 6-hour step warmer than this at the station is rain, not snow
WARM_F = 45.0                # a window averaging at least this warm at the station: no snowfall
DEPTH_STEP_IN = 1.5          # depth steps must exceed this (so 2 in) unless SWE confirms; 0.5 (1 in) when it does
MIN_SAMPLE_SHARE = 0.6       # need this share of the 6-hour samples to trust a series


def get_json(path, params, tries=4, timeout=90):
    """AWDB sometimes stalls; retry with a growing pause before giving up."""
    for attempt in range(tries):
        try:
            r = requests.get(f'{AWDB_URL}/{path}', params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))


def utc(s):
    return datetime.strptime(s, '%Y-%m-%dT%H:%M').replace(tzinfo=timezone.utc)


def station_meta(triplets):
    return {m['stationTriplet']: m for m in get_json('stations', {'stationTriplets': ','.join(triplets)})}


def fetch_hourly(triplets, start, end):
    """{triplet: {element: {utc hour: value}}} for PREC, SNWD, WTEQ and TOBS around [start, end]."""
    meta = station_meta(triplets)
    params = {
        'stationTriplets': ','.join(triplets), 'elements': 'PREC,SNWD,WTEQ,TOBS', 'duration': 'HOURLY',
        'beginDate': (start - timedelta(days=1)).date().isoformat(),
        'endDate': (end + timedelta(days=1)).date().isoformat(),
    }
    out = {t: {} for t in triplets}
    for st in get_json('data', params, timeout=120):
        trip = st['stationTriplet']
        tz = float(meta.get(trip, {}).get('dataTimeZone', -8.0))   # hours from UTC, e.g. -8 for PST
        for block in st.get('data', []):
            series = {}
            for v in block.get('values', []):
                if v.get('value') is None:
                    continue
                local = datetime.strptime(v['date'], '%Y-%m-%d %H:%M')
                series[(local - timedelta(hours=tz)).replace(tzinfo=timezone.utc)] = v['value']
            out[trip][block['stationElement']['elementCode']] = series
    return out, meta


def sample(series, t, back_h=3):
    for h in range(back_h + 1):
        v = series.get(t - timedelta(hours=h))
        if v is not None:
            return v
    return None


def mean_temp(tseries, t0, t1):
    """Mean air temperature over the hours (t0, t1], or None when there is none."""
    vals, t = [], t0 + timedelta(hours=1)
    while t <= t1:
        v = tseries.get(t)
        if v is not None:
            vals.append(v)
        t += timedelta(hours=1)
    return sum(vals) / len(vals) if vals else None


def is_cold(tseries, t0, t1):
    """Snow is possible over (t0, t1]. With no temperature record we do not gate (and rely on the other checks)."""
    m = mean_temp(tseries, t0, t1)
    return True if m is None else m <= SNOW_T_MAX_F


def gain(samples, times, tseries, noise=0.0):
    """Sum of positive changes between consecutive available samples, split into (cold, warm) amounts."""
    prev_v = prev_t = None
    cold = warm = 0.0
    for v, t in zip(samples, times):
        if v is None:
            continue
        if prev_v is not None and v - prev_v > noise:
            if is_cold(tseries, prev_t, t):
                cold += v - prev_v
            else:
                warm += v - prev_v
        prev_v, prev_t = v, t
    return cold, warm


def station_window_v1(series_by_el, start, end):
    """Original window-level estimator (6 h steps). Kept only to compare against station_window."""
    times = []
    t = start
    while t <= end:
        times.append(t)
        t += timedelta(hours=STEP_H)
    n = len(times)
    out = {}
    tseries = series_by_el.get('TOBS', {})

    def samples(el):
        s = series_by_el.get(el, {})
        return [sample(s, t) for t in times]

    wteq, snwd, tobs = samples('WTEQ'), samples('SNWD'), samples('TOBS')
    share = lambda xs: sum(v is not None for v in xs) / n  # noqa: E731
    out['coverage'] = {'swe': round(share(wteq), 2), 'depth': round(share(snwd), 2), 'temp': round(share(tobs), 2)}
    have_swe, have_depth = share(wteq) >= MIN_SAMPLE_SHARE, share(snwd) >= MIN_SAMPLE_SHARE

    swe_cold, swe_warm = gain(wteq, times, tseries, SWE_NOISE_IN) if have_swe else (None, None)
    # PREC is reported sparsely, so look back further (it only ever increases, so an earlier value is safe)
    p0, p1 = sample(series_by_el.get('PREC', {}), times[0], back_h=12), sample(series_by_el.get('PREC', {}), times[-1], back_h=12)
    out['precip_in'] = round(max(0.0, p1 - p0), 2) if p0 is not None and p1 is not None else None
    present = [v for v in tobs if v is not None]
    out['temp_mean_f'] = round(sum(present) / len(present), 1) if present else None
    out['swe_end_in'] = next((v for v in reversed(wteq) if v is not None), None)
    out['depth_end_in'] = next((v for v in reversed(snwd) if v is not None), None)

    swe_supported = swe_cold is not None and swe_cold >= 0.1
    swe_eff = (swe_cold if swe_supported else 0.0) if swe_cold is not None else None
    if swe_eff and out['precip_in'] is not None:
        swe_eff = round(min(swe_eff, PRECIP_CAP * out['precip_in']), 2)
    depth_cold, depth_warm = gain(snwd, times, tseries, 0.5 if swe_supported else DEPTH_STEP_IN) if have_depth else (None, None)
    depth_eff = None if depth_cold is None else round(depth_cold, 1)
    out['swe_gain_in'], out['depth_gain_in'] = swe_eff, depth_eff
    out['swe_gain_warm_ignored_in'] = None if swe_warm is None else round(swe_warm, 2)

    gate = None
    precip = out['precip_in']
    if precip is not None and precip < TRACE_PRECIP_IN:
        gate = 'trace precipitation' if precip > 0 else 'no precipitation'
    elif out['temp_mean_f'] is not None and out['temp_mean_f'] >= WARM_F:
        gate = 'too warm for snow'
    out['gate'] = gate
    if gate:
        high = round(precip / DENSITY_HIGH, 1) if (gate == 'trace precipitation' and precip) else 0.0
        out['snowfall_in'] = {'low': 0.0, 'mid': 0.0, 'high': high, 'method': gate}
    else:
        out['snowfall_in'] = estimate_snowfall(swe_eff, depth_eff)
        if out['snowfall_in'] and out['snowfall_in']['mid'] == 0 and (out['swe_gain_warm_ignored_in'] or 0) >= 0.1:
            out['snowfall_in']['method'] = 'warm steps only (rain on snow)'
    return out


# --- Step-based estimator (Oct 2026) -----------------------------------------------------------------
# Every check runs on a fixed 3-hour UTC grid and depends only on the data around that step, never on the
# window being scored. Window totals are therefore sums of cleaned steps, so two 12 h periods add up to
# the 24 h total and to the weekend total by construction (the old window-level checks did not).
STEP_NEW_H = 3
PAD = 10                     # extra grid steps read on each side of a window (context for the checks)
SWE_STEP_MAX_IN = 2.0        # a single 3 h SWE rise above this is a sensor fault, not snow
DEPTH_STEP_MAX_IN = 12.0     # same for depth
SWE_SPIKE_IN, DEPTH_SPIKE_IN = 0.5, 4.0   # a one-step jump that is undone by the next step is a glitch
DENSITY_MIN, DENSITY_MAX = 0.04, 0.25     # depth-implied density outside this is not believed
DEPTH_MIN_NEIGHBOURHOOD_IN = 2.0          # need this much depth gain nearby to estimate density from it


def _despike(vals, thr):
    """Replace a one-step excursion of at least `thr` that the next sample undoes by the previous value."""
    out = list(vals)
    for i in range(1, len(out) - 1):
        a, b, c = out[i - 1], out[i], out[i + 1]
        if None in (a, b, c):
            continue
        if abs(b - a) >= thr and abs(c - a) < thr / 2:
            out[i] = a
    return out


def station_steps(series_by_el, start, end):
    """Cleaned 3 h steps covering [start, end] (plus context): a list of dicts, oldest first.

    Each step has t0, t1 (UTC), snow {low, mid, high} in inches, swe_in (cleaned cold SWE gain), depth_in
    (cleaned cold depth gain), warm_in (SWE gain ignored because it was warm), trace_in (SWE gain the
    precipitation record around it does not support: more than 1.3 x the 24 h precipitation), fault_in (implausible rise), temp_f.
    """
    h = timedelta(hours=STEP_NEW_H)
    edges = [start + (k - PAD) * h for k in range(int((end - start) / h) + 2 * PAD + 1)]
    wteq_s, snwd_s, tobs_s = (series_by_el.get(k, {}) for k in ('WTEQ', 'SNWD', 'TOBS'))
    prec_s = series_by_el.get('PREC', {})
    swe = _despike([sample(wteq_s, t, 3) for t in edges], SWE_SPIKE_IN)
    dep = _despike([sample(snwd_s, t, 3) for t in edges], DEPTH_SPIKE_IN)

    steps = []
    for j in range(1, len(edges)):
        t0, t1 = edges[j - 1], edges[j]
        st = {'t0': t0, 't1': t1, 'swe_in': 0.0, 'depth_in': 0.0, 'warm_in': 0.0, 'trace_in': 0.0, 'fault_in': 0.0,
              'avail_swe': None not in (swe[j - 1], swe[j]), 'avail_depth': None not in (dep[j - 1], dep[j]),
              'temp_f': mean_temp(tobs_s, t0, t1)}
        p1, p0 = sample(prec_s, t1 + timedelta(hours=12), 12), sample(prec_s, t1 - timedelta(hours=12), 12)
        st['p24'] = None if p0 is None or p1 is None else max(0.0, p1 - p0)
        cold = st['temp_f'] is None or st['temp_f'] <= SNOW_T_MAX_F
        too_warm = st['temp_f'] is not None and st['temp_f'] >= WARM_F
        dswe = swe[j] - swe[j - 1] if st['avail_swe'] else 0.0
        ddep = dep[j] - dep[j - 1] if st['avail_depth'] else 0.0
        if dswe > SWE_STEP_MAX_IN:
            st['fault_in'] = dswe
        elif dswe > SWE_NOISE_IN:
            if not cold or too_warm:
                st['warm_in'] = dswe
            else:
                st['swe_in'] = dswe
        st['depth_raw'] = ddep if 1 <= ddep <= DEPTH_STEP_MAX_IN and cold and not too_warm else 0.0
        steps.append(st)

    # SWE cannot exceed 1.3 x the precipitation measured around it (wind loading allows some excess).
    raw = [s['swe_in'] for s in steps]
    for j, s in enumerate(steps):
        near = sum(raw[max(0, j - 4):j + 5])
        if s['p24'] is not None and near > PRECIP_CAP * s['p24']:
            s['swe_in'] = raw[j] * PRECIP_CAP * s['p24'] / near
            s['trace_in'] = raw[j] - s['swe_in']   # the part the precipitation record does not support
    # Depth sets the snow density locally: gain over +-2 steps next to the SWE gain (depth lags SWE a little).
    for j, s in enumerate(steps):
        lo_j, hi_j = max(0, j - 2), j + 3
        swe_n = sum(x['swe_in'] for x in steps[lo_j:hi_j])
        dep_n = sum(x['depth_raw'] for x in steps[lo_j:hi_j])
        dens = swe_n / dep_n if dep_n >= DEPTH_MIN_NEIGHBOURHOOD_IN and swe_n >= 0.1 else None
        if dens is not None and not DENSITY_MIN <= dens <= DENSITY_MAX:
            dens = None
        w = s['swe_in']
        mid = w / (dens or DENSITY_TYPICAL)
        s['snow'] = {'low': min(w / DENSITY_LOW, mid), 'mid': mid, 'high': max(w / DENSITY_HIGH, mid)}
        s['depth_in'] = s['depth_raw'] if swe_n >= 0.1 else 0.0
    return steps


def station_window(series_by_el, start, end):
    """Observed snowfall at one station over [start, end] from cleaned 3 h steps (see station_steps).

    start and end must be on the 3 h UTC grid (the 12Z and 0Z period edges are). Same output keys as v1.
    """
    steps = station_steps(series_by_el, start, end)
    inside = [s for s in steps if s['t0'] >= start and s['t1'] <= end]
    n = len(inside)
    out = {}
    share = lambda k: sum(s[k] for s in inside) / n if n else 0.0  # noqa: E731
    temps = [s['temp_f'] for s in inside if s['temp_f'] is not None]
    out['coverage'] = {'swe': round(share('avail_swe'), 2), 'depth': round(share('avail_depth'), 2),
                       'temp': round(len(temps) / n, 2) if n else 0.0}
    have_swe, have_depth = share('avail_swe') >= MIN_SAMPLE_SHARE, share('avail_depth') >= MIN_SAMPLE_SHARE
    prec = series_by_el.get('PREC', {})
    p0, p1 = sample(prec, start, back_h=12), sample(prec, end, back_h=12)
    out['precip_in'] = round(max(0.0, p1 - p0), 2) if p0 is not None and p1 is not None else None
    out['temp_mean_f'] = round(sum(temps) / len(temps), 1) if temps else None
    out['swe_end_in'] = sample(series_by_el.get('WTEQ', {}), end, 3)
    out['depth_end_in'] = sample(series_by_el.get('SNWD', {}), end, 3)
    warm = sum(s['warm_in'] for s in inside)
    out['swe_gain_warm_ignored_in'] = round(warm, 2) if have_swe else None
    out['swe_gain_in'] = round(sum(s['swe_in'] for s in inside), 2) if have_swe else None
    out['depth_gain_in'] = round(sum(s['depth_in'] for s in inside), 1) if have_depth else None
    out['flags'] = {'trace_ignored_in': round(sum(s['trace_in'] for s in inside), 2),
                    'fault_ignored_in': round(sum(s['fault_in'] for s in inside), 2)}

    if have_swe:
        tot = {k: round(sum(s['snow'][k] for s in inside), 1) for k in ('low', 'mid', 'high')}
        tot['method'] = 'cleaned 3 h steps' if tot['mid'] > 0 else 'none observed'
    elif have_depth:   # no usable SWE: depth only, with the same cold/trace screening, steps of 2 in or more
        d = round(sum(s['depth_raw'] for s in inside if s['depth_raw'] >= 2), 1)
        tot = {'low': d, 'mid': d, 'high': d, 'method': 'depth only'}
    else:
        out['gate'], out['snowfall_in'] = None, None
        return out
    # A gain this small is at the sensors' resolution (0.1 in SWE): keep the middle estimate, but the true
    # amount may be nothing, so the low end is 0 and the window is flagged.
    out['flags']['near_sensor_resolution'] = bool(have_swe and 0 < out['swe_gain_in'] < 0.2)
    if out['flags']['near_sensor_resolution']:
        tot['low'] = 0.0
    gate = None
    if tot['mid'] == 0:
        if out['flags']['trace_ignored_in'] > 0 or (out['precip_in'] is not None and out['precip_in'] < TRACE_PRECIP_IN):
            gate = 'trace precipitation' if (out['precip_in'] or out['flags']['trace_ignored_in']) else 'no precipitation'
        elif out['temp_mean_f'] is not None and out['temp_mean_f'] >= WARM_F:
            gate = 'too warm for snow'
        elif warm >= 0.1:
            tot['method'] = 'warm steps only (rain on snow)'
        if gate == 'trace precipitation' and out['precip_in']:
            tot['high'] = round(out['precip_in'] / DENSITY_HIGH, 1)
    out['gate'] = gate
    out['snowfall_in'] = tot
    return out


def estimate_snowfall(swe_gain, depth_gain):
    """{low, mid, high, method} in inches, or None when neither SWE nor depth is available."""
    if swe_gain is None and depth_gain is None:
        return None
    if (swe_gain or 0) == 0 and (depth_gain or 0) == 0:
        return {'low': 0.0, 'mid': 0.0, 'high': 0.0, 'method': 'none observed'}
    if swe_gain is None:
        return {'low': depth_gain, 'mid': depth_gain, 'high': depth_gain, 'method': 'depth only'}
    if swe_gain == 0:   # depth rose with no cold SWE gain: not confirmed, treat as noise
        return {'low': 0.0, 'mid': 0.0, 'high': 0.0, 'method': 'depth only, SWE did not confirm'}
    lo, mid, hi = swe_gain / DENSITY_LOW, swe_gain / DENSITY_TYPICAL, swe_gain / DENSITY_HIGH
    if depth_gain is None:
        return {'low': round(lo, 1), 'mid': round(mid, 1), 'high': round(hi, 1), 'method': 'swe only'}
    agree = lo * 0.8 <= depth_gain <= hi * 1.25
    if agree:   # depth is consistent with SWE: use it for the middle and let it widen the range
        return {'low': round(min(lo, depth_gain), 1), 'mid': round(depth_gain, 1), 'high': round(max(hi, depth_gain), 1), 'method': 'depth'}
    return {'low': round(lo, 1), 'mid': round(mid, 1), 'high': round(hi, 1), 'method': 'swe (depth disagreed)'}


def combine(triplets, hourly, meta, start, end):
    """One forecast area over [start, end]: per-station inputs plus the average estimate."""
    stations = {}
    for trip in triplets:
        res = station_window(hourly.get(trip, {}), start, end)
        res['name'] = meta.get(trip, {}).get('name')
        res['elev_ft'] = None if meta.get(trip, {}).get('elevation') is None else round(meta[trip]['elevation'])
        stations[trip] = res
    good = [s['snowfall_in'] for s in stations.values() if s['snowfall_in']]
    combined = None
    if good:
        mean = lambda k: round(sum(g[k] for g in good) / len(good), 1)  # noqa: E731
        combined = {'low': mean('low'), 'mid': mean('mid'), 'high': mean('high'),
                    'stations_used': len(good), 'stations_requested': len(triplets)}
    return {'snowfall_in': combined, 'stations': stations}


def window_obs(triplets, start, end):
    """Observed snowfall for one forecast area over [start, end] (UTC datetimes).

    Several stations are averaged. Returns the combined estimate plus each station's inputs.
    """
    hourly, meta = fetch_hourly(triplets, start, end)
    return combine(triplets, hourly, meta, start, end)


def windows_obs(triplets, windows):
    """Same for several windows at once: windows is {id: (start, end)}; one fetch covers them all."""
    hourly, meta = fetch_hourly(triplets, min(s for s, _ in windows.values()), max(e for _, e in windows.values()))
    return {wid: combine(triplets, hourly, meta, s, e) for wid, (s, e) in windows.items()}


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    res = window_obs(sys.argv[3:], utc(sys.argv[1]), utc(sys.argv[2]))
    print('combined:', res['snowfall_in'])
    for trip, s in res['stations'].items():
        print(f"  {trip} {s['name']} ({s['elev_ft']} ft): snowfall {s['snowfall_in']}, swe_gain {s['swe_gain_in']} "
              f"(warm ignored {s['swe_gain_warm_ignored_in']}), depth_gain {s['depth_gain_in']}, precip {s['precip_in']}, "
              f"temp {s['temp_mean_f']}F, coverage {s['coverage']}")
