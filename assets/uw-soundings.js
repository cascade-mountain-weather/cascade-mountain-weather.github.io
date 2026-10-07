// UW WRF forecast soundings: skew-T and freezing level / snow level / dendritic growth zone charts, drawn as SVG strings
// for assets/model-viewer.js. Data: assets/data/uw_soundings/<site>.json, written by scripts/uw_soundings.py.
// Each frame has a compact profile (p hPa, t and td in C, z in m) and the derived levels (feet MSL).
(function () {
    'use strict';
    const BASE = (document.currentScript && document.currentScript.src || '').replace(/[^/]*$/, '');
    const FT = 3.28084;
    const PAC_H = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', hour: 'numeric', hourCycle: 'h23' });
    const PAC_D = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', weekday: 'short', month: 'numeric', day: 'numeric' });
    const PAC_T = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', hour: 'numeric', timeZoneName: 'short' });
    const pacHour = ms => +PAC_H.format(ms);
    const zStr = ms => `${String(new Date(ms).getUTCHours()).padStart(2, '0')}Z`;
    const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
    const fmtFt = v => (v == null ? '–' : Math.round(v).toLocaleString('en-US') + ' ft');
    const C = { t: '#dc2626', td: '#15803d', frz: '#2563eb', snow: '#d97706', dgz: '#9333ea', ground: '#d6d3d1', grid: '#e2e8f0', text: '#334155', muted: '#64748b' };
    const halo = 'paint-order="stroke" stroke="#fff" stroke-width="3" stroke-linejoin="round"';

    const cache = {};
    function load(site) {
        if (!cache[site]) {
            cache[site] = fetch(BASE + 'data/uw_soundings/' + site + '.json', { cache: 'no-cache' })
                .then(r => (r.ok ? r.json() : null)).catch(() => null);
        }
        return cache[site];
    }
    const initDate = d => {
        const s = String(d.init_utc);
        return new Date(Date.UTC(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8), +s.slice(8, 10)));
    };

    // pressure at a height (m, MSL) from one profile, interpolated in ln p
    function pAtZ(f, zm) {
        const z = f.z, p = f.p;
        if (zm <= z[0]) return p[0];
        for (let i = 1; i < z.length; i++) {
            if (zm <= z[i]) { const w = (zm - z[i - 1]) / (z[i] - z[i - 1]); return Math.exp(Math.log(p[i - 1]) + w * (Math.log(p[i]) - Math.log(p[i - 1]))); }
        }
        return null;
    }

    // ---------------------------------------------------------------- skew-T
    const W = 640, H = 570, X0 = 54, Y0 = 62, PW = 516, PH = 400;
    const P_BOT = 1050, P_TOP = 300, T_MIN = -30, T_MAX = 30, SKEW = 0.9;
    const yOf = p => Y0 + PH * Math.log(p / P_TOP) / Math.log(P_BOT / P_TOP);
    const xOf = (t, p) => X0 + (t - T_MIN) * (PW / (T_MAX - T_MIN)) + (Y0 + PH - yOf(p)) * SKEW;
    const pts = (ts, ps, from, to) => {
        const out = [];
        for (let i = 0; i < ps.length; i++) {
            if (ts[i] == null || (to != null && ps[i] < to)) continue;
            out.push(`${xOf(ts[i], ps[i]).toFixed(1)},${yOf(ps[i]).toFixed(1)}`);
        }
        return out.join(' ');
    };

    function skewT(site, idx) {
        const f = site.frames[idx];
        const valid = Date.parse(f.valid_utc), init = initDate(site).getTime();
        let g = '';
        // isotherms
        for (let t = -100; t <= 40; t += 10) {
            const hot = t === 0;
            g += `<line x1="${xOf(t, P_BOT)}" y1="${yOf(P_BOT)}" x2="${xOf(t, P_TOP)}" y2="${yOf(P_TOP)}" stroke="${hot ? C.frz : C.grid}" stroke-width="${hot ? 1.6 : 1}"${hot ? ' opacity=".7"' : ''}/>`;
        }
        // isobars
        for (let p = 1000; p >= 300; p -= 100) {
            g += `<line x1="${X0}" y1="${yOf(p)}" x2="${X0 + PW}" y2="${yOf(p)}" stroke="${C.grid}"/>`;
        }
        // the ground
        const gy = yOf(f.p[0]);
        g += `<rect x="${X0}" y="${gy}" width="${PW}" height="${Y0 + PH - gy}" fill="${C.ground}" opacity=".8"/>`;
        // dendritic growth zone: the layer of this profile that is between -12 and -18 C, shaded across the whole plot
        if (f.dgz_base_ft != null && f.dgz_top_ft != null) {
            const pb = pAtZ(f, f.dgz_base_ft / FT), pt = pAtZ(f, f.dgz_top_ft / FT);
            if (pb != null && pt != null) {
                g += `<rect x="${X0}" y="${yOf(pt)}" width="${PW}" height="${Math.max(2, yOf(pb) - yOf(pt))}" fill="${C.dgz}" opacity=".16"/>`;
                g += `<text x="${X0 + 8}" y="${yOf(pt) + 14}" font-size="12" font-weight="700" fill="${C.dgz}" ${halo}>dendritic growth zone</text>`;
            }
        }
        g += `<polyline points="${pts(f.td, f.p)}" fill="none" stroke="${C.td}" stroke-width="2.6" stroke-linejoin="round"/>`;
        g += `<polyline points="${pts(f.t, f.p)}" fill="none" stroke="${C.t}" stroke-width="2.8" stroke-linejoin="round"/>`;
        // freezing level and snow level
        const marks = [['freezing level', f.freezing_level_ft, C.frz], ['snow level', f.snow_level_ft, C.snow]];
        marks.forEach(([label, ft, col]) => {
            const p = ft == null ? null : pAtZ(f, ft / FT);
            if (p == null) return;
            const y = yOf(p);
            g += `<line x1="${X0}" y1="${y}" x2="${X0 + PW}" y2="${y}" stroke="${col}" stroke-width="1.6" stroke-dasharray="7 4"/>`;
            g += `<text x="${X0 + PW - 6}" y="${y - 5}" text-anchor="end" font-size="13" font-weight="700" fill="${col}" ${halo}>${label} ${fmtFt(ft)}</text>`;
        });

        // axes: pressure on the left, height on the right, temperature along the bottom
        let ax = '';
        for (let p = 1000; p >= 300; p -= 100) ax += `<text x="${X0 - 7}" y="${yOf(p) + 4}" text-anchor="end" font-size="12" fill="${C.muted}">${p}</text>`;
        ax += `<text x="14" y="${Y0 + PH / 2}" transform="rotate(-90 14 ${Y0 + PH / 2})" text-anchor="middle" font-size="12" fill="${C.muted}">pressure (hPa)</text>`;
        for (let kft = 5; kft <= 40; kft += 5) {
            const p = pAtZ(f, kft * 1000 / FT);
            if (p == null || p < P_TOP || p > f.p[0]) continue;
            ax += `<line x1="${X0 + PW}" y1="${yOf(p)}" x2="${X0 + PW + 5}" y2="${yOf(p)}" stroke="${C.muted}"/>`;
            ax += `<text x="${X0 + PW + 8}" y="${yOf(p) + 4}" font-size="12" fill="${C.muted}">${kft}k ft</text>`;
        }
        for (let t = -30; t <= 30; t += 10) {
            const x = xOf(t, P_BOT);
            ax += `<text x="${x}" y="${Y0 + PH + 18}" text-anchor="middle" font-size="12" fill="${C.muted}">${t}&#176;C</text>`;
        }
        ax += `<text x="${xOf(0, 500) - 8}" y="${yOf(500) + 4}" text-anchor="end" font-size="12" font-weight="700" fill="${C.frz}" ${halo}>0&#176;C</text>`;

        const lead = f.hour ? `+${f.hour} h` : 'analysis';
        const when = `${PAC_D.format(valid)}, ${PAC_T.format(valid)} (${zStr(valid)})`;
        const dgz = f.dgz_thickness_m ? `${Math.round(f.dgz_thickness_m * FT).toLocaleString('en-US')} ft thick, ${Math.round(f.dgz_saturated_m * FT).toLocaleString('en-US')} ft near saturation` : 'none in this profile';
        const head = `<text x="${X0}" y="24" font-size="17" font-weight="700" fill="#1e3c72">${esc(site.name.replace(',WA', ''))}: UW WRF forecast sounding</text>
            <text x="${X0}" y="44" font-size="14" fill="${C.text}">${when} &#183; ${lead} &#183; run ${zStr(init)} ${PAC_D.format(init)}</text>`;
        const legend = `<g font-size="12" fill="${C.text}">
            <line x1="${X0}" y1="${H - 36}" x2="${X0 + 22}" y2="${H - 36}" stroke="${C.t}" stroke-width="3"/><text x="${X0 + 28}" y="${H - 32}">temperature</text>
            <line x1="${X0 + 108}" y1="${H - 36}" x2="${X0 + 130}" y2="${H - 36}" stroke="${C.td}" stroke-width="3"/><text x="${X0 + 136}" y="${H - 32}">dew point</text>
            <text x="${X0}" y="${H - 16}" fill="${C.muted}">Dendritic growth zone (-12 to -18 &#176;C): ${dgz}.</text>
            <text x="${X0}" y="${H - 2}" fill="${C.muted}">Snow level is the melting-model (wet bulb) level, not the freezing level.</text></g>`;
        return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="system-ui,Segoe UI,Arial,sans-serif" role="img" aria-label="Skew-T sounding"><rect width="${W}" height="${H}" fill="#fff"/>
            ${head}<clipPath id="pa"><rect x="${X0}" y="${Y0}" width="${PW}" height="${PH}"/></clipPath><g clip-path="url(#pa)">${g}</g>
            <rect x="${X0}" y="${Y0}" width="${PW}" height="${PH}" fill="none" stroke="#94a3b8"/>${ax}${legend}</svg>`;
    }

    // ---------------------------------------------------------------- levels over time
    const niceStep = span => { const raw = span / 5, m = Math.pow(10, Math.floor(Math.log10(raw))); return [1, 2, 2.5, 5, 10].map(k => k * m).find(s => s >= raw); };

    function levels(site) {
        const fr = site.frames, t0 = Date.parse(fr[0].valid_utc), t1 = Date.parse(fr[fr.length - 1].valid_utc);
        const LW = 760, LH = 500, left = 66, right = 20, aTop = 70, aH = 340;
        const pw = LW - left - right, x = ms => left + pw * (ms - t0) / (t1 - t0);
        const lo0 = Math.min(site.elevation_ft, ...fr.map(f => f.snow_level_ft).filter(v => v != null)), hi0 = Math.max(...fr.map(f => Math.max(f.freezing_level_ft || 0, f.dgz_top_ft || 0)));
        const step = niceStep(hi0 - lo0 + 1000), yLo = Math.max(0, Math.floor((lo0 - 600) / step) * step), yHi = Math.ceil((hi0 + 400) / step) * step;
        const ya = v => aTop + aH * (1 - (v - yLo) / (yHi - yLo));
        let s = '';
        for (let v = yLo; v <= yHi; v += step) s += `<line x1="${left}" y1="${ya(v)}" x2="${left + pw}" y2="${ya(v)}" stroke="${C.grid}"/><text x="${left - 7}" y="${ya(v) + 4}" text-anchor="end" font-size="12" fill="${C.muted}">${v.toLocaleString('en-US')}</text>`;
        // day boundaries and hour ticks (Pacific time)
        let axis = '';
        for (let ms = t0; ms <= t1; ms += 3600e3) {
            const h = pacHour(ms);
            if (h === 0) {
                s += `<line x1="${x(ms)}" y1="${aTop}" x2="${x(ms)}" y2="${aTop + aH}" stroke="#94a3b8"/>`;
                axis += `<text x="${x(ms) + 4}" y="${aTop + aH + 30}" font-size="12" font-weight="700" fill="${C.text}">${PAC_D.format(ms + 3600e3)}</text>`;
            }
            if (h % 6 === 0) axis += `<text x="${x(ms)}" y="${aTop + aH + 15}" text-anchor="middle" font-size="11" fill="${C.muted}">${h === 0 ? '12a' : h === 12 ? '12p' : (h % 12) + (h < 12 ? 'a' : 'p')}</text>`;
        }
        // growth zone band (base to top) wherever the profile has one
        const dg = fr.filter(f => f.dgz_base_ft != null);
        const band = [];
        fr.forEach((f, i) => { if (f.dgz_base_ft != null && f.dgz_top_ft != null) band.push(i); });
        let seg = [];
        const flush = () => {
            if (seg.length > 1) s += `<polygon points="${seg.map(i => `${x(Date.parse(fr[i].valid_utc))},${ya(fr[i].dgz_top_ft)}`).join(' ')} ${seg.slice().reverse().map(i => `${x(Date.parse(fr[i].valid_utc))},${ya(fr[i].dgz_base_ft)}`).join(' ')}" fill="${C.dgz}" opacity=".2"/>`; seg = [];
        };
        band.forEach((i, k) => { if (k && i !== band[k - 1] + 1) flush(); seg.push(i); });
        flush();
        const line = (key, col, w) => {
            let d = '', pen = false;
            fr.forEach(f => {
                if (f[key] == null) { pen = false; return; }
                d += `${pen ? 'L' : 'M'}${x(Date.parse(f.valid_utc)).toFixed(1)},${ya(f[key]).toFixed(1)}`; pen = true;
            });
            return `<path d="${d}" fill="none" stroke="${col}" stroke-width="${w}" stroke-linejoin="round"/>` +
                fr.map(f => (f[key] == null ? '' : `<circle cx="${x(Date.parse(f.valid_utc)).toFixed(1)}" cy="${ya(f[key]).toFixed(1)}" r="2.6" fill="${col}"/>`)).join('');
        };
        s += `<line x1="${left}" y1="${ya(site.elevation_ft)}" x2="${left + pw}" y2="${ya(site.elevation_ft)}" stroke="#78716c" stroke-dasharray="3 4"/>`;
        s += `<text x="${left + pw - 4}" y="${ya(site.elevation_ft) - 5}" text-anchor="end" font-size="12" fill="#78716c" ${halo}>sounding point ${fmtFt(site.elevation_ft)}</text>`;
        s += line('freezing_level_ft', C.frz, 2.6) + line('snow_level_ft', C.snow, 2.6);
        const init = initDate(site).getTime();
        const head = `<text x="${left}" y="24" font-size="17" font-weight="700" fill="#1e3c72">${esc(site.name.replace(',WA', ''))}: freezing level, snow level and dendritic growth zone</text>
            <text x="${left}" y="44" font-size="14" fill="${C.text}">UW WRF forecast, run ${zStr(init)} ${PAC_D.format(init)}, every 3 hours. Times are Pacific.</text>`;
        const lg = `<g font-size="12" fill="${C.text}">
            <line x1="${left}" y1="${aTop - 10}" x2="${left + 22}" y2="${aTop - 10}" stroke="${C.frz}" stroke-width="3"/><text x="${left + 28}" y="${aTop - 6}">freezing level (0&#176;C)</text>
            <line x1="${left + 170}" y1="${aTop - 10}" x2="${left + 192}" y2="${aTop - 10}" stroke="${C.snow}" stroke-width="3"/><text x="${left + 198}" y="${aTop - 6}">snow level</text>
            <rect x="${left + 285}" y="${aTop - 16}" width="22" height="12" fill="${C.dgz}" opacity=".25"/><text x="${left + 313}" y="${aTop - 6}">dendritic growth zone (-12 to -18&#176;C)</text></g>
            <text x="${left}" y="${aTop + aH + 52}" font-size="12" fill="${C.muted}">Heights are feet above sea level. Snow level is the melting-model (wet bulb) level.</text>`;
        return `<svg xmlns="http://www.w3.org/2000/svg" width="${LW}" height="${LH}" viewBox="0 0 ${LW} ${LH}" font-family="system-ui,Segoe UI,Arial,sans-serif" role="img" aria-label="Freezing level, snow level and dendritic growth zone over time"><rect width="${LW}" height="${LH}" fill="#fff"/>
            ${head}${lg}${s}<rect x="${left}" y="${aTop}" width="${pw}" height="${aH}" fill="none" stroke="#94a3b8"/>${axis}</svg>`;
    }

    const dataUrl = svg => 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    window.CMWSounding = { load, initDate, skewT: (site, i) => dataUrl(skewT(site, i)), levels: site => dataUrl(levels(site)), skewTSvg: skewT, levelsSvg: levels };
}());
