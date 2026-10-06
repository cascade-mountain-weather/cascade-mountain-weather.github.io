// Forecast evaluation page. Plain DOM and SVG (no chart library); the map uses Leaflet.
// Data: assets/data/evaluation.json, built by scripts/build_evaluation_json.py from the scored weekends.
// All statistics are computed here from the records, so a new product (HRRR, HRDPS) only needs a new field
// on each record and an entry in `products`.
//
// What is scored: the weekend snowfall total for each area. A product gives a middle value (NBM median, the
// middle of our range, or a single model value) and, for the range products, a low-high range. The "truth"
// is an estimate from SNOTEL stations and is itself a range (new-snow density is unknown), so it is drawn as
// a band and only its midpoint is used for errors and hits.

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

    let D = null;
    const S = { area: 'ALL', metric: 'mae', mapProduct: 'nbm', axis: 'sqrt', view: 'values', show: { nbm: true, ours: true },
        weekend: null, threshold: 6, snowSite: 'ALL' };

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

    // Weekend-clustered bootstrap: areas share storms, so whole weekends are resampled, not single rows.
    function mulberry(seed) { return () => { seed |= 0; seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
    function bootCI(its, stat, B) {
        B = B || 600;
        const groups = new Map();
        its.forEach(i => { if (!groups.has(i.w)) groups.set(i.w, []); groups.get(i.w).push(i); });
        const g = [...groups.values()];
        if (g.length < 5) return null;
        const rnd = mulberry(20260105), res = [];
        for (let b = 0; b < B; b++) {
            const pick = [];
            for (let k = 0; k < g.length; k++) pick.push(...g[Math.floor(rnd() * g.length)]);
            res.push(stat(pick));
        }
        res.sort((p, q) => p - q);
        return [res[Math.floor(B * 0.05)], res[Math.floor(B * 0.95)]];
    }
    const statMae = its => mean(its.map(i => i.abs)), statBias = its => mean(its.map(i => i.err));

    // Our forecast against the NBM on the weekends where both exist.
    function matchedPairs(area) {
        const nb = new Map(items('nbm', area).map(i => [`${i.w}|${i.a}`, i]));
        return items('ours', area).filter(i => nb.has(`${i.w}|${i.a}`)).map(i => ({ w: i.w, a: i.a, abs: i.abs, nbmAbs: nb.get(`${i.w}|${i.a}`).abs }));
    }
    function skill(pairs) {
        const n = mean(pairs.map(p => p.nbmAbs)), o = mean(pairs.map(p => p.abs));
        return n ? 1 - o / n : null;
    }

    const available = () => D.products.filter(p => p.available && D.records.some(r => value(p.id, r)));

    // ---- trackers -----------------------------------------------------------------------------

    function renderTrackers() {
        const prods = D.products;
        const live = available();
        // rank on the weekends where every live product has a forecast
        const key = r => `${r.w}|${r.a}`;
        let common = null;
        live.forEach(p => { const ks = new Set(items(p.id, S.area).map(i => `${i.w}|${i.a}`)); common = common ? new Set([...common].filter(k => ks.has(k))) : ks; });
        const maeOn = pid => mean(items(pid, S.area).filter(i => common && common.has(`${i.w}|${i.a}`)).map(i => i.abs));
        const ranked = live.map(p => ({ id: p.id, mae: maeOn(p.id) })).sort((a, b) => a.mae - b.mae);

        $('eval-trackers').innerHTML = prods.map(p => {
            if (!p.available || !live.some(l => l.id === p.id)) {
                return `<div class="eval-card eval-card--off"><h4>${esc(p.label)}</h4><div class="eval-note">Coming soon. It will appear here once its forecasts are saved each week.</div></div>`;
            }
            const its = items(p.id, S.area), m = metrics(its), ci = bootCI(its, statMae);
            const rank = ranked.findIndex(r => r.id === p.id);
            let extra = '';
            if (p.id === 'ours') {
                const pairs = matchedPairs(S.area), sk = skill(pairs);
                if (pairs.length) {
                    const nbm = mean(pairs.map(x => x.nbmAbs)), ours = mean(pairs.map(x => x.abs));
                    extra = `<li>Against the NBM on the same ${pairs.length} weekends: ${fmt(ours)} in vs ${fmt(nbm)} in (${sk >= 0 ? sk * 100 > 0.5 ? Math.round(sk * 100) + '% smaller error' : 'about equal' : Math.round(-sk * 100) + '% larger error'})</li>`;
                }
            }
            return `<div class="eval-card">
                <h4><span style="color:${COLORS[p.id] || '#1e3c72'}">&#9632;</span>&nbsp;${esc(p.label)}${live.length > 1 && rank >= 0 ? `<span class="eval-rank">${rank + 1} of ${live.length}</span>` : ''}</h4>
                <div class="eval-big">${fmt(m.mae)} <small>in typical error</small></div>
                <ul class="eval-lines">
                    <li>Bias ${signed(m.bias)} in ${m.bias === null ? '' : m.bias < -0.25 ? '(too low)' : m.bias > 0.25 ? '(too high)' : '(about right)'}</li>
                    <li>Observed value inside the range ${pct(m.hit)}</li>
                    ${ci ? `<li class="eval-ci">Typical error, 90% interval: ${fmt(ci[0])}&ndash;${fmt(ci[1])} in</li>` : ''}
                    <li class="eval-ci">${m.n} area-weekends${S.area === 'ALL' ? '' : ' at ' + esc(S.area)}</li>
                    ${extra}
                </ul></div>`;
        }).join('');
    }

    // ---- heatmap and map ----------------------------------------------------------------------

    const areasNS = () => D.areas.slice().sort((a, b) => (b.lat || 0) - (a.lat || 0));

    function cellValue(m) { return S.metric === 'mae' ? m.mae : S.metric === 'bias' ? m.bias : m.hit; }
    function cellText(v) { return S.metric === 'hit' ? pct(v) : S.metric === 'bias' ? signed(v) : fmt(v); }
    function cellColor(v, caps) {
        if (v === null || v === undefined) return { bg: '#f1f5f9', fg: '#94a3b8' };
        if (S.metric === 'bias') return { bg: diverging(-v / caps.bias), fg: '#0f172a' };
        const t = S.metric === 'mae' ? v / caps.mae : v;
        return { bg: sequential(S.metric === 'mae' ? t : t), fg: t > 0.55 ? '#fff' : '#0f172a' };
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
            return `<td style="background:${c.bg};color:${c.fg}" title="${esc(`${label}: n = ${m.n}, typical error ${fmt(m.mae)} in, bias ${signed(m.bias)} in, inside range ${pct(m.hit)}`)}">${cellText(v)}<small>n=${m.n}</small></td>`;
        }).join('')}</tr>`;
        $('eval-heat').innerHTML = `<table><thead><tr><th></th>${h.prods.map(p => `<th>${esc(p.label)}</th>`).join('')}</tr></thead><tbody>${
            h.grid.map(r => row(r, r.area, '')).join('')}${row(h.all, 'All areas', 'is-all')}</tbody></table>
            <p class="eval-sub">${S.metric === 'mae' ? 'Average distance between the forecast middle and the observed estimate; lower is better.' :
                S.metric === 'bias' ? 'Forecast minus observed. Blue = too low, red = too high.' : 'How often the observed estimate fell inside the forecast range. Higher is better; an NBM 25–75% range should score about 50%.'} Click a row to look at one area.</p>`;
        updateMap(h);
    }

    let map = null;
    const markers = {};
    function initMap() {
        const pts = D.areas.filter(a => typeof a.lat === 'number');
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
            const cm = r.cells[pi], v = cellValue(cm), c = cellColor(v, h.caps);
            m.setStyle({ fillColor: c.bg, weight: S.area === r.area ? 3.5 : 1.5, color: S.area === r.area ? '#0f172a' : '#334155' });
            m.unbindTooltip();
            m.bindTooltip(`<strong>${esc(r.area)}</strong><br>${esc(label)}: ${esc(cellText(v))}<br>${cm.n} weekends`, { direction: 'top', offset: [0, -8] });
        });
        const stops = S.metric === 'bias' ? SCALE : [0, 0.25, 0.5, 0.75, 1].map(sequential);
        const [l, r] = S.metric === 'bias' ? ['Too low', 'Too high'] : S.metric === 'mae' ? ['Small error', `Large (${fmt(h.caps.mae)} in)`] : ['0%', '100%'];
        const ordered = S.metric === 'bias' ? SCALE.slice().reverse() : stops;   // blue (too low) on the left, red (too high) on the right
        $('eval-maplegend').innerHTML = `<div class="eval-legend-bar" style="background:linear-gradient(to right,${ordered.join(',')})"></div><div class="eval-legend-labels"><span>${l}</span><span>${r}</span></div>`;
    }

    // ---- weekend plot -------------------------------------------------------------------------

    const avg = arr => (arr.length ? mean(arr) : null);
    const avg3 = list => (list.length ? [0, 1, 2].map(k => mean(list.map(x => x[k]))) : null);

    function plotRows(area) {
        return D.weekends.map((wk, i) => {
            const recs = D.records.filter(r => r.w === i && inArea(r, area));
            if (!recs.length) return { i, wk, none: true };
            const obs = avg3(recs.filter(r => r.obs).map(r => r.obs));
            const obsOurs = avg3(recs.filter(r => r.obs_ours).map(r => r.obs_ours)) || obs;
            const nbm = avg3(recs.filter(r => r.nbm).map(r => r.nbm));
            const ours = recs.filter(r => r.ours).length
                ? (() => { const a = avg3(recs.filter(r => r.ours).map(r => [r.ours[0], (r.ours[0] + r.ours[1]) / 2, r.ours[1]])); return a; })() : null;
            return { i, wk, obs, obsOurs, nbm, ours };
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
        const W = 920, H = 360, PL = 46, PR = 10, PT = 16, PB = 40, pw = W - PL - PR, ph = H - PT - PB, cw = pw / n;
        const T = S.axis === 'sqrt' ? sq : (v => v);
        const err = S.view === 'error';

        // value ranges
        let top = 1;
        rows.forEach(r => {
            if (r.none) return;
            [r.obs && r.obs[2], r.nbm && r.nbm[2], r.ours && r.ours[2]].forEach(v => { if (v) top = Math.max(top, v); });
        });
        let eAbs = 1;
        if (err) rows.forEach(r => {
            if (r.none || !r.obs) return;
            [['nbm', r.obs], ['ours', r.obsOurs]].forEach(([pid, o]) => {
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
                `${r.nbm ? `\nNBM ${fmt(r.nbm[1])} in (${fmt(r.nbm[0])}–${fmt(r.nbm[2])})` : ''}${r.ours ? `\nOurs ${fmt(r.ours[1])} in (${fmt(r.ours[0])}–${fmt(r.ours[2])})` : ''}`;
            g += `<rect class="ep-col${S.weekend === r.i ? ' is-sel' : ''}" data-i="${r.i}" x="${(cx - cw / 2).toFixed(1)}" y="${PT}" width="${cw.toFixed(1)}" height="${ph}"><title>${esc(tip)}</title></rect>`;
            if (r.none || !r.obs) return;

            // the observed band ("truth")
            const o = r.obs;
            if (err) g += `<rect class="ep-obs" x="${(cx - bw / 2).toFixed(1)}" y="${y(o[2] - o[1]).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(1, y(o[0] - o[1]) - y(o[2] - o[1])).toFixed(1)}"/>`;
            else g += `<rect class="ep-obs" x="${(cx - bw / 2).toFixed(1)}" y="${y(o[2]).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(1, y(o[0]) - y(o[2])).toFixed(1)}"/>` +
                `<line class="ep-obsmid" x1="${(cx - bw / 2).toFixed(1)}" x2="${(cx + bw / 2).toFixed(1)}" y1="${y(o[1]).toFixed(1)}" y2="${y(o[1]).toFixed(1)}"/>`;

            // forecast products, side by side
            const shown = ['nbm', 'ours'].filter(pid => S.show[pid] && r[pid]);
            shown.forEach((pid, k) => {
                const f = r[pid], ob = pid === 'ours' ? r.obsOurs : r.obs;
                const off = (k - (shown.length - 1) / 2) * cw * 0.26, x = cx + off;
                const lo = err ? f[0] - ob[1] : f[0], mid = err ? f[1] - ob[1] : f[1], hi = err ? f[2] - ob[1] : f[2];
                g += `<line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${y(lo).toFixed(1)}" y2="${y(hi).toFixed(1)}" stroke="${COLORS[pid]}" stroke-width="3.5" stroke-linecap="round"/>` +
                    `<circle cx="${x.toFixed(1)}" cy="${y(mid).toFixed(1)}" r="3.6" fill="#fff" stroke="${COLORS[pid]}" stroke-width="2"/>`;
            });
        });
        $('eval-plot').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Forecasts and observed snowfall for each weekend">${g}</svg>`;

        const who = S.area === 'ALL' ? 'the average of the 9 areas' : S.area;
        $('eval-plotcaption').textContent = (err ? 'Each mark is how far the forecast was from the observed value (zero line = exact). ' : 'Grey band = observed estimate (its range is wide because new-snow density is unknown). ') +
            `Showing ${who}. Click a weekend for the day-by-day view.`;
        $('eval-key').innerHTML = `<span><i style="background:#94a3b8;opacity:.6"></i>Observed range${err ? ' (around zero)' : ' with its middle marked'}</span>` +
            D.products.filter(p => p.available && ['nbm', 'ours'].includes(p.id)).map(p => `<span><i style="background:${COLORS[p.id]}"></i>${esc(p.long)} &ndash; bar = range, circle = middle</span>`).join('');
    }

    function renderToggles() {
        $('eval-toggles').innerHTML = ['nbm', 'ours'].map(pid => {
            const p = D.products.find(x => x.id === pid);
            return `<label><input type="checkbox" data-prod="${pid}"${S.show[pid] ? ' checked' : ''}> <span style="color:${COLORS[pid]}">&#9632;</span> ${esc(p.label)}</label>`;
        }).join('');
    }

    // ---- one weekend, day by day --------------------------------------------------------------

    const dayName = (first, k) => { const d = new Date(`${first}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + k); return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' }); };

    function renderDetail() {
        const box = $('eval-detail');
        if (S.weekend === null) { box.hidden = true; return; }
        const wk = D.weekends[S.weekend];
        const recs = D.records.filter(r => r.w === S.weekend && inArea(r, S.area));
        if (!recs.length) { box.hidden = true; return; }
        const keys = [...new Set(recs.flatMap(r => Object.keys(r.days || {})))].sort();
        const dayVals = keys.map(k => {
            const list = recs.map(r => r.days && r.days[k]).filter(Boolean);
            return { k, obs: avg3(list.filter(x => x.obs).map(x => x.obs)), nbm: avg3(list.filter(x => x.nbm).map(x => x.nbm)) };
        });
        const tot = plotRows(S.area)[S.weekend];
        const W = 520, H = 200, PL = 40, PR = 8, PT = 12, PB = 34, pw = W - PL - PR, ph = H - PT - PB, cw = pw / Math.max(1, keys.length);
        const T = S.axis === 'sqrt' ? sq : (v => v);
        const top = Math.max(1, ...dayVals.flatMap(d => [d.obs && d.obs[2], d.nbm && d.nbm[2]].filter(Boolean))) * 1.05;
        const y = v => PT + (T(top) - T(v)) / T(top) * ph;
        let g = niceTicks(top, S.axis).map(t => `<line x1="${PL}" x2="${W - PR}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}" class="ep-grid"/><text x="${PL - 5}" y="${(y(t) + 3.5).toFixed(1)}" text-anchor="end" class="ep-axis">${t}</text>`).join('');
        dayVals.forEach((d, k) => {
            const cx = PL + (k + 0.5) * cw, bw = cw * 0.5;
            g += `<text x="${cx.toFixed(1)}" y="${H - 12}" text-anchor="middle" class="ep-axis">${esc(dayName(wk.id, k))}</text>`;
            if (d.obs) g += `<rect class="ep-obs" x="${(cx - bw / 2).toFixed(1)}" y="${y(d.obs[2]).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(1, y(d.obs[0]) - y(d.obs[2])).toFixed(1)}"/>` +
                `<line class="ep-obsmid" x1="${(cx - bw / 2).toFixed(1)}" x2="${(cx + bw / 2).toFixed(1)}" y1="${y(d.obs[1]).toFixed(1)}" y2="${y(d.obs[1]).toFixed(1)}"/>`;
            if (d.nbm) g += `<line x1="${(cx + bw / 2 + 8).toFixed(1)}" x2="${(cx + bw / 2 + 8).toFixed(1)}" y1="${y(d.nbm[0]).toFixed(1)}" y2="${y(d.nbm[2]).toFixed(1)}" stroke="${COLORS.nbm}" stroke-width="3.5" stroke-linecap="round"/>` +
                `<circle cx="${(cx + bw / 2 + 8).toFixed(1)}" cy="${y(d.nbm[1]).toFixed(1)}" r="3.6" fill="#fff" stroke="${COLORS.nbm}" stroke-width="2"/>`;
        });
        const line = (label, tri) => (tri ? `<li>${label}: <strong>${fmt(tri[1])} in</strong> (${fmt(tri[0])}&ndash;${fmt(tri[2])})</li>` : '');
        box.hidden = false;
        box.innerHTML = `<button type="button" class="ed-close" aria-label="Close">&times;</button>
            <h4>${esc(wk.label)} &middot; ${S.area === 'ALL' ? 'average of the 9 areas' : esc(S.area)}</h4>
            <ul class="eval-lines">${line('Observed estimate, weekend total', tot.obs)}${line('NBM', tot.nbm)}${line('Our forecast', tot.ours)}</ul>
            <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Day by day, observed and NBM">${g}</svg>
            <p class="eval-note">Grey = observed estimate for each day. Blue = NBM (circle is the median, bar is the 25&ndash;75% range). The forecast was saved only as a weekend total, so the day-by-day view shows the NBM only. Daily windows run 5 am to 5 am Pacific.</p>`;
    }

    // ---- statistics table ---------------------------------------------------------------------

    function renderStats() {
        const ci = (c, nd) => (c ? `<span class="eval-ci"> (${fmt(c[0], nd)} to ${fmt(c[1], nd)})</span>` : '');
        const rows = D.products.map(p => {
            if (!p.available || !available().some(a => a.id === p.id)) return `<tr><td>${esc(p.label)}</td><td colspan="6" class="eval-ci">Not yet available</td></tr>`;
            const its = items(p.id, S.area), m = metrics(its);
            let vs = DASH;
            if (p.id === 'ours') {
                const pairs = matchedPairs(S.area), sk = skill(pairs);
                const bs = (() => { const g = new Map(); pairs.forEach(x => { if (!g.has(x.w)) g.set(x.w, []); g.get(x.w).push(x); }); const gs = [...g.values()]; if (gs.length < 5) return null; const rnd = mulberry(7), out = []; for (let b = 0; b < 600; b++) { const pick = []; for (let k = 0; k < gs.length; k++) pick.push(...gs[Math.floor(rnd() * gs.length)]); out.push(skill(pick)); } out.sort((a, c) => a - c); return [out[30], out[570]]; })();
                vs = sk === null ? DASH : `${signed(-sk * 100, 0)}%${bs ? `<span class="eval-ci"> (${signed(-bs[1] * 100, 0)}% to ${signed(-bs[0] * 100, 0)}%)</span>` : ''}`;   // +10% = ten percent larger error
            }
            return `<tr><td><span style="color:${COLORS[p.id] || '#1e3c72'}">&#9632;</span> ${esc(p.label)}</td><td>${m.n}</td>
                <td>${signed(m.bias)} in${ci(bootCI(its, statBias), 1)}</td><td>${fmt(m.mae)} in${ci(bootCI(its, statMae), 1)}</td>
                <td>${pct(m.hit)}</td><td>${fmt(m.width)} in</td><td>${vs}</td></tr>`;
        }).join('');
        $('eval-stats').innerHTML = `<table class="eval-table"><thead><tr><th>Product</th><th>Weekends</th><th>Bias</th><th>Typical error</th><th>Observed value inside range</th><th>Average range width</th><th>Error vs NBM (same weekends)</th></tr></thead><tbody>${rows}</tbody></table>
            <p class="eval-sub">${S.area === 'ALL' ? 'Every area-weekend. ' : ''}Bias is forecast minus observed. Intervals are 90% and resample whole weekends, because areas share storms. Our forecast is scored against what fell over our own forecast period (4 pm Thursday to 4 am Monday); the NBM over Friday 12Z to Monday 12Z. In "error vs NBM", a positive percentage means a larger error than the NBM and a negative one a smaller error. With about ${D.weekends.length - 1} weekends and an uncertain observation, small differences are not meaningful.</p>`;
    }

    // ---- big storms: hits and misses ----------------------------------------------------------

    function renderEvents() {
        const thr = S.threshold;
        const out = ['nbm', 'ours'].map(pid => {
            const p = D.products.find(x => x.id === pid);
            const c = { hit: 0, miss: 0, fa: 0, cn: 0, unHit: 0, unNo: 0 };
            D.records.forEach(r => {
                if (!inArea(r, S.area)) return;
                const v = value(pid, r);
                if (!v) return;
                const yes = v.mid >= thr;
                const o = v.obs;
                if (o[2] < thr) { if (yes) c.fa++; else c.cn++; }
                else if (o[0] >= thr) { if (yes) c.hit++; else c.miss++; }
                else if (yes) c.unHit++; else c.unNo++;
            });
            const pod = c.hit + c.miss ? c.hit / (c.hit + c.miss) : null, far = c.hit + c.fa ? c.fa / (c.hit + c.fa) : null;
            return `<div class="eval-conf"><h4><span style="color:${COLORS[pid]}">&#9632;</span> ${esc(p.label)}</h4>
                <table><thead><tr><th></th><th>Observed ${thr}"+</th><th>Observed under ${thr}"</th><th>Unclear</th></tr></thead><tbody>
                <tr><th>Forecast ${thr}"+</th><td class="ec-hit">${c.hit}<small>hits</small></td><td class="ec-fa">${c.fa}<small>false alarms</small></td><td class="ec-cn">${c.unHit}</td></tr>
                <tr><th>Forecast under ${thr}"</th><td class="ec-miss">${c.miss}<small>misses</small></td><td class="ec-cn">${c.cn}<small>correct "no"</small></td><td class="ec-cn">${c.unNo}</td></tr></tbody></table>
                <p>Caught ${pct(pod)} of the ${thr}"+ storms${far === null ? '' : `; ${pct(far)} of the ${thr}"+ forecasts did not verify`}.</p></div>`;
        });
        $('eval-events').innerHTML = out.join('') +
            `<p class="eval-sub" style="grid-column:1/-1">"Forecast ${thr}"+" means the middle of the forecast was at least ${thr} in. Observed counts as ${thr}"+ only if even the low end of the observed estimate reached it, and as under only if even the high end fell short; when the threshold falls inside the observed range, the weekend is "unclear".</p>`;
    }

    // ---- snow level ---------------------------------------------------------------------------

    function renderSnow() {
        const rows = D.snow_level.filter(r => r.sat && r.nbm && r.sonde !== null && (S.snowSite === 'ALL' || r.site === S.snowSite));
        const sites = [...new Set(D.snow_level.map(r => r.site))];
        const colors = { Quillayute: '#2a5298', Salem: '#d97706' };
        const panel = (title, xKey, note) => {
            const pts = rows.filter(r => r[xKey] !== null && r[xKey] !== undefined);
            const errs = pts.map(r => r.nbm[1] - r[xKey]);
            const W = 380, H = 340, PL = 46, PR = 10, PT = 10, PB = 38, pw = W - PL - PR, ph = H - PT - PB, max = 12000;
            const x = v => PL + v / max * pw, y = v => PT + (1 - v / max) * ph;
            let g = [0, 3000, 6000, 9000, 12000].map(t => `<line x1="${PL}" x2="${W - PR}" y1="${y(t)}" y2="${y(t)}" class="ep-grid"/><text x="${PL - 5}" y="${y(t) + 3.5}" text-anchor="end" class="ep-axis">${t / 1000}k</text><text x="${x(t)}" y="${H - 22}" text-anchor="middle" class="ep-axis">${t / 1000}k</text>`).join('');
            g += `<line x1="${x(0)}" y1="${y(0)}" x2="${x(max)}" y2="${y(max)}" stroke="#0f172a" stroke-dasharray="4 3" stroke-width="1.2"/>`;
            g += pts.map(r => `<circle class="sp-pt" cx="${x(Math.min(max, r[xKey])).toFixed(1)}" cy="${y(Math.min(max, r.nbm[1])).toFixed(1)}" r="3.4" fill="${colors[r.site] || '#475569'}"><title>${esc(`${r.site} ${r.valid}: ${title.toLowerCase()} ${r[xKey]} ft, NBM ${Math.round(r.nbm[1])} ft`)}</title></circle>`).join('');
            g += `<text x="${PL + pw / 2}" y="${H - 6}" text-anchor="middle" class="ep-axis">${esc(title)} (feet)</text><text transform="translate(11 ${PT + ph / 2}) rotate(-90)" text-anchor="middle" class="ep-axis">NBM snow level, median (feet)</text>`;
            return `<div class="eval-card"><h4>NBM vs ${esc(title.toLowerCase())}</h4>
                <div class="eval-big">${errs.length ? signed(Math.round(mean(errs)), 0) : DASH} <small>ft bias</small></div>
                <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="NBM snow level against ${esc(title.toLowerCase())}">${g}</svg>
                <ul class="eval-lines"><li>Typical error ${errs.length ? Math.round(mean(errs.map(Math.abs))).toLocaleString() : DASH} ft over ${errs.length} soundings</li></ul><p class="eval-note">${note}</p></div>`;
        };
        $('eval-snow').innerHTML = panel('Sounding snow level', 'sonde', 'The snow level the radiosonde tool computes from the sounding with a melting-layer model.') +
            panel('Sounding freezing level', 'freezing', 'The height of 0&deg;C measured directly by the balloon, with no model in between.') +
            `<p class="eval-sub" style="grid-column:1/-1">Only soundings where the air column is close to saturated are used (a dry sounding gives a snow level that says nothing about a precipitation forecast). Points on the dashed line would be perfect. Sites: ${sites.map(s => `<span style="color:${colors[s] || '#475569'}">&#9679;</span> ${esc(s)}`).join(' &nbsp; ')}. The NBM has no freezing-level product; its snow level sits much closer to the measured freezing level than to the modeled snow level, so the gap in the left panel is mostly a difference in definition, not forecast skill.</p>`;
    }

    function renderMethod() {
        $('eval-method').innerHTML = `<ul>
            <li><strong>Forecast values.</strong> The NBM is the National Blend of Models; we use its median and 25th&ndash;75th percentile range for the weekend total. For this season the NBM numbers were rebuilt from the model archive using the Thursday 19Z run, so they are a consistent stand-in for what was available when each forecast was written, not the exact numbers seen at the time. Our forecast is the range printed in the post.</li>
            <li><strong>Observed snowfall.</strong> There is no direct measurement. It is estimated from the nearest SNOTEL stations (snow water equivalent and snow depth, hourly), with checks for sensor noise: no snowfall if the precipitation gauge shows almost nothing or if the window was too warm. New-snow density is the main unknown, so the estimate is a wide range; only its midpoint is used for errors.</li>
            <li><strong>Station elevation.</strong> The SNOTEL stations sit at their own elevation, not the 5,000 ft the forecasts target. Where a station is much lower or higher than that, expect some of the difference to be the elevation, not the forecast.</li>
            <li><strong>Hit.</strong> The observed midpoint fell inside the forecast range (with half an inch of slack).</li>
            <li><strong>Typical error</strong> is the average distance between the forecast middle and the observed midpoint. <strong>Bias</strong> is the average signed difference.</li>
            <li><strong>Not yet included.</strong> HRRR and HRDPS (only reach about 48 hours, so they will be scored on the first days of the weekend), and our own snow-level and freezing-level forecasts.</li>
            <li><strong>The older evaluation</strong> (2025&ndash;26, original method) is kept on the <a href="{{ '/evaluation.html' | relative_url }}">current evaluation page</a>; its numbers are not comparable with these.</li></ul>`;
    }

    // ---- wiring -------------------------------------------------------------------------------

    function setArea(a) { S.area = a; $('eval-area').value = a; S.weekend = S.weekend; renderAll(); }

    function renderAll() {
        renderTrackers(); renderHeat(); renderPlot(); renderDetail(); renderStats(); renderEvents(); renderSnow();
    }

    function init() {
        $('eval-area').innerHTML = '<option value="ALL">All areas</option>' + areasNS().map(a => `<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('');
        $('eval-mapprod').innerHTML = available().map(p => `<option value="${p.id}">${esc(p.label)}</option>`).join('');
        $('eval-snowsite').innerHTML = '<option value="ALL">Both</option>' + [...new Set(D.snow_level.map(r => r.site))].map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
        renderToggles(); renderMethod();
        try { initMap(); } catch (e) { console.error('Evaluation map failed:', e); map = null; const w = $('eval-mapwrap') || $('eval-map').parentNode; if (w) w.hidden = true; }

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

        // open on the weekend with the most snow so the detail view is not empty
        renderAll();
        if (map) map.invalidateSize();
    }

    fetch(root.dataset.src, { cache: 'no-cache' })
        .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(d => { D = d; init(); })
        .catch(err => {
            console.error('Evaluation failed:', err && err.stack ? err.stack : err);
            $('eval-trackers').innerHTML = '<p class="eval-status">The evaluation data is temporarily unavailable.</p>';
        });
}());
