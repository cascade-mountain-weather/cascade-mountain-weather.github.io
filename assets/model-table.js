// Model comparison heat table. Reads assets/data/meteograms.json (the home-page point forecast, written by
// scripts/meteograms.py): models.{nbm,hrrr,hrdps}.{cycle_utc, time_utc[], sites.{name}.{temp_f, rh, wind_mph, precip_in,
// and optionally dewpoint_f, wind_dir, gust_mph}}, hourly. Without dewpoint_f the dew point is computed from temperature and RH.
// The palettes are approximations of the National Weather Service graphical forecast colors, not the
// exact NWS tables; edit the stops below to tune them.
(function () {
    'use strict';
    const root = document.getElementById('mt');
    if (!root) return;

    // ---- palettes: [value, color] stops, blended linearly between stops ----
    const PAL = {
        t: [[-30, '#5b1a8a'], [-10, '#8a3fc0'], [0, '#4a4fd6'], [10, '#3b7cf0'], [20, '#4fb3f2'], [32, '#b9e6fa'], [40, '#7fd6a0'],
            [50, '#4fbf4a'], [60, '#c9e04a'], [70, '#f6d83a'], [80, '#f7a531'], [90, '#ee5a2a'], [100, '#c81d25'], [110, '#8c0f1a']],
        td: [[0, '#7b4a1e'], [20, '#b88a4a'], [32, '#e6d29a'], [40, '#bfe0a0'], [50, '#7cc77c'], [60, '#3fae7a'], [65, '#25a0a8'], [70, '#2a7fd0'], [75, '#4b4fc4']],
        rh: [[0, '#8c5a2b'], [20, '#c8a063'], [40, '#e8dca0'], [60, '#a8d89a'], [80, '#4fb87a'], [100, '#1f8f6a']],
        wind: [[0, '#ffffff'], [5, '#d6eefa'], [10, '#9ad3f2'], [15, '#5fb4ea'], [20, '#4fc58a'], [25, '#a6d94a'], [30, '#f0d83a'],
            [40, '#f59a2e'], [50, '#e8402a'], [60, '#b0147c'], [80, '#6a1b9a']],
        pcp: [[0, '#ffffff'], [0.01, '#c7f0c7'], [0.05, '#8be08b'], [0.1, '#3fc03f'], [0.25, '#2f9fd8'], [0.5, '#1e5fd0'],
            [0.75, '#5a3fc8'], [1, '#9b2fc4'], [1.5, '#e03aa0'], [2, '#e8402a']],
    };
    const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
    function color(stops, v) {
        if (v <= stops[0][0]) return hex(stops[0][1]);
        for (let i = 1; i < stops.length; i++) {
            if (v <= stops[i][0]) {
                const [v0, c0] = stops[i - 1], [v1, c1] = stops[i], f = (v - v0) / (v1 - v0), a = hex(c0), b = hex(c1);
                return a.map((x, k) => Math.round(x + (b[k] - x) * f));
            }
        }
        return hex(stops[stops.length - 1][1]);
    }
    const css = c => `rgb(${c[0]},${c[1]},${c[2]})`;
    const ink = c => ((0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) > 150 ? '#0f172a' : '#fff');
    const gradient = stops => { const lo = stops[0][0], hi = stops[stops.length - 1][0];
        return `linear-gradient(90deg, ${stops.map(([v, c]) => `${c} ${((v - lo) / (hi - lo) * 100).toFixed(1)}%`).join(', ')})`; };

    // ---- time formatting (Pacific first) ----
    const TZ = 'America/Los_Angeles';
    const fDay = new Intl.DateTimeFormat('en-US', { timeZone: TZ, weekday: 'short', month: 'numeric', day: 'numeric' });
    const fKey = new Intl.DateTimeFormat('en-CA', { timeZone: TZ });
    const fHour = new Intl.DateTimeFormat('en-US', { timeZone: TZ, hour: 'numeric', hourCycle: 'h23' });
    const fFull = new Intl.DateTimeFormat('en-US', { timeZone: TZ, weekday: 'short', hour: 'numeric', timeZoneName: 'short' });
    const pacHour = d => { const h = +fHour.format(d); return h === 0 ? '12a' : h < 12 ? h + 'a' : h === 12 ? '12p' : (h - 12) + 'p'; };
    const dayName = d => fDay.format(d).replace(',', '');

    const store = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { /* ignore */ } return null; };
    const state = { site: null, span: 48, step: 3, humid: 'td', units: store('mg-units') === 'metric' ? 'metric' : 'us' };
    let data = null;
    const F2C = v => (v - 32) * 5 / 9, MPH2MS = 0.44704, IN2MM = 25.4;
    const SHORT = { nbm: 'NBM', hrrr: 'HRRR', hrdps: 'HRDPS' };

    // dew point (F) from temperature (F) and relative humidity (%) when the data file has no dew point (Magnus)
    function dewFrom(tF, rh) {
        if (tF == null || rh == null || rh <= 0) return null;
        const t = F2C(tF), g = Math.log(rh / 100) + 17.625 * t / (243.04 + t);
        return (243.04 * g / (17.625 - g)) * 9 / 5 + 32;
    }
    // one value per model per column: instantaneous fields sampled at the column time, precipitation summed over the step
    function series(m, siteName, key, cols, step) {
        const md = data.models[m], s = md.sites[siteName];
        if (!s) return null;
        const idx = new Map(md.time_utc.map((t, i) => [Date.parse(t), i]));
        return cols.map(c => {
            const i = idx.get(+c.d);
            if (key === 'precip_in') {
                let tot = 0;
                for (let k = 0; k < step; k++) { const j = idx.get(+c.d - k * 3600e3); if (j == null || s.precip_in[j] == null) return null; tot += s.precip_in[j]; }
                return tot;
            }
            if (key === 'dewpoint_f' && !s.dewpoint_f) return i == null ? null : dewFrom(s.temp_f[i], s.rh[i]);
            return i == null || !s[key] ? null : s[key][i];
        });
    }

    const SECTIONS = [
        { key: 'temp', field: 'temp_f', title: () => state.units === 'us' ? 'Temperature (°F)' : 'Temperature (°C)' },
        { key: 'dew', field: () => state.humid === 'td' ? 'dewpoint_f' : 'rh', title: () => state.humid === 'td' ? (state.units === 'us' ? 'Dew point (°F)' : 'Dew point (°C)') : 'Relative humidity (%)' },
        { key: 'wind', field: 'wind_mph', title: () => state.units === 'us' ? 'Wind speed (mph) and direction' : 'Wind speed (m/s) and direction' },
        { key: 'pcp', field: 'precip_in', title: () => (state.units === 'us' ? 'Precipitation (in' : 'Precipitation (mm') + ' per ' + (state.step === 1 ? 'hour)' : state.step + ' hours)') },
    ];
    const palFor = s => ({ temp: PAL.t, dew: state.humid === 'td' ? PAL.td : PAL.rh, wind: PAL.wind, pcp: PAL.pcp })[s.key];
    // display value from the stored US value; colors always use the US value
    function show(s, v) {
        if (state.units === 'us') return s.key === 'pcp' ? v.toFixed(2) : Math.round(v);
        if (s.key === 'temp' || (s.key === 'dew' && state.humid === 'td')) return Math.round(F2C(v));
        if (s.key === 'wind') return (v * MPH2MS).toFixed(1);
        if (s.key === 'pcp') return (v * IN2MM).toFixed(1);
        return Math.round(v);
    }
    const unitOf = s => state.units === 'us' ? (s.key === 'temp' || (s.key === 'dew' && state.humid === 'td') ? '°F' : s.key === 'wind' ? ' mph' : s.key === 'pcp' ? ' in' : '%')
        : (s.key === 'temp' || (s.key === 'dew' && state.humid === 'td') ? '°C' : s.key === 'wind' ? ' m/s' : s.key === 'pcp' ? ' mm' : '%');

    function ctl(label, inner) { return `<div class="mt-group"><span class="mt-label">${label}</span>${inner}</div>`; }
    const chips = (name, opts, cur) => `<div class="mt-chips">${opts.map(([v, l]) => `<button type="button" class="mt-chip" data-${name}="${v}" aria-pressed="${String(cur) === String(v)}">${l}</button>`).join('')}</div>`;

    function render() {
        const ms = Object.keys(data.models);
        const step = state.step, stepMs = step * 3600e3;
        // columns: every `step` hours on the UTC clock, from about now to the end of the chosen span
        const t0 = Date.now() - stepMs, t1 = Date.now() + state.span * 3600e3;
        const all = new Set();
        ms.forEach(m => data.models[m].time_utc.forEach(t => all.add(Date.parse(t))));
        const cols = [...all].filter(t => t >= t0 && t <= t1 && (t / 3600e3) % step === 0).sort((a, b) => a - b).map(t => ({ d: new Date(t) }));
        const siteName = state.site;

        const days = [];
        cols.forEach(c => { const k = fKey.format(c.d); const last = days[days.length - 1];
            if (last && last.k === k) last.n++; else days.push({ k, n: 1, label: dayName(c.d) }); });
        const isMid = c => +fHour.format(c.d) === 0;
        const head = () => `<tr><th class="mt-name"></th>${days.map(d => `<th class="mt-day" colspan="${d.n}">${d.label}</th>`).join('')}</tr>
            <tr><th class="mt-name"></th>${cols.map(c => `<th class="mt-hour${isMid(c) ? ' mt-midnight' : ''}" title="${fFull.format(c.d)}">${pacHour(c.d)}</th>`).join('')}</tr>`;

        let body = '';
        SECTIONS.forEach(s => {
            const field = typeof s.field === 'function' ? s.field() : s.field;
            const stops = palFor(s);
            const lo = stops[0][0], hi = stops[stops.length - 1][0];
            const legend = `<span class="mt-legend"><span>${lo}</span><span class="mt-legend-bar" style="background:${gradient(stops)}"></span><span>${hi}${s.key === 'pcp' ? '+' : ''}</span><span>${s.key === 'temp' || (s.key === 'dew' && state.humid === 'td') ? '\u00b0F' : s.key === 'wind' ? 'mph' : s.key === 'pcp' ? 'in per 3 h' : '%'} scale</span></span>`;
            body += `<tr class="mt-section"><th class="mt-sec" colspan="${cols.length + 1}"><div class="mt-sec-in">${s.title()}${legend}</div></th></tr>${head()}`;
            ms.forEach(m => {
                const vals = series(m, siteName, field, cols, step) || [];
                const dirs = s.key === 'wind' ? (series(m, siteName, 'wind_dir', cols, step) || []) : [];
                const gusts = s.key === 'wind' ? (series(m, siteName, 'gust_mph', cols, step) || []) : [];
                body += `<tr><th class="mt-name" title="${data.models[m].label}">${SHORT[m] || m}<small>${data.models[m].cycle_utc ? data.models[m].cycle_utc.slice(11, 13) + 'Z run' : ''}</small></th>`;
                cols.forEach((c, i) => {
                    const v = vals[i], mid = isMid(c) ? ' mt-midnight' : '';
                    if (v == null) { body += `<td class="mt-cell mt-null${mid}">–</td>`; return; }
                    const col = color(stops, s.key === 'pcp' ? v / step * 3 : v);   // palette is per 3 hours; scale other steps to it
                    let txt = show(s, v);
                    if (s.key === 'pcp' && v < 0.005) txt = '';
                    if (s.key === 'wind' && dirs[i] != null) txt += `<span class="mt-arrow" style="transform:rotate(${(dirs[i] + 180) % 360}deg)">↑</span>`;
                    const tip = `${SHORT[m] || m}, ${fFull.format(c.d)}: ${show(s, v)}${unitOf(s)}${s.key === 'wind' && dirs[i] != null ? ' from ' + Math.round(dirs[i]) + '°' : ''}`;
                    body += `<td class="mt-cell${s.key === 'wind' ? ' mt-wind' : ''}${mid}" style="background:${css(col)};color:${ink(col)}" title="${tip}">${txt}</td>`;
                });
                body += '</tr>';
            });
        });

        const gen = new Date(data.generated_utc);
        const km = ms.map(m => { const s = data.models[m].sites[siteName]; return s && s.grid_km != null ? `${SHORT[m] || m} ${s.grid_km} km` : null; }).filter(Boolean).join(', ');
        root.innerHTML = `<div class="mt-controls">
            ${ctl('Area', `<select class="mt-select" id="mt-site">${data.sites.map(s => `<option value="${s.name}"${s.name === siteName ? ' selected' : ''}>${s.name}</option>`).join('')}</select>`)}
            ${ctl('Time span', chips('span', [[24, '24 h'], [48, '48 h']], state.span))}
            ${ctl('Column step', chips('step', [[1, '1 h'], [3, '3 h'], [6, '6 h']], state.step))}
            ${ctl('Humidity', chips('humid', [['td', 'Dew point'], ['rh', 'Relative humidity']], state.humid))}
            ${ctl('Units', chips('units', [['us', '°F, mph, in'], ['metric', '°C, m/s, mm']], state.units))}
        </div>
        <div class="mt-scroll"><table class="mt-table">${body}</table></div>
        <p class="mt-note"><strong>Grid-based, not downscaled.</strong> Each value is the model grid cell nearest the ski area${km ? ' (' + km + ' away)' : ''}, with no elevation or terrain correction, so temperatures run warmer and snow lower than on the slopes. Wind arrows point the way the wind blows toward. Colors approximate the National Weather Service palettes. Times are Pacific. Updated ${fFull.format(gen)}.</p>`;
        root.querySelector('#mt-site').addEventListener('change', e => { state.site = e.target.value; store('mg-site', state.site); render(); });
        const bind = (name, fn) => root.querySelectorAll(`[data-${name}]`).forEach(b => b.addEventListener('click', () => { fn(b.dataset[name]); render(); }));
        bind('span', v => { state.span = +v; });
        bind('step', v => { state.step = +v; });
        bind('humid', v => { state.humid = v; });
        bind('units', v => { state.units = v; store('mg-units', v); });
    }

    const hash = new URLSearchParams(location.hash.slice(1));
    fetch(root.dataset.src, { cache: 'no-cache' })
        .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(d => {
            data = d;
            const names = d.sites.map(s => s.name);
            state.site = [hash.get('site'), store('mg-site'), names[0]].find(n => n && names.includes(n));
            render();
        })
        .catch(() => { root.innerHTML = '<div class="mt-empty">The point forecast table is not available right now.</div>'; });
}());
