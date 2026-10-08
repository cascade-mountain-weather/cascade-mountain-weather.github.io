// Home-page point-forecast meteogram: NBM, HRRR and HRDPS at each ski area (assets/data/meteograms.json, scripts/meteograms.py).
// Plain SVG, no chart library. Values are model grid cells, not downscaled; the page says so.
// Hover (or tap) for values; drag across the chart to zoom to a time window; double-click or "Reset zoom" to go back.
(function () {
    const root = document.getElementById('meteogram');
    if (!root) return;
    const COLORS = { nbm: '#1e3c72', hrrr: '#d97706', hrdps: '#0d9488' };
    const NAMES = { nbm: 'NBM', hrrr: 'HRRR', hrdps: 'HRDPS' };
    const MPH_TO_MS = 0.44704, IN_TO_MM = 25.4;
    // Data are stored in US units (F, mph, inches). `conv` turns them into the chosen system.
    const PANELS = [
        { key: 'temp_f', title: { us: 'Temperature (°F)', metric: 'Temperature (°C)' }, conv: { us: v => v, metric: v => (v - 32) * 5 / 9 }, dec: { us: 0, metric: 0 }, unit: { us: '°F', metric: '°C' }, ref: { us: 32, metric: 0 } },
        { key: 'wind_mph', title: { us: 'Wind speed (mph)', metric: 'Wind speed (m/s)' }, conv: { us: v => v, metric: v => v * MPH_TO_MS }, dec: { us: 0, metric: 1 }, unit: { us: ' mph', metric: ' m/s' }, min0: true },
        { key: 'rh', title: { us: 'Relative humidity (%)', metric: 'Relative humidity (%)' }, conv: { us: v => v, metric: v => v }, dec: { us: 0, metric: 0 }, unit: { us: '%', metric: '%' }, lo: 0, hi: 100 },
        { key: 'precip_in', title: { us: 'Precipitation (in per hour)', metric: 'Precipitation (mm per hour)' }, conv: { us: v => v, metric: v => v * IN_TO_MM }, dec: { us: 2, metric: 1 }, unit: { us: ' in', metric: ' mm' }, bars: true, min0: true, minHi: { us: 0.1, metric: 2.5 } },
    ];
    const W = 720, PH = 104, GAP = 24, L = 46, R = 10, T = 22, B = 38, HOUR = 36e5;
    const TZ = 'America/Los_Angeles';
    const hourFmt = new Intl.DateTimeFormat('en-US', { timeZone: TZ, hour: 'numeric', hour12: true });
    const dayFmt = new Intl.DateTimeFormat('en-US', { timeZone: TZ, weekday: 'short', month: 'short', day: 'numeric' });
    const fullFmt = new Intl.DateTimeFormat('en-US', { timeZone: TZ, weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', hour12: true });
    const hourNum = new Intl.DateTimeFormat('en-US', { timeZone: TZ, hour: 'numeric', hourCycle: 'h23' });
    const el = (tag, attrs, text) => { const e = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; return e; };
    const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
    const store = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { /* ignore */ } return null; };

    const select = root.querySelector('#mg-site'), chips = root.querySelector('#mg-models'), host = root.querySelector('#mg-chart'),
        tip = root.querySelector('#mg-tip'), meta = root.querySelector('#mg-meta'), reset = root.querySelector('#mg-reset'),
        unitsEl = root.querySelector('#mg-units');
    let data = null, zoom = null, units = store('mg-units') === 'metric' ? 'metric' : 'us';
    const on = { nbm: true, hrrr: true, hrdps: true };

    function init(d) {
        data = d;
        select.innerHTML = d.sites.map(s => `<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
        const saved = store('mg-site');
        if (saved && d.sites.some(s => s.name === saved)) select.value = saved;
        chips.innerHTML = Object.keys(d.models).map(m => `<label class="mg-chip"><input type="checkbox" data-m="${m}" checked><span class="mg-sw" style="background:${COLORS[m]}"></span>${NAMES[m]}</label>`).join('');
        unitsEl.querySelector(`input[value="${units}"]`).checked = true;
        select.addEventListener('change', () => { store('mg-site', select.value); draw(); });
        chips.addEventListener('change', e => { on[e.target.dataset.m] = e.target.checked; draw(); });
        unitsEl.addEventListener('change', e => { units = e.target.value; store('mg-units', units); draw(); });
        reset.addEventListener('click', () => { zoom = null; draw(); });
        const when = new Intl.DateTimeFormat('en-US', { timeZone: TZ, weekday: 'short', hour: 'numeric', hour12: true });
        meta.textContent = 'Model runs: ' + Object.keys(d.models).map(m => `${NAMES[m]} ${when.format(new Date(d.models[m].cycle_utc))}`).join(' · ') + ' (Pacific time).';
        draw();
    }

    function draw() {
        const site = select.value, models = Object.keys(data.models).filter(m => on[m] && data.models[m].sites[site]);
        host.innerHTML = '';
        host.appendChild(tip);                 // the tooltip lives inside the chart box; clearing it must not drop it
        tip.hidden = true;
        if (!models.length) { host.insertBefore(document.createTextNode('Select at least one model.'), tip); return; }
        const full0 = Math.min(...models.map(m => +new Date(data.models[m].time_utc[0])));
        const full1 = Math.max(...models.map(m => +new Date(data.models[m].time_utc.slice(-1)[0])));
        let t0 = full0, t1 = full1;
        if (zoom) { t0 = Math.max(full0, zoom[0]); t1 = Math.min(full1, zoom[1]); if (t1 - t0 < 3 * HOUR) { zoom = null; t0 = full0; t1 = full1; } }
        reset.hidden = !zoom;
        const x = t => L + (t - t0) / (t1 - t0) * (W - L - R);
        const inv = px => t0 + Math.min(Math.max((px - L) / (W - L - R), 0), 1) * (t1 - t0);
        const yb = T + PANELS.length * PH + (PANELS.length - 1) * GAP;
        const svg = el('svg', { viewBox: `0 0 ${W} ${yb + B}`, class: 'mg-svg', role: 'img', 'aria-label': 'Forecast meteogram for ' + site });
        const defs = el('defs', {});
        PANELS.forEach((p, pi) => { const c = el('clipPath', { id: 'mg-clip' + pi }); c.appendChild(el('rect', { x: L, y: T + pi * (PH + GAP), width: W - L - R, height: PH })); defs.appendChild(c); });
        svg.appendChild(defs);

        // time axis: pick a tick step so the view has roughly 5 to 10 ticks; a bold line at local midnight
        const span = (t1 - t0) / HOUR;
        const step = [1, 2, 3, 6, 12, 24].find(s => span / s <= 10) || 24;
        const ticks = [];
        for (let t = Math.ceil(t0 / HOUR) * HOUR; t <= t1; t += HOUR) if (+hourNum.format(new Date(t)) % step === 0) ticks.push(t);

        const hov = [];          // per panel: {y fn, conv} so the hover dots can be placed
        PANELS.forEach((p, pi) => {
            const y0 = T + pi * (PH + GAP), cv = p.conv[units];
            let lo = Infinity, hi = -Infinity;
            models.forEach(m => {
                const md = data.models[m], vals = md.sites[site][p.key];
                md.time_utc.forEach((t, i) => { const tt = +new Date(t); if (vals[i] != null && tt >= t0 && tt <= t1) { const v = cv(vals[i]); lo = Math.min(lo, v); hi = Math.max(hi, v); } });
            });
            if (!isFinite(lo)) { lo = 0; hi = 1; }
            const ref = p.ref ? p.ref[units] : null;
            if (ref != null) { lo = Math.min(lo, ref); hi = Math.max(hi, ref); }
            if (p.min0) lo = 0;
            if (p.lo != null) lo = p.lo;
            if (p.hi != null) hi = p.hi;
            if (p.minHi) hi = Math.max(hi, p.minHi[units]);
            if (hi - lo < 1e-6) hi = lo + 1;
            if (p.lo == null && !p.min0) lo -= (hi - lo) * 0.08;
            if (p.hi == null) hi += (hi - lo) * 0.08;
            const y = v => y0 + PH - (v - lo) / (hi - lo) * PH;
            hov.push({ y, cv });
            svg.appendChild(el('rect', { x: L, y: y0, width: W - L - R, height: PH, fill: 'none', stroke: '#e2e8f0' }));
            ticks.forEach(t => {
                const mid = +hourNum.format(new Date(t)) === 0;
                svg.appendChild(el('line', { x1: x(t), x2: x(t), y1: y0, y2: y0 + PH, stroke: mid ? '#94a3b8' : '#eef2f7' }));
            });
            const dec = p.dec[units];
            [lo, hi].forEach(v => {
                if (ref != null && v === lo && Math.abs(y(ref) - y(lo)) < 14) return;      // the reference label would sit on top of it
                svg.appendChild(el('text', { x: L - 5, y: y(v) + (v === hi ? 9 : 0), 'text-anchor': 'end', class: 'mg-ax' }, v.toFixed(p.key === 'precip_in' ? dec : 0)));
            });
            if (ref != null && ref > lo && ref < hi) {
                svg.appendChild(el('line', { x1: L, x2: W - R, y1: y(ref), y2: y(ref), stroke: '#64748b', 'stroke-dasharray': '4 3' }));
                svg.appendChild(el('text', { x: L - 5, y: y(ref) + 3, 'text-anchor': 'end', class: 'mg-ax' }, ref + p.unit[units]));
            }
            svg.appendChild(el('text', { x: L, y: y0 - 6, class: 'mg-pt' }, p.title[units]));
            const g = el('g', { 'clip-path': `url(#mg-clip${pi})` });
            models.forEach((m, mi) => {
                const md = data.models[m], vals = md.sites[site][p.key], times = md.time_utc;
                if (p.bars) {
                    const bw = Math.max(1.2, (W - L - R) / (t1 - t0) * HOUR / (models.length + 0.6));
                    vals.forEach((v, i) => {
                        if (v == null || v <= 0) return;
                        const tt = +new Date(times[i]);
                        if (tt < t0 - HOUR || tt > t1 + HOUR) return;
                        const c = cv(v);
                        g.appendChild(el('rect', { x: x(tt) - bw * models.length / 2 + mi * bw, y: y(c), width: bw, height: y0 + PH - y(c), fill: COLORS[m], opacity: 0.9 }));
                    });
                } else {
                    let d = '', pen = false;
                    vals.forEach((v, i) => {
                        if (v == null) { pen = false; return; }
                        d += (pen ? 'L' : 'M') + x(+new Date(times[i])).toFixed(1) + ' ' + y(cv(v)).toFixed(1);
                        pen = true;
                    });
                    g.appendChild(el('path', { d, fill: 'none', stroke: COLORS[m], 'stroke-width': 1.8, 'stroke-linejoin': 'round' }));
                }
            });
            svg.appendChild(g);
        });

        // bottom axis: an hour label per tick, a day label at each local midnight (and at the left edge if midnight is far away)
        let firstMid = null;
        ticks.forEach(t => {
            const h = +hourNum.format(new Date(t));
            if (h === 0) { svg.appendChild(el('text', { x: x(t) + 3, y: yb + 30, class: 'mg-day' }, dayFmt.format(new Date(t)))); if (firstMid == null) firstMid = x(t); }
            svg.appendChild(el('text', { x: x(t), y: yb + 14, 'text-anchor': 'middle', class: 'mg-ax' }, hourFmt.format(new Date(t))));
        });
        if (firstMid == null || firstMid - L > 110) svg.appendChild(el('text', { x: L + 2, y: yb + 30, class: 'mg-day' }, dayFmt.format(new Date(t0))));

        // hover marker, drag-zoom selection, and a transparent layer over the plots to catch the pointer
        const cross = el('line', { y1: T, y2: yb, stroke: '#0f172a', 'stroke-width': 1, opacity: 0 });
        const dots = hov.map(() => models.map(m => el('circle', { r: 3.2, fill: COLORS[m], stroke: '#fff', 'stroke-width': 1, opacity: 0 })));
        const sel = el('rect', { y: T, height: yb - T, fill: '#2a5298', opacity: 0.18, visibility: 'hidden' });
        svg.appendChild(cross); dots.forEach(r => r.forEach(c => svg.appendChild(c))); svg.appendChild(sel);
        svg.appendChild(el('rect', { x: L, y: T, width: W - L - R, height: yb - T, fill: 'transparent', class: 'mg-hit' }));
        host.insertBefore(svg, tip);

        const toX = ev => { const r = svg.getBoundingClientRect(); return (ev.clientX - r.left) / r.width * W; };
        function hover(ev) {
            const hr = Math.round(inv(toX(ev)) / HOUR) * HOUR;
            cross.setAttribute('x1', x(hr)); cross.setAttribute('x2', x(hr)); cross.setAttribute('opacity', 0.5);
            let html = `<strong>${esc(fullFmt.format(new Date(hr)))}</strong><table><tr><td></td>${PANELS.map(p => `<td>${esc(p.title[units].split(' (')[0].replace('Relative humidity', 'RH').replace('Temperature', 'Temp').replace('Wind speed', 'Wind').replace('Precipitation', 'Precip'))}</td>`).join('')}</tr>`;
            models.forEach((m, mi) => {
                const i = data.models[m].time_utc.findIndex(t => +new Date(t) === hr);
                dots.forEach((row, pi) => row[mi].setAttribute('opacity', 0));
                if (i < 0) return;
                const s = data.models[m].sites[site];
                html += `<tr><td><span class="mg-sw" style="background:${COLORS[m]}"></span>${NAMES[m]}</td>` + PANELS.map((p, pi) => {
                    const v = s[p.key][i];
                    if (v == null) return '<td>&ndash;</td>';
                    const c = p.conv[units](v);
                    const dot = dots[pi][mi]; dot.setAttribute('cx', x(hr)); dot.setAttribute('cy', hov[pi].y(c)); dot.setAttribute('opacity', 1);
                    return `<td>${c.toFixed(p.dec[units]) + p.unit[units]}</td>`;
                }).join('') + '</tr>';
            });
            tip.innerHTML = html + '</table>';
            tip.hidden = false;
            const hostR = host.getBoundingClientRect();
            const px = ev.clientX - hostR.left;
            tip.style.left = Math.max(0, px + 14 + tip.offsetWidth > hostR.width ? px - tip.offsetWidth - 14 : px + 14) + 'px';
            tip.style.top = Math.max(ev.clientY - hostR.top - tip.offsetHeight - 10, 0) + 'px';
        }
        function clearHover() { cross.setAttribute('opacity', 0); dots.forEach(r => r.forEach(c => c.setAttribute('opacity', 0))); tip.hidden = true; }

        let drag = null;
        svg.addEventListener('pointerdown', ev => {
            drag = { x0: Math.min(Math.max(toX(ev), L), W - R), moved: false };
            svg.setPointerCapture(ev.pointerId);
            hover(ev);
        });
        svg.addEventListener('pointermove', ev => {
            if (!drag) { hover(ev); return; }
            const xx = Math.min(Math.max(toX(ev), L), W - R);
            if (Math.abs(xx - drag.x0) > 6) {
                drag.moved = true; clearHover();
                sel.setAttribute('x', Math.min(drag.x0, xx)); sel.setAttribute('width', Math.abs(xx - drag.x0)); sel.setAttribute('visibility', 'visible');
            } else if (!drag.moved) hover(ev);
        });
        svg.addEventListener('pointerup', ev => {
            if (!drag) return;
            const xx = Math.min(Math.max(toX(ev), L), W - R), d = drag; drag = null;
            sel.setAttribute('visibility', 'hidden');
            if (d.moved && Math.abs(xx - d.x0) > 10) { zoom = [inv(Math.min(d.x0, xx)), inv(Math.max(d.x0, xx))]; draw(); }
        });
        svg.addEventListener('pointerleave', () => { if (!drag) clearHover(); });
        svg.addEventListener('pointercancel', () => { drag = null; sel.setAttribute('visibility', 'hidden'); clearHover(); });
        svg.addEventListener('dblclick', () => { if (zoom) { zoom = null; draw(); } });

        const km = models.map(m => `${NAMES[m]} ${data.models[m].sites[site].grid_km} km`).join(', ');
        root.querySelector('#mg-grid').textContent = `Grid point is ${km} from the ski area.`;
    }

    const url = root.dataset.src;
    fetch(url, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : Promise.reject(r.status))).then(init)
        .catch(() => { host.textContent = 'The point forecast is not available right now.'; });
})();
