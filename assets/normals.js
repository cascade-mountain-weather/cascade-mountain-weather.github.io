// Homepage "season vs normal" bar chart: pick a variable, timeframe and unit.
// Drawn with plain DOM/CSS (no chart library).
// Data: assets/data/normals.json, written daily by scripts/collect_normals.py.
// A missing value renders as an en dash with no bar.

(function () {
    'use strict';

    const root = document.getElementById('season-normals');
    if (!root) return;
    const grid = document.getElementById('normals-grid');
    const foot = document.getElementById('normals-foot');
    const varSel = document.getElementById('normals-var');
    const tfSel = document.getElementById('normals-tf');
    const unitSel = document.getElementById('normals-unit');

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
    const TEMP_CAP_F = 10;    // temperature axis runs +/-10 F

    function nameCell(a) {
        return `<span class="nbar-name">${esc(a.station)}${a.resort ? `<small>${esc(a.resort)}</small>` : ''}</span>`;
    }

    function emptyRow(a) {
        return `<li class="nbar">${nameCell(a)}<span class="nbar-track"></span><span class="nbar-val">${DASH}</span></li>`;
    }

    // One row's data: { value, normal, label, title } or null when missing.
    function cell(variable, tf, unit, a) {
        const m = a.metrics[variable][tf];
        if (m === null || m === undefined) return null;
        if (variable === 'temp') {
            const v = unit === 'c' ? m * 5 / 9 : m;
            return { value: v, f: m, label: `${v > 0 ? '+' : ''}${v.toFixed(1)}°` };
        }
        if (unit === 'pct') {
            if (m.pct === null) return null;
            return { value: m.pct, label: `${m.pct}%`, title: m.normal === null ? '' : `${m.obs.toFixed(1)} in vs ${m.normal.toFixed(1)} in normal` };
        }
        const sign = variable === 'swe' && tf !== 'wy' && m.obs > 0 ? '+' : '';
        return { value: m.obs, normal: m.normal, label: `${sign}${m.obs.toFixed(1)} in`,
            title: m.normal === null ? '' : `Normal: ${m.normal.toFixed(1)} in` };
    }

    function renderRows(variable, tf, unit, areas) {
        const cells = areas.map(a => [a, cell(variable, tf, unit, a)]);
        if (!cells.some(c => c[1])) return null;

        if (variable === 'temp') {
            return cells.map(([a, c]) => {
                if (!c) return emptyRow(a);
                const half = Math.min(Math.abs(c.f), TEMP_CAP_F) / TEMP_CAP_F * 50;
                const warm = c.f >= 0;
                const style = warm ? `left:50%;width:${half}%` : `left:${50 - half}%;width:${half}%`;
                return `<li class="nbar">${nameCell(a)}
                    <span class="nbar-track nbar-track--mid"><span class="nbar-fill ${warm ? 'nbar-fill--warm' : 'nbar-fill--cold'}" style="${style}"></span></span>
                    <span class="nbar-val">${c.label}</span></li>`;
            }).join('');
        }

        if (unit === 'pct') {
            return cells.map(([a, c]) => {
                if (!c) return emptyRow(a);
                const width = Math.min(c.value, PCT_CAP) / PCT_CAP * 100;
                return `<li class="nbar" title="${esc(c.title)}">${nameCell(a)}
                    <span class="nbar-track nbar-track--mid"><span class="nbar-fill ${c.value >= 100 ? 'nbar-fill--wet' : 'nbar-fill--dry'}" style="left:0;width:${width}%"></span></span>
                    <span class="nbar-val">${c.label}</span></li>`;
            }).join('');
        }

        // Inches: bar from zero to the observed value, tick at the normal. The axis fits
        // the data, so it can include negative values (SWE change during melt).
        const vals = cells.filter(c => c[1]).flatMap(([, c]) => [c.value, c.normal === null || c.normal === undefined ? 0 : c.normal]);
        const lo = Math.min(0, ...vals);
        const hi = Math.max(0.5, ...vals);
        const pos = v => (v - lo) / (hi - lo) * 100;
        return cells.map(([a, c]) => {
            if (!c) return emptyRow(a);
            const x0 = pos(Math.min(0, c.value)), x1 = pos(Math.max(0, c.value));
            const tick = c.normal === null || c.normal === undefined ? ''
                : `<span class="nbar-tick" style="left:${pos(c.normal)}%"></span>`;
            return `<li class="nbar" title="${esc(c.title)}">${nameCell(a)}
                <span class="nbar-track"><span class="nbar-fill nbar-fill--wet" style="left:${x0}%;width:${x1 - x0}%"></span>${tick}</span>
                <span class="nbar-val">${c.label}</span></li>`;
        }).join('');
    }

    function caption(variable, tf, unit) {
        if (variable === 'temp') {
            return 'Average temperature over the window minus the station’s 1991–2020 average for the same days. The center line is normal.';
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

    let data = null;
    function show() {
        const variable = varSel.value, tf = tfSel.value, unit = unitSel.value;
        const tfLabel = TIMEFRAMES.find(t => t.key === tf).label;
        const rows = renderRows(variable, tf, unit, data.areas);
        grid.innerHTML = `<h3>${esc(VARS[variable].label)}: ${esc(tfLabel.toLowerCase())}</h3>
            <p class="normals-sub">${esc(caption(variable, tf, unit))}</p>` +
            (rows ? `<ul class="nbars">${rows}</ul>`
                : '<p class="normals-empty">Not enough data for this selection yet. Early in the water year the normals are near zero; try a different timeframe.</p>');
    }

    varSel.innerHTML = Object.entries(VARS).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join('');
    tfSel.innerHTML = TIMEFRAMES.map(t => `<option value="${t.key}">${esc(t.label)}</option>`).join('');
    fillUnits();

    fetch(root.dataset.src, { cache: 'no-cache' })
        .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(d => {
            data = d;
            // Open on a combination that has data (early in the season some are empty).
            const opens = [['precip', '30'], ['precip', '7'], ['temp', '7']];
            const first = opens.find(([v, tf]) => d.areas.some(a => cell(v, tf, VARS[v].units[0][0], a)));
            if (first) { varSel.value = first[0]; tfSel.value = first[1]; fillUnits(); }
            varSel.addEventListener('change', () => { fillUnits(); show(); });
            tfSel.addEventListener('change', show);
            unitSel.addEventListener('change', show);
            show();
            const through = d.areas.map(a => a.data_through).filter(Boolean).sort().pop();
            foot.textContent = (through ? `Data through ${through}. ` : '') +
                'Updated daily from NRCS SNOTEL stations, labeled with the nearest ski area. Mazama and Alpental have no SNOTEL station, so they are not shown.';
        })
        .catch(err => {
            console.error('Season normals failed:', err && err.stack ? err.stack : err);
            grid.innerHTML = '<p class="normals-status">Season comparisons are temporarily unavailable.</p>';
        });
}());
