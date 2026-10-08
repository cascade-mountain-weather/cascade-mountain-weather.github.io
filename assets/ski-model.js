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
    const COMFORT = { hike: [40, 65], bike: [50, 75] };      // comfortable temperature band, F (a first guess)
    const MAX_TRAIL_SNOW = 4;                // inches on the ground that rule a trail out
    const MAX_TRAIL_NEW = 2;                 // inches of forecast new snow that rule it out
    const STAY_IN_TOWN = 30;                 // best score below this: nothing looks good enough to drive for
    // Rough starting values, to be tuned: the snow on the ground a mode needs, and the months resorts are closed.
    const MIN_BASE = { resort: 20, backcountry: 24, nordic: 12 };
    const CLOSED_MONTHS = [5, 6, 7, 8, 9];          // 0-based: June to October
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

    // 1 inside the comfortable band, falling to 0 twenty degrees outside it
    function comfortScore(t, band) {
        const lo = band[0], hi = band[1];
        return 1 - clamp((t < lo ? lo - t : t > hi ? t - hi : 0) / 20);
    }

    function score(z, d, S) {
        const why = [];
        const timed = ((z.drive_by_time || {})[S.origin] || {})[S.leave];     // typical drive at your leave time, when we have it
        const drive = timed != null ? timed : (z.drive_hours || {})[S.origin];
        const lowest = Math.max(S.minElev, z.access_ft || 0);
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
        if (wet != null && wet >= 0.05 && S.wet !== 'dry') notes.push(`About ${wet.toFixed(2)} in of rain or wet snow likely while you are out` + (d.temp_f != null && Math.abs(d.temp_f - 34) < 5 ? ' (near freezing, so expect wet snow or slush)' : '') + '.');
        if (d.gust_mph != null && d.gust_mph >= 40) notes.push('Strong gusts, expect lift holds or closed upper terrain.');
        if (z.road_risk && z.road_risk.model === 'nps_gate') notes.push('The Paradise road also closes for staffing, snow removal and unsafe road conditions, and in some winters on weekdays. Check the NPS Longmire gate status before you drive.');
        else if (d.delay_risk != null && d.delay_risk >= 0.2) notes.push(`About a ${Math.round(d.delay_risk * 100)}% chance of a traction or avalanche-control delay on the way` + (d.risk_parts && d.risk_parts.length > 1 ? ' (' + d.risk_parts.map(p => p.route.replace(/ (Snoqualmie|Stevens|White|Blewett) Pass| North Cascades Highway/, '') + ' ' + Math.round(p.p * 100) + '%').join(', ') + ')' : ' on ' + z.road_risk.route) + ' that day.');
        return { z, d, drive, vert, total, parts, why, notes, wet };
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
                    <ul class="sk-facts">
                        ${LOW.includes(S.mode) ? `<li><strong>${d.temp_f == null ? '?' : d.temp_f + ' F'}</strong></li>` : ''}<li><strong>${d.new_snow_in == null ? '?' : d.new_snow_in.toFixed(1)} in</strong> new snow${d.new_snow_lo_in != null && d.new_snow_hi_in != null ? ` (${d.new_snow_lo_in.toFixed(1)}&ndash;${d.new_snow_hi_in.toFixed(1)})` : ''}</li><li>snow level <strong>${d.snow_level_ft == null ? '?' : d.snow_level_ft.toLocaleString() + ' ft'}</strong></li>
                        <li>gusts <strong>${d.gust_mph == null ? '?' : d.gust_mph + ' mph'}</strong></li>${r.wet != null ? `<li>wet <strong>${r.wet.toFixed(2)} in</strong></li>` : ''}<li><strong>${r.drive == null ? '?' : r.drive.toFixed(1)} h</strong> drive</li>${d.delay_risk != null ? `<li>pass delay chance <strong>${Math.round(d.delay_risk * 100)}%</strong></li>` : ''}
                        ${LOW.includes(S.mode) ? '' : `<li>about <strong>${Math.round(r.vert).toLocaleString()} ft</strong> of vert</li>`}
                        ${r.z.nwac_zone && !LOW.includes(S.mode) ? `<li>avalanche <strong>${esc(AVY[d.avy_danger] || 'n/a')}</strong></li>` : ''}
                    </ul>
                    <div class="sk-bars" aria-label="score breakdown">${r.parts.map(p => `<div class="sk-bar" title="${esc(p.label)}: ${Math.round(p.s * 100)}% (weight ${p.w})"><span style="height:${Math.round(p.s * 100)}%"></span><em>${esc(SHORT[p.id] || p.label.split(' ')[0])}</em></div>`).join('')}</div>
                    ${r.notes.map(n => `<p class="sk-note">${esc(n)}</p>`).join('')}
                    <p class="sk-access">Park at: ${r.z.access_points.filter(p => p.modes.includes(S.mode)).map(p => esc(p.name)).join(', ') || 'see zone page'} &middot; <a href="${esc(r.z.url)}" target="_blank" rel="noopener noreferrer">conditions</a></p>
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
            <details class="sk-weights"><summary>What matters to you</summary>
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
