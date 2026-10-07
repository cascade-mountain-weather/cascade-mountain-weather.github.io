// Forecast evaluation page. Plain DOM and SVG (no chart library); the map uses Leaflet.
// Data: assets/data/evaluation.json, built by scripts/build_evaluation_json.py from the scored weekends.
// Statistics are computed here from the records, so a new product (HRRR, HRDPS) only needs a new field on
// each record and an entry in `products`. A season selector filters everything on the page.
//
// What is scored: the weekend snowfall total for each area. A product gives a middle value (NBM median, the
// middle of our range, or a single model value) and, for the range products, a low-high range. The "truth" is
// an estimate from SNOTEL stations and is itself a range (new-snow density is unknown), so it is drawn as a
// band and only its midpoint is used for errors and hits.
//
// Two ways to compare: the weekend total (NBM and our forecast), or Friday only, which adds HRRR and HRDPS. Those
// two models run 48 hours, so they cannot give a weekend total; Friday (day 1) is the window they all cover.

(function () {
    'use strict';

    const root = document.getElementById('eval');
    if (!root) return;
    const $ = id => document.getElementById(id);
    const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    const SLACK = 0.5;            // a hit allows half an inch either side of the range
    const DASH = '–';
    const COLORS = { nbm: '#2a5298', ours: '#d97706', hrrr: '#0d9488', hrdps: '#7c3aed' };
    const SCALE = ['#b2182b', '#e5694d', '#f2b79a', '#cfd6dd', '#9ec8e2', '#4a90c4', '#2166ac'];   // red .. grey .. blue
    const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
    function diverging(s) {   // s in [-1, 1]; +1 is blue, -1 is red
        const x = (Math.max(-1, Math.min(1, s)) + 1) / 2 * (SCALE.length - 1);
        const i = Math.min(SCALE.length - 2, Math.floor(x)), a = hex(SCALE[i]), b = hex(SCALE[i + 1]), t = x - i;
        return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * t)).join(',')})`;
    }
    function sequential(t) {  // 0 light .. 1 dark blue
        const a = [238, 242, 251], b = [30, 60, 114], c = Math.max(0, Math.min(1, t));
        return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * c)).join(',')})`;
    }

    const fmt = (v, nd) => (v === null || v === undefined || Number.isNaN(v) ? DASH : v.toFixed(nd === undefined ? 1 : nd));
    const signed = (v, nd) => (v === null || v === undefined || Number.isNaN(v) ? DASH : `${v > 0 ? '+' : ''}${v.toFixed(nd === undefined ? 1 : nd)}`);
    const pct = v => (v === null || v === undefined ? DASH : `${Math.round(v * 100)}%`);
    const mean = xs => (xs.length ? xs.reduce((p, q) => p + q, 0) / xs.length : null);

    let RAW = null;     // everything in the file
    let D = null;       // the selected season's weekends, records and soundings (weekend indexes renumbered)
    const POINT = ['hrrr', 'hrdps'];   // single-valued model products
    const S = { season: null, win: 'total', area: 'ALL', metric: 'mae', mapProduct: 'nbm', axis: 'sqrt', view: 'values', show: { nbm: true, ours: true, hrrr: true, hrdps: true },
        weekend: null, threshold: 6, snowSite: 'ALL' };

    // ---- seasons ------------------------------------------------------------------------------

    function buildView(id) {
        const idx = {}, wk = [];
        RAW.weekends.forEach((w, i) => { if (w.season === id) { idx[i] = wk.length; wk.push(w); } });
        const keep = r => idx[r.w] !== undefined;
        const renum = r => Object.assign({}, r, { w: idx[r.w] });
        // A single-window view: each record becomes the values for that window. Friday is day 1 (observed, NBM, HRRR, HRDPS, and
        // ours when a day-level forecast was saved); the 12-hour periods carry observed and NBM (and HRRR/HRDPS where archived).
        const winRec = r => {
            const d = S.win === 'day1' ? (r.days && r.days.day1) : (r.periods && r.periods[S.win]);
            if (!d || !d.obs) return null;
            return { w: r.w, a: r.a, obs: d.obs, nbm: d.nbm || null, ours: d.ours || null, hrrr: d.hrrr, hrdps: d.hrdps, coco: d.coco || null, days: r.days, periods: r.periods };
        };
        let recs = RAW.records.filter(keep).map(renum);
        if (S.win !== 'total') recs = recs.map(winRec).filter(Boolean);
        return Object.assign({}, RAW, { weekends: wk, records: recs, snow_level: RAW.snow_level.filter(keep).map(renum) });
    }

    // ---- statistics ---------------------------------------------------------------------------

    // One product's forecast for a record: { lo, mid, hi, obs: [low, mid, high] }, or null when it has none.
    function value(pid, r) {
        const o = pid === 'ours' ? (r.obs_ours || r.obs) : r.obs;   // our forecast is scored over our own period
        if (!o) return null;
        if (pid === 'nbm') return r.nbm ? { lo: r.nbm[0], mid: r.nbm[1], hi: r.nbm[2], obs: o } : null;
        if (pid === 'ours') return r.ours ? { lo: r.ours[0], mid: (r.ours[0] + r.ours[1]) / 2, hi: r.ours[1], obs: o } : null;
        const x = r[pid];                                           // a single-valued product (HRRR, HRDPS)
        return typeof x === 'number' ? { lo: x, mid: x, hi: x, obs: o } : null;
    }

    const isPeriod = () => S.win !== 'total' && S.win !== 'day1';
    // Name of the window being compared, for captions. A period is day (12Z-0Z) or night (0Z-12Z).
    function winName() {
        if (S.win === 'total') return 'weekend total';
        if (S.win === 'day1') return 'Friday';
        const p = ((RAW && RAW.periods) || []).find(x => x.id === S.win);
        return p ? p.label.toLowerCase() : S.win;
    }
    function winCaption() {
        if (S.win === 'total') return 'Weekend total.';
        if (S.win === 'day1') return 'Friday only (Friday 4 am to Saturday 4 am Pacific).';
        const night = /night$/.test(S.win);
        return `${winName().replace(/^./, c => c.toUpperCase())} (${night ? '0Z to 12Z, about 4 pm to 4 am' : '12Z to 0Z, about 4 am to 4 pm'} Pacific). NBM values for 12-hour periods are approximate: the NBM has no 12-hour window, so each is built from two 6-hour windows.`;
    }

    const inArea = (r, area) => area === 'ALL' || r.a === area;

    function items(pid, area) {
        const out = [];
        D.records.forEach(r => {
            if (!inArea(r, area)) return;
            const v = value(pid, r);
            if (!v) return;
            const err = v.mid - v.obs[1];
            out.push({ w: r.w, a: r.a, err, abs: Math.abs(err), hit: v.obs[1] >= v.lo - SLACK && v.obs[1] <= v.hi + SLACK, width: v.hi - v.lo });
        });
        return out;
    }

    function metrics(its) {
        return { n: its.length, bias: mean(its.map(i => i.err)), mae: mean(its.map(i => i.abs)), hit: mean(its.map(i => (i.hit ? 1 : 0))), width: mean(its.map(i => i.width)) };
    }

    const available = () => D.products.filter(p => p.available && D.records.some(r => value(p.id, r)));

    // ---- trackers -----------------------------------------------------------------------------

    function renderTrackers() {
        const live = available();
        // rank on the weekends where every live product has a forecast
        let common = null;
        live.forEach(p => { const ks = new Set(items(p.id, S.area).map(i => `${i.w}|${i.a}`)); common = common ? new Set([...common].filter(k => ks.has(k))) : ks; });
        const maeOn = pid => mean(items(pid, S.area).filter(i => common && common.has(`${i.w}|${i.a}`)).map(i => i.abs));
        const ranked = live.map(p => ({ id: p.id, mae: maeOn(p.id) })).sort((a, b) => a.mae - b.mae);

        $('eval-trackers').innerHTML = D.products.map(p => {
            if (!live.some(l => l.id === p.id)) {
                const why = POINT.includes(p.id) ? (S.win === 'total' ? 'Choose the Friday view to compare' : isPeriod() ? 'Not archived for 12-hour periods yet' : p.id === 'hrdps' ? 'Not archived: starts when the 2026&ndash;27 forecasts begin' : 'No data for this season yet')
                    : p.id === 'ours' && S.win !== 'total' ? (isPeriod() ? 'Our forecast is the weekend total only' : 'No day-level forecast saved yet') : 'Coming soon';
                return `<div class="eval-card eval-card--off"><h4>${esc(p.label)}</h4><div class="eval-note">${why}</div></div>`;
            }
            const m = metrics(items(p.id, S.area)), rank = ranked.findIndex(r => r.id === p.id);
            return `<div class="eval-card">
                <h4><span><span style="color:${COLORS[p.id] || '#1e3c72'}">&#9632;</span>&nbsp;${esc(p.label)}</span>${live.length > 1 && rank >= 0 ? `<span class="eval-rank">${rank + 1} of ${live.length}</span>` : ''}</h4>
                <div class="eval-big">${fmt(m.mae)} <small>in typical error</small></div>
                <ul class="eval-lines">
                    <li>Bias ${signed(m.bias)} in</li>
                    <li>Observed value inside the range ${pct(m.hit)}</li>
                    <li class="eval-ci">${m.n} area-weekends</li>
                </ul></div>`;
        }).join('');
    }

    // ---- heatmap and map ----------------------------------------------------------------------

    const areasNS = () => RAW.areas.slice().sort((a, b) => (b.lat || 0) - (a.lat || 0));

    function cellValue(m) { return S.metric === 'mae' ? m.mae : S.metric === 'bias' ? m.bias : m.hit; }
    function cellText(v) { return S.metric === 'hit' ? pct(v) : S.metric === 'bias' ? signed(v) : fmt(v); }
    function cellColor(v, caps) {
        if (v === null || v === undefined) return { bg: '#f1f5f9', fg: '#94a3b8' };
        if (S.metric === 'bias') return { bg: diverging(-v / caps.bias), fg: '#0f172a' };
        const t = S.metric === 'mae' ? v / caps.mae : v;
        return { bg: sequential(t), fg: t > 0.55 ? '#fff' : '#0f172a' };
    }

    function heatData() {
        const prods = available(), areas = areasNS();
        const grid = areas.map(a => ({ area: a.id, cells: prods.map(p => metrics(items(p.id, a.id))) }));
        const all = { area: 'ALL', cells: prods.map(p => metrics(items(p.id, 'ALL'))) };
        const flat = grid.flatMap(r => r.cells).concat(all.cells);
        const caps = { mae: Math.max(0.1, ...flat.map(m => m.mae || 0)), bias: Math.max(0.1, ...flat.map(m => Math.abs(m.bias || 0))) };
        return { prods, grid, all, caps };
    }

    function renderHeat() {
        const h = heatData();
        const row = (r, label, cls) => `<tr class="${cls}${S.area === r.area ? ' is-selected' : ''}" data-area="${esc(r.area)}"><th scope="row">${esc(label)}</th>${r.cells.map(m => {
            const v = cellValue(m), c = cellColor(v, h.caps);
            return `<td style="background:${c.bg};color:${c.fg}" title="${esc(`${label}: ${m.n} weekends`)}">${cellText(v)}<small>n=${m.n}</small></td>`;
        }).join('')}</tr>`;
        $('eval-heat').innerHTML = `<table><thead><tr><th></th>${h.prods.map(p => `<th>${esc(p.label)}</th>`).join('')}</tr></thead><tbody>${
            h.grid.map(r => row(r, r.area, '')).join('')}${row(h.all, 'All areas', 'is-all')}</tbody></table>
            <p class="eval-sub">${S.metric === 'mae' ? 'Lower is better.' : S.metric === 'bias' ? 'Blue = forecast too low, red = too high.' : 'Higher is better.'} Click a row to pick an area.</p>`;
        updateMap(h);
    }

    let map = null;
    const markers = {};
    function initMap() {
        const pts = RAW.areas.filter(a => typeof a.lat === 'number');
        if (!window.L || !pts.length) { $('eval-map').parentNode.hidden = true; return; }
        map = L.map('eval-map', { scrollWheelZoom: false, dragging: true, maxZoom: 12 }).setView([47.5, -121.6], 7);
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', { attribution: 'Tiles &copy; Esri', maxZoom: 12 }).addTo(map);
        const coarse = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
        pts.forEach(a => {
            const m = L.circleMarker([a.lat, a.lon], { radius: coarse ? 12 : 10, weight: 1.5, color: '#334155', fillColor: '#e2e8f0', fillOpacity: 0.95 }).addTo(map);
            m.on('click', () => setArea(a.id));
            markers[a.id] = m;
        });
        map.fitBounds(L.latLngBounds(pts.map(a => [a.lat, a.lon])).pad(0.2));
    }

    function updateMap(h) {
        if (!map) return;
        const pi = Math.max(0, h.prods.findIndex(p => p.id === S.mapProduct));
        const label = h.prods[pi] ? h.prods[pi].label : '';
        h.grid.forEach(r => {
            const m = markers[r.area];
            if (!m) return;
            const cm = r.cells[pi] || { n: 0 }, v = cellValue(cm), c = cellColor(v, h.caps);
            m.setStyle({ fillColor: c.bg, weight: S.area === r.area ? 3.5 : 1.5, color: S.area === r.area ? '#0f172a' : '#334155' });
            m.unbindTooltip();
            m.bindTooltip(`<strong>${esc(r.area)}</strong><br>${esc(label)}: ${esc(cellText(v))}<br>${cm.n} weekends`, { direction: 'top', offset: [0, -8] });
        });
        const [l, r] = S.metric === 'bias' ? ['Too low', 'Too high'] : S.metric === 'mae' ? ['Small error', `Large (${fmt(h.caps.mae)} in)`] : ['0%', '100%'];
        const ordered = S.metric === 'bias' ? SCALE.slice().reverse() : [0, 0.25, 0.5, 0.75, 1].map(sequential);   // blue (too low) on the left, red on the right
        $('eval-maplegend').innerHTML = `<div class="eval-legend-bar" style="background:linear-gradient(to right,${ordered.join(',')})"></div><div class="eval-legend-labels"><span>${l}</span><span>${r}</span></div>`;
    }

    // ---- weekend plot -------------------------------------------------------------------------

    const avg3 = list => (list.length ? [0, 1, 2].map(k => mean(list.map(x => x[k]))) : null);

    function plotRows(area) {
        return D.weekends.map((wk, i) => {
            const recs = D.records.filter(r => r.w === i && inArea(r, area));
            if (!recs.length) return { i, wk, none: true };
            const obs = avg3(recs.filter(r => r.obs).map(r => r.obs));
            const obsOurs = avg3(recs.filter(r => r.obs_ours).map(r => r.obs_ours)) || obs;
            const nbm = avg3(recs.filter(r => r.nbm).map(r => r.nbm));
            const withOurs = recs.filter(r => r.ours);
            const ours = withOurs.length ? avg3(withOurs.map(r => [r.ours[0], (r.ours[0] + r.ours[1]) / 2, r.ours[1]])) : null;
            const point = {};
            POINT.forEach(pid => { const vs = recs.map(r => r[pid]).filter(v => typeof v === 'number'); if (vs.length) point[pid] = [mean(vs), mean(vs), mean(vs)]; });
            return Object.assign({ i, wk, obs, obsOurs, nbm, ours }, point);
        });
    }

    const sq = v => Math.sign(v) * Math.sqrt(Math.abs(v));
    function niceTicks(maxV, axis) {
        if (axis === 'sqrt') return [0, 1, 4, 9, 16, 25, 36, 49, 64, 81, 100].filter(t => t <= maxV * 1.001 || t === 0);
        const step = maxV <= 8 ? 2 : maxV <= 20 ? 5 : maxV <= 50 ? 10 : 20;
        const out = [];
        for (let t = 0; t <= maxV + 1e-9; t += step) out.push(t);
        return out;
    }

    function renderPlot() {
        const rows = plotRows(S.area), n = rows.length;
        const W = 920, H = 360, PL = 46, PR = 10, PT = 16, PB = 40, pw = W - PL - PR, ph = H - PT - PB, cw = pw / Math.max(1, n);
        const T = S.axis === 'sqrt' ? sq : (v => v);
        const err = S.view === 'error';

        let top = 1;
        rows.forEach(r => {
            if (r.none) return;
            [r.obs && r.obs[2], r.nbm && r.nbm[2], r.ours && r.ours[2], r.hrrr && r.hrrr[2], r.hrdps && r.hrdps[2]].forEach(v => { if (v) top = Math.max(top, v); });
        });
        let eAbs = 1;
        if (err) rows.forEach(r => {
            if (r.none || !r.obs) return;
            [['nbm', r.obs], ['ours', r.obsOurs], ['hrrr', r.obs], ['hrdps', r.obs]].forEach(([pid, o]) => {
                const f = r[pid]; if (!f || !o) return;
                [f[0] - o[1], f[2] - o[1], o[0] - o[1], o[2] - o[1]].forEach(v => { eAbs = Math.max(eAbs, Math.abs(v)); });
            });
        });
        const lim = err ? eAbs * 1.05 : top * 1.05;
        const yMin = err ? -T(lim) : 0, yMax = T(lim);
        const y = v => PT + (yMax - T(v)) / (yMax - yMin) * ph;
        const ticks = niceTicks(lim, S.axis).flatMap(t => (err && t > 0 ? [t, -t] : [t]));

        let g = ticks.map(t => `<line x1="${PL}" x2="${W - PR}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}" class="${err && t === 0 ? 'ep-zero' : 'ep-grid'}"/>` +
            `<text x="${PL - 6}" y="${(y(t) + 3.5).toFixed(1)}" text-anchor="end" class="ep-axis">${err && t > 0 ? '+' : ''}${t}</text>`).join('');
        g += `<text transform="translate(12 ${PT + ph / 2}) rotate(-90)" text-anchor="middle" class="ep-axis">${err ? 'Forecast minus observed (inches)' : 'Snowfall (inches)'}</text>`;

        rows.forEach(r => {
            const cx = PL + (r.i + 0.5) * cw, bw = cw * 0.62;
            const label = r.wk.id.slice(5).replace('-', '/').replace(/^0/, '').replace('/0', '/');
            g += `<text x="${cx.toFixed(1)}" y="${H - PB + 15}" text-anchor="middle" class="ep-axis">${label}</text>`;
            const tip = r.none ? `${r.wk.label}: no data` : `${r.wk.label}\nObserved ${fmt(r.obs && r.obs[1])} in (${fmt(r.obs && r.obs[0])}–${fmt(r.obs && r.obs[2])})` +
                `${r.nbm ? `\nNBM ${fmt(r.nbm[1])} in (${fmt(r.nbm[0])}–${fmt(r.nbm[2])})` : ''}${r.ours ? `\nOurs ${fmt(r.ours[1])} in (${fmt(r.ours[0])}–${fmt(r.ours[2])})` : ''}${r.hrrr ? `\nHRRR ${fmt(r.hrrr[1])} in` : ''}${r.hrdps ? `\nHRDPS ${fmt(r.hrdps[1])} in` : ''}`;
            g += `<rect class="ep-col${S.weekend === r.i ? ' is-sel' : ''}" data-i="${r.i}" x="${(cx - cw / 2).toFixed(1)}" y="${PT}" width="${cw.toFixed(1)}" height="${ph}"><title>${esc(tip)}</title></rect>`;
            if (r.none || !r.obs) return;

            const o = r.obs;   // the observed band
            if (err) g += `<rect class="ep-obs" x="${(cx - bw / 2).toFixed(1)}" y="${y(o[2] - o[1]).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(1, y(o[0] - o[1]) - y(o[2] - o[1])).toFixed(1)}"/>`;
            else g += `<rect class="ep-obs" x="${(cx - bw / 2).toFixed(1)}" y="${y(o[2]).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(1, y(o[0]) - y(o[2])).toFixed(1)}"/>` +
                `<line class="ep-obsmid" x1="${(cx - bw / 2).toFixed(1)}" x2="${(cx + bw / 2).toFixed(1)}" y1="${y(o[1]).toFixed(1)}" y2="${y(o[1]).toFixed(1)}"/>`;

            const shown = ['nbm', 'ours', 'hrrr', 'hrdps'].filter(pid => S.show[pid] && r[pid]);   // forecasts, side by side
            shown.forEach((pid, k) => {
                const f = r[pid], ob = pid === 'ours' ? r.obsOurs : r.obs;
                const x = cx + (k - (shown.length - 1) / 2) * cw * (shown.length > 2 ? 0.2 : 0.26);
                const lo = err ? f[0] - ob[1] : f[0], mid = err ? f[1] - ob[1] : f[1], hi = err ? f[2] - ob[1] : f[2];
                g += `<line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${y(lo).toFixed(1)}" y2="${y(hi).toFixed(1)}" stroke="${COLORS[pid]}" stroke-width="3.5" stroke-linecap="round"/>` +
                    `<circle cx="${x.toFixed(1)}" cy="${y(mid).toFixed(1)}" r="3.6" fill="#fff" stroke="${COLORS[pid]}" stroke-width="2"/>`;
            });
        });
        $('eval-plot').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Forecasts and observed snowfall for each weekend">${g}</svg>`;

        $('eval-plotcaption').textContent = `${S.area === 'ALL' ? 'Average of the 9 areas' : S.area}. ${winCaption()} Click a weekend for the day-by-day view.`;
        $('eval-key').innerHTML = `<span><i style="background:#94a3b8;opacity:.6"></i>Observed range</span>` +
            available().map(p => `<span><i style="background:${COLORS[p.id]}"></i>${esc(p.label)} ${POINT.includes(p.id) ? '(circle = model value)' : '(bar = range, circle = middle)'}</span>`).join('');
    }

    function renderToggles() {
        $('eval-toggles').innerHTML = available().map(p => p.id).map(pid => {
            const p = RAW.products.find(x => x.id === pid);
            return `<label><input type="checkbox" data-prod="${pid}"${S.show[pid] ? ' checked' : ''}> <span style="color:${COLORS[pid]}">&#9632;</span> ${esc(p.label)}</label>`;
        }).join('');
    }

    // ---- one weekend, day by day --------------------------------------------------------------

    const dayName = (first, k) => { const d = new Date(`${first}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + k); return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' }); };

    function renderDetail() {
        const box = $('eval-detail');
        if (S.weekend === null || !D.weekends[S.weekend]) { box.hidden = true; return; }
        const wk = D.weekends[S.weekend];
        const recs = D.records.filter(r => r.w === S.weekend && inArea(r, S.area));
        if (!recs.length) { box.hidden = true; return; }
        const keys = [...new Set(recs.flatMap(r => Object.keys(r.days || {})))].sort();
        const dayVals = keys.map(k => {
            const list = recs.map(r => r.days && r.days[k]).filter(Boolean);
            return { k, obs: avg3(list.filter(x => x.obs).map(x => x.obs)), nbm: avg3(list.filter(x => x.nbm).map(x => x.nbm)),
                ours: list.some(x => x.ours) ? avg3(list.filter(x => x.ours).map(x => [x.ours[0], (x.ours[0] + x.ours[1]) / 2, x.ours[1]])) : null };
        });
        const tot = plotRows(S.area)[S.weekend];
        const W = 520, H = 200, PL = 40, PR = 8, PT = 12, PB = 34, pw = W - PL - PR, ph = H - PT - PB, cw = pw / Math.max(1, keys.length);
        const T = S.axis === 'sqrt' ? sq : (v => v);
        const top = Math.max(1, ...dayVals.flatMap(d => [d.obs && d.obs[2], d.nbm && d.nbm[2], d.ours && d.ours[2]].filter(Boolean))) * 1.05;
        const y = v => PT + (T(top) - T(v)) / T(top) * ph;
        let g = niceTicks(top, S.axis).map(t => `<line x1="${PL}" x2="${W - PR}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}" class="ep-grid"/><text x="${PL - 5}" y="${(y(t) + 3.5).toFixed(1)}" text-anchor="end" class="ep-axis">${t}</text>`).join('');
        dayVals.forEach((d, k) => {
            const cx = PL + (k + 0.5) * cw, bw = cw * 0.5;
            g += `<text x="${cx.toFixed(1)}" y="${H - 12}" text-anchor="middle" class="ep-axis">${esc(dayName(wk.id, k))}</text>`;
            if (d.obs) g += `<rect class="ep-obs" x="${(cx - bw / 2).toFixed(1)}" y="${y(d.obs[2]).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(1, y(d.obs[0]) - y(d.obs[2])).toFixed(1)}"/>` +
                `<line class="ep-obsmid" x1="${(cx - bw / 2).toFixed(1)}" x2="${(cx + bw / 2).toFixed(1)}" y1="${y(d.obs[1]).toFixed(1)}" y2="${y(d.obs[1]).toFixed(1)}"/>`;
            if (d.nbm) g += `<line x1="${(cx + bw / 2 + 8).toFixed(1)}" x2="${(cx + bw / 2 + 8).toFixed(1)}" y1="${y(d.nbm[0]).toFixed(1)}" y2="${y(d.nbm[2]).toFixed(1)}" stroke="${COLORS.nbm}" stroke-width="3.5" stroke-linecap="round"/>` +
                `<circle cx="${(cx + bw / 2 + 8).toFixed(1)}" cy="${y(d.nbm[1]).toFixed(1)}" r="3.6" fill="#fff" stroke="${COLORS.nbm}" stroke-width="2"/>`;
            if (d.ours) g += `<line x1="${(cx + bw / 2 + 20).toFixed(1)}" x2="${(cx + bw / 2 + 20).toFixed(1)}" y1="${y(d.ours[0]).toFixed(1)}" y2="${y(d.ours[2]).toFixed(1)}" stroke="${COLORS.ours}" stroke-width="3.5" stroke-linecap="round"/>` +
                `<circle cx="${(cx + bw / 2 + 20).toFixed(1)}" cy="${y(d.ours[1]).toFixed(1)}" r="3.6" fill="#fff" stroke="${COLORS.ours}" stroke-width="2"/>`;
        });
        const line = (label, tri) => (tri ? `<li>${label}: <strong>${fmt(tri[1])} in</strong> (${fmt(tri[0])}&ndash;${fmt(tri[2])})</li>` : '');
        box.hidden = false;
        box.innerHTML = `<button type="button" class="ed-close" aria-label="Close">&times;</button>
            <h4>${esc(wk.label)} &middot; ${S.area === 'ALL' ? 'average of the 9 areas' : esc(S.area)}</h4>
            <ul class="eval-lines">${line(`Observed, ${winName()}`, tot.obs)}${line('NBM', tot.nbm)}${line('Our forecast', tot.ours)}${tot.hrrr ? `<li>HRRR: <strong>${fmt(tot.hrrr[1])} in</strong></li>` : ''}${tot.hrdps ? `<li>HRDPS: <strong>${fmt(tot.hrdps[1])} in</strong></li>` : ''}</ul>
            <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Day by day, observed and NBM">${g}</svg>
            <p class="eval-note">Grey = observed. Blue = NBM.${dayVals.some(d => d.ours) ? ' Orange = our forecast.' : ' Our forecast was only a weekend total.'}</p>`;
    }

    // ---- statistics table ---------------------------------------------------------------------

    function renderStats() {
        const rows = D.products.map(p => {
            if (!available().some(a => a.id === p.id)) return `<tr><td>${esc(p.label)}</td><td colspan="5" class="eval-ci">Not yet available</td></tr>`;
            const m = metrics(items(p.id, S.area));
            return `<tr><td><span style="color:${COLORS[p.id] || '#1e3c72'}">&#9632;</span> ${esc(p.label)}</td><td>${m.n}</td>
                <td>${signed(m.bias)} in</td><td>${fmt(m.mae)} in</td><td>${pct(m.hit)}</td><td>${fmt(m.width)} in</td></tr>`;
        }).join('');
        $('eval-stats').innerHTML = `<table class="eval-table"><thead><tr><th>Product</th><th>Weekends</th><th>Bias</th><th>Typical error</th><th>Inside range</th><th>Range width</th></tr></thead><tbody>${rows}</tbody></table>
            <p class="eval-sub">${S.area === 'ALL' ? 'All areas. ' : esc(S.area) + '. '}Bias is forecast minus observed.</p>`;
    }

    // ---- big storms: hits and misses ----------------------------------------------------------

    function renderEvents() {
        const thr = S.threshold;
        const out = available().map(a => a.id).map(pid => {
            const p = RAW.products.find(x => x.id === pid);
            const c = { hit: 0, miss: 0, fa: 0, cn: 0, unHit: 0, unNo: 0 };
            D.records.forEach(r => {
                if (!inArea(r, S.area)) return;
                const v = value(pid, r);
                if (!v) return;
                const yes = v.mid >= thr, o = v.obs;
                if (o[2] < thr) { if (yes) c.fa++; else c.cn++; }
                else if (o[0] >= thr) { if (yes) c.hit++; else c.miss++; }
                else if (yes) c.unHit++; else c.unNo++;
            });
            const pod = c.hit + c.miss ? c.hit / (c.hit + c.miss) : null;
            return `<div class="eval-conf"><h4><span style="color:${COLORS[pid]}">&#9632;</span> ${esc(p.label)}</h4>
                <table><thead><tr><th></th><th>Observed ${thr}"+</th><th>Observed under ${thr}"</th><th>Unclear</th></tr></thead><tbody>
                <tr><th>Forecast ${thr}"+</th><td class="ec-hit">${c.hit}<small>hits</small></td><td class="ec-fa">${c.fa}<small>false alarms</small></td><td class="ec-cn">${c.unHit}</td></tr>
                <tr><th>Forecast under ${thr}"</th><td class="ec-miss">${c.miss}<small>misses</small></td><td class="ec-cn">${c.cn}<small>correct "no"</small></td><td class="ec-cn">${c.unNo}</td></tr></tbody></table>
                <p>Caught ${pct(pod)} of the ${thr}"+ storms.</p></div>`;
        });
        $('eval-events').innerHTML = out.join('') +
            `<p class="eval-sub" style="grid-column:1/-1">"Unclear" means the storm size falls inside the observed range, so we can't say which side it was on.</p>`;
    }

    // ---- CoCoRaHS cross-check -----------------------------------------------------------------

    const COCO = { weekend: 'all', minElev: 0, snowOnly: false, fullOnly: false, all: false };
    const COCO_ROWS = 12;

    function renderCocoControls() {
        const opts = ['<option value="all">All weekends</option>'].concat(D.weekends.map((w, i) => `<option value="${i}">${esc(w.label)}</option>`));
        $('eval-cococontrols').innerHTML = `
            <label>Weekend <select id="coco-weekend">${opts.join('')}</select></label>
            <label>Station elevation <select id="coco-elev"><option value="0">Any</option><option value="1000">1,000 ft or higher</option><option value="2000">2,000 ft or higher</option><option value="3000">3,000 ft or higher</option></select></label>
            <label class="eval-check"><input type="checkbox" id="coco-snow"> Only where snow fell (any measure)</label>
            <label class="eval-check"><input type="checkbox" id="coco-full"> Only stations that reported every day</label>`;
        COCO.weekend = 'all'; COCO.minElev = 0; COCO.snowOnly = false; COCO.fullOnly = false; COCO.all = false;
        const on = (id, fn) => $(id).addEventListener('change', e => { fn(e.target); COCO.all = false; renderCoco(); });
        on('coco-weekend', t => { COCO.weekend = t.value; });
        on('coco-elev', t => { COCO.minElev = Number(t.value); });
        on('coco-snow', t => { COCO.snowOnly = t.checked; });
        on('coco-full', t => { COCO.fullOnly = t.checked; });
    }

    // One row per area and weekend, rebuilt from the stations that pass the filters.
    function cocoRows() {
        const out = [];
        D.records.forEach(r => {
            if (!r.coco || !r.obs || !inArea(r, S.area)) return;
            if (COCO.weekend !== 'all' && r.w !== Number(COCO.weekend)) return;
            let sts = r.coco.st;
            if (!sts) sts = [[r.coco.top && r.coco.top[0], r.coco.top && r.coco.top[1], null, r.coco.med, r.coco.full]];   // data without station detail
            sts = sts.filter(x => (!COCO.minElev || (x[1] && x[1] >= COCO.minElev)) && (!COCO.fullOnly || x[4]));
            if (!sts.length) return;
            const full = sts.filter(x => x[4]), use = full.length ? full : sts;
            const vals = use.map(x => x[3]).sort((p, q) => p - q), m = vals.length;
            const med = m % 2 ? vals[(m - 1) / 2] : (vals[m / 2 - 1] + vals[m / 2]) / 2;
            const top = use.reduce((p, q) => ((q[1] || 0) > (p[1] || 0) ? q : p));
            if (COCO.snowOnly && !(vals[m - 1] > 0 || r.obs[1] >= 0.5)) return;
            out.push({ r, n: use.length, full: full.length > 0, med, max: vals[m - 1], top });
        });
        return out.sort((p, q) => p.r.w - q.r.w || p.r.a.localeCompare(q.r.a));
    }

    function renderCoco() {
        const rows = cocoRows(), win = winName();
        const area = S.area === 'ALL';
        if (isPeriod()) {
            $('eval-coco').innerHTML = '<p class="eval-sub">CoCoRaHS volunteers report once a day, so the cross-check is not available for 12-hour periods. Choose the weekend total or Friday.</p>';
            return;
        }
        if (!rows.length) {
            $('eval-coco').innerHTML = `<p class="eval-sub">No CoCoRaHS reports match these filters near ${area ? 'any area' : esc(S.area)} for this season and window. Few volunteers live near ski terrain, so most areas have none.</p>`;
            return;
        }
        const shown = COCO.all ? rows : rows.slice(0, COCO_ROWS);
        const body = shown.map(x => {
            const wk = D.weekends[x.r.w], nbm = x.r.nbm;
            return `<tr><td>${esc(wk.label)}</td>${area ? `<td>${esc(x.r.a)}</td>` : ''}<td>${fmt(x.r.obs[1])}</td><td>${nbm ? fmt(nbm[1]) : DASH}</td>
                <td><strong>${fmt(x.med)}</strong>${x.max === x.med ? '' : ` <small>(${fmt(x.max)} max)</small>`}</td>
                <td>${x.n}${x.full ? '' : '*'}</td><td>${x.top[0] ? `${esc(x.top[0])}, ${x.top[1] ? Number(x.top[1]).toLocaleString() + ' ft' : '?'}: ${fmt(x.top[3])} in` : DASH}</td></tr>`;
        }).join('');
        $('eval-coco').innerHTML = `<div class="eval-scroll"><table class="eval-table"><thead><tr><th>Weekend</th>${area ? '<th>Area</th>' : ''}<th>SNOTEL estimate</th><th>NBM median</th><th>CoCoRaHS median</th><th>Stations</th><th>Highest station</th></tr></thead><tbody>${body}</tbody></table></div>
            ${rows.length > COCO_ROWS ? `<p class="eval-sub"><button type="button" class="eval-more" id="coco-more">${COCO.all ? 'Show fewer' : `Show all ${rows.length} rows`}</button></p>` : ''}
            <p class="eval-sub">${esc(win)}, inches; ${rows.length} area-weekend${rows.length === 1 ? '' : 's'}. Volunteer stations within 25 km. They are mostly in valleys and towns, well below the forecast elevation, so they check the storm, not the amount. A star means a station missed some days, so its total is a floor. This is a cross-check and is not part of any score.</p>`;
        const more = $('coco-more');
        if (more) more.addEventListener('click', () => { COCO.all = !COCO.all; renderCoco(); });
    }

    // ---- snow level ---------------------------------------------------------------------------

    function renderSnow() {
        const rows = D.snow_level.filter(r => r.sat && r.nbm && r.sonde !== null && (S.snowSite === 'ALL' || r.site === S.snowSite));
        const colors = { Quillayute: '#2a5298', Salem: '#d97706' };
        const panel = (title, xKey) => {
            const pts = rows.filter(r => r[xKey] !== null && r[xKey] !== undefined);
            const errs = pts.map(r => r.nbm[1] - r[xKey]);
            const W = 380, H = 330, PL = 46, PR = 10, PT = 10, PB = 38, pw = W - PL - PR, ph = H - PT - PB, max = 12000;
            const x = v => PL + v / max * pw, y = v => PT + (1 - v / max) * ph;
            let g = [0, 3000, 6000, 9000, 12000].map(t => `<line x1="${PL}" x2="${W - PR}" y1="${y(t)}" y2="${y(t)}" class="ep-grid"/><text x="${PL - 5}" y="${y(t) + 3.5}" text-anchor="end" class="ep-axis">${t / 1000}k</text><text x="${x(t)}" y="${H - 22}" text-anchor="middle" class="ep-axis">${t / 1000}k</text>`).join('');
            g += `<line x1="${x(0)}" y1="${y(0)}" x2="${x(max)}" y2="${y(max)}" stroke="#0f172a" stroke-dasharray="4 3" stroke-width="1.2"/>`;
            g += pts.map(r => `<circle class="sp-pt" cx="${x(Math.min(max, r[xKey])).toFixed(1)}" cy="${y(Math.min(max, r.nbm[1])).toFixed(1)}" r="3.4" fill="${colors[r.site] || '#475569'}"><title>${esc(`${r.site} ${r.valid}: ${r[xKey]} ft, NBM ${Math.round(r.nbm[1])} ft`)}</title></circle>`).join('');
            g += `<text x="${PL + pw / 2}" y="${H - 6}" text-anchor="middle" class="ep-axis">${esc(title)} (feet)</text><text transform="translate(11 ${PT + ph / 2}) rotate(-90)" text-anchor="middle" class="ep-axis">NBM snow level (feet)</text>`;
            return `<div class="eval-card"><h4>NBM vs ${esc(title.toLowerCase())}</h4>
                <div class="eval-big">${errs.length ? signed(Math.round(mean(errs)), 0) : DASH} <small>ft bias</small></div>
                <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="NBM snow level against ${esc(title.toLowerCase())}">${g}</svg>
                <ul class="eval-lines"><li>Typical error ${errs.length ? Math.round(mean(errs.map(Math.abs))).toLocaleString() : DASH} ft over ${errs.length} soundings</li></ul></div>`;
        };
        $('eval-snow').innerHTML = panel('Sounding snow level', 'sonde') + panel('Sounding freezing level', 'freezing') +
            `<p class="eval-sub" style="grid-column:1/-1">Radiosonde launches at Quillayute and Salem where the air was near saturation. The snow level is computed from the sounding with a melting-layer model; the freezing level is measured directly. The NBM has no freezing-level product.</p>`;
    }

    function renderMethod() {
        $('eval-method').innerHTML = `<ul>
            <li><strong>Forecasts.</strong> The NBM (National Blend of Models) median and 25&ndash;75% range for the weekend total, and our range from each post. For 2025&ndash;26 the NBM was rebuilt from the model archive using the Thursday 19Z run, not the exact numbers seen at the time.</li>
            <li><strong>Observed snowfall</strong> is an estimate from nearby SNOTEL stations (snow water equivalent and depth). Trace precipitation counts as none, and gains while the station was above 35&deg;F are treated as rain. The estimate is a range because new-snow density is unknown; only its midpoint is used for errors.</li>
            <li><strong>Stations</strong> sit at their own elevation, not the 5,000 ft the forecasts target.</li>
            <li><strong>HRRR and HRDPS</strong> are single-value models that run 48 hours, so they are compared on Friday only (the first day the Thursday forecast covers). HRRR snowfall is the model&rsquo;s own; HRDPS snowfall is its water equivalent of snow times 10, an assumed ratio. HRDPS is not archived, so it appears only for weekends scored from the 2026&ndash;27 season on; HRRR was rebuilt from the archive for 2025&ndash;26.</li>
            <li><strong>CoCoRaHS</strong> volunteer reports within 25 km are shown as a cross-check and are not scored.</li>
            <li><strong>Inside range</strong> means the observed midpoint fell in the forecast range (half an inch of slack). <strong>Typical error</strong> is the average distance from the forecast middle; <strong>bias</strong> is forecast minus observed.</li>
            <li>The <a href="/evaluation-2025-26-original.html">original 2025&ndash;26 evaluation</a> used a different method, so its numbers are not comparable.</li></ul>`;
    }

    // ---- wiring -------------------------------------------------------------------------------

    function setArea(a) { S.area = a; $('eval-area').value = a; renderAll(); }

    function renderAll() {
        renderTrackers(); renderHeat(); renderPlot(); renderDetail(); renderStats(); renderEvents(); renderCoco(); renderSnow();
    }

    function refreshProducts() {
        const ids = available().map(p => p.id);
        if (!ids.includes(S.mapProduct)) S.mapProduct = ids[0] || 'nbm';
        $('eval-mapprod').innerHTML = available().map(p => `<option value="${p.id}"${p.id === S.mapProduct ? ' selected' : ''}>${esc(p.label)}</option>`).join('');
        renderToggles();
    }

    function setSeason(id) {
        S.season = id; S.weekend = null;
        D = buildView(id);
        const season = RAW.seasons.find(s => s.id === id) || {};
        $('eval-season').value = id;
        $('eval-seasonnote').textContent = season.note || '';
        $('eval-seasonnote').hidden = !season.note;
        const empty = D.weekends.length === 0;
        $('eval-empty').hidden = !empty;
        $('eval-main').hidden = empty;
        if (empty) return;
        refreshProducts();
        renderCocoControls();
        renderAll();
        if (map) map.invalidateSize();
    }

    function init() {
        // open on the newest season that has weekends
        const withData = RAW.seasons.filter(s => RAW.weekends.some(w => w.season === s.id));
        const first = (withData[0] || RAW.seasons[0]).id;
        $('eval-season').innerHTML = RAW.seasons.map(s => `<option value="${esc(s.id)}">${esc(s.label)}${RAW.weekends.some(w => w.season === s.id) ? '' : ' (not started)'}</option>`).join('');
        $('eval-area').innerHTML = '<option value="ALL">All areas</option>' + areasNS().map(a => `<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('');
        $('eval-snowsite').innerHTML = '<option value="ALL">Both</option>' + [...new Set(RAW.snow_level.map(r => r.site))].map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
        D = buildView(first);
        refreshProducts(); renderMethod();
        try { initMap(); } catch (e) { console.error('Evaluation map failed:', e); map = null; $('eval-map').parentNode.hidden = true; }

        $('eval-season').addEventListener('change', e => setSeason(e.target.value));
        $('eval-window').addEventListener('change', e => { S.win = e.target.value; setSeason(S.season); });
        $('eval-area').addEventListener('change', e => setArea(e.target.value));
        $('eval-metric').addEventListener('change', e => { S.metric = e.target.value; renderHeat(); });
        $('eval-mapprod').addEventListener('change', e => { S.mapProduct = e.target.value; renderHeat(); });
        $('eval-axis').addEventListener('change', e => { S.axis = e.target.value; renderPlot(); renderDetail(); });
        $('eval-view').addEventListener('change', e => { S.view = e.target.value; renderPlot(); });
        $('eval-threshold').addEventListener('change', e => { S.threshold = Number(e.target.value); renderEvents(); });
        $('eval-snowsite').addEventListener('change', e => { S.snowSite = e.target.value; renderSnow(); });
        $('eval-toggles').addEventListener('change', e => { const p = e.target.dataset.prod; if (p) { S.show[p] = e.target.checked; renderPlot(); } });
        $('eval-heat').addEventListener('click', e => { const tr = e.target.closest('tr[data-area]'); if (tr) setArea(tr.dataset.area); });
        $('eval-plot').addEventListener('click', e => { const c = e.target.closest('.ep-col'); if (c) { S.weekend = Number(c.dataset.i); renderPlot(); renderDetail(); const d = $('eval-detail'); if (!d.hidden) d.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } });
        $('eval-detail').addEventListener('click', e => { if (e.target.closest('.ed-close')) { S.weekend = null; renderPlot(); renderDetail(); } });

        setSeason(first);
    }

    fetch(root.dataset.src, { cache: 'no-cache' })
        .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(d => { RAW = d; init(); })
        .catch(err => {
            console.error('Evaluation failed:', err && err.stack ? err.stack : err);
            $('eval-trackers').innerHTML = '<p class="eval-status">The evaluation data is temporarily unavailable.</p>';
        });
}());
