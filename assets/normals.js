// Homepage "season vs normal": bar chart plus a map. Pick a variable, timeframe and unit.
// Bars are drawn with plain DOM/CSS. The map uses Leaflet (loaded by the conditions-map include);
// without Leaflet only the bars show. Hovering (or focusing) a bar highlights its dot, and
// hovering a dot highlights its bar.
// Data: assets/data/normals.json, written daily by scripts/collect_normals.py.
// A missing value renders as an en dash with no bar, and a hollow grey dot.

(function () {
    'use strict';

    const root = document.getElementById('season-normals');
    if (!root) return;
    const grid = document.getElementById('normals-grid');
    const foot = document.getElementById('normals-foot');
    const varSel = document.getElementById('normals-var');
    const tfSel = document.getElementById('normals-tf');
    const unitSel = document.getElementById('normals-unit');
    const mapWrap = document.getElementById('normals-mapwrap');
    const legendEl = document.getElementById('normals-legend');

    const DASH = '–';
    const esc = s => String(s).replace(/[&<>"']/g, c => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    const TIMEFRAMES = [
        { key: '7', label: 'Last 7 days' },
        { key: '30', label: 'Last 30 days' },
        { key: 'wy', label: 'Water year to date' },
    ];

    // units: first entry is the default for that variable.
    const VARS = {
        precip: { label: 'Precipitation', units: [['pct', '% of normal'], ['in', 'Inches']] },
        swe: { label: 'Snow water equivalent (SWE)', units: [['pct', '% of normal'], ['in', 'Inches']] },
        temp: { label: 'Temperature', units: [['f', '°F vs normal'], ['c', '°C vs normal']] },
    };

    const PCT_CAP = 200;      // percent axis runs 0-200%, with the 100% marker centered
    // Temperature bars and colors saturate at +/-4 F or +/-2 C (whichever unit is selected)
    const TEMP_CAP = { f: 4, c: 2 };

    // One red-blue scale shared by the bars and the map dots. s runs -1 (red) to +1 (blue) with a
    // grey midpoint at normal. Dry and warm are red; wet and cold are blue.
    const SCALE = ['#b2182b', '#e5694d', '#f2b79a', '#cfd6dd', '#9ec8e2', '#4a90c4', '#2166ac'];
    const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
    function colorAt(s) {
        const x = (Math.max(-1, Math.min(1, s)) + 1) / 2 * (SCALE.length - 1);
        const i = Math.min(SCALE.length - 2, Math.floor(x));
        const a = hex(SCALE[i]), b = hex(SCALE[i + 1]), t = x - i;
        return 'rgb(' + a.map((v, k) => Math.round(v + (b[k] - v) * t)).join(',') + ')';
    }

    function nameCell(a) {
        return `<span class="nbar-name">${esc(a.station)}${a.resort ? `<small>${esc(a.resort)}</small>` : ''}</span>`;
    }

    function rowOpen(a, extra) {
        return `<li class="nbar" tabindex="0" data-id="${esc(a.id)}"${extra || ''}>`;
    }

    function emptyRow(a) {
        return `${rowOpen(a)}${nameCell(a)}<span class="nbar-track"></span><span class="nbar-val">${DASH}</span></li>`;
    }

    // One row's data: { value, normal, label, title, s } or null when missing.
    // s is the position on the color scale (null = no color).
    function cell(variable, tf, unit, a) {
        const m = a.metrics[variable][tf];
        if (m === null || m === undefined) return null;
        if (variable === 'temp') {
            const v = unit === 'c' ? m * 5 / 9 : m;
            return { value: v, s: -v / TEMP_CAP[unit === 'c' ? 'c' : 'f'], label: `${v > 0 ? '+' : ''}${v.toFixed(1)}°` };
        }
        const s = m.pct === null ? null : (Math.min(m.pct, PCT_CAP) - 100) / 100;
        if (unit === 'pct') {
            if (m.pct === null) return null;
            return { value: m.pct, s, label: `${m.pct}%`, title: m.normal === null ? '' : `${m.obs.toFixed(1)} in vs ${m.normal.toFixed(1)} in normal` };
        }
        const sign = variable === 'swe' && tf !== 'wy' && m.obs > 0 ? '+' : '';
        return { value: m.obs, normal: m.normal, s, label: `${sign}${m.obs.toFixed(1)} in`,
            title: m.normal === null ? '' : `Normal: ${m.normal.toFixed(1)} in` };
    }

    const fillStyle = c => (c.s === null ? '' : `background:${colorAt(c.s)};`);

    function renderRows(variable, tf, unit, areas) {
        const cells = areas.map(a => [a, cell(variable, tf, unit, a)]);
        if (!cells.some(c => c[1])) return null;

        if (variable === 'temp') {
            return cells.map(([a, c]) => {
                if (!c) return emptyRow(a);
                const cap = TEMP_CAP[unit === 'c' ? 'c' : 'f'];
                const half = Math.min(Math.abs(c.value), cap) / cap * 50;
                const warm = c.value >= 0;
                const pos = warm ? `left:50%;width:${half}%` : `left:${50 - half}%;width:${half}%`;
                return `${rowOpen(a)}${nameCell(a)}
                    <span class="nbar-track nbar-track--mid"><span class="nbar-fill" style="${pos};${fillStyle(c)}"></span></span>
                    <span class="nbar-val">${c.label}</span></li>`;
            }).join('');
        }

        if (unit === 'pct') {
            return cells.map(([a, c]) => {
                if (!c) return emptyRow(a);
                const width = Math.min(c.value, PCT_CAP) / PCT_CAP * 100;
                return `${rowOpen(a, ` title="${esc(c.title)}"`)}${nameCell(a)}
                    <span class="nbar-track nbar-track--mid"><span class="nbar-fill" style="left:0;width:${width}%;${fillStyle(c)}"></span></span>
                    <span class="nbar-val">${c.label}</span></li>`;
            }).join('');
        }

        // Inches: bar from zero to the observed value, tick at the normal. The axis fits the
        // data, so it can include negative values (SWE change during melt).
        const vals = cells.filter(c => c[1]).flatMap(([, c]) => [c.value, c.normal === null || c.normal === undefined ? 0 : c.normal]);
        const lo = Math.min(0, ...vals);
        const hi = Math.max(0.5, ...vals);
        const pos = v => (v - lo) / (hi - lo) * 100;
        return cells.map(([a, c]) => {
            if (!c) return emptyRow(a);
            const x0 = pos(Math.min(0, c.value)), x1 = pos(Math.max(0, c.value));
            const tick = c.normal === null || c.normal === undefined ? ''
                : `<span class="nbar-tick" style="left:${pos(c.normal)}%"></span>`;
            return `${rowOpen(a, ` title="${esc(c.title)}"`)}${nameCell(a)}
                <span class="nbar-track"><span class="nbar-fill" style="left:${x0}%;width:${x1 - x0}%;${c.s === null ? 'background:#2a5298;' : fillStyle(c)}"></span>${tick}</span>
                <span class="nbar-val">${c.label}</span></li>`;
        }).join('');
    }

    function caption(variable, tf, unit) {
        if (variable === 'temp') {
            return `Average temperature over the window minus the station’s 1991–2020 average for the same days. The center line is normal; bars and colors top out at ±${unit === 'c' ? '2°C' : '4°F'}.`;
        }
        if (variable === 'precip') {
            return unit === 'pct'
                ? 'Precipitation over the window as a percent of the NRCS median for the same days. The line marks 100% (normal).'
                : 'Precipitation over the window, in inches. The dark tick marks the NRCS median for the same days.';
        }
        if (tf === 'wy') {
            return unit === 'pct'
                ? 'Snow water equivalent today as a percent of the NRCS median for today. The line marks 100% (normal).'
                : 'Snow water equivalent today, in inches. The dark tick marks the NRCS median for today.';
        }
        return unit === 'pct'
            ? 'Change in SWE over the window as a percent of the median change. Blank when the normal change is near zero or negative (melt season).'
            : 'Change in SWE over the window, in inches (negative is melt). The dark tick marks the median change.';
    }

    function fillUnits() {
        const prev = unitSel.value;
        const units = VARS[varSel.value].units;
        unitSel.innerHTML = units.map(([k, label]) => `<option value="${k}">${esc(label)}</option>`).join('');
        if (units.some(u => u[0] === prev)) unitSel.value = prev;
    }

    // ---- map -------------------------------------------------------------------------------

    let map = null;
    const markers = {};          // area id -> Leaflet circle marker
    let hotId = null;

    const BASE = { radius: 9, weight: 1.5, color: '#334155', fillOpacity: 0.95 };
    const HOT = { radius: 13, weight: 3, color: '#0f172a' };

    function initMap(areas) {
        const pts = areas.filter(a => typeof a.lat === 'number' && typeof a.lon === 'number');
        if (!window.L || !pts.length || !document.getElementById('normals-map')) return;
        mapWrap.hidden = false;
        map = L.map('normals-map', {
            scrollWheelZoom: false,
            dragging: !L.Browser.mobile, // keep one-finger scrolling usable on phones
            maxZoom: 12,
        }).setView([47.5, -121.6], 7);
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri',
            maxZoom: 12,
        }).addTo(map);
        pts.forEach(a => {
            const m = L.circleMarker([a.lat, a.lon], Object.assign({ fillColor: '#e2e8f0' }, BASE)).addTo(map);
            m.on('mouseover', () => hot(a.id));
            m.on('mouseout', unhot);
            m.on('click', () => hot(a.id)); // touch: a tap highlights the bar
            markers[a.id] = m;
        });
        map.fitBounds(L.latLngBounds(pts.map(a => [a.lat, a.lon])).pad(0.12));
    }

    function legend(variable, unit) {
        const stops = variable === 'temp' ? SCALE.slice().reverse() : SCALE;  // blue on the left for temperature
        const t = unit === 'c' ? '2°C' : '4°F';
        const [l, mid, r] = variable === 'temp'
            ? [`Colder (−${t})`, 'Normal', `Warmer (+${t})`]
            : ['Dry (0%)', 'Normal', 'Wet (200%)'];
        legendEl.innerHTML = `<div class="normals-legend-bar" style="background:linear-gradient(to right,${stops.join(',')})"></div>
            <div class="normals-legend-labels"><span>${l}</span><span>${mid}</span><span>${r}</span></div>`;
    }

    function updateMap(variable, tf, unit, areas) {
        if (!map) return;
        legend(variable, unit);
        areas.forEach(a => {
            const m = markers[a.id];
            if (!m) return;
            const c = cell(variable, tf, unit, a);
            const withColor = c && c.s !== null;
            m.setStyle(withColor ? { fillColor: colorAt(c.s), fillOpacity: 0.95, dashArray: null }
                                 : { fillColor: '#f8fafc', fillOpacity: 0.55, dashArray: '3 3' });
            const text = c ? c.label : 'no data';
            m.unbindTooltip();
            m.bindTooltip(`<strong>${esc(a.station)}</strong>${a.resort ? `<br>${esc(a.resort)}` : ''}<br>${esc(text)}`,
                { direction: 'top', offset: [0, -8] });
        });
    }

    function hot(id) {
        if (hotId === id) return;
        unhot();
        hotId = id;
        const row = grid.querySelector(`.nbar[data-id="${CSS.escape(id)}"]`);
        if (row) row.classList.add('is-hot');
        const m = markers[id];
        if (m) { m.setStyle(HOT); m.bringToFront(); m.openTooltip(); }
    }

    function unhot() {
        if (hotId === null) return;
        const row = grid.querySelector(`.nbar[data-id="${CSS.escape(hotId)}"]`);
        if (row) row.classList.remove('is-hot');
        const m = markers[hotId];
        if (m) { m.setStyle(BASE); m.closeTooltip(); }
        hotId = null;
    }

    grid.addEventListener('mouseover', e => { const li = e.target.closest('.nbar'); if (li) hot(li.dataset.id); });
    grid.addEventListener('mouseleave', unhot);
    grid.addEventListener('focusin', e => { const li = e.target.closest('.nbar'); if (li) hot(li.dataset.id); });
    grid.addEventListener('focusout', unhot);

    // ---- page ------------------------------------------------------------------------------

    let data = null;
    function show() {
        unhot();
        const variable = varSel.value, tf = tfSel.value, unit = unitSel.value;
        const tfLabel = TIMEFRAMES.find(t => t.key === tf).label;
        const rows = renderRows(variable, tf, unit, data.areas);
        grid.innerHTML = `<h3>${esc(VARS[variable].label)}: ${esc(tfLabel.toLowerCase())}</h3>
            <p class="normals-sub">${esc(caption(variable, tf, unit))}</p>` +
            (rows ? `<ul class="nbars">${rows}</ul>`
                : '<p class="normals-empty">Not enough data for this selection yet. Early in the water year the normals are near zero; try a different timeframe.</p>');
        updateMap(variable, tf, unit, data.areas);
    }

    varSel.innerHTML = Object.entries(VARS).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join('');
    tfSel.innerHTML = TIMEFRAMES.map(t => `<option value="${t.key}">${esc(t.label)}</option>`).join('');
    fillUnits();

    fetch(root.dataset.src, { cache: 'no-cache' })
        .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(d => {
            data = d;
            // North to south, so the list reads in the same order as the map. Stations without
            // coordinates go last.
            d.areas.sort((a, b) => (typeof b.lat === 'number' ? b.lat : -90) - (typeof a.lat === 'number' ? a.lat : -90));
            // Open on a combination that has data (early in the season some are empty).
            const opens = [['precip', '30'], ['precip', '7'], ['temp', '7']];
            const first = opens.find(([v, tf]) => d.areas.some(a => cell(v, tf, VARS[v].units[0][0], a)));
            if (first) { varSel.value = first[0]; tfSel.value = first[1]; fillUnits(); }
            varSel.addEventListener('change', () => { fillUnits(); show(); });
            tfSel.addEventListener('change', show);
            unitSel.addEventListener('change', show);
            try { initMap(d.areas); } catch (err) { console.error('Season map failed:', err); mapWrap.hidden = true; map = null; }
            show();
            if (map) map.invalidateSize();
            const through = d.areas.map(a => a.data_through).filter(Boolean).sort().pop();
            foot.textContent = (through ? `Data through ${through}. ` : '') +
                'Updated daily from NRCS SNOTEL stations, labeled with the nearest ski area. ' +
                (map ? 'Hover a bar or a dot to see where the station is. ' : '') +
                'Mazama and Alpental have no SNOTEL station, so they are not shown.';
        })
        .catch(err => {
            console.error('Season normals failed:', err && err.stack ? err.stack : err);
            grid.innerHTML = '<p class="normals-status">Season comparisons are temporarily unavailable.</p>';
        });
}());
