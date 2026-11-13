// Ski recommendation tool (first draft). Data: assets/data/ski_features.json (built by scripts/ski_features.py).
// A scoring problem, not a trained model: hard gates remove a zone and say why; the rest are ranked by a weighted
// average of 0-1 criteria, using the sliders as weights, so every ranking can be explained. Mount: <div id="ski-app">.
(function () {
    'use strict';
    const BASE = (document.currentScript && document.currentScript.src || '').replace(/[^/]*$/, '');
    const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
    const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const AVY = { 1: 'Low', 2: 'Moderate', 3: 'Considerable', 4: 'High', 5: 'Extreme' };

    const SKI_MODES = ['resort', 'backcountry', 'nordic'];
    // criteria: id, label, default weight, what a high score means
    const CRIT = [
        { id: 'fresh', label: 'Fresh snow', w: 5, modes: SKI_MODES, tip: 'New snow in the day window, topping out near 10 inches' },
        { id: 'quality', label: 'Snow quality', w: 3, modes: SKI_MODES, tip: 'Snow-to-liquid ratio: drier, lighter snow scores higher than heavy Cascade concrete' },
        { id: 'wind', label: 'Calm wind', w: 2, tip: 'Gusts above about 15 mph start to cost points' },
        { id: 'vis', label: 'Visibility and sun', w: 2, tip: 'Visibility and cloud cover' },
        { id: 'vert', label: 'Vertical', w: 2, tip: 'Terrain between your minimum elevation and the top', modes: ['resort', 'backcountry'] },
        { id: 'drive', label: 'Short drive', w: 3, tip: 'Free-flow drive time from your starting city; the more of your limit it uses, the lower the score' },
        { id: 'comfort', label: 'Comfortable temperature', w: 3, modes: ['hike', 'bike'], tip: 'Temperature in the comfortable range: about 40-65 F for hiking and running, 50-75 F for biking' },
        { id: 'trail', label: 'Snow-free trail', w: 4, modes: ['hike', 'bike'], tip: 'No snow on the ground or falling: snow on the trail makes for slow hiking and bad biking' },
        { id: 'dry', label: 'Staying dry', w: 2, tip: 'Rain, or snow wet enough to soak through (near freezing), expected while you are out. Counts only liquid that falls as rain at your skiing elevations or as wet snow' },
        { id: 'road', label: 'Road reliability', w: 3, tip: 'Lower chance of a traction or avalanche-control delay on the pass, from how much snow is forecast (based on seven winters of I-90 delays)' },
    ];
    const MODES = { resort: 'Resort', backcountry: 'Backcountry', nordic: 'Nordic', hike: 'Hike / run', bike: 'Bike' };
    const TOWN_DAY = "🧺 Go to the farmer's market, 🎿 wax your skis, 🧶 knit, or 🍞 make some sourdough.";
    const SHORT = { fresh: 'Snow', quality: 'Quality', wind: 'Wind', vis: 'Sun', vert: 'Vert', comfort: 'Temp', trail: 'Trail', dry: 'Dry', drive: 'Drive', road: 'Road' };
    const LOW = ['hike', 'bike'];            // the low-snow-day modes: no snow, no avalanche gates, no season gate
    const COMFORT = { hike: [35, 75], bike: [45, 75] };      // comfortable temperature band, F (a first guess)
    const MAX_TRAIL_SNOW = 4;                // inches on the ground that rule a trail out
    const MAX_TRAIL_NEW = 2;                 // inches of forecast new snow that rule it out
    const STAY_IN_TOWN = 30;                 // best score below this: nothing looks good enough to drive for
    // Rough starting values, to be tuned: the snow on the ground a mode needs, and the months resorts are closed.
    const MIN_BASE = { resort: 20, backcountry: 6, nordic: 12 };
    const CLOSED_MONTHS = [5, 6, 7, 8];             // 0-based: June to September
    const WET = { ok: 'Fine with wet', prefer: 'Prefer dry', dry: 'Keep me dry' };
    const WET_LIMIT = 0.1;          // inches of liquid that gets you wet: the "Keep me dry" cutoff
    let LIVE = null;      // assets/data/pass_now.json: closures and restrictions right now (scripts/pass_log.py)
    const S = { mode: 'resort', day: 0, origin: 'seattle', leave: '07:00', wet: 'prefer', maxDrive: 4, minElev: 3500, w: Object.fromEntries(CRIT.map(c => [c.id, c.w])) };

    // Liquid (in) that reaches you as rain or wet snow during the ski window. Rain share: 50% when the snow level is at the middle of
    // your skiing range, ramping over +/-1,000 ft. Wet-snow share: highest at 34 F, zero by 29 and 39 F (the NBM temperature is the
    // grid point's, not corrected for elevation, so this is a rough flag). Null when there is no liquid forecast.
    function wetness(d, lowest, top) {
        if (d.liquid_in == null) return null;
        const mid = (lowest + top) / 2;
        const rain = d.snow_level_ft == null ? 0.5 : clamp((d.snow_level_ft - mid) / 2000 + 0.5);
        const slush = d.temp_f == null ? 0 : clamp(1 - Math.abs(d.temp_f - 34) / 5);
        return d.liquid_in * (rain + (1 - rain) * slush);
    }

    // Timing recommender: the best 4-hour window of the ski day (08:00-16:00 local), from the hourly NBM series (d.hourly). Each hour gets a
    // badness from 0 (calm and dry) to 1: rain counts most, active snow less for skiers (it is why you came) but fully for hiking and
    // biking, gusts above about 15 mph add to it, and so does temperature: outside the comfortable band for hiking and biking, and for snow activities warmth (above about 30 F) counts against a window much more than cold. A window's score is 100 x (1 - mean badness). Snow that already fell before the
    // window (fresh, not falling) breaks ties for skiers. The score only picks the window; it is not shown. Trend: badness in the 3 hours after
    // the window against the 3 hours before it.
    const WIN_H = 4;
    const RAIN_FULL = 0.04;     // in/h of rain that counts as fully wet
    const SNOW_FULL = 0.04;     // in/h of liquid falling as snow that is fully "snowing hard"
    const hh = h => `${((h + 11) % 12) + 1} ${h % 24 < 12 ? 'AM' : 'PM'}`;
    function bestWindow(z, d, S, lowest, top) {
        const H = d.hourly;
        if (!H || !H.lh || H.lh.length < 2) return null;
        const low = LOW.includes(S.mode);
        const mid = (lowest + (low ? lowest + 1500 : top)) / 2;
        const ratio = d.snow_ratio || 10;
        // one entry per hour, labelled by the hour it ends, filled from the nearest sample (3-hourly files stand for 3 hours)
        // `all` also holds up to 2 hours either side of the ski day (6-8 am and 4-6 pm, where the forecast has them) so the trend can look
        // at what comes before and after the window; `hours` is the ski day itself, the only place a window can sit.
        const all = [];
        for (let h = 6; h <= 18; h++) {
            const core = h >= 8 && h <= 16;
            let k = 0;
            H.lh.forEach((x, i) => { if (Math.abs(x - h) < Math.abs(H.lh[k] - h)) k = i; });
            if (Math.abs(H.lh[k] - h) > (H.block[k] > 1 ? 2 : 1)) { if (core) return null; continue; }
            const p = H.precip_in[k], g = H.gust_mph[k], sl = H.snow_level_ft[k];
            if (p == null && g == null) { if (core) return null; continue; }
            all.push({ h, p: p || 0, g, sl, t: H.temp_f ? H.temp_f[k] : null, c: H.cloud_pct ? H.cloud_pct[k] : null, coarse: H.block[k] > 1 });
        }
        const hours = all.filter(x => x.h >= 8 && x.h <= 16);
        // Beyond 48 h the NBM only has a 1 h snapshot every third hour, which misses rain that falls in between. There the 6 h liquid totals
        // (about 4-10 am and 10 am-4 pm) set how much falls, and the snapshots only shape it within the block (spread evenly when they are dry).
        (H.blocks || []).forEach(b => {
            const hs = all.filter(x => x.coarse && x.h > b.end_lh - 6 && x.h <= b.end_lh);
            if (!hs.length || b.liquid_in == null) return;
            const sum = hs.reduce((a, x) => a + x.p, 0), avg = b.liquid_in / 6;
            hs.forEach(x => { x.p = sum > 0 ? avg * x.p / (sum / hs.length) : avg; });
        });
        all.forEach(x => {
            const rainShare = x.sl == null ? 0.5 : clamp((x.sl - mid) / 2000 + 0.5);
            x.rain = x.p * rainShare; x.snow = x.p * (1 - rainShare);
            x.bRain = clamp(x.rain / RAIN_FULL); x.bSnow = clamp(x.snow / SNOW_FULL) * (low ? 1 : 0.35); x.bWind = x.g == null ? 0 : 0.8 * clamp((x.g - 15) / 35);
            x.bTemp = x.t == null ? 0 : low ? 0.5 * (1 - comfortScore(x.t, COMFORT[S.mode])) : snowTempBad(x.t);
            x.b = 1 - (1 - x.bRain) * (1 - x.bSnow) * (1 - x.bWind) * (1 - x.bTemp);
        });
        let best = null;
        for (let i = 0; i + WIN_H <= hours.length; i++) {
            const w = hours.slice(i, i + WIN_H);
            const mean = f => w.reduce((a, x) => a + f(x), 0) / WIN_H;
            const before = hours.slice(0, i).reduce((a, x) => a + x.snow, 0) * ratio;          // inches of snow that fell earlier in the day
            const fresh = S.mode === 'resort' || S.mode === 'backcountry' || S.mode === 'nordic' ? clamp((Math.max(0, (d.new_snow_in || 0) - w.reduce((a, x) => a + x.snow, 0) * ratio) + before) / 8) : 0;
            const score = 100 * (1 - mean(x => x.b));
            const key = score + 5 * fresh - 0.05 * Math.abs(w[0].h - 1 - 9);      // ties go to a window starting near 9 am: after the cold start, before the afternoon
            if (!best || key > best.key) best = { i, w, score, key };
        }
        const w = best.w, half = (a, f) => a.reduce((t, x) => t + f(x), 0) / a.length;
        // Trend: the 3 hours after the window against the 3 hours before it. Where the forecast has nothing on one side (the window sits at
        // the edge of the data), the window's own first or second half stands in for that side.
        const bef = all.filter(x => x.h < w[0].h && x.h >= w[0].h - 3), aft = all.filter(x => x.h > w[WIN_H - 1].h && x.h <= w[WIN_H - 1].h + 3);
        const early = bef.length ? bef : w.slice(0, 2), late = aft.length ? aft : w.slice(2);
        const span = bef.concat(w, aft);
        const delta = half(late, x => x.b) - half(early, x => x.b);
        const trend = delta > 0.12 ? 'deteriorating' : delta < -0.12 ? 'improving' : 'stable';
        // why: the factors that change most between the period before and the period after, in words
        const dT = half(late, x => x.t == null ? 0 : x.t) - half(early, x => x.t == null ? 0 : x.t);
        const phrase = {
            rain: up => up ? 'rain increasing (storm approaching)' : 'rain easing (storm leaving)',
            snow: up => up ? 'snow increasing (storm approaching)' : 'snow easing (storm leaving)',
            wind: up => up ? 'wind picking up' : 'wind dropping',
            temp: () => dT > 0 ? 'warming up' : 'cooling off',
        };
        const changes = [['rain', x => x.bRain], ['snow', x => x.bSnow], ['wind', x => x.bWind], ['temp', x => x.bTemp]]
            .map(([n, f]) => [n, half(late, f) - half(early, f)]).filter(c => Math.abs(c[1]) >= 0.05).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 2);
        const meanB = half(span, x => x.b);
        const steady = [['rain', 'steady rain', x => x.bRain], ['snow', 'snow throughout', x => x.bSnow], ['wind', 'windy throughout', x => x.bWind], ['temp', low ? 'uncomfortable temperatures throughout' : 'warm, soft snow throughout', x => x.bTemp]]
            .find(([, , f]) => half(span, f) >= 0.3);
        const why = trend === 'stable' ? (meanB < 0.1 ? 'dry and calm throughout' : steady ? steady[1] : 'little change through the window')
            : changes.length ? 'with ' + changes.map(([n, v]) => phrase[n](v > 0)).join(' and ') : '';
        // beyond 48 h the NBM has no hourly precipitation, so the timing within the day is approximate
        const fuzzy = hours.filter(x => x.coarse).length / hours.length > 0.5;
        // corn clock (snow activities): a sunny, dry day whose temperature climbs through freezing. If the snow froze overnight, the surface
        // softens into corn a couple of hours after it thaws, east-facing slopes first, then south, then west, and turns to mush later.
        let corn = null;
        if (!low) {
            const tt = hours.filter(x => x.t != null), cl = hours.filter(x => x.c != null);
            const sunny = cl.length && cl.reduce((a, x) => a + x.c, 0) / cl.length < 50;
            const dry = hours.reduce((a, x) => a + x.p, 0) < 0.03;
            const thaw = tt.find(x => x.t >= 32);
            if (tt.length && sunny && dry && thaw && tt[0].t < 32 + 4) {
                const mush = tt.find(x => x.t >= 45);
                corn = { thaw: thaw.h - 1, mush: mush ? mush.h - 1 : null, allDay: tt[0].t >= 32 };
            }
        }
        return { start: w[0].h - 1, end: w[WIN_H - 1].h, trend, why, fuzzy, corn };
    }

    // Snow activities: cold is fine, warm is not. Badness from the forecast point temperature (not corrected for elevation, so a rough guide):
    // none up to 30 F, rising to 0.5 by 42 F (soft, heavy snow and wet gear); only a mild 0.2 penalty for bitter cold, from 10 F down to -5 F.
    function snowTempBad(t) {
        if (t > 30) return 0.5 * clamp((t - 30) / 12);
        if (t < 10) return 0.2 * clamp((10 - t) / 15);
        return 0;
    }

    // 1 inside the comfortable band, falling to 0 twenty degrees outside it
    function comfortScore(t, band) {
        const lo = band[0], hi = band[1];
        return 1 - clamp((t < lo ? lo - t : t > hi ? t - hi : 0) / 20);
    }

    function score(z, d, S) {
        const why = [];
        const timed = ((z.drive_by_time || {})[S.origin] || {})[S.leave];     // typical drive at your leave time, when we have it
        const drive = timed != null ? timed : (z.drive_hours || {})[S.origin];
        const lowest = LOW.includes(S.mode) ? (z.access_ft || 0) : Math.max(S.minElev, z.access_ft || 0);       // hiking and biking start at the trailhead, not your ski minimum
        const vert = z.top_ft - lowest;
        if (!z.modes.includes(S.mode)) why.push(`Not set up for ${MODES[S.mode].toLowerCase()} here`);
        if (drive == null) why.push('No drive time from this city');
        else if (drive > S.maxDrive) why.push(`${drive.toFixed(1)} h drive is over your ${S.maxDrive} h limit`);
        const low = LOW.includes(S.mode);
        if (S.mode !== 'nordic' && !low && vert < 600) why.push('Almost no terrain above your minimum elevation');
        if (S.mode === 'backcountry') {
            if (!z.nwac_zone) why.push('No NWAC avalanche forecast covers this area');
            else if (d.avy_danger == null || d.avy_danger < 0) why.push('No avalanche forecast right now');
            else if (d.avy_danger >= 4) why.push(`Avalanche danger ${AVY[d.avy_danger]}`);
        }
        if (d.gate_hold) why.push('The Longmire gate is likely held: avalanche danger High or above closes the Paradise road (NPS winter road rules)');
        if (d.new_snow_in == null) why.push('No forecast for this day yet');
        if (low) {
            if (z.base_in != null && z.base_in >= MAX_TRAIL_SNOW) why.push(`${z.base_in.toFixed(0)} in of snow on the ground at ${z.base_station}`);
            if (d.new_snow_in != null && d.new_snow_in >= MAX_TRAIL_NEW) why.push(`${d.new_snow_in.toFixed(1)} in of new snow forecast`);
        }
        const offSeason = S.mode === 'resort' && CLOSED_MONTHS.includes(+d.date.slice(5, 7) - 1);
        if (offSeason) why.push('Ski areas are closed for the season (lifts usually open in late November)');
        if (z.base_in !== undefined && !offSeason && !low) {
            if (z.base_in == null) { if (S.mode !== 'resort') why.push('No snow-depth report from this area right now'); }
            else if (z.base_in < MIN_BASE[S.mode]) why.push(`Only ${z.base_in.toFixed(0)} in of snow on the ground at ${z.base_station} (${MODES[S.mode].toLowerCase()} needs about ${MIN_BASE[S.mode]} in)`);
        }
        const live = S.day === 0 ? liveClosed(z) : null;           // a closure reported right now only counts for today
        if (live) why.push('Road closed right now: ' + live);
        // snow level: rain at your minimum elevation only matters when something is falling
        const raining = d.new_snow_in >= 0.5 && d.snow_level_ft != null && d.snow_level_ft > S.minElev + 1500;
        if (raining && S.mode !== 'nordic' && !low) why.push(`Snow level ${d.snow_level_ft.toLocaleString()} ft is well above your ${S.minElev.toLocaleString()} ft minimum`);
        const wet = wetness(d, lowest, low ? lowest + 1500 : z.top_ft);       // low modes: the trailhead and just above it
        if (S.wet === 'dry' && wet != null && wet >= WET_LIMIT) why.push(`About ${wet.toFixed(2)} in of rain or wet snow forecast (your limit is ${WET_LIMIT} in)`);
        const s = {
            comfort: d.temp_f == null ? 0.5 : comfortScore(d.temp_f, COMFORT[S.mode] || COMFORT.hike),
            trail: clamp(1 - Math.max((z.base_in || 0) / MAX_TRAIL_SNOW, (d.new_snow_in || 0) / MAX_TRAIL_NEW)),
            dry: wet == null ? 0.5 : 1 - clamp(wet / 0.3),
            fresh: clamp((d.new_snow_in || 0) / 10),
            quality: d.snow_ratio == null ? 0.5 : clamp((d.snow_ratio - 9) / 6),                 // no ratio: neutral
            wind: d.gust_mph == null ? 0.5 : 1 - clamp((d.gust_mph - 15) / 35),
            vis: (d.vis_mi == null ? 0.5 : 0.6 * clamp(d.vis_mi / 6)) + (d.cloud_pct == null ? 0.2 : 0.4 * (1 - d.cloud_pct / 100)),
            vert: clamp(vert / 3500),
            drive: drive == null ? 0 : 1 - clamp(drive / S.maxDrive),
            road: 1 - clamp(d.road_risk / 0.5),         // a 50% chance of a delay scores zero
        };
        let num = 0, den = 0;
        const parts = [];
        CRIT.forEach(c => {
            if (c.modes && !c.modes.includes(S.mode)) return;
            const w = c.id === 'dry' && S.wet === 'ok' ? 0 : S.w[c.id];
            num += w * s[c.id]; den += w;
            parts.push({ id: c.id, label: c.label, s: s[c.id], w });
        });
        const total = den ? 100 * num / den : 0;
        const notes = [];
        if (d.avy_danger === 3) notes.push('Avalanche danger Considerable: be conservative with terrain choices.');
        if (S.mode !== 'backcountry' && d.avy_danger >= 4) notes.push(`Avalanche danger ${AVY[d.avy_danger]} in the mountains; expect slower travel and a higher chance of road control work.`);
        if (low && d.temp_f != null && d.temp_f < COMFORT[S.mode][0]) notes.push(`Cold: about ${Math.round(d.temp_f)} F at the forecast point.`);
        if (low && d.temp_f != null && d.temp_f > COMFORT[S.mode][1]) notes.push(`Warm: about ${Math.round(d.temp_f)} F at the forecast point.`);
        if (low && d.snow_level_ft != null && d.snow_level_ft < (z.top_ft || 0) && (d.liquid_in || 0) > 0.05) notes.push(`Snow level ${d.snow_level_ft.toLocaleString()} ft: higher trails may have fresh snow.`);
        if (d.new_snow_in != null && d.new_snow_in < 0.5 && S.mode === 'resort') notes.push('Little or no new snow forecast: expect whatever snow is already on the ground.');
        if (low && d.liquid_in != null && d.liquid_in >= 0.05) {
            const snowy = d.snow_level_ft != null && d.snow_level_ft < (z.top_ft || 0);
            notes.push(`${d.liquid_in.toFixed(2)} in of precipitation in the past 24 hours` + (d.liquid_in >= 0.25 ? (S.mode === 'bike' ? ': expect muddy, soft trails' : ': expect muddy trails') + (snowy ? ' and a moderate amount of fresh snow higher up' : '') : ': trails may be damp') + '.');
        }
        if (!low && wet != null && wet >= 0.05 && S.wet !== 'dry') notes.push(`About ${wet.toFixed(2)} in of rain or wet snow likely while you are out` + (d.temp_f != null && Math.abs(d.temp_f - 34) < 5 ? ' (near freezing, so expect wet snow or slush)' : '') + '.');
        if (d.gust_mph != null && d.gust_mph >= 40) notes.push('Strong gusts, expect lift holds or closed upper terrain.');
        if (z.road_risk && z.road_risk.model === 'nps_gate') notes.push('The Paradise road also closes for staffing, snow removal and unsafe road conditions, and in some winters on weekdays. Check the NPS Longmire gate status before you drive.');
        else if (d.delay_risk != null && d.delay_risk >= 0.2) notes.push(`About a ${Math.round(d.delay_risk * 100)}% chance of a traction or avalanche-control delay on the way` + (d.risk_parts && d.risk_parts.length > 1 ? ' (' + d.risk_parts.map(p => p.route.replace(/ (Snoqualmie|Stevens|White|Blewett) Pass| North Cascades Highway/, '') + ' ' + Math.round(p.p * 100) + '%').join(', ') + ')' : ' on ' + z.road_risk.route) + ' that day.');
        return { z, d, drive, vert, total, parts, why, notes, wet, win: bestWindow(z, d, S, lowest, low ? lowest + 1500 : z.top_ft) };
    }

    // A closure or restriction the log has seen on this zone's road, if the log is fresh (under 6 hours old; it is read in the morning).
    function liveClosed(z) {
        if (!LIVE || !LIVE.generated_utc || !z.road_risk) return null;
        if ((Date.now() - Date.parse(LIVE.generated_utc.replace(/Z$/, ':00Z'))) > 6 * 3600e3) return null;
        const tags = z.road_risk.tags || [];
        if (z.road_risk.model === 'nps_gate' && LIVE.paradise_gate && LIVE.paradise_gate.open === false) return (LIVE.paradise_gate.status || 'closed').slice(0, 90);
        for (const t of tags) for (const it of (LIVE.passes[t] || [])) if (it.closed) return (it.text || 'closed').slice(0, 90);
        return null;
    }

    function clock(t) {
        const [h, m] = t.split(':').map(Number);
        return `${h}:${String(m).padStart(2, '0')} am`;
    }

    function cycleLabel(iso) {
        const d = new Date(iso);
        return `run of ${WD[d.getUTCDay()]} ${MON[d.getUTCMonth()]} ${d.getUTCDate()}, ${String(d.getUTCHours()).padStart(2, '0')}Z`;
    }

    function dayLabel(iso) {
        const [y, m, dd] = iso.split('-').map(Number);
        const d = new Date(Date.UTC(y, m - 1, dd));
        return `${WD[d.getUTCDay()]} ${MON[d.getUTCMonth()]} ${d.getUTCDate()}`;
    }

    function mount(el, data) {
        if (!data.origins[S.origin]) S.origin = Object.keys(data.origins)[0];
        const hp = new URLSearchParams(location.hash.slice(1));              // optional #mode=hike&day=1 (shareable, and handy for testing)
        if (MODES[hp.get('mode')]) S.mode = hp.get('mode');
        if (hp.get('day') >= 0 && hp.get('day') < data.zones[0].days.length) S.day = +hp.get('day');
        if (WET[hp.get('wet')]) S.wet = hp.get('wet');
        if (hp.get('drive') > 0) S.maxDrive = +hp.get('drive');
        function render() {
            const rows = data.zones.map(z => score(z, z.days[S.day], S));
            const ok = rows.filter(r => !r.why.length).sort((a, b) => b.total - a.total);
            const out = rows.filter(r => r.why.length);
            const modeCrit = CRIT.filter(c => !c.modes || c.modes.includes(S.mode));
            const chips = (items, cur, name) => `<div class="sk-chips" role="radiogroup" aria-label="${name}">${items.map(([id, label]) =>
                `<button type="button" class="sk-chip" role="radio" aria-checked="${String(id) === String(cur)}" data-k="${name}" data-v="${esc(id)}">${esc(label)}</button>`).join('')}</div>`;
            const card = (r, i) => {
                const top = r.parts.slice().sort((a, b) => b.w * b.s - a.w * a.s).slice(0, 2).map(p => p.label.toLowerCase());
                const d = r.d;
                return `<article class="sk-card${i === 0 ? ' sk-best' : ''}">
                    <div class="sk-head"><span class="sk-rank">${i + 1}</span><h3>${esc(r.z.name)}</h3><span class="sk-score">${Math.round(r.total)}<small>/100</small></span></div>
                    <p class="sk-why">Leads on ${top.join(' and ')}.</p>
                    ${r.win ? `<p class="sk-window"><span class="sk-wlabel">When to go</span> <strong>${hh(r.win.start)} &ndash; ${hh(r.win.end)}</strong><small>because conditions are <span class="sk-trend sk-trend-${r.win.trend}">${r.win.trend === 'deteriorating' ? '&#8600; ' : r.win.trend === 'improving' ? '&#8599; ' : '&rarr; '}${r.win.trend}</span>${r.win.trend === 'stable' ? ': ' : ', '}${esc(r.win.why)}</small>${r.win.corn ? `<small class="sk-corn"><strong>Corn clock:</strong> sunny and ${r.win.corn.allDay ? 'above freezing all day' : 'thawing through freezing around ' + hh(r.win.corn.thaw)}. If it froze overnight, the surface softens ${hh(r.win.corn.thaw + 1)}&ndash;${hh(r.win.corn.thaw + 3)}: east and southeast slopes first, south around midday, west in the afternoon${r.win.corn.mush != null ? '; by ' + hh(r.win.corn.mush) + ' it is likely mush, so be off steep sunny slopes' : ''}. Timing shifts with elevation and a cloudy or windy night (no refreeze, no corn).</small>` : ''}${r.win.fuzzy ? '<small class="sk-fuzzy">Timing is approximate: more than 48 hours out, the forecast only gives rain in 6-hour blocks, so the window could shift by a few hours.</small>' : ''}</p>` : ''}
                    <ul class="sk-facts">
                        ${LOW.includes(S.mode) ? `<li><strong>${d.temp_f == null ? '?' : d.temp_f + ' F'}</strong></li>` : ''}<li><strong>${d.new_snow_in == null ? '?' : d.new_snow_in.toFixed(1)} in</strong> new snow${d.new_snow_lo_in != null && d.new_snow_hi_in != null ? ` (${d.new_snow_lo_in.toFixed(1)}&ndash;${d.new_snow_hi_in.toFixed(1)})` : ''}</li><li>snow level <strong>${d.snow_level_ft == null ? '?' : d.snow_level_ft.toLocaleString() + ' ft'}</strong></li>
                        <li>gusts <strong>${d.gust_mph == null ? '?' : d.gust_mph + ' mph'}</strong></li>${LOW.includes(S.mode) ? (d.liquid_in != null ? `<li>precip, past 24 h <strong>${d.liquid_in.toFixed(2)} in</strong></li>` : '') : (r.wet != null ? `<li>wet <strong>${r.wet.toFixed(2)} in</strong></li>` : '')}<li><strong>${r.drive == null ? '?' : r.drive.toFixed(1)} h</strong> drive</li>${d.delay_risk != null ? `<li>pass delay chance <strong>${Math.round(d.delay_risk * 100)}%</strong></li>` : ''}
                        ${LOW.includes(S.mode) ? '' : `<li>about <strong>${Math.round(r.vert).toLocaleString()} ft</strong> of vert</li>`}
                        ${r.z.nwac_zone && !LOW.includes(S.mode) ? `<li>avalanche <strong>${esc(AVY[d.avy_danger] || 'n/a')}</strong></li>` : ''}
                    </ul>
                    <div class="sk-bars" aria-label="score breakdown">${r.parts.map(p => `<div class="sk-bar" title="${esc(p.label)}: ${Math.round(p.s * 100)}% (weight ${p.w})"><span style="height:${Math.round(p.s * 100)}%"></span><em>${esc(SHORT[p.id] || p.label.split(' ')[0])}</em></div>`).join('')}</div>
                    ${r.notes.map(n => `<p class="sk-note">${esc(n)}</p>`).join('')}
                </article>`;
            };
            el.innerHTML = `
            ${data.mock ? '<div class="sk-banner" role="note"><strong>Sample data.</strong> This is a first draft: the numbers below are made up to test the scoring and layout. They are not a forecast and not for planning a trip.</div>'
                : `<div class="sk-banner" role="note"><strong>Beta test.</strong> Snow, snow level, wind, cloud and visibility are the National Blend of Models forecast${data.forecast ? ' (' + cycleLabel(data.forecast.cycle_utc) + ')' : ''} at one point near each area, not corrected for elevation. Avalanche forecasts begin in late November, so backcountry mode has nothing to check yet. Drive times are estimates. It has not yet been checked against what happened; do not use it to plan a trip.</div>`}
            <div class="sk-ctrl">
                <div class="sk-group"><span class="sk-label">Mode</span>${chips(Object.entries(MODES), S.mode, 'mode')}</div>
                <div class="sk-group"><span class="sk-label">Getting wet</span>${chips(Object.entries(WET), S.wet, 'wet')}</div>
                <div class="sk-group"><span class="sk-label">Day</span>${chips(data.zones[0].days.map((d, i) => [i, dayLabel(d.date)]), S.day, 'day')}</div>
                <div class="sk-group"><label class="sk-label" for="sk-origin">Starting from</label>
                    <select id="sk-origin" class="sk-select">${Object.entries(data.origins).map(([k, v]) => `<option value="${k}"${k === S.origin ? ' selected' : ''}>${esc(v)}</option>`).join('')}</select></div>
                ${(data.leave_times || []).length ? `<div class="sk-group"><span class="sk-label">Leaving at</span>${chips(data.leave_times.map(t => [t, clock(t)]), S.leave, 'leave')}</div>` : ''}
                <div class="sk-group"><label class="sk-label" for="sk-drive">Longest drive: <b>${S.maxDrive} h</b></label><input id="sk-drive" type="range" min="1" max="6" step="0.5" value="${S.maxDrive}"></div>
                ${LOW.includes(S.mode) ? '' : `<div class="sk-group"><label class="sk-label" for="sk-elev">Lowest elevation you will ski: <b>${S.minElev.toLocaleString()} ft</b></label><input id="sk-elev" type="range" min="1500" max="6500" step="250" value="${S.minElev}"></div>`}
            </div>
            <details class="sk-weights"><summary>Rank what conditions matter to you</summary>
                <div class="sk-wgrid">${modeCrit.map(c => `<label title="${esc(c.tip)}"><span>${esc(c.label)}</span><input type="range" min="0" max="5" step="1" value="${S.w[c.id]}" data-w="${c.id}"><b>${S.w[c.id]}</b></label>`).join('')}</div>
                <p class="sk-small">Slide to 0 to ignore a factor. Scores are a weighted average of each factor from 0 to 1, so the bars on each card show exactly where its score comes from.</p></details>
            ${ok.length ? `<h2 class="sk-h">Best bets for ${esc(dayLabel(data.zones[0].days[S.day].date))}</h2><div class="sk-list">${ok.map(card).join('')}</div>`
                : `<div class="sk-null"><strong>Nothing fits your criteria today.</strong> Every area was ruled out; the reasons are listed below. ${LOW.includes(S.mode) ? '<br>Stay in town. ' + TOWN_DAY : 'Loosen the drive limit or minimum elevation, or try another day. Not enough snow to ski? Try <button type="button" class="sk-link" data-k="mode" data-v="hike">Hike / run</button> or <button type="button" class="sk-link" data-k="mode" data-v="bike">Bike</button>.'}</div>`}
            ${ok.length && LOW.includes(S.mode) && ok[0].total < STAY_IN_TOWN ? `<div class="sk-null"><strong>Nothing looks great.</strong> The best option scores under ${STAY_IN_TOWN}, so staying in town may be the better day. ${TOWN_DAY}</div>` : ''}
            ${out.length ? `<details class="sk-out" ${ok.length ? '' : 'open'}><summary>Ruled out (${out.length})</summary><ul>${out.map(r => `<li><strong>${esc(r.z.name)}</strong>: ${r.why.map(esc).join('; ')}</li>`).join('')}</ul></details>` : ''}
            <p class="sk-small">&ldquo;Fits your criteria&rdquo; is not &ldquo;safe&rdquo;. Backcountry travel needs the avalanche forecast, your own assessment and the right gear.</p>`;
            el.querySelectorAll('.sk-chip, .sk-link').forEach(b => b.addEventListener('click', () => { S[b.dataset.k] = b.dataset.k === 'day' ? +b.dataset.v : b.dataset.v; render(); }));
            el.querySelector('#sk-origin').addEventListener('change', e => { S.origin = e.target.value; render(); });
            el.querySelector('#sk-drive').addEventListener('input', e => { S.maxDrive = +e.target.value; render(); });
            if (el.querySelector('#sk-elev')) el.querySelector('#sk-elev').addEventListener('input', e => { S.minElev = +e.target.value; render(); });
            el.querySelectorAll('[data-w]').forEach(i => i.addEventListener('input', e => { S.w[i.dataset.w] = +e.target.value; render(); el.querySelector('.sk-weights').open = true; }));
        }
        render();
    }

    const el = document.getElementById('ski-app');
    if (!el) return;
    fetch(BASE + 'data/pass_now.json', { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null).then(j => { LIVE = j; })
        .then(() => fetch(BASE + 'data/ski_features.json', { cache: 'no-cache' }))
        .then(r => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
        .then(d => mount(el, d))
        .catch(() => { el.innerHTML = '<p class="sk-banner">The conditions data could not be loaded right now.</p>'; });
}());
