// Home-page point-forecast meteogram: NBM, HRRR and HRDPS at each ski area (assets/data/meteograms.json, scripts/meteograms.py).
// Plain SVG, no chart library. Values are model grid cells, not downscaled; the page says so.
(function () {
    const root = document.getElementById('meteogram');
    if (!root) return;
    const COLORS = { nbm: '#1e3c72', hrrr: '#d97706', hrdps: '#0d9488' };
    const NAMES = { nbm: 'NBM', hrrr: 'HRRR', hrdps: 'HRDPS' };
    const PANELS = [
        { key: 'temp_f', label: 'Temperature (°F)', fmt: v => v.toFixed(0) + '°F', ref: 32, refLabel: '32°F' },
        { key: 'wind_mph', label: 'Wind speed (mph)', fmt: v => v.toFixed(0) + ' mph', min0: true },
        { key: 'rh', label: 'Relative humidity (%)', fmt: v => v.toFixed(0) + '%', lo: 0, hi: 100 },
        { key: 'precip_in', label: 'Precipitation (in per hour)', fmt: v => v.toFixed(2) + ' in', bars: true, min0: true },
    ];
    const W = 720, PH = 104, GAP = 22, L = 46, R = 10, T = 8, B = 36;
    const TZ = 'America/Los_Angeles';
    const hourFmt = new Intl.DateTimeFormat('en-US', { timeZone: TZ, hour: 'numeric', hour12: true });
    const dayFmt = new Intl.DateTimeFormat('en-US', { timeZone: TZ, weekday: 'short', month: 'short', day: 'numeric' });
    const fullFmt = new Intl.DateTimeFormat('en-US', { timeZone: TZ, weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', hour12: true });
    const hourNum = new Intl.DateTimeFormat('en-US', { timeZone: TZ, hour: 'numeric', hourCycle: 'h23' });
    const el = (tag, attrs, text) => { const e = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; return e; };
    const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

    const select = root.querySelector('#mg-site'), chips = root.querySelector('#mg-models'), host = root.querySelector('#mg-chart'),
        tip = root.querySelector('#mg-tip'), meta = root.querySelector('#mg-meta');
    let data = null;
    const on = { nbm: true, hrrr: true, hrdps: true };
    const stored = (() => { try { return localStorage.getItem('mg-site'); } catch (e) { return null; } })();

    function init(d) {
        data = d;
        select.innerHTML = d.sites.map(s => `<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
        if (stored && d.sites.some(s => s.name === stored)) select.value = stored;
        chips.innerHTML = Object.keys(d.models).map(m => `<label class="mg-chip"><input type="checkbox" data-m="${m}" checked><span class="mg-sw" style="background:${COLORS[m]}"></span>${NAMES[m]}</label>`).join('');
        select.addEventListener('change', () => { try { localStorage.setItem('mg-site', select.value); } catch (e) { /* ignore */ } draw(); });
        chips.addEventListener('change', e => { on[e.target.dataset.m] = e.target.checked; draw(); });
        const when = new Intl.DateTimeFormat('en-US', { timeZone: TZ, weekday: 'short', hour: 'numeric', hour12: true });
        meta.textContent = 'Model runs: ' + Object.keys(d.models).map(m => `${NAMES[m]} ${when.format(new Date(d.models[m].cycle_utc))}`).join(' · ') + ' (Pacific time).';
        draw();
    }

    function draw() {
        const site = select.value, models = Object.keys(data.models).filter(m => on[m] && data.models[m].sites[site]);
        host.innerHTML = '';
        if (!models.length) { host.textContent = 'Select at least one model.'; return; }
        const t0 = Math.min(...models.map(m => +new Date(data.models[m].time_utc[0])));
        const t1 = Math.max(...models.map(m => +new Date(data.models[m].time_utc.slice(-1)[0])));
        const x = t => L + (t - t0) / (t1 - t0) * (W - L - R);
        const H = T + PANELS.length * PH + (PANELS.length - 1) * GAP + B;
        const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, class: 'mg-svg', role: 'img', 'aria-label': 'Forecast meteogram for ' + site });
        const idx = {};   // per model: ms time -> array index, for the hover lookup

        // time axis grid: a tick every 6 local hours, bold line at local midnight
        const ticks = [];
        for (let t = Math.ceil(t0 / 36e5) * 36e5; t <= t1; t += 36e5) if (+hourNum.format(new Date(t)) % 6 === 0) ticks.push(t);

        PANELS.forEach((p, pi) => {
            const y0 = T + pi * (PH + GAP);
            let lo = Infinity, hi = -Infinity;
            models.forEach(m => data.models[m].sites[site][p.key].forEach(v => { if (v != null) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }));
            if (!isFinite(lo)) { lo = 0; hi = 1; }
            if (p.ref != null) { lo = Math.min(lo, p.ref); hi = Math.max(hi, p.ref); }
            if (p.min0) lo = 0;
            if (p.lo != null) lo = p.lo;
            if (p.hi != null) hi = p.hi;
            if (p.key === 'precip_in') hi = Math.max(hi, 0.1);
            if (hi - lo < 1e-6) hi = lo + 1;
            const pad = p.hi != null || p.bars ? 0 : (hi - lo) * 0.08;
            lo = p.min0 || p.lo != null ? lo : lo - pad; hi += pad;
            const y = v => y0 + PH - (v - lo) / (hi - lo) * PH;
            svg.appendChild(el('rect', { x: L, y: y0, width: W - L - R, height: PH, fill: 'none', stroke: '#e2e8f0' }));
            ticks.forEach(t => {
                const mid = +hourNum.format(new Date(t)) === 0;
                svg.appendChild(el('line', { x1: x(t), x2: x(t), y1: y0, y2: y0 + PH, stroke: mid ? '#94a3b8' : '#eef2f7', 'stroke-width': mid ? 1 : 1 }));
            });
            // y labels: low, high, reference
            [lo, hi].forEach(v => svg.appendChild(el('text', { x: L - 5, y: y(v) + (v === hi ? 9 : 0), 'text-anchor': 'end', class: 'mg-ax' }, (p.key === 'precip_in' ? v.toFixed(2) : v.toFixed(0)))));
            if (p.ref != null && p.ref > lo && p.ref < hi) {
                svg.appendChild(el('line', { x1: L, x2: W - R, y1: y(p.ref), y2: y(p.ref), stroke: '#64748b', 'stroke-dasharray': '4 3' }));
                svg.appendChild(el('text', { x: L - 5, y: y(p.ref) + 3, 'text-anchor': 'end', class: 'mg-ax' }, p.refLabel));
            }
            svg.appendChild(el('text', { x: L, y: y0 - 3, class: 'mg-pt' }, p.label));
            models.forEach((m, mi) => {
                const md = data.models[m], vals = md.sites[site][p.key], times = md.time_utc;
                if (!idx[m]) { idx[m] = {}; times.forEach((t, i) => { idx[m][+new Date(t)] = i; }); }
                if (p.bars) {
                    const bw = Math.max(1.2, (W - L - R) / (t1 - t0) * 36e5 / (models.length + 0.6));
                    vals.forEach((v, i) => {
                        if (v == null || v <= 0) return;
                        const bx = x(+new Date(times[i])) - bw * models.length / 2 + mi * bw;
                        svg.appendChild(el('rect', { x: bx, y: y(v), width: bw, height: y0 + PH - y(v), fill: COLORS[m], opacity: 0.9 }));
                    });
                } else {
                    let d = '', pen = false;
                    vals.forEach((v, i) => {
                        if (v == null) { pen = false; return; }
                        d += (pen ? 'L' : 'M') + x(+new Date(times[i])).toFixed(1) + ' ' + y(v).toFixed(1);
                        pen = true;
                    });
                    svg.appendChild(el('path', { d, fill: 'none', stroke: COLORS[m], 'stroke-width': 1.8, 'stroke-linejoin': 'round' }));
                }
            });
        });

        // bottom axis
        const yb = T + PANELS.length * PH + (PANELS.length - 1) * GAP;
        ticks.forEach(t => {
            const h = +hourNum.format(new Date(t));
            if (h === 0) {
                svg.appendChild(el('text', { x: x(t) + 3, y: yb + 28, class: 'mg-day' }, dayFmt.format(new Date(t))));
            }
            if (h % 12 === 0 || (t1 - t0) < 30 * 36e5) svg.appendChild(el('text', { x: x(t), y: yb + 13, 'text-anchor': 'middle', class: 'mg-ax' }, hourFmt.format(new Date(t))));
        });
        const cross = el('line', { y1: T, y2: yb, stroke: '#0f172a', 'stroke-width': 1, opacity: 0 });
        svg.appendChild(cross);
        svg.appendChild(el('rect', { x: L, y: T, width: W - L - R, height: yb - T, fill: 'transparent', class: 'mg-hit' }));
        host.appendChild(svg);

        function hover(ev) {
            const r = svg.getBoundingClientRect();
            const px = (ev.clientX - r.left) / r.width * W;
            const t = t0 + Math.min(Math.max((px - L) / (W - L - R), 0), 1) * (t1 - t0);
            const hr = Math.round(t / 36e5) * 36e5;
            cross.setAttribute('x1', x(hr)); cross.setAttribute('x2', x(hr)); cross.setAttribute('opacity', 0.5);
            let html = `<strong>${esc(fullFmt.format(new Date(hr)))}</strong><table><tr><td></td><td>Temp</td><td>Wind</td><td>RH</td><td>Precip</td></tr>`;
            models.forEach(m => {
                const i = idx[m][hr];
                if (i == null) return;
                const s = data.models[m].sites[site];
                html += `<tr><td><span class="mg-sw" style="background:${COLORS[m]}"></span>${NAMES[m]}</td>` + PANELS.map(p => `<td>${s[p.key][i] == null ? '&ndash;' : p.fmt(s[p.key][i])}</td>`).join('') + '</tr>';
            });
            html += '</table>';
            tip.innerHTML = html;
            tip.hidden = false;
            const hostR = host.getBoundingClientRect();
            const left = ev.clientX - hostR.left + 14;
            tip.style.left = Math.min(left, hostR.width - tip.offsetWidth - 4) + 'px';
            tip.style.top = Math.max(ev.clientY - hostR.top - tip.offsetHeight - 10, 0) + 'px';
        }
        svg.addEventListener('pointermove', hover);
        svg.addEventListener('pointerdown', hover);
        svg.addEventListener('pointerleave', () => { cross.setAttribute('opacity', 0); tip.hidden = true; });

        const km = models.map(m => `${NAMES[m]} ${data.models[m].sites[site].grid_km} km`).join(', ');
        root.querySelector('#mg-grid').textContent = `Grid point is ${km} from the ski area.`;
    }

    const url = root.dataset.src;
    fetch(url, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : Promise.reject(r.status))).then(init)
        .catch(() => { host.textContent = 'The point forecast is not available right now.'; });
})();
