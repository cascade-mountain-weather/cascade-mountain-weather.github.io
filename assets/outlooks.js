// Long-term outlook pages: ECMWF sub-seasonal (extended range) and seasonal (SEAS5) charts, for comparing products.
// Data: assets/data/outlook_links.json, written daily by scripts/outlook_links.py (the image addresses; the images load
// straight from ECMWF, CC BY 4.0). Mount points: <div class="ol-mount" data-kind="extended|seasonal"></div>.
// Two views: "compare products" (pick a week or season, see precipitation, temperature and 500 hPa side by side) and
// "compare weeks/seasons" (pick a product, see every week or season next to each other).
(function () {
    'use strict';
    const BASE = (document.currentScript && document.currentScript.src || '').replace(/[^/]*$/, '');
    const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    const dt = s => new Date(s);
    const md = d => `${MON[d.getUTCMonth()]} ${d.getUTCDate()}`;

    // What each chart shows, in plain language. Written from the charts themselves and ECMWF's descriptions.
    const HOW = {
        extended: {
            precip: 'Shading is how the week&rsquo;s total precipitation differs from the model&rsquo;s climatological median, in mm: browns drier, greens wetter. Contours show how spread out the ensemble members are: green means they agree, purple means they do not.',
            temp: 'Shading is the weekly average temperature compared with the model&rsquo;s climatological median, in &deg;C: blues colder, reds warmer. Contours are the same ensemble-spread measure.',
            z500: 'The weekly average height of the 500 hPa surface compared with normal. A ridge (higher than normal) tends to bring dry, mild weather to the Northwest; a trough (lower) tends to bring cooler, wetter weather.',
        },
        seasonal: {
            t850: 'The chance that the three-month average temperature at about 5,000 ft (850 hPa) falls in its most likely third (tercile) of the 1993&ndash;2016 climate. Reds favor warmer than normal, blues colder, white means no clear signal. The map is global; click it to zoom in on the Pacific Northwest.',
            rain: 'The same idea for precipitation: the chance the three-month total falls in its most likely category. See the legend on the chart for which colors mean wetter and which drier.',
            z500: 'The three-month average pattern of 500 hPa heights. Ridges and troughs steer the storm track, so a persistent trough near the coast favors a wetter, cooler Northwest.',
        },
    };
    const WARN = {
        extended: 'ECMWF labels these extended-range weekly maps experimental. Skill falls off quickly after week 2, so read them as shifts in the odds, not a forecast.',
        seasonal: 'Seasonal forecasts say little about any one storm. They can tilt the odds for a whole season; they cannot say when the snow will fall.',
    };

    // Frame labels
    function weekLabel(base, f) {
        const end = dt(f.valid), start = new Date(end.getTime() - 7 * 864e5);
        const lead = Math.max(1, Math.ceil((end - dt(base)) / (7 * 864e5)));
        return { short: `Week ${lead}`, long: `${md(start)}–${md(end)}` };
    }
    function seasonLabel(f) {
        const m = dt(f.valid).getUTCMonth(), ms = [0, 1, 2].map(k => (m + k) % 12), y = dt(f.valid).getUTCFullYear();
        const initials = ms.map(k => 'JFMAMJJASOND'[k]).join('');
        return { short: initials, long: `${MON[ms[0]]}–${MON[ms[2]]} ${y}${ms[2] < ms[0] ? '/' + String((y + 1) % 100).padStart(2, '0') : ''}` };
    }
    const runLabel = (base, noun) => {
        const d = dt(base);
        return `${noun} run of ${WD[d.getUTCDay()]} ${md(d)}, ${String(d.getUTCHours()).padStart(2, '0')}Z (UTC).`;
    };

    function mount(el, data, kind) {
        const grp = data[kind];
        const pids = Object.keys((grp && grp.products) || {});
        if (!grp || !pids.length) { el.innerHTML = '<p class="ol-fail">No charts are available right now.</p>'; return; }
        const label = kind === 'extended' ? weekLabel.bind(null, grp.base_time) : seasonLabel;
        const unit = kind === 'extended' ? 'Week' : 'Season';
        const frames = grp.products[pids[0]].frames;                  // the same valid times for every product
        const S = { view: 'time', i: 0, product: pids[0] };
        const hasFrame = (pid, valid) => (grp.products[pid].frames.find(f => f.valid === valid) || null);

        function figure(pid, f, cap) {
            return `<figure class="ol-fig"><img class="PlotFormat" loading="lazy" src="${esc(f.url)}" alt="${esc(grp.products[pid].label + ', ' + cap + ': ' + (f.desc || ''))}">
                <figcaption><strong>${esc(grp.products[pid].label)}</strong> &middot; ${esc(cap)}<span class="ol-how">${HOW[kind][pid] || ''}</span></figcaption></figure>`;
        }

        function render() {
            const chips = (name, items, cur) => `<div class="ol-chips" role="radiogroup" aria-label="${name}">${items.map(it =>
                `<button type="button" class="ol-chip" role="radio" aria-checked="${it.id === cur}" data-id="${esc(it.id)}">${it.html}</button>`).join('')}</div>`;
            let pick, figs;
            if (S.view === 'time') {
                const f = frames[S.i];
                pick = `<div class="ol-group"><span class="ol-label">${unit}</span>${chips(unit, frames.map((fr, k) => ({ id: String(k), html: `${esc(label(fr).short)}<span style="font-weight:400"> &middot; ${esc(label(fr).long)}</span>` })), String(S.i))}</div>`;
                figs = `<div class="ol-figs">${pids.map(pid => { const fr = hasFrame(pid, f.valid); return fr ? figure(pid, fr, `${label(f).short}, ${label(f).long}`) : ''; }).join('')}</div>`;
            } else {
                pick = `<div class="ol-group"><span class="ol-label">Product</span>${chips('Product', pids.map(pid => ({ id: pid, html: esc(grp.products[pid].label) })), S.product)}</div>`;
                figs = `<div class="ol-figs">${grp.products[S.product].frames.map(fr => figure(S.product, fr, `${label(fr).short}, ${label(fr).long}`)).join('')}</div>`;
            }
            const viewSel = `<div class="ol-group"><label class="ol-label" for="${kind}-view">View</label><select class="ol-select" id="${kind}-view">
                <option value="time"${S.view === 'time' ? ' selected' : ''}>Compare products (pick a ${unit.toLowerCase()})</option>
                <option value="product"${S.view === 'product' ? ' selected' : ''}>Compare ${unit.toLowerCase()}s (pick a product)</option></select></div>`;
            el.innerHTML = `<div class="ol"><div class="ol-ctrl">${viewSel}${pick}</div>
                <p class="ol-run">${esc(runLabel(grp.base_time, kind === 'extended' ? 'ECMWF extended-range' : 'ECMWF SEAS5'))} ${WARN[kind]}</p>${figs}
                <p class="ol-credit">Charts: &copy; ECMWF, <a href="${esc(data.licence_url)}" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>. Click a chart to enlarge it.</p></div>`;
            if (window.CMWLightbox) el.querySelectorAll('img.PlotFormat').forEach(i => window.CMWLightbox.bind(i));
            el.querySelector('select').addEventListener('change', e => { S.view = e.target.value; render(); });
            el.querySelectorAll('.ol-chip').forEach(b => b.addEventListener('click', () => {
                if (S.view === 'time') S.i = +b.dataset.id; else S.product = b.dataset.id;
                render();
                const nb = el.querySelector('.ol-chip[aria-checked="true"]'); if (nb) nb.focus();
            }));
        }
        render();
    }

    // Weather regime figures: saved each Wednesday by scripts/fetch_subseasonal.py into assets/data/subseasonal/ (manifest.json lists them).
    const REGIME_GROUPS = [
        { title: 'Regime forecast (CFSv2, IRI)', ids: ['cfs_regimes'], more: ['wr_precip', 'wr_temp'], moreTitle: 'What each regime means: precipitation and temperature maps', how: {
            cfs_regimes: 'Each column is a day being forecast and each row is how many days ahead the forecast was made. Colors show which of four large-scale patterns the 48-member CFSv2 ensemble favors (Pacific Ridge, Pacific Trough, Greenland High, West Coast Ridge); darker means more members agree. Read up a column to see how the forecast for one day changes as it gets closer. A Pacific Trough is the stormy, wetter pattern for the Northwest; a West Coast Ridge is the dry, mild one.',
            wr_precip: 'What each regime tends to do to precipitation: the average departure from normal when that regime is in place (browns drier, greens wetter).',
            wr_temp: 'The same for temperature: the average departure from normal when each regime is in place.' } },
        { title: 'West Coast weather patterns (CW3E)', ids: ['wc_precip', 'wc_temp'], how: {
            wc_precip: 'Each column is one of 16 weather regimes (WR1 to WR16). The small maps on top show the typical precipitation anomaly when that regime occurs, and the shading below is the NCEP ensemble probability of that regime in each week, so a dark block in a column means that regime is likely that week. Match the likely regimes to their maps to see whether the week leans wet or dry.',
            wc_temp: 'The same weather regimes with the typical temperature anomaly on top and the weekly probability of each regime below.' } },
    ];
    function mountRegimes(el) {
        fetch(BASE + 'data/subseasonal/manifest.json', { cache: 'no-cache' })
            .then(r => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
            .then(m => {
                const byId = {}; (m.figures || []).forEach(f => { byId[f.id] = f; });
                const upd = m.updated ? dt(m.updated.replace('Z', ':00Z')) : null;
                const fig = (id, g) => {
                    const f = byId[id];
                    return `<figure class="ol-fig"><img class="PlotFormat" loading="lazy" src="${esc(BASE + 'data/subseasonal/' + f.file + '?v=' + (f.sha256 || '').slice(0, 8))}" alt="${esc(f.title)}">
                        <figcaption><strong>${esc(f.title)}</strong> &middot; ${esc(f.source)}<span class="ol-how">${g.how[id] || ''}</span></figcaption></figure>`;
                };
                el.innerHTML = REGIME_GROUPS.map(g => `<h3>${esc(g.title)}</h3><div class="ol-figs" style="grid-template-columns:1fr">${g.ids.filter(id => byId[id]).map(id => fig(id, g)).join('')}</div>`
                    + (g.more && g.more.some(id => byId[id]) ? `<details class="ol-more"><summary>${esc(g.moreTitle)}</summary><div class="ol-figs" style="grid-template-columns:1fr">${g.more.filter(id => byId[id]).map(id => fig(id, g)).join('')}</div></details>` : '')).join('')
                    + `<p class="ol-credit">Figures are saved every Wednesday${upd ? ` (last checked ${md(upd)})` : ''}; the models behind them update on their own schedules, so the date printed on each figure is the one that counts. Click a figure to enlarge it.</p>`;
                if (window.CMWLightbox) el.querySelectorAll('img.PlotFormat').forEach(i => window.CMWLightbox.bind(i));
            })
            .catch(() => { el.innerHTML = '<p class="ol-fail">The weather regime figures could not be loaded right now.</p>'; });
    }

    // Single ECMWF charts (the MJO forecast and the PNA outlook) dropped into an existing figure grid on the Teleconnections
    // page: <figure class="ol-slot" data-index="mjo|pna" data-caption="..."></figure>. The chart address comes from the same JSON.
    function fillSlots(data) {
        document.querySelectorAll('[data-index]').forEach(el => {
            const it = ((data && data.indices) || {})[el.dataset.index];
            if (!it) { el.hidden = true; return; }
            const d = dt(it.base_time);
            el.innerHTML = `<img class="PlotFormat" loading="lazy" src="${esc(it.url)}" alt="${esc(it.label)}">
                <figcaption><strong>${esc(it.label)}</strong>${el.dataset.caption ? ' &middot; ' + esc(el.dataset.caption) : ''}
                <span class="ol-how">${esc(runLabel(it.base_time, 'ECMWF'))} &copy; ECMWF, CC BY 4.0.</span></figcaption>`;
            if (window.CMWLightbox) window.CMWLightbox.bind(el.querySelector('img'));
        });
    }

    document.querySelectorAll('.ol-regimes').forEach(mountRegimes);
    const mounts = document.querySelectorAll('.ol-mount');
    const slots = document.querySelectorAll('[data-index]');
    if (!mounts.length && !slots.length) return;
    fetch(BASE + 'data/outlook_links.json', { cache: 'no-cache' })
        .then(r => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
        .then(data => { mounts.forEach(el => mount(el, data, el.dataset.kind)); fillSlots(data); })
        .catch(() => { slots.forEach(el => { el.hidden = true; }); mounts.forEach(el => { el.innerHTML = '<p class="ol-fail">The ECMWF charts could not be loaded right now. You can still see them at <a href="https://charts.ecmwf.int/" target="_blank" rel="noopener noreferrer">charts.ecmwf.int</a>.</p>'; }); });
}());
