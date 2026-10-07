// Climate index explorer for the Teleconnections page: ENSO (ONI) and PDO as one interactive chart.
// Data: assets/data/climate_indices.json, written by scripts/collect_climate_indices.py (monthly; both indices from NOAA).
// Mount point: <div class="ci-mount"></div>. Views: ONI, PDO, or both overlaid (own axis for each). Hover or touch for values.
(function () {
    'use strict';
    const BASE = (document.currentScript && document.currentScript.src || '').replace(/[^/]*$/, '');
    const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const SEAS = ['DJF', 'JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ'];   // by center month, Jan first
    const C = { warm: '#dc2626', cool: '#2563eb', oni: '#c2410c', pdo: '#0f766e', grid: '#e2e8f0', text: '#334155', muted: '#64748b', axis: '#94a3b8' };
    const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    const fmt = (v, nd) => (v == null ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(nd == null ? 1 : nd));

    // A series on a common month axis: gm = year * 12 + (month - 1)
    function series(key, d, nd) {
        const [y, m] = d.start.split('-').map(Number);
        const gm0 = y * 12 + (m - 1);
        return { key, name: d.name, values: d.values, gm0, nd, last: gm0 + d.values.length - 1,
            at: gm => { const v = d.values[gm - gm0]; return v === undefined ? null : v; },
            // trailing 12-month mean (needs at least 9 of the 12 months), used to show decadal phases on long spans
            smAt: gm => {
                let n = 0, t = 0;
                for (let k = gm - 11; k <= gm; k++) { const v = d.values[k - gm0]; if (v != null) { n++; t += v; } }
                return n >= 9 ? t / n : null;
            } };
    }
    const gmLabel = gm => `${MON[gm % 12]} ${Math.floor(gm / 12)}`;

    // Signed run length of the latest value, and whether it is the longest run of that sign in the record
    function runInfo(s) {
        const v = s.values, n = v.length;
        let i = n - 1;
        while (i >= 0 && v[i] == null) i--;
        if (i < 0) return null;
        const sign = Math.sign(v[i]);
        let cur = 0, best = 0, run = 0;
        for (let k = 0; k <= i; k++) {
            if (v[k] != null && Math.sign(v[k]) === sign && sign !== 0) { run++; if (run > best) best = run; } else run = 0;
        }
        for (let k = i; k >= 0 && v[k] != null && Math.sign(v[k]) === sign; k--) cur++;
        return { idx: i, sign, cur, record: cur === best && cur >= 12 };
    }

    function oniClass(v) {
        const a = Math.abs(v);
        if (a < 0.5) return 'in the neutral range';
        const size = a >= 2 ? 'very strong' : a >= 1.5 ? 'strong' : a >= 1 ? 'moderate' : 'weak';
        return `in the ${v > 0 ? 'El Niño' : 'La Niña'} range (${size} by value)`;
    }

    function summary(oni, pdo) {
        const out = [];
        const ro = runInfo(oni), rp = runInfo(pdo);
        if (ro) {
            const v = oni.values[ro.idx], gm = oni.gm0 + ro.idx;
            out.push({ cls: 'oni', title: 'ENSO (ONI)', big: fmt(v), body: `${SEAS[gm % 12]} ${Math.floor(gm / 12)}: ${oniClass(v)}. Recent values are estimates, and NOAA declares an El Niño or La Niña with more than this one number.` });
        }
        if (rp) {
            const v = pdo.values[rp.idx], gm = pdo.gm0 + rp.idx, phase = v > 0 ? 'positive' : 'negative';
            const recordTxt = rp.record ? ` That is the longest unbroken ${phase} stretch in the record, which starts in ${Math.floor(pdo.gm0 / 12)}.` : '';
            out.push({ cls: 'pdo', title: 'PDO', big: fmt(v, 2), body: `${gmLabel(gm)}: ${phase} phase, ${rp.cur} month${rp.cur === 1 ? '' : 's'} in a row.${recordTxt}` });
        }
        let note = '';
        if (ro && rp) {
            const vo = oni.values[ro.idx], vp = pdo.values[rp.idx];
            if (Math.abs(vo) >= 0.5 && Math.sign(vo) !== Math.sign(vp)) {
                note = `Right now the two pull in opposite directions for the Northwest: ${vo > 0 ? 'El Niño tends to lean warmer and drier, ' : 'La Niña tends to lean cooler and wetter, '}while a ${vp < 0 ? 'negative' : 'positive'} PDO tends to lean ${vp < 0 ? 'cooler and wetter' : 'warmer'}. When they disagree the signal is weaker, so treat both as small nudges to the odds.`;
            }
        }
        return { cards: out, note };
    }

    function mount(el, data) {
        const oni = series('oni', data.oni, 1), pdo = series('pdo', data.pdo, 2);
        const S = { view: 'oni', years: 50 };   // both indices share the same spans; the default is the last 50 years
        const sum = summary(oni, pdo);

        el.innerHTML = `<div class="ci">
            <div class="ci-stats">${sum.cards.map(c => `<div class="ci-stat ci-stat--${c.cls}"><div class="ci-stat-title">${esc(c.title)}</div><div class="ci-stat-big">${esc(c.big)}</div><p>${esc(c.body)}</p></div>`).join('')}</div>
            ${sum.note ? `<p class="ci-note">${esc(sum.note)}</p>` : ''}
            <div class="ol-ctrl">
                <div class="ol-group"><span class="ol-label">Index</span><div class="ol-chips" role="radiogroup" aria-label="Index" id="ci-view"></div></div>
                <div class="ol-group"><span class="ol-label">Time span</span><div class="ol-chips" role="radiogroup" aria-label="Time span" id="ci-years"></div></div>
            </div>
            <div class="ci-chart" id="ci-chart"></div>
            <p class="ci-hint">Hover or touch the chart for values. ONI is plotted at the middle month of each three-month season. On long spans the PDO is drawn as a 12-month average over the faint monthly values.</p>
            <details class="ci-table"><summary>Recent values</summary><div id="ci-recent"></div></details>
            <p class="ol-credit">Data: <a href="${esc(data.oni.source)}" target="_blank" rel="noopener noreferrer">NOAA CPC, Oceanic Niño Index (v6)</a> and
                <a href="${esc(data.pdo.source)}" target="_blank" rel="noopener noreferrer">NOAA NCEI, ERSST v6 PDO index</a>. Updated monthly.</p></div>`;
        const chartEl = el.querySelector('#ci-chart');

        function chips(id, items, cur, onPick) {
            const box = el.querySelector(id);
            box.innerHTML = items.map(it => `<button type="button" class="ol-chip" role="radio" aria-checked="${it.id === cur}" data-id="${esc(it.id)}">${it.label}</button>`).join('');
            box.querySelectorAll('button').forEach(b => b.addEventListener('click', () => { onPick(b.dataset.id); }));
        }
        function controls() {
            chips('#ci-view', [{ id: 'oni', label: 'ENSO (ONI)' }, { id: 'pdo', label: 'PDO' }, { id: 'both', label: 'Overlay both' }], S.view, id => { S.view = id; controls(); draw(); });
            const yrs = [{ id: '5', label: '5 years' }, { id: '10', label: '10 years' }, { id: '30', label: '30 years' }, { id: '50', label: '50 years' }, { id: '0', label: `Since ${Math.floor(Math.max(oni.gm0, pdo.gm0) / 12)}` }];
            chips('#ci-years', yrs, String(S.years), id => { S.years = +id; controls(); draw(); });
        }

        function draw() {
            const W = Math.max(280, chartEl.clientWidth || 600), H = Math.round(Math.min(400, Math.max(260, W * 0.42)));
            const both = S.view === 'both', shown = both ? [oni, pdo] : [S.view === 'pdo' ? pdo : oni];
            const last = Math.max(...shown.map(s => s.last));
            const firstAvail = Math.max(oni.gm0, pdo.gm0);   // the same start for every view, so the two indices cover the same years
            const g0 = S.years ? Math.max(firstAvail, last - S.years * 12 + 1) : firstAvail;
            const L = 46, R = both ? 46 : 14, T = 14, B = 30, pw = W - L - R, ph = H - T - B;
            const x = gm => L + pw * (gm - g0) / Math.max(1, last - g0);
            // symmetric y range per series so zero lines up in the overlay
            const yr = s => {
                let m = 0;
                for (let g = g0; g <= last; g++) { const v = s.at(g); if (v != null) m = Math.max(m, Math.abs(v)); }
                const step = m > 4 ? 2 : 1;
                return Math.max(step * 2, Math.ceil(m / step) * step);
            };
            const range = {}; shown.forEach(s => { range[s.key] = yr(s); });
            const y = (s, v) => T + ph / 2 - (v / range[s.key]) * (ph / 2);
            // On long spans the monthly PDO is too jagged to read, so it is drawn faintly under a 12-month average
            const smooth = s => s.key === 'pdo' && last - g0 > 400;
            let g = '';
            // grid and left axis (first series), right axis (second, in overlay)
            const axisFor = (s, side) => {
                const r = range[s.key], step = r > 6 ? 2 : r > 3 ? 1 : 0.5, col = both ? (s.key === 'oni' ? C.oni : C.pdo) : C.muted;
                let a = '';
                for (let v = -r; v <= r + 1e-9; v += step) {
                    const yy = y(s, v);
                    if (side === 'L') a += `<line x1="${L}" y1="${yy}" x2="${L + pw}" y2="${yy}" stroke="${v === 0 ? C.axis : C.grid}" stroke-width="${v === 0 ? 1.4 : 1}"/>`;
                    a += `<text x="${side === 'L' ? L - 6 : L + pw + 6}" y="${yy + 4}" text-anchor="${side === 'L' ? 'end' : 'start'}" font-size="11" fill="${col}">${v === 0 ? '0' : fmt(v, step < 1 ? 1 : 0)}</text>`;
                }
                a += `<text transform="translate(${side === 'L' ? 11 : W - 11} ${T + ph / 2}) rotate(-90)" text-anchor="middle" font-size="11" fill="${col}">${s.key === 'oni' ? 'ONI (°C)' : 'PDO index'}</text>`;
                return a;
            };
            g += axisFor(shown[0], 'L');
            if (both) g += axisFor(shown[1], 'R');
            // x axis ticks at January of round years
            const span = (last - g0) / 12, step = span <= 6.5 ? 1 : span <= 13 ? 2 : span <= 35 ? 5 : span <= 80 ? 10 : 20;
            for (let yr0 = Math.ceil(g0 / 12 / step) * step; yr0 * 12 <= last; yr0 += step) {
                const xx = x(yr0 * 12);
                g += `<line x1="${xx}" y1="${T}" x2="${xx}" y2="${T + ph}" stroke="${C.grid}"/><text x="${xx}" y="${H - 10}" text-anchor="middle" font-size="11" fill="${C.muted}">${yr0}</text>`;
            }
            // ENSO thresholds in the ONI-only view
            if (!both && shown[0].key === 'oni') {
                [0.5, -0.5].forEach(t => { g += `<line x1="${L}" y1="${y(oni, t)}" x2="${L + pw}" y2="${y(oni, t)}" stroke="${t > 0 ? C.warm : C.cool}" stroke-dasharray="4 4" opacity=".55"/>`; });
                g += `<text x="${L + 6}" y="${y(oni, 0.5) - 4}" font-size="10.5" fill="${C.warm}">El Niño range (≥ +0.5)</text><text x="${L + 6}" y="${y(oni, -0.5) + 13}" font-size="10.5" fill="${C.cool}">La Niña range (≤ −0.5)</text>`;
            }
            // data
            const path = (s, get) => {
                get = get || s.at;
                let d = '', pen = false;
                for (let gm = g0; gm <= last; gm++) {
                    const v = get(gm);
                    if (v == null) { pen = false; continue; }
                    d += `${pen ? 'L' : 'M'}${x(gm).toFixed(1)},${y(s, v).toFixed(1)}`; pen = true;
                }
                return d;
            };
            if (!both) {
                const s = shown[0], z = y(s, 0), sm = smooth(s), d = path(s, sm ? s.smAt : s.at);
                const area = d + `L${x(Math.min(last, s.last)).toFixed(1)},${z}L${x(Math.max(g0, s.gm0)).toFixed(1)},${z}Z`;
                g += `<clipPath id="ci-up"><rect x="${L}" y="${T}" width="${pw}" height="${z - T}"/></clipPath><clipPath id="ci-dn"><rect x="${L}" y="${z}" width="${pw}" height="${T + ph - z}"/></clipPath>`;
                g += `<path d="${area}" fill="${C.warm}" opacity=".35" clip-path="url(#ci-up)"/><path d="${area}" fill="${C.cool}" opacity=".35" clip-path="url(#ci-dn)"/>`;
                if (sm) g += `<path d="${path(s)}" fill="none" stroke="#1e3c72" stroke-width="0.8" opacity=".3"/>`;
                g += `<path d="${d}" fill="none" stroke="#1e3c72" stroke-width="${sm ? 2 : 1.6}" stroke-linejoin="round"/>`;
            } else {
                shown.forEach(s => {
                    const col = s.key === 'oni' ? C.oni : C.pdo, sm = smooth(s);
                    if (sm) g += `<path d="${path(s)}" fill="none" stroke="${col}" stroke-width="0.8" opacity=".3"/>`;
                    g += `<path d="${path(s, sm ? s.smAt : s.at)}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round"/>`;
                });
            }
            chartEl.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(shown.map(s => s.name).join(' and '))}, ${esc(gmLabel(g0))} to ${esc(gmLabel(last))}" font-family="system-ui,Segoe UI,Arial,sans-serif" style="touch-action:pan-y">
                <rect width="${W}" height="${H}" fill="#fff"/>${g}<g id="ci-hov"></g><rect id="ci-hit" x="${L}" y="${T}" width="${pw}" height="${ph}" fill="transparent"/></svg><div class="ci-tip" id="ci-tip" hidden></div>`;

            // Hovering only repaints a small overlay (never the chart), so touch dragging is not interrupted
            const tip = chartEl.querySelector('#ci-tip'), hit = chartEl.querySelector('#ci-hit'), hov = chartEl.querySelector('#ci-hov');
            let cur = null;
            const colorOf = s => (both ? (s.key === 'oni' ? C.oni : C.pdo) : '#1e3c72');
            const paint = gm => {
                if (gm === cur) return;
                cur = gm;
                const xx = x(gm);
                let o = `<line x1="${xx}" y1="${T}" x2="${xx}" y2="${T + ph}" stroke="#1e3c72" stroke-width="1"/>`, rows = '';
                shown.forEach(s => {
                    const v = s.at(gm);
                    if (v == null) return;
                    const sm = smooth(s), av = sm ? s.smAt(gm) : null;
                    o += `<circle cx="${xx}" cy="${y(s, sm && av != null ? av : v)}" r="4" fill="${colorOf(s)}" stroke="#fff" stroke-width="1.5"/>`;
                    const when = s.key === 'oni' ? `${SEAS[gm % 12]} ${Math.floor(gm / 12)}` : gmLabel(gm);
                    rows += `<div><span class="ci-dot" style="background:${colorOf(s)}"></span><strong>${s.key === 'oni' ? 'ONI' : 'PDO'}</strong> ${esc(when)}: <strong>${fmt(v, s.nd)}</strong>${av != null ? ` &middot; 12-month avg <strong>${fmt(av, s.nd)}</strong>` : ''}</div>`;
                });
                hov.innerHTML = o;
                if (!rows) { tip.hidden = true; return; }
                tip.innerHTML = rows; tip.hidden = false;
                tip.style.left = Math.min(W - tip.offsetWidth - 4, Math.max(4, xx + 10)) + 'px';
                tip.style.top = (T + 6) + 'px';
            };
            const clear = () => { cur = null; hov.innerHTML = ''; tip.hidden = true; };
            const move = e => {
                const r = hit.getBoundingClientRect();
                paint(Math.min(last, Math.max(g0, Math.round(g0 + (e.clientX - r.left) / r.width * (last - g0)))));
            };
            hit.addEventListener('pointermove', move);
            hit.addEventListener('pointerdown', move);
            hit.addEventListener('pointerleave', clear);
        }

        function recent() {
            const rows = [];
            const lastGm = Math.max(oni.last, pdo.last);
            for (let gm = lastGm; gm > lastGm - 12; gm--) {
                rows.push(`<tr><td>${esc(gmLabel(gm))}</td><td>${fmt(oni.at(gm), 1)}</td><td>${fmt(pdo.at(gm), 2)}</td></tr>`);
            }
            el.querySelector('#ci-recent').innerHTML = `<table><thead><tr><th>Month</th><th>ONI (3-month, centered)</th><th>PDO</th></tr></thead><tbody>${rows.join('')}</tbody></table>`;
        }

        controls(); draw(); recent();
        let timer = null, lastW = chartEl.clientWidth;
        window.addEventListener('resize', () => { clearTimeout(timer); timer = setTimeout(() => { if (chartEl.clientWidth !== lastW) { lastW = chartEl.clientWidth; draw(); } }, 120); });
    }

    document.querySelectorAll('.ci-mount').forEach(el => {
        fetch(BASE + 'data/climate_indices.json', { cache: 'no-cache' })
            .then(r => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
            .then(d => mount(el, d))
            .catch(() => { el.innerHTML = '<p class="ol-fail">The index data could not be loaded right now. See the <a href="https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/" target="_blank" rel="noopener noreferrer">CPC ONI table</a> and the <a href="https://www.ncei.noaa.gov/access/monitoring/pdo/" target="_blank" rel="noopener noreferrer">NCEI PDO page</a>.</p>'; });
    });
}());
