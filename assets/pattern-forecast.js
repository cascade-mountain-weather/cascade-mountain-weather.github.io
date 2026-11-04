/* Tea Leaves page: scrollable 72-hour ECMWF anomaly maps, the storm-pattern call for each day, and a map of how much more or less water each zone can expect.
   Reads pattern_forecast.json, pattern_zones.json and frames/ from the forecast-data branch (data-remote), or from the local
   assets/forecast/ (data-local) when that is not reachable. Built by scripts/pattern_forecast.py. Mount point: #pf-viewer. */
(function () {
    'use strict';
    var root = document.getElementById('pf-viewer');
    if (!root) return;
    var NAMES = ['Deep low offshore to the southwest', 'Deep low in the Gulf of Alaska', 'Low far to the southwest', 'Low to the south, over California',
                 'Moderate low just to the north', 'Weaker low, far out in the Gulf of Alaska'];
    var SHORT = ['Deep, offshore SW', 'Deep, Gulf of Alaska', 'Far SW', 'South (California)', 'Just to the north', 'Weak, Gulf of Alaska'];
    var COLORS = ['#1e3c72', '#2f80ed', '#0f9d8a', '#e0a100', '#8b5cf6', '#d6457a'];
    var ZONES = ['Mt. Baker', 'Washington Pass', 'Stevens Pass', 'Hurricane Ridge', 'Blewett Pass', 'Snoqualmie Pass', 'Crystal', 'Paradise', 'White Pass'];
    var state = { view: 'map', mapPat: 0, fmode: 'blend', basins: null, land: null, selA: null, selF: null, model: 'det', kind: 'height_anom', i: 0, day: 0, fc: null, zones: null, base: '', timer: null };
    var ui = {};

    function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
    function pad(n) { return ('00' + n).slice(-3); }
    function pct(x) { return Math.round(x * 100) + '%'; }
    function days() { return state.fc.models[state.model].days; }
    // How wet the day is: the median member's precipitation over the Cascades box, in inches of water.
    var WET = [[0.05, 'Dry'], [0.5, 'Slightly wet'], [1.5, 'Moderately wet'], [Infinity, 'Very wet']];
    function wetness(d) {
        var q = d.precip_mm.map(function (m) { return m / 25.4; }), v = q[1], i = 0;
        while (v >= WET[i][0]) i++;
        return { label: WET[i][1], dry: i === 0, inches: v, range: q,
                 tip: 'Median ' + v.toFixed(2) + ' in of water' + (d.members > 1 ? ' (middle half of members ' + q[0].toFixed(2) + '\u2013' + q[2].toFixed(2) + ')' : '') };
    }

    function chips(label, id, opts, key) {
        var g = el('div', 'ol-group'), l = el('span', 'ol-label', label), c = el('div', 'ol-chips');
        c.setAttribute('role', 'radiogroup'); l.id = id; c.setAttribute('aria-labelledby', id);
        opts.forEach(function (o) {
            var b = el('button', 'ol-chip', o[1]); b.type = 'button'; b.setAttribute('role', 'radio');
            b.setAttribute('aria-checked', state[key] === o[0] ? 'true' : 'false');
            b.addEventListener('click', function () {
                state[key] = o[0];
                Array.prototype.forEach.call(c.children, function (x) { x.setAttribute('aria-checked', x === b ? 'true' : 'false'); });
                render();
            });
            c.appendChild(b);
        });
        g.appendChild(l); g.appendChild(c);
        return g;
    }

    function stepIndexOfDay(d) {          // the 12 UTC frame of a forecast day
        for (var k = 0; k < state.fc.valid.length; k++) if (state.fc.valid[k].indexOf(d.label) === 0 && /12Z$/.test(state.fc.valid[k])) return k;
        return 0;
    }
    function dayOfStep(i) {
        var v = state.fc.valid[i], ds = days();
        for (var k = 0; k < ds.length; k++) if (v.indexOf(ds[k].label) === 0) return k;
        return -1;
    }
    function setStep(i) {
        state.i = i; ui.range.value = i;
        var k = dayOfStep(i);
        if (k >= 0 && k !== state.day) { state.day = k; renderDays(); renderZones(); }
        renderMap();
    }

    function build() {
        var fc = state.fc, models = Object.keys(fc.models);
        var opts = [['det', 'Deterministic'], ['eps', 'Ensemble mean']].filter(function (o) { return models.indexOf(o[0]) >= 0; });
        if (!opts.some(function (o) { return o[0] === state.model; })) state.model = opts[0][0];
        var layout = el('div', 'pf-layout'), left = el('div', 'pf-left'), right = el('div', 'pf-right');
        var ctrl = el('div', 'ol-ctrl');
        ctrl.appendChild(chips('Forecast', 'pf-l-model', opts, 'model'));
        ctrl.appendChild(chips('Map', 'pf-l-kind', [['height_anom', '500 hPa height'], ['t850_anom', '850 hPa temperature']], 'kind'));
        left.appendChild(ctrl);

        var fig = el('figure', 'pf-fig');
        ui.img = el('img', 'PlotFormat'); ui.img.alt = 'ECMWF forecast anomaly map';
        ui.cap = el('figcaption');
        fig.appendChild(ui.img); fig.appendChild(ui.cap);
        left.appendChild(fig);

        var row = el('div', 'pf-slider');
        ui.play = el('button', 'ol-chip', 'Play'); ui.play.type = 'button';
        ui.range = el('input'); ui.range.type = 'range'; ui.range.min = 0; ui.range.max = fc.steps.length - 1; ui.range.value = 0; ui.range.setAttribute('aria-label', 'Forecast hour');
        ui.when = el('output', 'pf-when'); ui.when.setAttribute('for', 'pf-range'); ui.range.id = 'pf-range';
        row.appendChild(ui.play); row.appendChild(ui.range); row.appendChild(ui.when);
        left.appendChild(row);
        ui.range.addEventListener('input', function () { stop(); setStep(+ui.range.value); });
        ui.play.addEventListener('click', function () {
            if (state.timer) return stop();
            ui.play.textContent = 'Pause';
            state.timer = setInterval(function () { setStep((state.i + 1) % fc.steps.length); }, 1000);
        });

        right.appendChild(el('h3', 'pf-h', 'Which pattern does the forecast suggest?'));
        ui.days = el('div', 'pf-days'); ui.days.setAttribute('role', 'tablist');
        ui.zones = el('div', 'pf-zones');
        right.appendChild(ui.days); right.appendChild(ui.zones);
        layout.appendChild(left); layout.appendChild(right);
        root.appendChild(layout);

        ui.all = el('details', 'pf-all');
        ui.all.appendChild(el('summary', null, 'All six patterns'));
        ui.allbody = el('div'); ui.all.appendChild(ui.allbody);
        root.appendChild(ui.all);
        render();
    }

    function stop() { if (state.timer) { clearInterval(state.timer); state.timer = null; ui.play.textContent = 'Play'; } }

    function render() {
        if (state.day >= days().length) state.day = 0;
        renderMap(); renderDays(); renderZones();
    }

    function renderMap() {
        var fc = state.fc, s = fc.steps[state.i];
        ui.img.src = state.base + 'frames/' + state.model + '_' + state.kind + '_' + pad(s) + '.png';
        ui.when.textContent = fc.valid[state.i] + '  (+' + s + ' h)';
        var what = state.kind === 'height_anom'
            ? 'Shading: 500 hPa height anomaly in standard deviations (blue = lower than normal). Black lines: height (dam). Red line: 0 °C at 850 hPa.'
            : 'Shading: 850 hPa temperature anomaly in kelvin. Dashed line: 0 °C. Grey lines: 500 hPa height (dam).';
        var note = state.model === 'eps' ? ' Mean of the 50 members; dots where at least 90% of them agree on the sign.' : ' One forecast.';
        ui.cap.textContent = what + note + ' Star = the Cascades. Run: ' + fc.init + '.';
    }

    function renderDays() {
        ui.days.textContent = '';
        days().forEach(function (d, k) {
            var on = k === state.day, w = wetness(d), maybe = !w.dry;
            var tab = el('button', 'pf-day' + (on ? ' pf-day--on' : '') + (maybe ? '' : ' pf-day--dry'));
            tab.type = 'button'; tab.setAttribute('role', 'tab'); tab.setAttribute('aria-selected', on ? 'true' : 'false');
            var top = el('div', 'pf-daytop');
            top.appendChild(el('strong', null, d.label));
            var wl = el('span', 'pf-storm', maybe ? w.label + ' \u00B7 ' + w.inches.toFixed(2) + ' in' : 'Dry'); wl.title = w.tip; top.appendChild(wl);
            tab.appendChild(top);
            if (maybe) {
                var bar = el('div', 'pf-stack');
                Object.keys(d.votes).filter(function (key) { return d.votes[key] > 0; }).sort(function (a, b) { return d.votes[b] - d.votes[a]; }).forEach(function (key) {
                    var seg = el('span', 'pf-seg' + (key === 'none' ? ' pf-seg--none' : ''));
                    var w = d.votes[key] / d.members;
                    seg.style.flexGrow = d.votes[key];
                    if (key !== 'none') { seg.style.background = COLORS[+key]; if (+key === 3) seg.style.color = '#1e293b'; }
                    seg.textContent = w >= 0.2 ? (key === 'none' ? 'No match' : 'P' + key) + (d.members > 1 ? ' ' + pct(w) : '') : '';
                    seg.title = (key === 'none' ? 'No good match' : 'Pattern ' + key + ': ' + NAMES[+key]) + ' · ' + pct(w) + (d.members > 1 ? ' of members' : '');
                    bar.appendChild(seg);
                });
                tab.appendChild(bar);
            }
            tab.addEventListener('click', function () { stop(); state.day = k; setStep(stepIndexOfDay(d)); renderDays(); renderZones(); });
            ui.days.appendChild(tab);
        });
    }

    function called(d) {
        return Object.keys(d.votes).filter(function (k) { return k !== 'none' && d.votes[k] / d.members >= 0.25; })
            .sort(function (a, b) { return d.votes[b] - d.votes[a]; });
    }

    // Cell shading: blue where the average storm in this pattern brings more water than a normal storm (as a share of the zone's usual storm),
    // yellow for less; a dark outline marks the ones the resampling says are not chance.
    var SCALE = 40, BLUE = [37, 99, 235], YELLOW = [234, 179, 8];
    function shade(v) {
        var t = Math.min(Math.abs(v) / SCALE, 1), c = v >= 0 ? BLUE : YELLOW;
        return 'rgb(' + c.map(function (x) { return Math.round(255 + (x - 255) * t * 0.85); }).join(',') + ')';
    }
    function spct(v) { var n = Math.round(v); return (n > 0 ? '+' : n < 0 ? '−' : '') + Math.abs(n) + '%'; }
    function signed(v) { return (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(2); }

    function pill(r, info, z) {
        var on = state.selA && state.selA.z === z && state.selA.p === r.pattern;
        var td = el('td', 'pf-cell' + (r.verdict !== 'average' ? ' pf-sig' : '') + (on ? ' pf-sel' : ''));
        td.style.background = shade(r.shift_pct);
        td.style.color = Math.abs(r.shift_pct) / SCALE > 0.75 ? '#fff' : '#1e293b';
        td.textContent = spct(r.shift_pct);
        td.tabIndex = 0; td.setAttribute('role', 'button');
        td.title = z + ', pattern ' + r.pattern + ': click for the picture';
        function pick() { state.selA = on ? null : { z: z, p: r.pattern }; if (state.selA) state.mapPat = r.pattern; renderMatrix(); }
        td.addEventListener('click', pick);
        td.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
        return td;
    }

    var SVGNS = 'http://www.w3.org/2000/svg';
    function sv(tag, attrs, text) {
        var e = document.createElementNS(SVGNS, tag);
        for (var k in attrs) e.setAttribute(k, attrs[k]);
        if (text != null) e.textContent = text;
        return e;
    }
    // One cell as a picture: the usual spread of storm days (dashed) against this pattern's (solid); in the two tails, solid colour where the
    // pattern has more days than usual and hatching where it has fewer. The ticks on the axis are the average storm.
    function cellFigure(z, p) {
        var info = state.zones.zones[z], r = info.patterns[p], X = state.zones.grid, T = state.zones.threshold_in;
        var W = 440, left = 14, right = 14, top = 54, plotH = 170, bottom = top + plotH, pw = W - left - right;
        var fa = info.all.f, fp = r.f, ymax = Math.max.apply(null, fa.concat(fp)) * 1.08;
        function px(x) { return left + (x - X[0]) / (X[X.length - 1] - X[0]) * pw; }
        function py(y) { return bottom - y / ymax * plotH; }
        function pt(j, y) { return px(X[j]).toFixed(1) + ' ' + py(y).toFixed(1); }
        function line(f) { return f.map(function (y, i) { return (i ? 'L' : 'M') + pt(i, y); }).join(' '); }
        function band(upper, lower, inTail) {
            var xs = [], i;
            for (i = 0; i < X.length; i++) if (inTail(X[i])) xs.push(i);
            if (!xs.length) return '';
            var up = xs.map(function (j) { return pt(j, upper(j)); });
            var lo = xs.slice().reverse().map(function (j) { return pt(j, lower(j)); });
            return 'M' + up.join(' L') + ' L' + lo.join(' L') + ' Z';
        }
        var gain = function (j) { return Math.max(fp[j] - fa[j], 0); }, loss = function (j) { return Math.max(fa[j] - fp[j], 0); };
        var svg = sv('svg', { viewBox: '0 0 ' + W + ' ' + (bottom + 82), role: 'img', 'class': 'pf-svg',
                              'aria-label': z + ', pattern ' + p + ': storm-day water against the zone’s usual' });
        var defs = sv('defs', {});
        [['pf-hy', '#a16207'], ['pf-hb', '#1e40af']].forEach(function (h) {
            var pat = sv('pattern', { id: h[0], width: 7, height: 7, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' });
            pat.appendChild(sv('line', { x1: 0, y1: 0, x2: 0, y2: 7, stroke: h[1], 'stroke-width': 2 }));
            defs.appendChild(pat);
        });
        svg.appendChild(defs);
        svg.appendChild(sv('text', { x: left, y: 22, 'class': 'pf-svg-title' }, z + ' · Pattern ' + p));
        svg.appendChild(sv('path', { d: 'M' + px(X[0]).toFixed(1) + ' ' + bottom + ' ' + line(fa).replace(/^M/, 'L') + ' L' + px(X[X.length - 1]).toFixed(1) + ' ' + bottom + ' Z', fill: '#e2e8f0' }));
        [[function (x) { return x < -T; }, '#eab308', 'url(#pf-hy)'], [function (x) { return x > T; }, '#2563eb', 'url(#pf-hb)']].forEach(function (g) {
            svg.appendChild(sv('path', { d: band(function (j) { return fa[j] + gain(j); }, function (j) { return fa[j]; }, g[0]), fill: g[1] }));
            svg.appendChild(sv('path', { d: band(function (j) { return fa[j]; }, function (j) { return fa[j] - loss(j); }, g[0]), fill: g[2] }));
        });
        svg.appendChild(sv('path', { d: line(fa), fill: 'none', stroke: '#475569', 'stroke-width': 2, 'stroke-dasharray': '6 4' }));
        svg.appendChild(sv('path', { d: line(fp), fill: 'none', stroke: '#1e293b', 'stroke-width': 3 }));
        [-T, T].forEach(function (x) { svg.appendChild(sv('line', { x1: px(x), x2: px(x), y1: top - 8, y2: bottom, stroke: '#64748b', 'stroke-dasharray': '2 3' })); });
        [[(X[0] - T) / 2, 'Under'], [0, 'Average'], [(X[X.length - 1] + T) / 2, 'Over']].forEach(function (l) {
            svg.appendChild(sv('text', { x: px(l[0]), y: top - 14, 'text-anchor': 'middle', 'class': 'pf-svg-note' }, l[1]));
        });
        svg.appendChild(sv('line', { x1: left, x2: left + pw, y1: bottom, y2: bottom, stroke: '#94a3b8' }));
        [-1, 0, 1, 2].forEach(function (x) {
            svg.appendChild(sv('text', { x: px(x), y: bottom + 20, 'text-anchor': 'middle', 'class': 'pf-svg-note' }, x > 0 ? '+' + x : x < 0 ? '−' + Math.abs(x) : '0'));
        });
        svg.appendChild(sv('text', { x: left + pw / 2, y: bottom + 40, 'text-anchor': 'middle', 'class': 'pf-svg-note' }, 'Water vs. usual (inches)'));
        svg.appendChild(sv('line', { x1: px(info.all.mean), x2: px(info.all.mean), y1: bottom - 14, y2: bottom, stroke: '#475569', 'stroke-width': 3, 'stroke-dasharray': '3 2' }));
        svg.appendChild(sv('line', { x1: px(r.mean), x2: px(r.mean), y1: bottom - 22, y2: bottom, stroke: '#1e293b', 'stroke-width': 4 }));
        var ly = bottom + 66, lx = left;
        function item(draw, label, w) { draw(lx, ly); svg.appendChild(sv('text', { x: lx + 26, y: ly + 5, 'class': 'pf-svg-note' }, label)); lx += w; }
        item(function (x, y) { svg.appendChild(sv('line', { x1: x, x2: x + 20, y1: y, y2: y, stroke: '#1e293b', 'stroke-width': 3 })); }, 'Pattern ' + p, 104);
        item(function (x, y) { svg.appendChild(sv('line', { x1: x, x2: x + 20, y1: y, y2: y, stroke: '#475569', 'stroke-width': 2, 'stroke-dasharray': '5 3' })); }, 'All storms', 112);
        item(function (x, y) { svg.appendChild(sv('rect', { x: x, y: y - 6, width: 20, height: 12, fill: '#2563eb' })); }, 'More', 74);
        item(function (x, y) { svg.appendChild(sv('rect', { x: x, y: y - 6, width: 20, height: 12, fill: 'url(#pf-hb)' })); }, 'Fewer', 70);
        return svg;
    }

    // key is 'selF' (the forecast map) or 'selA' (the all-patterns dropdown); each keeps its own picture.
    function cellPanel(key, rerender) {
        var sel = state[key];
        if (!sel) return null;
        var box = el('div', 'pf-cellfig');
        var z = sel.z, p = sel.p, info = state.zones.zones[z], r = info.patterns[p];
        var close = el('button', 'pf-close', '×'); close.type = 'button'; close.setAttribute('aria-label', 'Close');
        close.addEventListener('click', function () { state[key] = null; rerender(); });
        box.appendChild(close);
        box.appendChild(cellFigure(z, p));
        box.appendChild(el('p', 'pf-cellnote', 'Over: ' + pct(r.p_over) + ' of days (usually ' + pct(info.base_over) + ').  Under: ' + pct(r.p_under) + ' (usually ' + pct(info.base_under) + ').'));
        box.appendChild(el('p', 'pf-cellnote', 'Average storm: ' + spct(r.shift_pct) + ' water vs. a normal storm (' + signed(r.shift_in) + ' in on a usual ' + info.typical_in.toFixed(1) + ' in).'));
        return box;
    }

    function scaleLegend() {
        var l = el('div', 'pf-scale');
        l.appendChild(el('span', null, 'Less water'));
        var bar = el('span', 'pf-scalebar'); l.appendChild(bar);
        l.appendChild(el('span', null, 'More water'));
        return l;
    }

    // ---- the zone map: Washington / BC / Oregon basemap, each zone's watershed coloured by its shift. opts: value(z) -> {pct, sig}, sel (key), onPick(z).
    var HUC = { 'Mt. Baker': '17110004', 'Washington Pass': '17020008', 'Stevens Pass': '17110009', 'Hurricane Ridge': '17110020', 'Blewett Pass': '17020011',
                'Snoqualmie Pass': '17110010', 'Crystal': '17110014', 'Paradise': '17110015', 'White Pass': '17080004' };
    var LABEL_OFF = { 'Stevens Pass': [-30, -38, 'end'], 'Blewett Pass': [44, -8, 'start'], 'Snoqualmie Pass': [-40, 18, 'end'],
                      'Crystal': [50, -18, 'start'], 'Paradise': [-40, 20, 'end'], 'White Pass': [38, 14, 'start'] };
    function rings(g) { return g.type === 'Polygon' ? [g.coordinates[0]] : g.coordinates.map(function (c) { return c[0]; }); }
    function mapView(opts) {
        var wrap = el('div', 'pf-mapwrap'), feats = state.basins.features, byHuc = {};
        feats.forEach(function (f) { byHuc[f.properties.huc8] = f; });
        var bb = [-124.9, 45.75, -119.4, 49.45];                          // the part of the basemap that is shown: the zones with a little margin
        var k = Math.cos(47 * Math.PI / 180), W = 520, pad = 0, sc = (W - 2 * pad) / ((bb[2] - bb[0]) * k), H = Math.round((bb[3] - bb[1]) * sc + 2 * pad);
        function X(lon) { return pad + (lon - bb[0]) * k * sc; }
        function Y(lat) { return H - pad - (lat - bb[1]) * sc; }
        function ringPath(r) { return 'M' + r.map(function (c) { return X(c[0]).toFixed(1) + ' ' + Y(c[1]).toFixed(1); }).join(' L') + ' Z'; }
        var svg = sv('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'class': 'pf-svg', 'aria-label': 'Cascades zones coloured by how much more or less water the pattern brings' });
        svg.appendChild(sv('rect', { x: 0, y: 0, width: W, height: H, fill: '#e3edf7' }));
        if (state.land) {
            Object.keys(state.land.states).forEach(function (name) {
                svg.appendChild(sv('path', { d: state.land.states[name].map(ringPath).join(' '), fill: '#f8fafc', 'fill-rule': 'evenodd', stroke: '#9aa7b8', 'stroke-width': 1.4, 'stroke-linejoin': 'round' }));
            });
            [['BRITISH COLUMBIA', -122.4, 49.72], ['WASHINGTON', -119.95, 46.55], ['OREGON', -121.9, 45.55]].forEach(function (l) {
                svg.appendChild(sv('text', { x: X(l[1]), y: Y(l[2]), 'text-anchor': 'middle', 'class': 'pf-map-state' }, l[0]));
            });
            svg.appendChild(sv('text', { x: X(-125.3), y: Y(46.9), 'class': 'pf-map-state pf-map-sea' }, 'PACIFIC'));
        }
        ZONES.forEach(function (z) {
            var f = byHuc[HUC[z]], info = state.zones.zones[z]; if (!f || !info) return;
            var v = opts.value(z), sel = state[opts.sel], on = sel && sel.z === z;
            var g = sv('g', { tabindex: 0, role: 'button', 'class': 'pf-basin' + (on ? ' pf-basin--on' : ''), 'aria-label': z + ': ' + spct(v.pct) });
            g.appendChild(sv('path', { d: rings(f.geometry).map(ringPath).join(' '), fill: shade(v.pct), 'fill-opacity': 0.94, stroke: v.sig ? '#1e293b' : '#64748b', 'stroke-width': v.sig ? 2.5 : 1.1 }));
            var ring = rings(f.geometry).slice().sort(function (a, b) { return b.length - a.length; })[0], cx = 0, cy = 0;
            ring.forEach(function (c) { cx += c[0]; cy += c[1]; });
            cx = X(cx / ring.length); cy = Y(cy / ring.length);
            var off = LABEL_OFF[z], dark = !off && Math.abs(v.pct) / SCALE > 0.75, lx = cx, ly = cy, anchor = 'middle';
            if (off) {                                           // crowded zones: label pulled out beside the basin, joined by a short line
                lx = cx + off[0]; ly = cy + off[1]; anchor = off[2];
                g.appendChild(sv('line', { x1: cx, y1: cy, x2: lx - (anchor === 'end' ? -3 : anchor === 'start' ? 3 : 0), y2: ly - 6, stroke: '#475569', 'stroke-width': 1 }));
                g.appendChild(sv('circle', { cx: cx, cy: cy, r: 2.8, fill: '#1e293b' }));
            }
            g.appendChild(sv('text', { x: lx, y: ly - 2, 'text-anchor': anchor, 'class': 'pf-map-val' + (dark ? ' pf-map-val--light' : '') }, spct(v.pct)));
            g.appendChild(sv('text', { x: lx, y: ly + 15, 'text-anchor': anchor, 'class': 'pf-map-name' + (dark ? ' pf-map-val--light' : '') }, z));
            function pick() { opts.onPick(z); }
            g.addEventListener('click', pick);
            g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
            svg.appendChild(g);
        });
        wrap.appendChild(svg);
        return wrap;
    }

    function chipRow(label, opts, current, onpick) {
        var g = el('div', 'ol-group'), c = el('div', 'ol-chips'); c.setAttribute('role', 'radiogroup');
        g.appendChild(el('span', 'ol-label', label)); g.appendChild(c);
        opts.forEach(function (o) {
            var b = el('button', 'ol-chip', o[1]); b.type = 'button'; b.setAttribute('role', 'radio'); b.title = o[2] || '';
            b.setAttribute('aria-checked', current === o[0] ? 'true' : 'false');
            b.addEventListener('click', function () { onpick(o[0]); });
            c.appendChild(b);
        });
        return g;
    }

    // ---- the forecast output: the map for the selected day, blended over the ensemble's pattern votes (or one pattern)
    function forecastValue(d, mode, z) {
        var info = state.zones.zones[z];
        if (mode !== 'blend') { var r = info.patterns[+mode]; return { pct: r.shift_pct, sig: r.verdict !== 'average' }; }
        var pcts = 0, verd = [];
        for (var p = 0; p < NAMES.length; p++) {
            var w = (d.votes[p] || 0) / d.members; if (!w) continue;
            pcts += w * info.patterns[p].shift_pct;
            if (w >= 0.25) verd.push(info.patterns[p].verdict);
        }
        return { pct: pcts, sig: verd.length > 0 && verd[0] !== 'average' && verd.every(function (v) { return v === verd[0]; }) };
    }

    function renderZones() {
        ui.zones.textContent = '';
        renderMatrix();
        if (!state.zones) return;
        var d = days()[state.day], cs = called(d);
        var w = wetness(d);
        if (w.dry) { ui.zones.appendChild(el('p', 'pf-msg', d.label + ': dry over the Cascades (' + w.tip.toLowerCase() + '), so there is no storm to sort into a pattern.')); return; }
        if (!cs.length) { ui.zones.appendChild(el('p', 'pf-msg', d.label + ': the lowest low is not close to any of the six patterns, which usually means an unremarkable storm that will not make any zone stand out.')); return; }
        if (!state.basins) { ui.zones.appendChild(el('p', 'pf-msg', 'The zone map is not available right now; see the table under “All six patterns”.')); return; }
        if (state.fmode !== 'blend' && cs.indexOf(state.fmode) < 0) state.fmode = 'blend';
        if (cs.length > 1) {
            var opts = [['blend', 'Blend of members', 'Weighted by how many members chose each pattern']].concat(cs.map(function (p) { return [p, 'Pattern ' + p, NAMES[+p]]; }));
            ui.zones.appendChild(chipRow('Show', opts, state.fmode, function (v) { state.fmode = v; renderZones(); }));
        }
        var single = cs.length === 1 ? cs[0] : state.fmode;
        ui.zones.appendChild(el('p', 'pf-maptitle', d.label + ': ' + (single === 'blend' ? 'blend of ' + (d.members > 1 ? 'members' : 'patterns') : 'Pattern ' + single + ' · ' + NAMES[+single]) + ' \u00B7 ' + w.label.toLowerCase() + ' (' + w.inches.toFixed(2) + ' in)'));
        ui.zones.appendChild(mapView({
            sel: 'selF',
            value: function (z) { return forecastValue(d, single === 'blend' ? 'blend' : single, z); },
            onPick: function (z) { var pp = single === 'blend' ? +cs[0] : +single; state.selF = state.selF && state.selF.z === z ? null : { z: z, p: pp }; renderZones(); }
        }));
        ui.zones.appendChild(scaleLegend());
        ui.zones.appendChild(el('p', 'pf-legend', 'How much more (+) or less (−) water to expect than the average storm of this kind. Dark outline: greater likelihood. Click a zone.'));
        var pn = cellPanel('selF', renderZones);
        if (pn) ui.zones.appendChild(pn);
    }

    // ---- the dropdown: every pattern, as a map or a table
    function renderMatrix() {
        ui.allbody.textContent = '';
        if (!state.zones) return;
        var cs = called(days()[state.day]), bar = el('div', 'ol-ctrl pf-allctrl');
        var vopts = [['map', 'Map'], ['table', 'Table']];
        bar.appendChild(chipRow('View', vopts, state.view, function (v) { if (v === 'map' && !state.basins) return; state.view = v; renderMatrix(); }));
        if (state.view === 'map' && state.basins) {
            bar.appendChild(chipRow('Pattern', NAMES.map(function (n, q) { return [q, String(q), n]; }), state.mapPat, function (q) { state.mapPat = q; if (state.selA) state.selA = { z: state.selA.z, p: q }; renderMatrix(); }));
        }
        ui.allbody.appendChild(bar);
        if (state.view === 'map' && state.basins) {
            var q = state.mapPat;
            ui.allbody.appendChild(el('p', 'pf-maptitle', 'Pattern ' + q + ': ' + NAMES[q]));
            ui.allbody.appendChild(mapView({
                sel: 'selA',
                value: function (z) { var r = state.zones.zones[z].patterns[q]; return { pct: r.shift_pct, sig: r.verdict !== 'average' }; },
                onPick: function (z) { state.selA = state.selA && state.selA.z === z ? null : { z: z, p: q }; renderMatrix(); }
            }));
        } else {
            var t = el('table', 'pf-table pf-table--all'), head = el('tr');
            head.appendChild(el('th', null, ''));
            for (var p = 0; p < NAMES.length; p++) {
                var th = el('th', 'pf-colhead' + (cs.indexOf(String(p)) >= 0 ? ' pf-colhead--on' : ''));
                var sw = el('span', 'pf-sw'); sw.style.background = COLORS[p];
                th.appendChild(sw); th.appendChild(document.createTextNode('Pattern ' + p)); th.appendChild(el('small', null, SHORT[p])); th.title = NAMES[p];
                head.appendChild(th);
            }
            t.appendChild(head);
            ZONES.forEach(function (z) {
                var info = state.zones.zones[z]; if (!info) return;
                var tr = el('tr'); tr.appendChild(el('th', 'pf-zone', z));
                info.patterns.forEach(function (r) { tr.appendChild(pill(r, info, z)); });
                t.appendChild(tr);
            });
            var wrap = el('div', 'pf-tablewrap'); wrap.appendChild(t);
            ui.allbody.appendChild(wrap);
        }
        ui.allbody.appendChild(scaleLegend());
        ui.allbody.appendChild(el('p', 'pf-legend', '2,111 storm days, Nov 15–Apr 30, 1992–2026. Click ' + (state.view === 'map' ? 'a zone' : 'a cell') + ' for its picture.'));
        var pm = cellPanel('selA', renderMatrix);
        if (pm) ui.allbody.appendChild(pm);
    }

    function get(url) { return fetch(url).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
    function load(base) {
        return Promise.all([get(base + 'pattern_forecast.json'), get(base + 'pattern_zones.json')]).then(function (r) { state.base = base; return r; });
    }
    function optional(attr) { var u = root.getAttribute(attr); return u ? get(u).catch(function () { return null; }) : Promise.resolve(null); }
    var remote = root.getAttribute('data-remote'), local = root.getAttribute('data-local');
    var extras = Promise.all([optional('data-basins'), optional('data-land')]);
    load(remote).catch(function () { return load(local); })
        .then(function (r) { return extras.then(function (x) { state.basins = x[0]; state.land = x[1]; if (!x[0]) state.view = 'table'; return r; }); })
        .then(function (r) { state.fc = r[0]; state.zones = r[1]; build(); },
              function () { root.appendChild(el('p', 'ol-fail', 'The forecast frames are not available right now.')); });
})();
