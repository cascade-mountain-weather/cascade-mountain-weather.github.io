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

    // criteria: id, label, default weight, what a high score means
    const CRIT = [
        { id: 'fresh', label: 'Fresh snow', w: 5, tip: 'New snow in the day window, topping out near 10 inches' },
        { id: 'quality', label: 'Snow quality', w: 3, tip: 'Snow-to-liquid ratio: drier, lighter snow scores higher than heavy Cascade concrete' },
        { id: 'wind', label: 'Calm wind', w: 2, tip: 'Gusts above about 15 mph start to cost points' },
        { id: 'vis', label: 'Visibility and sun', w: 2, tip: 'Visibility and cloud cover' },
        { id: 'vert', label: 'Vertical', w: 2, tip: 'Terrain between your minimum elevation and the top', modes: ['resort', 'backcountry'] },
        { id: 'drive', label: 'Short drive', w: 3, tip: 'Free-flow drive time from your starting city; the more of your limit it uses, the lower the score' },
        { id: 'road', label: 'Road reliability', w: 3, tip: 'Lower chance of a traction or avalanche-control delay on the pass, from how much snow is forecast (based on seven winters of I-90 delays)' },
    ];
    const MODES = { resort: 'Resort', backcountry: 'Backcountry', nordic: 'Nordic' };
    let LIVE = null;      // assets/data/pass_now.json: closures and restrictions right now (scripts/pass_log.py)
    const S = { mode: 'resort', day: 0, origin: 'seattle', maxDrive: 4, minElev: 3500, w: Object.fromEntries(CRIT.map(c => [c.id, c.w])) };

    function score(z, d, S) {
        const why = [];
        const drive = (z.drive_hours || {})[S.origin];
        const lowest = Math.max(S.minElev, z.access_ft || 0);
        const vert = z.top_ft - lowest;
        if (!z.modes.includes(S.mode)) why.push(`Not set up for ${MODES[S.mode].toLowerCase()} here`);
        if (drive == null) why.push('No drive time from this city');
        else if (drive > S.maxDrive) why.push(`${drive.toFixed(1)} h drive is over your ${S.maxDrive} h limit`);
        if (S.mode !== 'nordic' && vert < 600) why.push('Almost no terrain above your minimum elevation');
        if (S.mode === 'backcountry') {
            if (!z.nwac_zone) why.push('No NWAC avalanche forecast covers this area');
            else if (d.avy_danger == null || d.avy_danger < 0) why.push('No avalanche forecast right now');
            else if (d.avy_danger >= 4) why.push(`Avalanche danger ${AVY[d.avy_danger]}`);
        }
        if (d.gate_hold) why.push('The Longmire gate is likely held: avalanche danger High or above closes the Paradise road (NPS winter road rules)');
        const live = S.day === 0 ? liveClosed(z) : null;           // a closure reported right now only counts for today
        if (live) why.push('Road closed right now: ' + live);
        // snow level: rain at your minimum elevation only matters when something is falling
        const raining = d.new_snow_in >= 0.5 && d.snow_level_ft > S.minElev + 1500;
        if (raining && S.mode !== 'nordic') why.push(`Snow level ${d.snow_level_ft.toLocaleString()} ft is well above your ${S.minElev.toLocaleString()} ft minimum`);
        const s = {
            fresh: clamp(d.new_snow_in / 10),
            quality: clamp((d.snow_ratio - 9) / 6),
            wind: 1 - clamp((d.gust_mph - 15) / 35),
            vis: 0.6 * clamp(d.vis_mi / 6) + 0.4 * (1 - d.cloud_pct / 100),
            vert: clamp(vert / 3500),
            drive: drive == null ? 0 : 1 - clamp(drive / S.maxDrive),
            road: 1 - clamp(d.road_risk / 0.5),         // a 50% chance of a delay scores zero
        };
        let num = 0, den = 0;
        const parts = [];
        CRIT.forEach(c => {
            if (c.modes && !c.modes.includes(S.mode)) return;
            const w = S.w[c.id];
            num += w * s[c.id]; den += w;
            parts.push({ id: c.id, label: c.label, s: s[c.id], w });
        });
        const total = den ? 100 * num / den : 0;
        const notes = [];
        if (d.avy_danger === 3) notes.push('Avalanche danger Considerable: be conservative with terrain choices.');
        if (S.mode !== 'backcountry' && d.avy_danger >= 4) notes.push(`Avalanche danger ${AVY[d.avy_danger]} in the mountains; expect slower travel and a higher chance of road control work.`);
        if (d.gust_mph >= 40) notes.push('Strong gusts, expect lift holds or closed upper terrain.');
        if (z.road_risk && z.road_risk.model === 'nps_gate') notes.push('The Paradise road also closes for staffing, snow removal and unsafe road conditions, and in some winters on weekdays. Check the NPS Longmire gate status before you drive.');
        else if (d.delay_risk != null && d.delay_risk >= 0.2) notes.push(`About a ${Math.round(d.delay_risk * 100)}% chance of a traction or avalanche-control delay on ${z.road_risk.route} that day.`);
        return { z, d, drive, vert, total, parts, why, notes };
    }

    // A closure or restriction the log has seen on this zone's road, if the log is fresh (under 4 hours old).
    function liveClosed(z) {
        if (!LIVE || !LIVE.generated_utc || !z.road_risk) return null;
        if ((Date.now() - Date.parse(LIVE.generated_utc.replace(/Z$/, ':00Z'))) > 4 * 3600e3) return null;
        const tags = z.road_risk.tags || [];
        if (z.road_risk.model === 'nps_gate' && LIVE.paradise_gate && LIVE.paradise_gate.open === false) return (LIVE.paradise_gate.status || 'closed').slice(0, 90);
        for (const t of tags) for (const it of (LIVE.passes[t] || [])) if (it.closed) return (it.text || 'closed').slice(0, 90);
        return null;
    }

    function dayLabel(iso) {
        const [y, m, dd] = iso.split('-').map(Number);
        const d = new Date(Date.UTC(y, m - 1, dd));
        return `${WD[d.getUTCDay()]} ${MON[d.getUTCMonth()]} ${d.getUTCDate()}`;
    }

    function mount(el, data) {
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
                        <li><strong>${d.new_snow_in.toFixed(1)} in</strong> new snow</li><li>snow level <strong>${d.snow_level_ft.toLocaleString()} ft</strong></li>
                        <li>gusts <strong>${d.gust_mph} mph</strong></li><li><strong>${r.drive == null ? '?' : r.drive.toFixed(1)} h</strong> drive</li>${d.delay_risk != null ? `<li>pass delay chance <strong>${Math.round(d.delay_risk * 100)}%</strong></li>` : ''}
                        <li>about <strong>${Math.round(r.vert).toLocaleString()} ft</strong> of vert</li>
                        ${r.z.nwac_zone ? `<li>avalanche <strong>${esc(AVY[d.avy_danger] || 'n/a')}</strong></li>` : ''}
                    </ul>
                    <div class="sk-bars" aria-label="score breakdown">${r.parts.map(p => `<div class="sk-bar" title="${esc(p.label)}: ${Math.round(p.s * 100)}% (weight ${p.w})"><span style="height:${Math.round(p.s * 100)}%"></span><em>${esc(p.label.split(' ')[0])}</em></div>`).join('')}</div>
                    ${r.notes.map(n => `<p class="sk-note">${esc(n)}</p>`).join('')}
                    <p class="sk-access">Park at: ${r.z.access_points.filter(p => p.modes.includes(S.mode)).map(p => esc(p.name)).join(', ') || 'see zone page'} &middot; <a href="${esc(r.z.url)}" target="_blank" rel="noopener noreferrer">conditions</a></p>
                </article>`;
            };
            el.innerHTML = `
            <div class="sk-banner" role="note"><strong>Sample data.</strong> This is a first draft: the numbers below are made up to test the scoring and layout. They are not a forecast and not for planning a trip.</div>
            <div class="sk-ctrl">
                <div class="sk-group"><span class="sk-label">Mode</span>${chips(Object.entries(MODES), S.mode, 'mode')}</div>
                <div class="sk-group"><span class="sk-label">Day</span>${chips(data.zones[0].days.map((d, i) => [i, dayLabel(d.date)]), S.day, 'day')}</div>
                <div class="sk-group"><label class="sk-label" for="sk-origin">Starting from</label>
                    <select id="sk-origin" class="sk-select">${Object.entries(data.origins).map(([k, v]) => `<option value="${k}"${k === S.origin ? ' selected' : ''}>${esc(v)}</option>`).join('')}</select></div>
                <div class="sk-group"><label class="sk-label" for="sk-drive">Longest drive: <b>${S.maxDrive} h</b></label><input id="sk-drive" type="range" min="1" max="6" step="0.5" value="${S.maxDrive}"></div>
                <div class="sk-group"><label class="sk-label" for="sk-elev">Lowest elevation you will ski: <b>${S.minElev.toLocaleString()} ft</b></label><input id="sk-elev" type="range" min="1500" max="6500" step="250" value="${S.minElev}"></div>
            </div>
            <details class="sk-weights"><summary>What matters to you</summary>
                <div class="sk-wgrid">${modeCrit.map(c => `<label title="${esc(c.tip)}"><span>${esc(c.label)}</span><input type="range" min="0" max="5" step="1" value="${S.w[c.id]}" data-w="${c.id}"><b>${S.w[c.id]}</b></label>`).join('')}</div>
                <p class="sk-small">Slide to 0 to ignore a factor. Scores are a weighted average of each factor from 0 to 1, so the bars on each card show exactly where its score comes from.</p></details>
            ${ok.length ? `<h2 class="sk-h">Best bets for ${esc(dayLabel(data.zones[0].days[S.day].date))}</h2><div class="sk-list">${ok.map(card).join('')}</div>`
                : `<div class="sk-null"><strong>Nothing fits your criteria today.</strong> Every area was ruled out; the reasons are listed below. Loosen the drive limit or minimum elevation, or try another day.</div>`}
            ${out.length ? `<details class="sk-out" ${ok.length ? '' : 'open'}><summary>Ruled out (${out.length})</summary><ul>${out.map(r => `<li><strong>${esc(r.z.name)}</strong>: ${r.why.map(esc).join('; ')}</li>`).join('')}</ul></details>` : ''}
            <p class="sk-small">&ldquo;Fits your criteria&rdquo; is not &ldquo;safe&rdquo;. Backcountry travel needs the avalanche forecast, your own assessment and the right gear.</p>`;
            el.querySelectorAll('.sk-chip').forEach(b => b.addEventListener('click', () => { S[b.dataset.k] = b.dataset.k === 'day' ? +b.dataset.v : b.dataset.v; render(); }));
            el.querySelector('#sk-origin').addEventListener('change', e => { S.origin = e.target.value; render(); });
            el.querySelector('#sk-drive').addEventListener('input', e => { S.maxDrive = +e.target.value; render(); });
            el.querySelector('#sk-elev').addEventListener('input', e => { S.minElev = +e.target.value; render(); });
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
