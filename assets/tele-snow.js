// Teleconnections and Washington snow: what SNOTEL stations did after each MJO phase, PNA class or ENSO class (Nov-May, 1992-2026).
// Data: assets/data/tele_composites.json (scripts/tele_export.py). Mount: <div class="ts-mount"></div>.
// Everything is a ratio to the station's normal (snowfall, rain, big days) or degrees F (temperature anomaly).
// The lag slider picks the center of a hump: nearby lags are blended with Gaussian weights (width set by "spread"), so the
// numbers do not jump around from one lag to the next, and the best lag stands out as the top of the curve.
(function () {
    'use strict';
    const BASE = (document.currentScript && document.currentScript.src || '').replace(/[^/]*$/, '');
    const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    const NS = 'http://www.w3.org/2000/svg';
    const METRICS = [['swe', 'Snowfall'], ['bigsnow', 'Big snow days'], ['tanom', 'Temperature'], ['rain', 'Rain'], ['bigwet', 'Big precipitation days']];
    const METRIC_NOTE = {
        swe: 'New snow (daily gain in snow water equivalent) compared with the station&rsquo;s November&ndash;May average. 1.30 means 30% more snow than normal.',
        bigsnow: 'How often a day brings a big snowfall (a day in the station&rsquo;s top 10% of snow days), relative to normal.',
        tanom: 'Daily average temperature minus the station&rsquo;s normal for the date, in &deg;F.',
        rain: 'Precipitation that did not add to the snowpack (rain or melt-out), relative to normal.',
        bigwet: 'How often a day is in the station&rsquo;s top 10% of wet days, snow or rain, relative to normal.',
    };
    const INDEX = {
        mjo: { label: 'MJO phase', short: 'MJO', lag: 8, lagLabel: 'Days after the phase is in place', lagNote: 'The MJO&rsquo;s effect on the Northwest arrives days after the phase is in place, so the lag is how many days later the stations are looked at. Lag 8 means the conditions 8 days after the MJO reached that phase. The best lag is the top of the curve below.', cls: { 1: 'Phase 1', 2: 'Phase 2', 3: 'Phase 3', 4: 'Phase 4', 5: 'Phase 5', 6: 'Phase 6', 7: 'Phase 7', 8: 'Phase 8' },
            note: 'The MJO is a pulse of tropical storminess that circles the globe in 30 to 60 days.' },
        pna: { label: 'PNA', short: 'PNA', lag: 0, lagLabel: 'Days after the PNA class', lagNote: 'The PNA changes within a week or two, so here the lag shows how long a PNA state keeps its grip: 0 is the same day, and the effect fades toward zero after about 10 days.', cls: { '-2': 'Strong &minus;PNA', '-1': '&minus;PNA', 0: 'Neutral', 1: '+PNA', 2: 'Strong +PNA' },
            note: 'The PNA is a pattern of upper-air ridges and troughs over the Pacific and North America. Strong negative (a trough off the coast side) is the coldest tenth of days; strong positive (a ridge over the West) the warmest tenth. The index is a 5-day average.' },
        enso: { label: 'ENSO (ONI)', short: 'ENSO', lag: 0, noLag: true, cls: { '-2': 'La Ni&ntilde;a (ONI &le; &minus;1)', '-1': 'Weak La Ni&ntilde;a', 0: 'Neutral', 1: 'Weak El Ni&ntilde;o', 2: 'El Ni&ntilde;o (ONI &ge; 1)' },
            note: 'The monthly Oceanic Ni&ntilde;o Index. There are only 35 winters, so only a handful sit in each class: read these as a tendency, not a rule.' },
    };
    const TIERS = [['all', 'All stations', () => true], ['low', 'Low, under 4,000 ft', e => e < 4000], ['mid', 'Mid, 4,000&ndash;5,000 ft', e => e >= 4000 && e < 5000], ['high', 'High, 5,000 ft and up', e => e >= 5000]];
    // PNA and ENSO classes as symbols on the map: ++ strong positive (El Nino), + positive, none for neutral, - negative, -- strong negative (La Nina)
    const SYM = { '-2': '\u2212\u2212', '-1': '\u2212', '0': '', '1': '+', '2': '++' };
    const SYM_COL = { '-2': '#1d4ed8', '-1': '#60a5fa', '0': '#cbd5e1', '1': '#fb923c', '2': '#c2410c' };
    const EXTREME = {
        swe: ['Snowiest', 'Least snowy'], bigsnow: ['Most big snow days', 'Fewest big snow days'], tanom: ['Warmest', 'Coldest'],
        rain: ['Rainiest', 'Least rain'], bigwet: ['Most big precipitation days', 'Fewest big precipitation days'],
    };
    const PHASE_COL = ['#d73027', '#f46d43', '#fdae61', '#c9b100', '#66bd63', '#1a9850', '#4575b4', '#8e6bbf'];
    const el = (t, a, kids) => { const n = document.createElementNS(NS, t); for (const k in a || {}) n.setAttribute(k, a[k]); (kids || []).forEach(c => n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c)); return n; };

    function lerp(a, b, t) { return a + (b - a) * t; }
    function color(v, metric, lim) {
        // diverging: ratio metrics blue-green for more, brown for less; temperature red for warm, blue for cold
        const base = metric === 'tanom' ? 0 : 1;
        const t = Math.max(-1, Math.min(1, (v - base) / lim));
        const stops = metric === 'tanom' ? { neg: [49, 99, 190], mid: [247, 247, 247], pos: [200, 40, 40] } : { neg: [166, 97, 26], mid: [245, 245, 240], pos: [1, 133, 113] };
        const a = t < 0 ? stops.mid : stops.mid, b = t < 0 ? stops.neg : stops.pos, k = Math.abs(t);
        return `rgb(${[0, 1, 2].map(i => Math.round(lerp(a[i], b[i], k))).join(',')})`;
    }

    function mount(root, data, basins) {
        const S = { index: 'mjo', metric: 'swe', tier: 'all', lag: 8, spread: 1.5, cls: 2, show: 'class' };
        const lags = i => Object.keys(data.data[i].swe).map(Number).sort((a, b) => a - b);
        const stationsIn = () => { const f = TIERS.find(t => t[0] === S.tier)[2]; return data.stations.map((s, i) => [s, i]).filter(([s]) => f(s.elev_ft)).map(([, i]) => i); };

        // blended values [station][class], using the hump of weights around the slider's lag
        function blended(index, metric, lag, spread) {
            const L = lags(index), ws = L.map(l => Math.exp(-((l - lag) ** 2) / (2 * spread * spread)));
            const tot = ws.reduce((a, b) => a + b, 0);
            const first = data.data[index][metric][String(L[0])].v;
            return first.map((row, s) => row.map((_, c) => {
                let num = 0, den = 0;
                L.forEach((l, k) => { const x = data.data[index][metric][String(l)].v[s][c]; if (x != null) { num += ws[k] * x; den += ws[k]; } });
                return den > tot * 0.5 ? num / den : null;
            }));
        }
        const avg = (vals) => { const x = vals.filter(v => v != null); return x.length ? x.reduce((a, b) => a + b, 0) / x.length : null; };

        function render() {
            const idx = INDEX[S.index], classes = data.classes[S.index];
            const clsKey = k => String(k);
            if (!classes.includes(+S.cls)) S.cls = classes[Math.floor(classes.length / 2)];
            const ids = stationsIn();
            const V = blended(S.index, S.metric, S.lag, S.spread);
            const base = S.metric === 'tanom' ? 0 : 1;
            const perClass = classes.map((_, c) => avg(ids.map(s => V[s][c])));
            const all = [].concat(...ids.map(s => V[s].filter(v => v != null)));
            const lim = Math.max(S.metric === 'tanom' ? 1.2 : 0.3, ...all.map(v => Math.abs(v - base)).sort((a, b) => a - b).slice(0, Math.ceil(all.length * 0.97)).slice(-1));
            const unit = S.metric === 'tanom' ? (v => (v >= 0 ? '+' : '') + v.toFixed(1) + ' °F') : (v => (v >= 1 ? '+' : '−') + Math.abs(Math.round((v - 1) * 100)) + '%');
            const chips = (name, items, cur) => `<div class="ol-chips" role="radiogroup" aria-label="${name}">${items.map(([id, label]) => `<button type="button" class="ol-chip" role="radio" aria-checked="${String(id) === String(cur)}" data-k="${name}" data-v="${esc(id)}">${label}</button>`).join('')}</div>`;
            const L = lags(S.index);
            root.innerHTML = `<div class="ts">
                <div class="ol-ctrl">
                    <div class="ol-group"><span class="ol-label">Index</span>${chips('index', Object.entries(INDEX).map(([k, v]) => [k, v.label]), S.index)}</div>
                    <div class="ol-group"><span class="ol-label">What to look at</span>${chips('metric', METRICS, S.metric)}</div>
                    <div class="ol-group"><span class="ol-label">Stations</span>${chips('tier', TIERS.map(t => [t[0], t[1]]), S.tier)}</div>
                    ${idx.noLag ? '' : `<div class="ol-group"><label class="ol-label" for="ts-lag">${idx.lagLabel}: <b>${S.lag}</b></label><input id="ts-lag" type="range" min="${L[0]}" max="${L[L.length - 1]}" step="1" value="${S.lag}" style="width:220px;max-width:100%">
                        <label class="ol-label" for="ts-spr" style="margin-top:.3rem">Blend nearby days (spread): <b>&plusmn;${S.spread}</b></label><input id="ts-spr" type="range" min="0.5" max="4" step="0.5" value="${S.spread}" style="width:220px;max-width:100%"></div>`}
                </div>
                <p class="ci-hint">${idx.note} ${idx.noLag ? 'The ENSO value is a monthly number, so it does not change over a couple of weeks and there is no lag to choose. ' : idx.lagNote + ' '}${METRIC_NOTE[S.metric]} ${S.tier !== 'all' ? 'Only the stations in the elevation group are averaged.' : ''}</p>
                <div class="ts-grid"><div class="ts-box"><h3>Average by ${idx.label}</h3><div id="ts-bars"></div></div>
                    <div class="ts-box"><h3>Where: ${S.show === 'class' ? idx.cls[S.cls] : EXTREME[S.metric][S.show === 'best' ? 0 : 1] + ' ' + (S.index === 'mjo' ? 'phase' : 'class') + ' at each station'}</h3>
                        <div class="ol-chips" style="margin-bottom:.4rem"><button type="button" class="ol-chip" role="radio" aria-checked="${S.show === 'class'}" data-k="show" data-v="class">Selected ${S.index === 'mjo' ? 'phase' : 'class'}</button>
                        <button type="button" class="ol-chip" role="radio" aria-checked="${S.show === 'best'}" data-k="show" data-v="best">${EXTREME[S.metric][0]} ${S.index === 'mjo' ? 'phase' : 'class'}</button>
                        <button type="button" class="ol-chip" role="radio" aria-checked="${S.show === 'worst'}" data-k="show" data-v="worst">${EXTREME[S.metric][1]} ${S.index === 'mjo' ? 'phase' : 'class'}</button></div>
                        <div id="ts-map"></div></div></div>
                ${idx.noLag ? '' : `<div class="ts-box"><h3>How the effect changes with the lag: ${idx.cls[S.cls]}</h3><div id="ts-lag-chart"></div></div>`}
                <p class="ci-hint">Click a bar to choose the class shown on the map and lag curve. Dots on a bar are single stations. A ring on a map station marks a difference the season-bootstrap test calls real at the 90% level (not corrected for testing many combinations, and nearby stations share the same storms).</p>
            </div>`;
            root.querySelectorAll('[data-k]').forEach(b => b.addEventListener('click', () => {
                const k = b.dataset.k, v = b.dataset.v;
                if (k === 'index') { S.index = v; S.lag = INDEX[v].lag; S.cls = data.classes[v][Math.floor(data.classes[v].length / 2)]; if (v === 'mjo') S.cls = 2; }
                else if (k === 'show') S.show = v; else S[k] = v;
                render();
                const nb = root.querySelector(`[data-k="${k}"][aria-checked="true"]`); if (nb) nb.focus();
            }));
            const lagEl = root.querySelector('#ts-lag'), sprEl = root.querySelector('#ts-spr');
            if (lagEl) lagEl.addEventListener('input', e => { S.lag = +e.target.value; render(); root.querySelector('#ts-lag').focus(); });
            if (sprEl) sprEl.addEventListener('input', e => { S.spread = +e.target.value; render(); root.querySelector('#ts-spr').focus(); });
            bars(root.querySelector('#ts-bars'), classes, perClass, ids, V, base, lim, unit, idx);
            (window.L ? mapLeaflet : mapSvg)(root.querySelector('#ts-map'), classes, ids, V, base, lim, unit, idx);
            if (!idx.noLag) lagChart(root.querySelector('#ts-lag-chart'), ids, classes, base, unit);
        }

        function bars(host, classes, perClass, ids, V, base, lim, unit, idx) {
            const W = 560, H = 250, m = { l: 46, r: 8, t: 10, b: 46 };
            const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Average by class', style: 'width:100%;height:auto' });
            const all = perClass.filter(v => v != null).concat(...ids.map(s => V[s].filter(v => v != null)));
            let lo = Math.min(base, ...all), hi = Math.max(base, ...all);
            const pad = (hi - lo) * 0.06; lo -= pad; hi += pad;
            const y = v => m.t + (H - m.t - m.b) * (1 - (v - lo) / (hi - lo));
            const bw = (W - m.l - m.r) / classes.length;
            for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4; svg.appendChild(el('line', { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: '#e2e8f0' })); const t = el('text', { x: m.l - 4, y: y(v) + 3, 'text-anchor': 'end', 'font-size': 10, fill: '#64748b' }); t.textContent = S.metric === 'tanom' ? v.toFixed(1) : v.toFixed(2); svg.appendChild(t); }
            svg.appendChild(el('line', { x1: m.l, x2: W - m.r, y1: y(base), y2: y(base), stroke: '#475569', 'stroke-width': 1.2 }));
            classes.forEach((c, i) => {
                const v = perClass[i]; if (v == null) return;
                const x = m.l + bw * i + bw * 0.15, w = bw * 0.7;
                const sel = +c === +S.cls;
                const r = el('rect', { x, y: Math.min(y(v), y(base)), width: w, height: Math.abs(y(v) - y(base)), fill: S.index === 'mjo' ? PHASE_COL[i] : color(v, S.metric, lim), stroke: sel ? '#0f172a' : 'none', 'stroke-width': 2.5, style: 'cursor:pointer', tabindex: 0, role: 'button', 'aria-label': `${idx.cls[c].replace(/&[^;]+;/g, '')}: ${unit(v)}` });
                const pick = () => { S.cls = +c; if (S.show !== 'class') S.show = 'class'; render(); };
                r.addEventListener('click', pick); r.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
                svg.appendChild(r);
                ids.forEach((s, j) => { const sv = V[s][i]; if (sv == null) return; svg.appendChild(el('circle', { cx: x + w * (0.15 + 0.7 * ((j * 37) % 100) / 100), cy: y(sv), r: 1.8, fill: '#0f172a', opacity: 0.35, 'pointer-events': 'none' })); });
                const t = el('text', { x: x + w / 2, y: v >= base ? y(v) - 4 : y(v) + 12, 'text-anchor': 'middle', 'font-size': 11, 'font-weight': 700, fill: '#0f172a', 'pointer-events': 'none' }); t.textContent = unit(v); svg.appendChild(t);
                const lab = el('text', { x: x + w / 2, y: H - m.b + 15, 'text-anchor': 'middle', 'font-size': 10.5, fill: '#334155' });
                lab.textContent = S.index === 'mjo' ? String(c) : idx.cls[c].replace(/&[^;]+;/g, m2 => ({ '&minus;': '-', '&ntilde;': 'ñ', '&le;': '<=', '&ge;': '>=' }[m2] || '')).split(' (')[0];
                svg.appendChild(lab);
            });
            host.innerHTML = ''; host.appendChild(svg);
        }

        function mapSvg(host, classes, ids, V, base, lim, unit, idx) {
            const W = 480, H = 440, lon0 = -124.2, lon1 = -117, lat0 = 45.6, lat1 = 49.1, k = Math.cos(47 * Math.PI / 180);
            const sx = (W - 10) / ((lon1 - lon0) * k), sy = (H - 10) / (lat1 - lat0), sc = Math.min(sx, sy);
            const X = lon => 5 + (lon - lon0) * k * sc, Y = lat => 5 + (lat1 - lat) * sc;
            const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Map of stations', style: 'width:100%;height:auto;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px' });
            (basins ? basins.features : []).forEach(f => { const g = f.geometry, polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates; polys.forEach(p => svg.appendChild(el('path', { d: p[0].map((c, i) => (i ? 'L' : 'M') + X(c[0]).toFixed(1) + ' ' + Y(c[1]).toFixed(1)).join('') + 'Z', fill: 'none', stroke: '#cbd5e1', 'stroke-width': 0.7 }))); });
            const ci = classes.findIndex(c => +c === +S.cls);
            const sigD = data.data[S.index][S.metric];
            const L = lags(S.index);
            const nearest = L.reduce((a, b) => Math.abs(b - S.lag) < Math.abs(a - S.lag) ? b : a, L[0]);
            ids.forEach(s => {
                const st = data.stations[s], row = V[s];
                let v, cidx = ci;
                if (S.show !== 'class') { const cand = row.map((x, i) => [x, i]).filter(p => p[0] != null); if (!cand.length) return; const pick = cand.reduce((a, b) => (S.show === 'best' ? (S.metric === 'tanom' ? b[0] > a[0] : b[0] > a[0]) : b[0] < a[0]) ? b : a); v = pick[0]; cidx = pick[1]; } else v = row[ci];
                if (v == null) return;
                const sig = sigD[String(nearest)].sig[s][cidx];
                const fill = S.show === 'class' ? color(v, S.metric, lim) : (S.index === 'mjo' ? PHASE_COL[cidx] : color(v, S.metric, lim));
                const c = el('circle', { cx: X(st.lon), cy: Y(st.lat), r: 7, fill, stroke: sig ? '#0f172a' : '#94a3b8', 'stroke-width': sig ? 2 : 0.8 });
                c.appendChild(el('title', {}, [`${st.name}, ${st.elev_ft.toLocaleString()} ft: ${unit(v)}${S.show !== 'class' ? ' (' + idx.cls[classes[cidx]].replace(/&[^;]+;/g, '') + ')' : ''}`]));
                svg.appendChild(c);
                if (S.show !== 'class' && S.index === 'mjo') svg.appendChild(el('text', { x: X(st.lon), y: Y(st.lat) + 3, 'text-anchor': 'middle', 'font-size': 8.5, fill: '#fff', 'font-weight': 700, 'pointer-events': 'none' }, [String(classes[cidx])]));
            });
            host.innerHTML = ''; host.appendChild(svg);
            const note = document.createElement('p'); note.className = 'ci-hint';
            note.innerHTML = S.show === 'class' ? 'Brown is below normal and green above for snow and rain measures; blue is colder and red warmer. Hover a dot for the station.' : (S.index === 'mjo' ? 'Dot color and number are the MJO phase.' : 'Dot color shows the size of the effect.') + ' Hover a dot for the station.';
            host.appendChild(note);
        }


        // Station map on a real background (Esri World Topo tiles, as on the normals map). The Leaflet map is created once and kept
        // between redraws so the view does not jump when a control changes. mapSvg above is the fallback when Leaflet is missing.
        let LM = null, LLayer = null;
        const mapDiv = document.createElement('div');
        mapDiv.className = 'ts-leaflet';
        function pickStations(classes, ids, V, base, lim, unit, idx) {
            const ci = classes.findIndex(c => +c === +S.cls), out = [];
            const Ls = lags(S.index), nearest = Ls.reduce((a, b) => Math.abs(b - S.lag) < Math.abs(a - S.lag) ? b : a, Ls[0]);
            ids.forEach(s => {
                const row = V[s];
                let v, cidx = ci;
                if (S.show !== 'class') {
                    const cand = row.map((x, i) => [x, i]).filter(p => p[0] != null); if (!cand.length) return;
                    const pk = cand.reduce((a, b) => (S.show === 'best' ? b[0] > a[0] : b[0] < a[0]) ? b : a); v = pk[0]; cidx = pk[1];
                } else v = row[ci];
                if (v == null) return;
                const fill = S.show === 'class' ? color(v, S.metric, lim) : (S.index === 'mjo' ? PHASE_COL[cidx] : SYM_COL[String(classes[cidx])]);
                out.push({ st: data.stations[s], v, cidx, fill, sig: data.data[S.index][S.metric][String(nearest)].sig[s][cidx] });
            });
            return out;
        }
        function mapLeaflet(host, classes, ids, V, base, lim, unit, idx) {
            host.innerHTML = '';
            host.appendChild(mapDiv);
            if (!LM) {
                LM = L.map(mapDiv, { scrollWheelZoom: false, dragging: true, maxZoom: 11 });
                L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', { attribution: 'Tiles &copy; Esri', maxZoom: 11 }).addTo(LM);
                if (basins) L.geoJSON(basins, { style: { color: '#475569', weight: 1, fill: false, opacity: 0.7 }, interactive: false }).addTo(LM);
                LM.fitBounds([[45.8, -124.0], [49.1, -117.1]]);
                LLayer = L.layerGroup().addTo(LM);
            } else { LM.invalidateSize(); }
            LLayer.clearLayers();
            pickStations(classes, ids, V, base, lim, unit, idx).forEach(p => {
                const tip = `${p.st.name}, ${p.st.elev_ft.toLocaleString()} ft: ${unit(p.v)}${S.show !== 'class' ? ' (' + idx.cls[classes[p.cidx]].replace(/&[^;]+;/g, '') + ')' : ''}`;
                let m;
                if (S.show !== 'class') {
                    const lab = S.index === 'mjo' ? String(classes[p.cidx]) : SYM[String(classes[p.cidx])];
                    m = L.marker([p.st.lat, p.st.lon], { icon: L.divIcon({ className: 'ts-pin', html: `<span style="background:${p.fill};border-color:${p.sig ? '#0f172a' : '#fff'};${S.index !== 'mjo' && p.fill === SYM_COL['0'] ? 'color:#334155;text-shadow:none' : ''}">${lab}</span>`, iconSize: [24, 24] }) });
                } else {
                    m = L.circleMarker([p.st.lat, p.st.lon], { radius: 8, fillColor: p.fill, fillOpacity: 0.95, color: p.sig ? '#0f172a' : '#64748b', weight: p.sig ? 2.5 : 1 });
                }
                m.bindTooltip(tip).addTo(LLayer);
            });
            const note = document.createElement('p'); note.className = 'ci-hint';
            note.innerHTML = S.show === 'class' ? 'Brown is below normal and green above for snow and rain measures; blue is colder and red warmer. A dark ring marks a difference the test calls real. Hover or tap a dot for the station. Thin lines are river basins.' : (S.index === 'mjo' ? 'Each dot shows the MJO phase (1 to 8) with the ' + EXTREME[S.metric][S.show === 'best' ? 0 : 1].toLowerCase() + ' results at that station. ' : S.index === 'pna' ? 'Each dot is the PNA class with the ' + EXTREME[S.metric][S.show === 'best' ? 0 : 1].toLowerCase() + ' results at that station: ++ strong positive PNA, + positive, no mark neutral, \u2212 negative, \u2212\u2212 strong negative. ' : 'Each dot is the ENSO class with the ' + EXTREME[S.metric][S.show === 'best' ? 0 : 1].toLowerCase() + ' results at that station: ++ El Ni\u00f1o, + weak El Ni\u00f1o, no mark neutral, \u2212 weak La Ni\u00f1a, \u2212\u2212 La Ni\u00f1a. ') + 'A dark ring marks a difference the test calls real. Hover or tap a dot for the station.';
            host.appendChild(note);
        }

        function lagChart(host, ids, classes, base, unit) {
            const W = 760, H = 230, m = { l: 46, r: 10, t: 12, b: 34 };
            const L = lags(S.index), ci = classes.findIndex(c => +c === +S.cls);
            const series = L.map(l => avg(ids.map(s => data.data[S.index][S.metric][String(l)].v[s][ci])));
            const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Effect versus lag', style: 'width:100%;height:auto' });
            const vals = series.filter(v => v != null);
            let lo = Math.min(base, ...vals), hi = Math.max(base, ...vals); const pad = (hi - lo) * 0.12 || 0.1; lo -= pad; hi += pad;
            const x = l => m.l + (W - m.l - m.r) * (l - L[0]) / (L[L.length - 1] - L[0]), y = v => m.t + (H - m.t - m.b) * (1 - (v - lo) / (hi - lo));
            // the hump: weights of the blend, drawn as a shaded bump along the bottom of the chart
            const hump = []; for (let l = L[0]; l <= L[L.length - 1]; l += 0.25) hump.push([l, Math.exp(-((l - S.lag) ** 2) / (2 * S.spread * S.spread))]);
            svg.appendChild(el('path', { d: 'M' + hump.map(([l, w]) => `${x(l).toFixed(1)} ${(H - m.b - w * (H - m.t - m.b) * 0.8).toFixed(1)}`).join('L') + `L${x(L[L.length - 1])} ${H - m.b}L${x(L[0])} ${H - m.b}Z`, fill: '#1e3c72', opacity: 0.12 }));
            for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4; svg.appendChild(el('line', { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: '#e2e8f0' })); const t = el('text', { x: m.l - 4, y: y(v) + 3, 'text-anchor': 'end', 'font-size': 10, fill: '#64748b' }); t.textContent = S.metric === 'tanom' ? v.toFixed(1) : v.toFixed(2); svg.appendChild(t); }
            svg.appendChild(el('line', { x1: m.l, x2: W - m.r, y1: y(base), y2: y(base), stroke: '#475569', 'stroke-width': 1.2 }));
            svg.appendChild(el('path', { d: 'M' + L.map((l, i) => series[i] == null ? '' : `${x(l).toFixed(1)} ${y(series[i]).toFixed(1)}`).filter(Boolean).join('L'), fill: 'none', stroke: '#c2410c', 'stroke-width': 2.5 }));
            L.forEach((l, i) => { if (series[i] == null) return; const c = el('circle', { cx: x(l), cy: y(series[i]), r: 3.5, fill: '#c2410c', style: 'cursor:pointer' }); c.appendChild(el('title', {}, [`${l} days: ${unit(series[i])}`])); c.addEventListener('click', () => { S.lag = l; render(); }); svg.appendChild(c); });
            L.forEach(l => { if (l % 2 === 0) { const t = el('text', { x: x(l), y: H - 14, 'text-anchor': 'middle', 'font-size': 10, fill: '#64748b' }); t.textContent = l; svg.appendChild(t); } });
            const t = el('text', { x: (W + m.l) / 2, y: H - 1, 'text-anchor': 'middle', 'font-size': 10, fill: '#64748b' }); t.textContent = 'days after the index state'; svg.appendChild(t);
            svg.appendChild(el('line', { x1: x(S.lag), x2: x(S.lag), y1: m.t, y2: H - m.b, stroke: '#1e3c72', 'stroke-dasharray': '4 3' }));
            const best = series.reduce((b, v, i) => v != null && (b < 0 || (S.metric === 'tanom' ? Math.abs(v) > Math.abs(series[b]) : Math.abs(v - base) > Math.abs(series[b] - base))) ? i : b, -1);
            host.innerHTML = ''; host.appendChild(svg);
            if (best >= 0) { const p = document.createElement('p'); p.className = 'ci-hint'; p.innerHTML = `Strongest at ${L[best]} days (${unit(series[best])}). The shaded hump is the blend around your chosen lag. Click a dot to jump to that lag. <button type="button" class="ol-chip" id="ts-best">Go to the strongest lag</button>`; host.appendChild(p); host.querySelector('#ts-best').addEventListener('click', () => { S.lag = L[best]; render(); }); }
        }
        render();
    }

    const root = document.querySelector('.ts-mount');
    if (!root) return;
    Promise.all([fetch(BASE + 'data/tele_composites.json').then(r => r.json()), fetch(BASE + 'data/basins.geojson').then(r => r.json()).catch(() => null)])
        .then(([d, b]) => mount(root, d, b))
        .catch(() => { root.innerHTML = '<p class="ol-fail">The station data could not be loaded right now.</p>'; });
}());
