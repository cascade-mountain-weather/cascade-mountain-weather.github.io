// Interactive plume map for a forecast post.
//
//   <div class="plume-map" data-src="../assets/images/YYYYMMDD_fx/plume_data.json"></div>
//
// data-src is the frozen file written by scripts/post_plume.py, so the map shows the numbers the post was
// written against and never changes afterward. Sites are colored by their total snow or liquid precipitation
// for the window; click a site (or its chip) to see that site's two plumes (snowfall and liquid precipitation) and its
// snow table. Optional ours.json next to the data file supplies the "Our call" row. No libraries: plain SVG.
(function () {
  'use strict';
  var SVGNS = 'http://www.w3.org/2000/svg';
  var CH = 400;   // height of each plume chart (SVG units)
  var BBOX = { lon0: -124.9, lon1: -119.4, lat0: 45.0, lat1: 49.2 };
  var MODELS = { nbm: { label: 'NBM', color: '#1e3c72' }, hrrr: { label: 'HRRR', color: '#dc2626', dx: -2 }, rrfs: { label: 'RRFS', color: '#16a34a', dx: 2 }, hrdps: { label: 'HRDPS', color: '#7c3aed', dx: 6 } };
  var PRODUCTS = {
    snow: { label: 'Snowfall', unit: 'snow', ramp: ['#dbe6f3', '#a9c8f2', '#5b8fd6', '#1e3c72'], floor6: 1, floorC: 2, colorFloor: 4, bar: '#3b82f6' },
    precip: { label: 'Liquid precipitation', unit: 'liquid', ramp: ['#d7ece8', '#8fd0c4', '#3aa595', '#0b4f4a'], floor6: 0.25, floorC: 0.5, colorFloor: 1, bar: '#0f766e' }
  };
  var PAC_H = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', hour: 'numeric', hourCycle: 'h23' });
  var PAC_D = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', weekday: 'short', month: 'numeric', day: 'numeric' });

  function el(name, attrs, parent, text) {
    var n = document.createElementNS(SVGNS, name);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (text != null) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  }
  function h(tag, attrs, parent, text) {
    var n = document.createElement(tag);
    for (var k in attrs) { if (k === 'class') n.className = attrs[k]; else n.setAttribute(k, attrs[k]); }
    if (text != null) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  }
  var clock = function (t) { var x = +PAC_H.format(t); return x === 0 ? '12a' : x < 12 ? x + 'a' : x === 12 ? '12p' : (x - 12) + 'p'; };
  var fmt = function (v, d) { return v == null ? 'n/a' : v.toFixed(d); };
  var nice = function (m) { var st = m <= 1 ? 0.25 : m <= 2 ? 0.5 : m <= 4 ? 1 : m <= 12 ? 2 : m <= 30 ? 5 : 10; return Math.ceil(m / st) * st; };
  var step = function (m) { return m <= 1 ? 0.25 : m <= 2 ? 0.5 : m <= 4 ? 1 : m <= 12 ? 2 : m <= 30 ? 5 : 10; };

  function cumulate(arr) { var c = [0]; for (var i = 0; i < arr.length; i++) { if (arr[i] == null) break; c.push(c[c.length - 1] + arr[i]); } return c; }
  function lerpColor(ramp, f) {
    f = Math.max(0, Math.min(1, f));
    var p = f * (ramp.length - 1), i = Math.min(ramp.length - 2, Math.floor(p)), u = p - i;
    var a = ramp[i], b = ramp[i + 1], ch = function (s, o) { return parseInt(s.substr(o, 2), 16); };
    var out = [1, 3, 5].map(function (o) { return Math.round(ch(a, o) + (ch(b, o) - ch(a, o)) * u); });
    return 'rgb(' + out.join(',') + ')';
  }

  function Plume(root, data, base, basins, ours) {
    var self = this;
    this.data = data;
    this.ours = ours || {};
    this.names = Object.keys(data.sites);
    this.ends = data.ends_utc.map(function (t) { return Date.parse(t); });
    var d0 = root.dataset || {};   // optional defaults: data-product="snow|precip", data-site="Crystal"
    this.state = { product: PRODUCTS[d0.product] ? d0.product : 'snow', model: 'nbm', same: true,
      site: this.names.indexOf(d0.site) >= 0 ? d0.site : this.names.indexOf('Mt. Baker') >= 0 ? 'Mt. Baker' : this.names[0] };

    // ---- controls ----
    var bar = h('div', { 'class': 'pm-controls' }, root);
    var seg = function (label, opts, key) {
      var g = h('div', { 'class': 'pm-group', role: 'group', 'aria-label': label }, bar);
      h('span', { 'class': 'pm-label' }, g, label);
      opts.forEach(function (o) {
        var b = h('button', { type: 'button', 'data-k': key, 'data-v': o[0], 'aria-pressed': 'false' }, g, o[1]);
        b.addEventListener('click', function () { self.state[key] = o[0]; self.render(); });
      });
    };
    seg('Color map by', [['snow', 'Snowfall'], ['precip', 'Liquid precip']], 'product');
    var models = ['nbm', 'hrrr', 'rrfs', 'hrdps'].filter(function (m) { return m === 'nbm' || self.names.some(function (n) { return data.sites[n][m]; }); });
    seg('Using', models.map(function (m) { return [m, MODELS[m].label]; }), 'model');
    var lab = h('label', { 'class': 'pm-check' }, bar);
    this.sameBox = h('input', { type: 'checkbox', checked: 'checked' }, lab);
    h('span', {}, lab, ' Same scale for every site');
    this.sameBox.addEventListener('change', function () { self.state.same = self.sameBox.checked; self.render(); });

    // ---- layout ----
    var grid = h('div', { 'class': 'pm-grid' }, root);
    var left = h('div', { 'class': 'pm-left' }, grid);
    this.right = h('div', { 'class': 'pm-right' }, grid);
    this.mapSvg = el('svg', { 'class': 'pm-map', viewBox: '0 0 420 470', role: 'img', 'aria-label': 'Map of Washington Cascades sites, colored by forecast total' }, null);
    left.appendChild(this.mapSvg);
    this.legend = h('div', { 'class': 'pm-legend' }, left);
    this.chips = h('div', { 'class': 'pm-chips' }, left);
    this.title = h('h3', { 'class': 'pm-title' }, this.right);
    this.charts = {};
    ['snow', 'precip'].forEach(function (pk) {
      var block = h('div', { 'class': 'pm-plume' }, self.right);
      var head = h('div', { 'class': 'pm-plume-head' }, block);
      h('h4', { 'class': 'pm-h4' }, head, PRODUCTS[pk].label + ' plume');
      var zoom = h('div', { 'class': 'pm-zoom', role: 'group', 'aria-label': 'Zoom the plume chart' }, head);
      var scroller = h('div', { 'class': 'pm-chart-scroll' }, block);
      var svg = el('svg', { 'class': 'pm-chart', viewBox: '0 0 760 ' + CH, role: 'img', 'aria-label': PRODUCTS[pk].label + ' plume for the selected site' }, null);
      scroller.appendChild(svg);
      var level = 1, apply = function () {
        svg.style.width = (level * 100) + '%';
        scroller.classList.toggle('zoomed', level > 1);
        zin.disabled = level >= 4; zout.disabled = level <= 1; zreset.disabled = level === 1;
      };
      var zbtn = function (txt, label, fn) { var b = h('button', { type: 'button', 'aria-label': label, title: label }, zoom, txt); b.addEventListener('click', fn); return b; };
      var zout = zbtn('−', 'Zoom out', function () { level = Math.max(1, level - 0.5); apply(); });
      var zin = zbtn('+', 'Zoom in', function () { level = Math.min(4, level + 0.5); apply(); });
      var zreset = zbtn('Reset', 'Reset zoom', function () { level = 1; apply(); scroller.scrollLeft = 0; });
      apply();
      self.charts[pk] = { block: block, svg: svg, sum: h('p', { 'class': 'pm-sum' }, block) };
    });
    this.tableBox = h('div', { 'class': 'pm-table-box' }, this.right);
    this.note = h('p', { 'class': 'pm-note' }, root);

    // ---- projection and static basemap ----
    var k = 460 / (BBOX.lat1 - BBOX.lat0), cx = Math.cos(47 * Math.PI / 180);
    this.proj = function (lon, lat) { return [10 + (lon - BBOX.lon0) * cx * k * 0.98, 5 + (BBOX.lat1 - lat) * k]; };
    this.drawBase(base, basins);
    this.siteLayer = el('g', {}, this.mapSvg);
    this.render();
  }

  Plume.prototype.drawBase = function (base, basins) {
    var self = this, svg = this.mapSvg;
    el('rect', { width: 420, height: 470, fill: '#e9f1fa' }, svg);
    var path = function (ring) { return 'M' + ring.map(function (p) { var q = self.proj(p[0], p[1]); return q[0].toFixed(1) + ' ' + q[1].toFixed(1); }).join('L') + 'Z'; };
    if (base && base.states) Object.keys(base.states).forEach(function (s) {
      var d = base.states[s].map(path).join('');
      el('path', { d: d, fill: s === 'Washington' ? '#fbfcfe' : '#f1f3f6', stroke: '#9aa8bb', 'stroke-width': 1, 'fill-rule': 'evenodd' }, svg);
    });
    if (basins && basins.features) basins.features.forEach(function (f) {
      var g = f.geometry, polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
      el('path', { d: polys.map(function (pl) { return pl.map(path).join(''); }).join(''), fill: 'none', stroke: '#c5d0de', 'stroke-width': 0.8 }, svg);
    });
  };

  // total over the window for one site, model and product: sum of the values until the model's data ends
  Plume.prototype.totalFor = function (name, model, product) {
    var s = this.data.sites[name], src = model === 'nbm' ? s.nbm : s[model];
    if (!src) return { v: null, n: 0 };
    var arr = model === 'nbm' ? (product === 'snow' ? src.p50 : src.precip) : (product === 'snow' ? src.snow : src.precip), t = 0, n = 0;
    for (var i = 0; i < arr.length; i++) { if (arr[i] == null) break; t += arr[i]; n++; }
    return { v: n ? t : null, n: n };
  };

  Plume.prototype.render = function () {
    var self = this, st = this.state, P = PRODUCTS[st.product];
    this.root = this.root || null;
    Array.prototype.forEach.call(document.querySelectorAll('.plume-map .pm-controls button'), function (b) {
      if (b.closest('.plume-map') !== self.mapSvg.closest('.plume-map')) return;
      b.setAttribute('aria-pressed', String(st.hasOwnProperty(b.dataset.k) && st[b.dataset.k] === b.dataset.v));
    });
    // color scale: top of the ramp is the largest total (never below a floor, so a dry weekend stays pale)
    var totals = {}, mx = P.colorFloor;
    this.names.forEach(function (n) { var t = self.totalFor(n, st.model, st.product); totals[n] = t; if (t.v != null && t.v > mx) mx = t.v; });
    this.colorMax = mx;
    var d = st.product === 'snow' ? 1 : 2;

    // sites
    var layer = this.siteLayer; while (layer.firstChild) layer.removeChild(layer.firstChild);
    this.names.forEach(function (n) {
      var s = self.data.sites[n], p = self.proj(s.lon, s.lat), t = totals[n], sel = n === st.site;
      var g = el('g', { 'class': 'pm-site' + (sel ? ' sel' : ''), tabindex: 0, role: 'button', 'aria-label': n + ': ' + (t.v == null ? 'no data' : fmt(t.v, d) + ' inches') }, layer);
      el('circle', { cx: p[0], cy: p[1], r: sel ? 12 : 9.5, fill: t.v == null ? '#d9dee5' : lerpColor(P.ramp, t.v / mx), stroke: sel ? '#0f172a' : '#475569', 'stroke-width': sel ? 3 : 1.3 }, g);
      if (t.v == null) el('path', { d: 'M' + (p[0] - 4) + ' ' + (p[1] - 4) + 'l8 8M' + (p[0] + 4) + ' ' + (p[1] - 4) + 'l-8 8', stroke: '#8a94a3', 'stroke-width': 1.4 }, g);
      el('title', {}, g, n + ': ' + (t.v == null ? 'no data for this model' : fmt(t.v, d) + '"' + (t.n < self.ends.length ? ' (model data covers ' + t.n + ' of ' + self.ends.length + ' windows)' : '')));
      if (sel) el('text', { x: p[0] + 16, y: p[1] + 4, 'font-size': 13, 'font-weight': 700, fill: '#0f172a', stroke: '#fff', 'stroke-width': 3, 'paint-order': 'stroke' }, g, n);
      var pick = function () { st.site = n; self.render(); };
      g.addEventListener('click', pick);
      g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
    });

    // legend
    this.legend.innerHTML = '';
    h('span', {}, this.legend, MODELS[st.model].label + ' ' + P.unit + ' total for the window: ');
    var ramp = h('span', { 'class': 'pm-ramp' }, this.legend);
    ramp.style.background = 'linear-gradient(90deg,' + P.ramp.join(',') + ')';
    h('span', {}, this.legend, ' 0 to ' + fmt(mx, d) + '"  ');
    h('span', { 'class': 'pm-nodata' }, this.legend, '✖ no data');

    // chips, biggest total first
    this.chips.innerHTML = '';
    this.names.slice().sort(function (a, b) { return (totals[b].v == null ? -1 : totals[b].v) - (totals[a].v == null ? -1 : totals[a].v); }).forEach(function (n) {
      var t = totals[n], b = h('button', { type: 'button', 'class': 'pm-chip' + (n === st.site ? ' sel' : ''), 'aria-pressed': String(n === st.site) }, self.chips);
      var sw = h('span', { 'class': 'pm-sw' }, b); sw.style.background = t.v == null ? '#d9dee5' : lerpColor(P.ramp, t.v / mx);
      h('span', {}, b, n + ' ');
      h('strong', {}, b, t.v == null ? 'n/a' : fmt(t.v, d) + '"');
      b.addEventListener('click', function () { st.site = n; self.render(); });
    });

    this.title.textContent = st.site + (st.same ? '' : ' (plots use this site’s own scale)');
    // show only the plume for the selected product ("Color map by")
    ['snow', 'precip'].forEach(function (pk) { self.charts[pk].block.hidden = pk !== st.product; });
    this.drawChart(st.product);
    this.tableBox.hidden = st.product !== 'snow';   // the table is snowfall only
    if (!this.tableBox.hidden) this.drawTable();
    var c =this.data.cycles;
    this.note.textContent = 'Frozen when this post was written (NBM ' + c.nbm.replace('T', ' ') + (c.hrrr ? ', HRRR ' + c.hrrr.replace('T', ' ') : '') + (c.hrdps ? ', HRDPS ' + c.hrdps.replace('T', ' ') : '') +
      '). Forecast days run 4 am to 4 am Pacific. Values are at the nearest model grid point, not corrected for elevation; HRDPS snowfall assumes a 10:1 ratio. A model that does not reach the whole window is totaled only as far as it goes. For current numbers see the meteograms.';
  };

  // largest values over all sites, so every site can share one scale
  Plume.prototype.extent = function (product, onlySite) {
    var self = this, P = PRODUCTS[product], m6 = P.floor6, mc = P.floorC;
    (onlySite ? [onlySite] : this.names).forEach(function (n) {
      var s = self.data.sites[n], nb = s.nbm, hi = product === 'snow' ? nb.p75 : nb.precip, mid = product === 'snow' ? nb.p50 : nb.precip;
      hi.forEach(function (v, i) { var x = v != null ? v : mid[i]; if (x != null && x * 1.1 > m6) m6 = x * 1.1; });
      (product === 'snow' ? nb.det : []).forEach(function (v) { if (v != null && v * 1.1 > m6) m6 = v * 1.1; });
      var cs = cumulate(hi.map(function (v, i) { return v != null ? v : mid[i]; })); mc = Math.max(mc, cs[cs.length - 1] * 1.05);
      ['hrrr', 'rrfs', 'hrdps'].forEach(function (k) {
        if (!s[k]) return;
        var a = product === 'snow' ? s[k].snow : s[k].precip;
        a.forEach(function (v) { if (v != null && v * 1.1 > m6) m6 = v * 1.1; });
        var c = cumulate(a); mc = Math.max(mc, c[c.length - 1] * 1.05);
      });
    });
    return { m6: nice(m6), mc: nice(mc) };
  };

  Plume.prototype.drawChart = function (product) {
    var st = this.state, P = PRODUCTS[product], s = this.data.sites[st.site], svg = this.charts[product].svg, snow = product === 'snow';
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var ends = this.ends, W = 6 * 3600e3, n = ends.length, t0 = ends[0] - W, t1 = ends[n - 1];
    var ext = this.extent(product, st.same ? null : st.site), d = snow ? 1 : 2;
    var padL = 52, padR = 16, plotW = 760 - padL - padR, X = function (t) { return padL + (t - t0) / (t1 - t0) * plotW; };
    var A = { y0: 34, h: 125 }, B = { y0: 222, h: 125 }, YA = function (v) { return A.y0 + A.h - v / ext.m6 * A.h; }, YB = function (v) { return B.y0 + B.h - v / ext.mc * B.h; };
    el('rect', { width: 760, height: CH, fill: '#fff' }, svg);
    var grid = function (p, M, Y, label) {
      var g = step(M);
      for (var v = 0; v <= M + 1e-9; v += g) {
        el('line', { x1: padL, x2: 760 - padR, y1: Y(v), y2: Y(v), stroke: '#e2e8f0' }, svg);
        el('text', { x: padL - 6, y: Y(v) + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' }, svg, +v.toFixed(2));
      }
      el('text', { x: 13, y: p.y0 + p.h / 2, transform: 'rotate(-90 13 ' + (p.y0 + p.h / 2) + ')', 'text-anchor': 'middle', 'font-size': 12, fill: '#334155' }, svg, label);
    };
    grid(A, ext.m6, YA, (snow ? 'snow' : 'liquid') + ' inches per 6 h');
    grid(B, ext.mc, YB, (snow ? 'snow' : 'liquid') + ' inches accumulated');
    // 6-hour ticks, 4 am day edges
    for (var i = 0; i <= n; i++) {
      var t = t0 + i * W, edge = new Date(t).getUTCHours() === 12;
      [A, B].forEach(function (p) { el('line', { x1: X(t), x2: X(t), y1: p.y0, y2: p.y0 + p.h, stroke: edge ? '#94a3b8' : '#eef2f7', 'stroke-dasharray': edge ? '3 3' : '' }, svg); });
      el('text', { x: X(t), y: B.y0 + B.h + 14, 'text-anchor': 'middle', 'font-size': 10, fill: '#64748b' }, svg, clock(t));
      if (edge && t < t1) el('text', { x: X(t) + 4, y: B.y0 + B.h + 32, 'font-size': 11.5, 'font-weight': 700, fill: '#334155' }, svg, PAC_D.format(t + 12 * 3600e3).replace(',', ''));
    }
    el('text', { x: padL, y: B.y0 + B.h + 50, 'font-size': 10.5, fill: '#64748b' }, svg, 'Pacific time. Dashed lines are 4 am; the day label is the forecast day that follows.');
    // NBM rates per 6 h: dots (median) with a light dashed line; whiskers are the 25th-75th percentile
    var nb = s.nbm, mid = snow ? nb.p50 : nb.precip, NDX = -6, seg0 = [];
    var flush0 = function () { if (seg0.length > 1) el('polyline', { points: seg0.join(' '), fill: 'none', stroke: '#1e3c72', 'stroke-width': 1, 'stroke-dasharray': '3 2', opacity: 0.5 }, svg); seg0 = []; };
    for (var j = 0; j < n; j++) { if (mid[j] == null) flush0(); else seg0.push((X(ends[j] - W / 2) + NDX) + ',' + YA(mid[j])); }
    flush0();
    for (var j2 = 0; j2 < n; j2++) {
      if (mid[j2] == null) continue;
      var xc = X(ends[j2] - W / 2) + NDX, lbl = clock(ends[j2] - W) + '–' + clock(ends[j2]);
      if (snow && nb.p25[j2] != null && nb.p75[j2] != null) {
        el('line', { x1: xc, x2: xc, y1: YA(nb.p25[j2]), y2: YA(nb.p75[j2]), stroke: '#1e3a8a', 'stroke-width': 1.4, opacity: 0.7 }, svg);
        [nb.p25[j2], nb.p75[j2]].forEach(function (v) { el('line', { x1: xc - 3, x2: xc + 3, y1: YA(v), y2: YA(v), stroke: '#1e3a8a', 'stroke-width': 1.4, opacity: 0.7 }, svg); });
      }
      var dot = el('circle', { cx: xc, cy: YA(mid[j2]), r: 4.2, fill: '#1e3c72', stroke: '#fff' }, svg);
      el('title', {}, dot, lbl + ' NBM ' + fmt(mid[j2], d + 1) + '"' + (snow && nb.p25[j2] != null ? ' (25th–75th: ' + fmt(nb.p25[j2], d + 1) + '–' + fmt(nb.p75[j2], d + 1) + '")' : ''));
    }
    // HRRR / RRFS / HRDPS rates per 6 h: dots joined by a light dashed line (broken where a model has no data)
    var shape = function (k, x, y) {
      if (k === 'hrrr') return 'M' + x + ' ' + (y - 4.5) + 'L' + (x + 4.5) + ' ' + y + 'L' + x + ' ' + (y + 4.5) + 'L' + (x - 4.5) + ' ' + y + 'Z';
      if (k === 'rrfs') return 'M' + (x - 4) + ' ' + (y - 4) + 'h8v8h-8Z';
      return 'M' + x + ' ' + (y - 4.5) + 'L' + (x + 4.5) + ' ' + (y + 3.5) + 'L' + (x - 4.5) + ' ' + (y + 3.5) + 'Z';
    };
    ['hrrr', 'rrfs', 'hrdps'].forEach(function (k) {
      if (!s[k]) return;
      var a = snow ? s[k].snow : s[k].precip, col = MODELS[k].color, seg = [];
      var flush = function () { if (seg.length > 1) el('polyline', { points: seg.join(' '), fill: 'none', stroke: col, 'stroke-width': 1, 'stroke-dasharray': '3 2', opacity: 0.5 }, svg); seg = []; };
      a.forEach(function (v, j) { if (v == null) { flush(); return; } seg.push((X(ends[j] - W / 2) + MODELS[k].dx) + ',' + YA(v)); });
      flush();
      a.forEach(function (v, j) {
        if (v == null) return;
        var m = el('path', { d: shape(k, X(ends[j] - W / 2) + MODELS[k].dx, YA(v)), fill: col, stroke: '#fff' }, svg);
        el('title', {}, m, clock(ends[j] - W) + '–' + clock(ends[j]) + ' ' + MODELS[k].label + ' ' + fmt(v, d + 1) + '"');
      });
    });
    // accumulation: NBM band and median, models dashed
    var parts = [], sumTxt = [];
    if (snow) {
      var lo = cumulate(nb.p25.map(function (v, j) { return v != null ? v : nb.p50[j]; })), hi = cumulate(nb.p75.map(function (v, j) { return v != null ? v : nb.p50[j]; })), md = cumulate(nb.p50), m = md.length;
      if (m > 1) {
        var xs = []; for (var q = 0; q < m; q++) xs.push(X(t0 + q * W));
        var up = xs.map(function (x, q) { return x + ',' + YB(hi[q]); }), dn = xs.map(function (x, q) { return x + ',' + YB(lo[q]); }).reverse();
        el('polygon', { points: up.concat(dn).join(' '), fill: '#3b82f6', opacity: 0.18 }, svg);
        el('polyline', { points: xs.map(function (x, q) { return x + ',' + YB(md[q]); }).join(' '), fill: 'none', stroke: '#1e3c72', 'stroke-width': 2.4 }, svg);
        sumTxt.push('NBM ' + fmt(md[m - 1], 1) + '" (' + fmt(lo[m - 1], 1) + '–' + fmt(hi[m - 1], 1) + '")');
      }
    } else {
      var cp = cumulate(nb.precip);
      if (cp.length > 1) {
        el('polyline', { points: cp.map(function (v, q) { return X(t0 + q * W) + ',' + YB(v); }).join(' '), fill: 'none', stroke: '#1e3c72', 'stroke-width': 2.4 }, svg);
        sumTxt.push('NBM ' + fmt(cp[cp.length - 1], 2) + '"');
      }
    }
    ['hrrr', 'rrfs', 'hrdps'].forEach(function (k) {
      if (!s[k]) return;
      var c = cumulate(snow ? s[k].snow : s[k].precip);
      if (c.length > 1) {
        el('polyline', { points: c.map(function (v, q) { return X(t0 + q * W) + ',' + YB(v); }).join(' '), fill: 'none', stroke: MODELS[k].color, 'stroke-width': 2.2, 'stroke-dasharray': '6 3' }, svg);
        sumTxt.push(MODELS[k].label + ' ' + fmt(c[c.length - 1], snow ? 1 : 2) + '"' + (c.length - 1 < n ? ' (through ' + clock(t0 + (c.length - 1) * W) + ')' : ''));
      }
    });
    // legend row
    var lx = padL; [['NBM', '#1e3c72']].concat(['hrrr', 'rrfs', 'hrdps'].filter(function (k) { return s[k] && (snow ? s[k].snow : s[k].precip).some(function (v) { return v != null; }); }).map(function (k) { return [MODELS[k].label, MODELS[k].color]; })).forEach(function (e) {
      el('rect', { x: lx, y: 10, width: 12, height: 12, fill: e[1] }, svg); el('text', { x: lx + 17, y: 21, 'font-size': 12, fill: '#334155' }, svg, e[0]); lx += 24 + e[0].length * 8;
    });
    el('text', { x: padL, y: B.y0 - 8, 'font-size': 11, fill: '#64748b' }, svg, 'Accumulation' + (snow ? ' (line: sum of NBM medians; shading: 25th to 75th percentile, approximate)' : ''));
    this.charts[product].sum.textContent = 'Window total: ' + (sumTxt.length ? sumTxt.join('  |  ') : 'no data for this site') + '.';
  };

  // Snow table for the selected site: rows are the models plus "Our call"; columns are 12-hour periods of each forecast
  // day (two 6-hour windows each). "—" = no data; "*" = only one of the period's two windows exists.
  Plume.prototype.drawTable = function () {
    var self = this, st = this.state, s = this.data.sites[st.site], ends = this.ends, W = 6 * 3600e3, H12 = 12 * 3600e3;
    var t0 = ends[0] - W, nper = Math.ceil(ends.length / 2), days = Math.ceil(nper / 2), box = this.tableBox, DASH = '—';
    box.innerHTML = '';
    h('h4', { 'class': 'pm-h4' }, box, 'Snow forecast table: ' + st.site);
    var wrap = h('div', { 'class': 'snow-table-wrap' }, box), tb = h('table', { 'class': 'snow-table' }, wrap);
    h('caption', {}, tb, 'Forecast snowfall in inches per 12 hours (forecast days run 4 am to 4 am Pacific), plus total');
    var hd = h('thead', {}, tb), r1 = h('tr', {}, hd), r2 = h('tr', {}, hd);
    h('th', { rowspan: 2, scope: 'col' }, r1, 'Source'); 
    for (var dd = 0; dd < days; dd++) {
      var np = Math.min(2, nper - dd * 2);
      h('th', { colspan: np, scope: 'colgroup' }, r1, PAC_D.format(t0 + dd * 24 * 3600e3 + 12 * 3600e3).replace(',', ''));
    }
    h('th', { rowspan: 2, scope: 'col' }, r1, 'Total');
    for (var k = 0; k < nper; k++) h('th', { scope: 'col' }, r2, clock(t0 + k * H12) + '–' + clock(t0 + (k + 1) * H12));
    var body = h('tbody', {}, tb);
    [['hrrr', 'HRRR'], ['rrfs', 'RRFS'], ['hrdps', 'HRDPS'], ['nbm', 'NBM']].forEach(function (m) {
      var vals = m[0] === 'nbm' ? s.nbm.p50 : (s[m[0]] ? s[m[0]].snow : null), tr = h('tr', {}, body), tot = 0, got = 0, full = true;
      h('th', { scope: 'row' }, tr, m[1]);
      for (var k = 0; k < nper; k++) {
        var pair = vals ? [vals[2 * k], vals[2 * k + 1]].filter(function (v) { return v != null; }) : [], want = Math.min(2, ends.length - 2 * k), txt;
        if (!pair.length) { txt = DASH; full = false; }
        else {
          var sum = pair.reduce(function (a, b) { return a + b; }, 0);
          tot += sum; got++; if (pair.length < want) full = false;
          txt = (Math.round(sum * 10) / 10 === 0 ? '0' : sum.toFixed(1)) + (pair.length < want ? '*' : '');
        }
        h('td', {}, tr, txt);
      }
      h('td', { 'class': 'total' }, tr, got ? (Math.round(tot * 10) / 10 === 0 ? '0' : tot.toFixed(1)) + (full ? '' : '*') : DASH);
    });
    var mine = (self.ours && self.ours[st.site]) || {}, tr = h('tr', { 'class': 'mine' }, body);
    h('th', { scope: 'row' }, tr, 'Our call');
    for (var q = 0; q < nper; q++) h('td', {}, tr, (mine.periods && mine.periods[q] != null) ? String(mine.periods[q]) : DASH);
    h('td', { 'class': 'total' }, tr, mine.total != null ? String(mine.total) : DASH);
    h('p', { 'class': 'snow-table-note' }, box, 'Inches of new snow as each model reports it (HRRR and RRFS snow depth; HRDPS water equivalent x 10; NBM median). “' + DASH + '”: the model has no data for that period. “*”: only part of the period (or window) is covered. “Our call” is our own estimate, not an average of the models.');
  };

  // One site's plume as a standalone SVG string (no map, controls or table), for the precipitation tools page.
  // data is the plume JSON (frozen or live); product is 'snow' or 'precip'. Returns { svg, summary } or null.
  function chartSvg(data, site, product) {
    if (!data || !data.sites || !data.sites[site] || !PRODUCTS[product]) return null;
    var self = Object.create(Plume.prototype), svg = el('svg', { viewBox: '0 0 760 ' + CH, width: 760, height: CH, xmlns: SVGNS, 'font-family': 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif' }, null);
    self.data = data; self.ours = {};
    self.names = Object.keys(data.sites);
    self.ends = data.ends_utc.map(function (t) { return Date.parse(t); });
    self.state = { product: product, model: 'nbm', same: false, site: site };
    self.charts = {}; self.charts[product] = { svg: svg, sum: {} };
    self.drawChart(product);
    var summary = self.charts[product].sum.textContent || '';
    svg.setAttribute('viewBox', '0 0 760 ' + (CH + 26)); svg.setAttribute('height', CH + 26);
    el('rect', { y: CH, width: 760, height: 26, fill: '#fff' }, svg);
    el('text', { x: 52, y: CH + 12, 'font-size': 11, fill: '#334155' }, svg, summary.replace(/^Window total: /, 'Total: '));
    return { svg: new XMLSerializer().serializeToString(svg), summary: summary };
  }
  window.CMWPlume = { chartSvg: chartSvg };

  function init(root) {
    var src = root.getAttribute('data-src');
    var baseSrc = root.getAttribute('data-basemap') || '../assets/data/pnw_basemap.json';
    var basinSrc = root.getAttribute('data-basins') || '../assets/data/basins.geojson';
    var get = function (u, opt) { return fetch(u).then(function (r) { if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); }).catch(function (e) { if (opt) return null; throw e; }); };
    root.textContent = 'Loading map…';
    var oursSrc = root.getAttribute('data-ours') || src.replace(/plume_data\.json$/, 'ours.json');
    Promise.all([get(src), get(baseSrc, true), get(basinSrc, true), get(oursSrc, true)]).then(function (r) {
      root.textContent = '';
      var p = new Plume(root, r[0], r[1], r[2], r[3]);
      p.root = root;
    }).catch(function () { root.textContent = 'The plume map could not be loaded. See the meteograms for current model output.'; });
  }

  document.addEventListener('DOMContentLoaded', function () {
    Array.prototype.forEach.call(document.querySelectorAll('.plume-map'), init);
  });
})();
