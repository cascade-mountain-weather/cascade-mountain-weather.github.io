// Homepage "season vs normal" bar charts, drawn with plain DOM/CSS (no chart library).
// Data: assets/data/normals.json, written daily by scripts/collect_normals.py.
// A missing value renders as an en dash with no bar.

(function () {
    'use strict';

    const root = document.getElementById('season-normals');
    if (!root) return;
    const grid = document.getElementById('normals-grid');
    const foot = document.getElementById('normals-foot');

    const DASH = '–';
    const esc = s => String(s).replace(/[&<>"']/g, c => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    // pct charts: bar from 0, marker at 100%, axis capped at 200%.
    // temp charts: bar diverges from 0 F, axis capped at +/-10 F.
    const CHARTS = [
        { key: 'precip_pct', title: 'Precipitation, water year to date', sub: '% of median', kind: 'pct',
          note: 'precip_in', fmt: a => a.precip_in === null ? '' : `${a.precip_in.toFixed(1)} in` },
        { key: 'swe_pct', title: 'Snow water equivalent', sub: '% of median for today', kind: 'pct',
          fmt: a => a.swe_in === null ? '' : `${a.swe_in.toFixed(1)} in` },
        { key: 'temp_anom_7d_f', title: 'Temperature, last 7 days', sub: '°F vs 1991–2020 average', kind: 'temp' },
        { key: 'temp_anom_wy_f', title: 'Temperature, water year to date', sub: '°F vs 1991–2020 average', kind: 'temp' },
    ];

    // SNOTEL station name, with the nearest ski area beneath it when there is one.
    const nameCell = a => `<span class="nbar-name">${esc(a.station)}${a.resort ? `<small>${esc(a.resort)}</small>` : ''}</span>`;

    function row(chart, a) {
        const v = a[chart.key];
        if (v === null || v === undefined) {
            return `<li class="nbar">${nameCell(a)}
                <span class="nbar-track"></span><span class="nbar-val">${DASH}</span></li>`;
        }
        if (chart.kind === 'pct') {
            const width = Math.min(v, 200) / 2;           // 0-200% -> 0-100% of track
            const cls = v >= 100 ? 'nbar-fill--wet' : 'nbar-fill--dry';
            const detail = chart.fmt ? chart.fmt(a) : '';
            return `<li class="nbar" title="${detail ? esc(detail) : ''}">
                ${nameCell(a)}
                <span class="nbar-track nbar-track--pct"><span class="nbar-fill ${cls}" style="width:${width}%"></span></span>
                <span class="nbar-val">${v}%</span></li>`;
        }
        const half = Math.min(Math.abs(v), 10) / 10 * 50;  // 0-10 F -> 0-50% of track
        const warm = v >= 0;
        const style = warm ? `left:50%;width:${half}%` : `left:${50 - half}%;width:${half}%`;
        return `<li class="nbar">
            ${nameCell(a)}
            <span class="nbar-track nbar-track--temp"><span class="nbar-fill ${warm ? 'nbar-fill--warm' : 'nbar-fill--cold'}" style="${style}"></span></span>
            <span class="nbar-val">${v > 0 ? '+' : ''}${v.toFixed(1)}°</span></li>`;
    }

    function chartHtml(chart, areas) {
        const have = areas.some(a => a[chart.key] !== null && a[chart.key] !== undefined);
        const body = have
            ? `<ul class="nbars">${areas.map(a => row(chart, a)).join('')}</ul>`
            : '<p class="normals-empty">Not enough data yet this season. This fills in as the water year builds.</p>';
        return `<div class="normals-chart"><h3>${esc(chart.title)}</h3><p class="normals-sub">${esc(chart.sub)}</p>${body}</div>`;
    }

    fetch(root.dataset.src, { cache: 'no-cache' })
        .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(data => {
            grid.innerHTML = CHARTS.map(c => chartHtml(c, data.areas)).join('');
            const through = data.areas.map(a => a.data_through).filter(Boolean).sort().pop();
            foot.textContent = (through ? `Data through ${through}. ` : '') +
                'Updated daily from NRCS SNOTEL stations, labeled with the nearest ski area. Mazama and Alpental have no SNOTEL station, so they are not shown.';
        })
        .catch(err => {
            console.error('Season normals failed:', err && err.stack ? err.stack : err);
            grid.innerHTML = '<p class="normals-status">Season comparisons are temporarily unavailable.</p>';
        });
}());
