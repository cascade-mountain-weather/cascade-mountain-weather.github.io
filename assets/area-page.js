// Fills an area page's charts (_layouts/area.html): the snowfall and precipitation plumes (CMWPlume, from
// assets/post-plume-map.js) and the NBM cloud cover (CMWCloud, from assets/nbm-cloud-chart.js) for one site.
// Reads assets/data/plume_live.json and assets/data/nbm_plumes.json, the files the model_data.yml workflow keeps current.
(function () {
  'use strict';
  var root = document.getElementById('area-charts');
  if (!root) return;
  var site = root.getAttribute('data-site');
  var get = function (u) { return fetch(u, { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw new Error(u); return r.json(); }).catch(function () { return null; }); };
  var img = function (svg, alt) {
    var im = document.createElement('img');
    im.className = 'PlotFormat'; im.alt = alt; im.decoding = 'async';
    im.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    return im;
  };
  var put = function (kind, svg, alt, cap) {
    var fig = root.querySelector('[data-chart="' + kind + '"]');
    if (!fig) return;
    fig.textContent = '';
    if (!svg) { var m = document.createElement('div'); m.className = 'area-loading'; m.textContent = 'This chart is not available right now.'; fig.appendChild(m); return; }
    fig.appendChild(img(svg, alt));
    if (cap) { var c = document.createElement('figcaption'); c.textContent = cap; fig.appendChild(c); }
  };
  var z = function (t) { return t ? t.replace('T', ' ') : ''; };

  // the chart scripts are deferred, so wait until both are ready
  function start() {
    Promise.all([get(root.getAttribute('data-plume-src')), get(root.getAttribute('data-nbm-src'))]).then(function (r) {
      var plume = r[0], nbm = r[1], P = window.CMWPlume, C = window.CMWCloud;
      var cyc = plume && plume.cycles ? plume.cycles : {};
      var runs = 'Model runs: NBM ' + z(cyc.nbm) + (cyc.hrrr ? ', HRRR ' + z(cyc.hrrr) : '') + (cyc.rrfs ? ', RRFS ' + z(cyc.rrfs) : '') + (cyc.hrdps ? ', HRDPS ' + z(cyc.hrdps) : '') + '.';
      ['snow', 'precip'].forEach(function (k) {
        var out = P && plume && P.chartSvg(plume, site, k);
        put(k, out && out.svg, (k === 'snow' ? 'Snowfall' : 'Liquid precipitation') + ' plume for ' + site + ' from the NBM, HRRR, RRFS and HRDPS', out ? runs : '');
      });
      var cloud = C && nbm && C.chartSvg(nbm, site);
      put('cloud', cloud, 'NBM cloud cover forecast for ' + site, nbm ? 'NBM run ' + z(nbm.cycle_utc) + '.' : '');
    });
  }
  if (document.readyState === 'complete') start(); else window.addEventListener('load', start);
})();
