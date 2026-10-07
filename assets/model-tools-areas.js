// Area x product catalog for assets/model-viewer.js, shared by two pages (set by data-page on #viewer):
//   precip  tools/model-tools-precipitation.html       snow, precipitation, clouds
//   level   tools/model-tools-freezing-level.html      forecast soundings, freezing level and snow level
// A product belongs to the 'level' page when it has page: 'level'; everything else is 'precip'.
(function () {
    'use strict';
    const BASE = (document.currentScript && document.currentScript.src || '').replace(/[^/]*$/, '');
    const PAGE = (document.getElementById('viewer') || {}).dataset && document.getElementById('viewer').dataset.page === 'level' ? 'level' : 'precip';
    const pageOf = p => p.page || 'precip';
    let nbmData = null; // assets/data/nbm_plumes.json, written by scripts/nbm_plume.py
    let soundings = {}; // assets/data/uw_soundings/<site>.json (UW WRF forecast soundings), written by scripts/uw_soundings.py
    let hiresData = null; // assets/data/hires_plumes.json (HRRR and HRDPS), written by scripts/hires_plume.py
    const pad = (n, w) => String(n).padStart(w, '0');
    const ymd = d => `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1, 2)}${pad(d.getUTCDate(), 2)}`;
    const ymdh = d => ymd(d) + pad(d.getUTCHours(), 2);
    const range = (a, b, st) => Array.from({ length: Math.floor((b - a) / st) + 1 }, (_, i) => a + i * st);
    // Candidate model runs on a 6-hour cycle, newest first. The viewer loads the first frame of
    // each until one exists, so a run that has not posted yet falls back to the previous one.
    const utahRuns = n => {
        const step = 6 * 3600e3, base = Math.floor(Date.now() / step) * step;
        return Array.from({ length: n }, (_, i) => new Date(base - i * step));
    };
    // Utah regional map: /{YYYYMMDD}/images/models/{dir}/{prefix}_NW{YYYYMMDDHH}F###.png
    const utahMap = (dir, prefix, hours) => ({
        hours, runs: utahRuns(8), runExact: true,
        urlFor: (r, h) => `https://weather.utah.edu/${ymd(r)}/images/models/${dir}/${prefix}_NW${ymdh(r)}F${pad(h, 3)}.png`,
        fallbackUrl: 'https://weather.utah.edu/',
    });
    const CW3E = 'https://cw3e.ucsd.edu/images';

    // wwrf: West-WRF meteogram panel code; utah: Utah ensemble point code;
    // basins: CW3E watershed freezing-level plots (HUC8 id).
    const AREAS = {
        'nw': { label: 'Northwest region (maps)', region: true },
        'mt-baker': { label: 'Mt. Baker (Heather Meadows)', uw: 'discl', wwrf: 'WA543', utah: 'MTB42', basins: [{ id: '17110005', label: 'Upper Skagit' }] },
        'stevens': { label: 'Stevens Pass', wwrf: 'US2', utah: 'TSTEV', basins: [{ id: '17110009', label: 'Skykomish (west side)' }, { id: '17020011', label: 'Wenatchee (east side)' }] },
        'snoqualmie': { label: 'Snoqualmie Pass', uw: 'ksmp', wwrf: 'I90', utah: 'SNO30', basins: [{ id: '17110010', label: 'Snoqualmie (west side)' }, { id: '17030001', label: 'Upper Yakima (east side)' }] },
        'hurricane': { label: 'Hurricane Ridge', uw: 'dowlx', utah: 'HUR53', basins: [{ id: '17110020', label: 'Dungeness-Elwha' }] },
        'winthrop': { label: 'Winthrop / Mazama (Methow Valley)', uw: 'mtwpm', wwrf: 'S52', basins: [{ id: '17020008', label: 'Methow' }] },
        'blewett': { label: 'Blewett Pass', uw: 'lvwth', wwrf: 'US97', utah: 'MISR', basins: [{ id: '17020011', label: 'Wenatchee' }] },
        'crystal': { label: 'Crystal Mountain', uw: 'pvc55', wwrf: 'MRNP', utah: 'CMT', basins: [{ id: '17110014', label: 'Puyallup' }] },
        'paradise': { label: 'Paradise (Mt. Rainier)', uw: 'pvc55', wwrf: 'MRNP', utah: 'PVC54', basins: [{ id: '17110015', label: 'Nisqually' }] },
        'white': { label: 'White Pass', uw: 'rimrk', wwrf: 'US12', utah: 'WPS45', basins: [{ id: '17080004', label: 'Upper Cowlitz' }] },
        'washington': { label: 'Washington Pass', uw: 'mtwpm', wwrf: 'WA20', utah: 'WAP55', basins: [{ id: '17020009', label: 'Lake Chelan (west side)' }, { id: '17020008', label: 'Methow (east side)' }] },
    };


    // ---- NBM snowfall plume, drawn as an SVG image so it behaves like the other figures ----
    const NBM_SITE = { 'mt-baker': 'Mt. Baker', stevens: 'Stevens Pass', snoqualmie: 'Snoqualmie Pass', blewett: 'Blewett Pass',
        crystal: 'Crystal', paradise: 'Paradise', white: 'White Pass', washington: 'Washington Pass',
        hurricane: 'Hurricane Ridge', winthrop: 'Winthrop' };
    const PAC_H = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', hour: 'numeric', hourCycle: 'h23' });
    const PAC_D = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', weekday: 'short', month: 'numeric', day: 'numeric' });
    const num = (v, d) => (v == null ? '\u2013' : (+v).toFixed(d == null ? 1 : d));

    // HRRR and HRDPS 6-hour windows for one site, drawn over the NBM: diamonds and triangles, lines for the totals
    const HIRES_STYLE = { hrrr: { color: '#dc2626', shape: 'diamond', dx: -4 }, hrdps: { color: '#7c3aed', shape: 'triangle', dx: 4 } };
    function hiresSeries(siteName) {
        if (!hiresData || !hiresData.models) return [];
        return Object.keys(hiresData.models).filter(m => HIRES_STYLE[m] && hiresData.models[m].sites[siteName]).map(m => {
            const md = hiresData.models[m], st = md.sites[siteName];
            return Object.assign({ key: m, label: md.label.split(' (')[0], cycle: Date.parse(md.cycle_utc),
                ends: md.window_end_utc.map(t => Date.parse(t)), snow: st.snow, precip: st.precip }, HIRES_STYLE[m]);
        }).filter(h => h.snow.some(v => v != null));
    }
    const marker = (shape, x, y, color) => shape === 'diamond'
        ? `<path d="M${x} ${y - 4.5}L${x + 4.5} ${y}L${x} ${y + 4.5}L${x - 4.5} ${y}Z" fill="${color}" stroke="#fff" stroke-width="1"/>`
        : `<path d="M${x} ${y - 4.5}L${x + 4.5} ${y + 3.5}L${x - 4.5} ${y + 3.5}Z" fill="${color}" stroke="#fff" stroke-width="1"/>`;
    const cumulate = arr => { const c = [0]; for (const v of arr) { if (v == null) break; c.push(c[c.length - 1] + v); } return c; };

    function nbmChart(areaId) {
        const site = nbmData && nbmData.sites[NBM_SITE[areaId]];
        if (!site) return null;
        const ends = nbmData.window_end_utc.map(t => Date.parse(t));
        const W = nbmData.window_hours * 3600e3, n = ends.length;
        const hi = hiresSeries(NBM_SITE[areaId]);
        const t0 = Math.min(ends[0] - W, ...hi.map(h => h.ends[0] - W)), t1 = Math.max(ends[n - 1], ...hi.map(h => h.ends[h.ends.length - 1]));
        const W_ = 820, pad = { l: 52, r: 16 }, plotW = W_ - pad.l - pad.r;
        const X = t => pad.l + (t - t0) / (t1 - t0) * plotW;
        const p25 = site.p25, p50 = site.p50, p75 = site.p75, det = site.det;
        // cumulative curves run until the first window with no data
        const cum = { lo: [0], mid: [0], hi: [0] };
        let known = 0;
        while (known < n && p50[known] != null) {
            cum.lo.push(cum.lo[known] + (p25[known] || 0));
            cum.mid.push(cum.mid[known] + p50[known]);
            cum.hi.push(cum.hi[known] + (p75[known] != null ? p75[known] : p50[known]));
            known++;
        }
        const hiCum = hi.map(h => cumulate(h.snow));
        const maxBar = Math.max(1, ...p75.filter(v => v != null), ...det.filter(v => v != null), ...hi.flatMap(h => h.snow.filter(v => v != null)));
        const maxCum = Math.max(1, cum.hi[cum.hi.length - 1] || 0, ...hiCum.map(c => c[c.length - 1]));
        const nice = m => { const st = m <= 1 ? 0.25 : m <= 2 ? 0.5 : m <= 4 ? 1 : m <= 12 ? 2 : m <= 30 ? 5 : 10; return Math.ceil(m / st) * st; };
        const topMax = nice(maxBar * 1.1), botMax = nice(maxCum * 1.05);
        const hiHasQ = hi.some(h => h.precip.some(v => v != null));
        const qpf = Array.isArray(site.precip) && site.precip.some(v => v != null) ? site.precip : (hiHasQ ? new Array(n).fill(null) : null);
        const A = { y0: 44, h: 170 }, Q = { y0: 262, h: 110 }, B = { y0: qpf ? 424 : 270, h: 170 };
        const H_ = qpf ? 646 : 492;
        const qMax = qpf ? nice(Math.max(0.25, ...qpf.filter(v => v != null), ...hi.flatMap(h => h.precip.filter(v => v != null))) * 1.1) : 1;
        const YQ = v => Q.y0 + Q.h - v / qMax * Q.h;
        const YA = v => A.y0 + A.h - v / topMax * A.h, YB = v => B.y0 + B.h - v / botMax * B.h;
        const out = [];
        const grid = (P, M, Y, label) => {
            const st = M <= 1 ? 0.25 : M <= 2 ? 0.5 : M <= 4 ? 1 : M <= 12 ? 2 : M <= 30 ? 5 : 10;
            for (let v = 0; v <= M; v += st) out.push(`<line x1="${pad.l}" x2="${W_ - pad.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#e2e8f0"/><text x="${pad.l - 6}" y="${Y(v) + 4}" text-anchor="end" font-size="11" fill="#64748b">${v}</text>`);
            out.push(`<text x="14" y="${P.y0 + P.h / 2}" transform="rotate(-90 14 ${P.y0 + P.h / 2})" text-anchor="middle" font-size="12" fill="#334155">${label}</text>`);
        };
        out.push(`<rect width="${W_}" height="${H_}" fill="#fff"/>`);
        out.push(`<text x="${pad.l}" y="18" font-size="14" font-weight="700" fill="#1e3c72">${hi.length ? 'Snowfall: NBM, ' + hi.map(h => h.label).join(' and ') : 'NBM snowfall'}</text>`);
        out.push(`<text x="${pad.l}" y="34" font-size="11" fill="#64748b">NBM bars: median per 6 hours. Whiskers: 25th to 75th percentile. Orange dot: NBM deterministic.</text>`);
        if (hi.length) {
            let lx = W_ - pad.r;
            for (const h of hi.slice().reverse()) {
                const lab = `${h.label} ${new Date(h.cycle).getUTCHours().toString().padStart(2, '0')}Z run`;
                out.push(`<text x="${lx}" y="18" text-anchor="end" font-size="11" fill="#334155">${lab}</text>`);
                lx -= lab.length * 5.6 + 14;
                out.push(marker(h.shape, lx, 14, h.color));
                lx -= 16;
            }
        }
        grid(A, topMax, YA, 'inches per 6 h');
        if (qpf) grid(Q, qMax, YQ, 'liquid inches per 6 h');
        grid(B, botMax, YB, 'snow inches accumulated');
        // Pacific midnights and day labels
        for (let t = Math.ceil(t0 / 3600e3) * 3600e3; t <= t1; t += 3600e3) {
            if (+PAC_H.format(t) !== 0) continue;
            for (const P of (qpf ? [A, Q, B] : [A, B])) out.push(`<line x1="${X(t)}" x2="${X(t)}" y1="${P.y0}" y2="${P.y0 + P.h}" stroke="#94a3b8" stroke-dasharray="3 3"/>`);
            if (X(t) > W_ - pad.r - 50) continue;
            out.push(`<text x="${X(t) + 4}" y="${B.y0 + B.h + 16}" font-size="11" fill="#334155">${PAC_D.format(t + 6 * 3600e3).replace(',', '')}</text>`);
        }
        out.push(`<text x="${pad.l}" y="${B.y0 + B.h + 34}" font-size="10.5" fill="#64748b">Dashed lines mark midnight Pacific time; labels are the Pacific day that follows.</text>`);
        // bars
        const bw = Math.max(3, plotW / n - 3);
        for (let i = 0; i < n; i++) {
            const xc = X(ends[i] - W / 2);
            if (p50[i] == null) {
                out.push(`<rect x="${xc - bw / 2}" y="${A.y0}" width="${bw}" height="${A.h}" fill="#f1f5f9"/>`);
                continue;
            }
            out.push(`<rect x="${xc - bw / 2}" y="${YA(p50[i])}" width="${bw}" height="${Math.max(0, YA(0) - YA(p50[i]))}" fill="#3b82f6" opacity="0.85"/>`);
            if (p25[i] != null && p75[i] != null) out.push(`<line x1="${xc}" x2="${xc}" y1="${YA(p25[i])}" y2="${YA(p75[i])}" stroke="#1e3a8a" stroke-width="1.6"/><line x1="${xc - 3}" x2="${xc + 3}" y1="${YA(p75[i])}" y2="${YA(p75[i])}" stroke="#1e3a8a" stroke-width="1.6"/><line x1="${xc - 3}" x2="${xc + 3}" y1="${YA(p25[i])}" y2="${YA(p25[i])}" stroke="#1e3a8a" stroke-width="1.6"/>`);
            if (det[i] != null) out.push(`<circle cx="${xc}" cy="${YA(det[i])}" r="3" fill="#f59e0b" stroke="#fff" stroke-width="1"/>`);
        }
        // HRRR / HRDPS 6-hour snowfall
        for (const h of hi) for (let i = 0; i < h.ends.length; i++) if (h.snow[i] != null) out.push(marker(h.shape, X(h.ends[i] - W / 2) + h.dx, YA(h.snow[i]), h.color));
        // liquid precipitation row: deterministic NBM value per window
        if (qpf) {
            out.push(`<text x="${pad.l}" y="${Q.y0 - 8}" font-size="12" font-weight="700" fill="#1e3c72">Liquid precipitation <tspan font-weight="400" fill="#64748b">(rain plus the water in snow, 6-hour totals; green bars are the NBM)</tspan></text>`);
            let tot = 0, seen = 0;
            for (let i = 0; i < n; i++) {
                const xc = X(ends[i] - W / 2);
                if (qpf[i] == null) { out.push(`<rect x="${xc - bw / 2}" y="${Q.y0}" width="${bw}" height="${Q.h}" fill="#f1f5f9"/>`); continue; }
                tot += qpf[i]; seen++;
                out.push(`<rect x="${xc - bw / 2}" y="${YQ(qpf[i])}" width="${bw}" height="${Math.max(0, YQ(0) - YQ(qpf[i]))}" fill="#0f766e" opacity="0.85"/>`);
            }
            for (const h of hi) for (let i = 0; i < h.ends.length; i++) if (h.precip[i] != null) out.push(marker(h.shape, X(h.ends[i] - W / 2) + h.dx, YQ(h.precip[i]), h.color));
            if (seen) out.push(`<text x="${W_ - pad.r}" y="${Q.y0 - 8}" text-anchor="end" font-size="12" font-weight="700" fill="#0f766e">NBM total ${num(tot, 2)} in</text>`);
        }
        // cumulative band + median
        if (known > 0) {
            const xs = [ends[0] - W, ...ends.slice(0, known)].map(X);
            const poly = (a, b) => a.map((v, i) => `${xs[i]},${YB(v)}`).join(' ') + ' ' + b.map((v, i) => `${xs[b.length - 1 - i]},${YB(b[b.length - 1 - i])}`).join(' ');
            out.push(`<polygon points="${poly(cum.hi, cum.lo)}" fill="#3b82f6" opacity="0.18"/>`);
            out.push(`<polyline points="${cum.mid.map((v, i) => `${xs[i]},${YB(v)}`).join(' ')}" fill="none" stroke="#1e3c72" stroke-width="2.4"/>`);
            const lastX = xs[xs.length - 1];
            out.push(`<text x="${Math.min(lastX + 6, W_ - 4)}" y="${YB(cum.mid[known]) - 6}" text-anchor="${lastX > W_ - 120 ? 'end' : 'start'}" font-size="12" font-weight="700" fill="#1e3c72">${num(cum.mid[known])}" (${num(cum.lo[known])}\u2013${num(cum.hi[known])}")</text>`);
        }
        hi.forEach((h, k) => {
            const c = hiCum[k], xs = [h.ends[0] - W, ...h.ends.slice(0, c.length - 1)].map(X);
            if (c.length < 2) return;
            out.push(`<polyline points="${c.map((v, i) => `${xs[i]},${YB(v)}`).join(' ')}" fill="none" stroke="${h.color}" stroke-width="2.2" stroke-dasharray="6 3"/>`);
            out.push(`<text x="${Math.min(xs[xs.length - 1] + 6, W_ - 4)}" y="${YB(c[c.length - 1]) + 14}" text-anchor="${xs[xs.length - 1] > W_ - 120 ? 'end' : 'start'}" font-size="12" font-weight="700" fill="${h.color}">${num(c[c.length - 1])}"</text>`);
        });
        out.push(`<text x="${pad.l}" y="${B.y0 - 6}" font-size="11" fill="#64748b">Accumulation: line is the sum of the medians, shading the sum of the 25th and 75th percentiles (approximate).</text>`);
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W_}" height="${H_}" viewBox="0 0 ${W_} ${H_}" font-family="-apple-system, Segoe UI, Roboto, Arial, sans-serif">${out.join('')}</svg>`;
        return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    }

    function cloudChart(areaId) {
        const site = nbmData && nbmData.sites[NBM_SITE[areaId]];
        if (!site || !site.cloud_pct || !nbmData.cloud_time_utc) return null;
        const ts = nbmData.cloud_time_utc.map(t => Date.parse(t)), v = site.cloud_pct;
        const W_ = 820, H_ = 300, pad = { l: 52, r: 16, t: 48, b: 58 };
        const t0 = ts[0], t1 = ts[ts.length - 1];
        const X = t => pad.l + (t - t0) / (t1 - t0) * (W_ - pad.l - pad.r);
        const Y = p => pad.t + (100 - p) / 100 * (H_ - pad.t - pad.b);
        const out = [`<rect width="${W_}" height="${H_}" fill="#fff"/>`,
            `<text x="${pad.l}" y="18" font-size="14" font-weight="700" fill="#1e3c72">NBM cloud cover</text>`,
            `<text x="${pad.l}" y="34" font-size="11" fill="#64748b">Percent of sky covered, every 3 hours. Under 25% is mostly sunny; over 75% is mostly cloudy.</text>`];
        out.push(`<rect x="${pad.l}" y="${Y(100)}" width="${W_ - pad.l - pad.r}" height="${Y(75) - Y(100)}" fill="#e2e8f0" opacity="0.5"/>`);
        out.push(`<rect x="${pad.l}" y="${Y(25)}" width="${W_ - pad.l - pad.r}" height="${Y(0) - Y(25)}" fill="#fef3c7" opacity="0.6"/>`);
        for (const g of [0, 25, 50, 75, 100]) out.push(`<line x1="${pad.l}" x2="${W_ - pad.r}" y1="${Y(g)}" y2="${Y(g)}" stroke="#e2e8f0"/><text x="${pad.l - 6}" y="${Y(g) + 4}" text-anchor="end" font-size="11" fill="#64748b">${g}</text>`);
        for (let t = Math.ceil(t0 / 3600e3) * 3600e3; t <= t1; t += 3600e3) {
            if (+PAC_H.format(t) !== 0) continue;
            out.push(`<line x1="${X(t)}" x2="${X(t)}" y1="${pad.t}" y2="${H_ - pad.b}" stroke="#94a3b8" stroke-dasharray="3 3"/>`);
            if (X(t) < W_ - pad.r - 50) out.push(`<text x="${X(t) + 4}" y="${H_ - pad.b + 16}" font-size="11" fill="#334155">${PAC_D.format(t + 6 * 3600e3).replace(',', '')}</text>`);
        }
        out.push(`<text x="${pad.l}" y="${H_ - pad.b + 34}" font-size="10.5" fill="#64748b">Dashed lines mark midnight Pacific time; labels are the Pacific day that follows.</text>`);
        const pts = ts.map((t, i) => v[i] == null ? null : [X(t), Y(v[i])]);
        // draw in runs so a missing value breaks the line
        let seg = [];
        const flush = () => { if (seg.length > 1) out.push(`<polyline points="${seg.map(p => p.join(',')).join(' ')}" fill="none" stroke="#1e3c72" stroke-width="2.4"/>`); seg = []; };
        pts.forEach(p => { if (p) seg.push(p); else flush(); });
        flush();
        pts.forEach(p => { if (p) out.push(`<circle cx="${p[0]}" cy="${p[1]}" r="2.2" fill="#1e3c72"/>`); });
        out.push(`<text x="14" y="${(pad.t + H_ - pad.b) / 2}" transform="rotate(-90 14 ${(pad.t + H_ - pad.b) / 2})" text-anchor="middle" font-size="12" fill="#334155">cloud cover (%)</text>`);
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W_}" height="${H_}" viewBox="0 0 ${W_} ${H_}" font-family="-apple-system, Segoe UI, Roboto, Arial, sans-serif">${out.join('')}</svg>`;
        return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    }

    const ENSEMBLE_HOW = 'Look at the range of the ensemble members (the ensemble spread) to judge uncertainty in the forecast. A larger spread means lower confidence.';
    const UTAH = 'https://weather.utah.edu/';

    // ---- UW WRF (University of Washington Atmospheric Sciences): Washington-wide maps ----
    const uwRuns = n => {
        const step = 12 * 3600e3, base = Math.floor(Date.now() / step) * step;
        return Array.from({ length: n }, (_, i) => new Date(base - i * step));
    };
    // Deterministic: /wrfrt/data/{YYYYMMDDHH}/images_d4/wa_{var}.{FF}.0000.gif
    // Ensemble mean: /mm5rt/ensembles/{YYYYMMDDHH}/images_d3/{var}.{FF}.mean.gif
    const UW = 'https://a.atmos.washington.edu';
    const UW_SRC = { source: 'UW Atmospheric Sciences', sourceUrl: UW + '/wrfrt/' };
    const uwDet = (v, hours, probeHour) => ({
        hours, probeHour, runs: uwRuns(6), runExact: true,
        urlFor: (r, h) => `${UW}/wrfrt/data/${ymdh(r)}/images_d4/wa_${v}.${pad(h, 2)}.0000.gif`,
        fallbackUrl: UW + '/wrfrt/',
    });
    const uwEns = (v, hours, probeHour) => ({
        hours, probeHour, runs: uwRuns(6), runExact: true,
        urlFor: (r, h) => `${UW}/mm5rt/ensembles/${ymdh(r)}/images_d3/${v}.${pad(h, 2)}.mean.gif`,
        fallbackUrl: UW + '/mm5rt/ensembles/',
    });
    const HOURLY48 = range(1, 48, 1), HOURLY_ENS = range(3, 84, 3);
    const ENS_NOTE = 'The ensemble mean averages every member, so it smooths out the extremes. Use it for the most likely pattern, and use the individual-member plume plots for the spread.';


    const PRODUCTS = {
        wwrf_snow: {
            needs: 'wwrf',
            label: 'Snow (West-WRF)',
            title: a => `${a.label}: West-WRF ensemble accumulated snow`,
            build: a => ({ urlFor: () => `${CW3E}/wwrf/images/ensemble/West-WRF_AccSnow_Meteogram_Panel_${a.wwrf}.png`, fallbackUrl: 'https://cw3e.ucsd.edu/west-wrf_ensemble_meteograms' }),
            info: {
                what: 'Accumulated snowfall for this area from the West-WRF ensemble, run by the Center for Western Weather and Water Extremes (CW3E) at UC San Diego. West-WRF is a 200-member ensemble at 9 km grid spacing, run October&ndash;March. It was built for high-intensity winter precipitation, especially atmospheric rivers, and recent studies show it performs better than the GEFS and as well or better than the ECMWF ensemble (<a href="https://journals.ametsoc.org/view/journals/mwre/153/8/MWR-D-24-0136.1.xml" target="_blank" rel="noopener noreferrer">Delle Monache et al. 2025</a>).',
                how: ENSEMBLE_HOW,
                source: 'CW3E West-WRF ensemble meteograms', sourceUrl: 'https://cw3e.ucsd.edu/west-wrf_ensemble_meteograms',
            },
        },
        wwrf_qpf: {
            needs: 'wwrf',
            label: 'Precip (West-WRF)',
            title: a => `${a.label}: West-WRF ensemble accumulated precipitation`,
            build: a => ({ urlFor: () => `${CW3E}/wwrf/images/ensemble/West-WRF_AccQPF_Meteogram_Panel_${a.wwrf}.png`, fallbackUrl: 'https://cw3e.ucsd.edu/west-wrf_ensemble_meteograms' }),
            info: {
                what: 'Accumulated precipitation (rain plus the water content of snow) for this area from the West-WRF ensemble at CW3E, UC San Diego. Same model as the snow plot; this one shows the total water, so compare the two to see how much of it falls as snow.',
                how: ENSEMBLE_HOW,
                source: 'CW3E West-WRF ensemble meteograms', sourceUrl: 'https://cw3e.ucsd.edu/west-wrf_ensemble_meteograms',
            },
        },
        utah_ens: {
            needs: 'utah',
            label: 'Utah 10-day ensemble',
            title: a => `${a.label}: Utah snow ensemble, 10 days`,
            build: a => ({
                runs: utahRuns(8), runExact: true,
                urlFor: r => `https://weather.utah.edu/${ymd(r)}/images/models/ensgefsds/ENSGEFSDSPL_${a.utah}${ymdh(r)}F240.png`,
                fallbackUrl: UTAH,
            }),
            info: {
                what: 'Accumulated snow and precipitation for this area from the University of Utah snow ensemble. It combines the GEFS (US) and ECMWF EPS (European) ensembles and applies statistical downscaling to bring them to the mountain.',
                how: `${ENSEMBLE_HOW} The bottom-left panel shows the 0.5&deg;C wet-bulb temperature level, which roughly tracks the rain/snow line.`,
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
            },
        },
        rrfs: {
            needs: 'utah',
            label: 'RRFS 2.5-day ensemble',
            title: a => `${a.label}: RRFS snow ensemble, 2.5 days`,
            build: a => ({
                runs: utahRuns(8), runExact: true,
                urlFor: r => `https://weather.utah.edu/${ymd(r)}/images/models/rrfsqsf/RRFSPL_${a.utah}${ymdh(r)}F060.png`,
                fallbackUrl: UTAH,
            }),
            info: {
                what: 'Accumulated snow and precipitation for this area from the Rapid Refresh Forecast System (RRFS) ensemble, NOAA&rsquo;s next-generation convection-allowing ensemble. It runs out 60 hours at 3 km grid spacing, rerun every 6 hours. Plots are hosted by the University of Utah.',
                how: `${ENSEMBLE_HOW} The bottom-left panel shows the 0.5&deg;C wet-bulb temperature level, which roughly tracks the rain/snow line.`,
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
            },
        },
        hrrr: {
            region: true, label: 'HRRR snow (48 h)',
            title: a => `${a.label}: HRRR snowfall, 48 hours`,
            build: () => utahMap('hrrrqsf', 'HRRR48HS', range(1, 48, 1)),
            info: {
                what: 'Map of forecast snowfall accumulated through each forecast hour from the HRRR, NOAA&rsquo;s hourly-updated 3 km model, over the Northwest. Plots are hosted by the University of Utah.',
                how: 'Step through the hours to watch when and where the snow falls. The HRRR is a single run (not an ensemble) and is best in the first day or so; compare with the RRFS and the Utah ensemble before trusting any one total.',
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
            },
        },
        rrfs_map: {
            region: true, label: 'RRFS snow (60 h)',
            title: a => `${a.label}: RRFS snowfall, 60 hours`,
            build: () => utahMap('rrfsqsf', 'RRFS60HS', range(1, 60, 1)),
            info: {
                what: 'Map of forecast snowfall accumulated through each forecast hour from the Rapid Refresh Forecast System (RRFS), NOAA&rsquo;s next-generation 3 km convection-allowing system. Plots are hosted by the University of Utah.',
                how: 'A second high-resolution view to compare against the HRRR. Where the two agree on the snow axis and amounts, confidence is higher; where they differ, treat the totals as uncertain.',
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
            },
        },
        utah_map: {
            region: true, label: 'Utah snow ensemble (10 d)',
            title: a => `${a.label}: Utah snow ensemble, 10 days`,
            build: () => utahMap('ensgefsds', 'ENSGEFSDS240HS', range(6, 240, 6)),
            info: {
                what: 'Map of forecast snowfall accumulated through each forecast hour from the University of Utah snow ensemble, which combines GEFS and ECMWF ensemble members with statistical downscaling, out to 10 days.',
                how: 'Use it for the longer-range snow pattern beyond what the HRRR and RRFS cover. Totals this far out are a guide to where snow is favored, not a point forecast.',
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
            },
        },
        uw_snow: {
            region: true, label: 'UW WRF snow',
            models: { acc: 'Accumulated (WRF)', p3: '3-hour (WRF)', ens: '24-hour (ensemble mean)' },
            title: (a, st) => ({ acc: 'UW WRF accumulated snowfall', p3: 'UW WRF 3-hour snowfall', ens: 'UW WRF ensemble mean 24-hour snowfall' })[st.model] || 'UW WRF accumulated snowfall',
            build: (a, st) => ({ acc: uwDet('snowacc', HOURLY48, 3), p3: uwDet('snow3', range(6, 48, 3), 6), ens: uwEns('msnow24', HOURLY_ENS, 24) })[st.model] || uwDet('snowacc', HOURLY48, 3),
            info: Object.assign({
                what: 'Snowfall from the University of Washington WRF model over Washington. The deterministic WRF (the 1.33 km domain) shows either the snow total accumulated through each forecast hour or the snow that falls in each 3-hour period. The ensemble option is the mean of the UW WRF ensemble&rsquo;s 24-hour snowfall.',
                how: 'Use the accumulated map for totals and the 3-hour map to see when the heaviest bursts hit. Compare the WRF with the ensemble mean: if a single run shows much more snow than the mean, treat it as the high end. ' + ENS_NOTE,
            }, UW_SRC),
        },
        uw_precip: {
            region: true, label: 'UW WRF total precip',
            models: { tot: 'Accumulated (24, 36, 48 h)', p3: '3-hour' },
            title: (a, st) => st.model === 'p3' ? 'UW WRF 3-hour precipitation' : 'UW WRF total accumulated precipitation',
            build: (a, st) => st.model === 'p3' ? uwDet('pcp3', range(6, 48, 3), 6) : uwDet('pcpt', [24, 36, 48], 24),
            info: Object.assign({
                what: 'Precipitation (rain plus the water in snow) from the UW WRF model over Washington: either the total accumulated since the start of the run, which the model posts at 24, 36 and 48 hours, or the amount that falls in each 3-hour period.',
                how: 'Compare it with the snow map: where precipitation is high but snow is low, the model has rain or a high snow level. Use the 3-hour maps for timing. Totals are heavily shaped by terrain, so look at the Cascade crest and windward slopes.',
            }, UW_SRC),
        },
        uw_cloud: {
            region: true, label: 'UW WRF clouds',
            models: { low: '0-3,000 ft', mid: '3,000-10,000 ft', high: '10,000-20,000 ft' },
            title: (a, st) => 'UW WRF ensemble mean cloud water, ' + ({ low: '0-3,000 ft', mid: '3,000-10,000 ft', high: '10,000-20,000 ft' })[st.model || 'low'],
            build: (a, st) => {
                const hrs = HOURLY_ENS.concat([0]).sort((x, y) => x - y);
                return ({ low: uwEns('qclst', hrs, 0), mid: uwEns('qcll', hrs, 0), high: uwEns('qclm', hrs, 0) })[st.model] || uwEns('qclst', hrs, 0);
            },
            info: Object.assign({
                what: 'Ensemble mean cloud water in three layers: the lowest 3,000 ft (valley fog and low stratus), 3,000 to 10,000 ft (the layer covering ski terrain), and 10,000 to 20,000 ft (higher cloud).',
                how: 'Use the middle layer to see whether the terrain will be in cloud, the low layer to judge valley fog and inversions, and the high layer to judge sunshine and sky color. ' + ENS_NOTE,
            }, UW_SRC),
        },
        nbm: {
            label: 'NBM snow (6 h)',
            title: a => `${a.label}: NBM snowfall, 6-hour windows`,
            build: (a, st) => ({
                hours: [null], runs: nbmData ? [new Date(Date.parse(nbmData.cycle_utc))] : null, runExact: true,
                urlFor: () => nbmChart(st.area) || '',
                fallbackUrl: 'https://www.weather.gov/mdl/nbm_home',
            }),
            info: {
                what: 'Snowfall from the National Blend of Models (NBM), NOAA&rsquo;s statistical blend of many models, for the grid cell nearest this area (2.5 km), in 6-hour windows. Bars are the median, whiskers span the 25th to 75th percentile, and the orange dot is the NBM deterministic value. The middle panel is liquid precipitation (rain plus the water in snow) for the same windows: green bars are the NBM deterministic value. Red diamonds are the HRRR and purple triangles the HRDPS, two high-resolution models that run only 48 hours; they are drawn over the NBM so you can compare them. The bottom panel adds the snowfall windows up (the NBM median with its range, and a dashed line for each high-resolution model). HRRR snowfall is the model&rsquo;s own; HRDPS snowfall is its water equivalent of snow times 10, an assumed ratio. Updated every 6 hours.',
                how: 'A blend like this tends to be smooth and conservative, so compare its total and spread with the West-WRF and Utah ensembles: when they all agree, confidence is high. Percentiles do not add exactly, so the accumulated shading is approximate. Gaps mean the NBM has no snowfall window for that period.',
                source: 'NOAA National Blend of Models, via Herbie', sourceUrl: 'https://www.weather.gov/mdl/nbm_home',
            },
        },
        nbm_cloud: {
            label: 'NBM clouds',
            title: a => `${a.label}: NBM cloud cover`,
            build: (a, st) => ({
                hours: [null], runs: nbmData ? [new Date(Date.parse(nbmData.cycle_utc))] : null, runExact: true,
                urlFor: () => cloudChart(st.area) || '',
                fallbackUrl: 'https://www.weather.gov/mdl/nbm_home',
            }),
            info: {
                what: 'Total cloud cover from the National Blend of Models (NBM) for the grid cell nearest this area, every 3 hours, as a percent of the sky covered. It is the NBM deterministic value, with no spread shown.',
                how: 'Use it for sun versus cloud timing on touring and powder days: under about 25% is mostly sunny, over about 75% is mostly cloudy. Cloud cover is hard to forecast, so treat the exact hours as approximate and compare with the UW WRF cloud layers on the synoptic page.',
                source: 'NOAA National Blend of Models, via Herbie', sourceUrl: 'https://www.weather.gov/mdl/nbm_home',
            },
        },
        uw_snd: {
            page: 'level',
            needs: 'uw',
            label: 'UW WRF sounding',
            title: a => `${a.label}: UW WRF forecast sounding (${soundings[a.uw].name.replace(',WA', '')}, ${Math.round(soundings[a.uw].elevation_ft).toLocaleString('en-US')} ft)`,
            build: a => {
                const site = soundings[a.uw];
                return {
                    hours: site.frames.map(f => f.hour), runs: [CMWSounding.initDate(site)], runExact: true, maxWidth: 640,
                    urlFor: (r, h) => CMWSounding.skewT(site, Math.max(0, site.frames.findIndex(f => f.hour === h))),
                    fallbackUrl: 'https://a.atmos.washington.edu/mm5rt/rt/',
                };
            },
            info: a => ({
                what: `A forecast sounding from the University of Washington WRF model at ${soundings[a.uw].name.replace(',WA', '')}, the nearest UW sounding point to this area: temperature (red) and dew point (green) up through the atmosphere, drawn on a skew-T. The blue line is 0&deg;C and the purple band is the dendritic growth zone, the layer between -12 and -18&deg;C where the best powder-making snow crystals grow. Dashed lines mark the freezing level and the melting-model snow level.`,
                how: 'Press play to watch the column evolve every 3 hours. Where the red and green lines touch the air is saturated (cloud or precipitation). Snow reaches the ground when the temperature below the cloud stays near or under freezing; a snow level well above the sounding point means rain there. A saturated layer (red and green lines together) inside the purple band is when fluffy dendrites form. Treat one model run as a single scenario, and check it against the NBM, HRRR and ensembles.',
                source: 'University of Washington Atmospheric Sciences, PacNW WRF-GFS 4/3 km', sourceUrl: 'https://a.atmos.washington.edu/mm5rt/rt/',
            }),
        },
        uw_lvl: {
            page: 'level',
            needs: 'uw',
            label: 'UW WRF levels over time',
            title: a => `${a.label}: UW WRF freezing level, snow level and dendritic growth zone (${soundings[a.uw].name.replace(',WA', '')})`,
            build: a => {
                const site = soundings[a.uw];
                return {
                    hours: [null], runs: [CMWSounding.initDate(site)], runExact: true,
                    urlFor: () => CMWSounding.levels(site),
                    fallbackUrl: 'https://a.atmos.washington.edu/mm5rt/rt/',
                };
            },
            info: {
                what: 'The freezing level (blue), the melting-model snow level (orange) and the dendritic growth zone (purple band, from its base to its top) from the UW WRF forecast soundings at the nearest UW sounding point, every 3 hours for 72 hours. The growth zone is the layer between -12 and -18&deg;C, and it only makes powder where the air in it is moist, so check the sounding for saturation.',
                how: 'Compare the snow level with the elevation you plan to ski (the dashed line is the sounding point itself). A snow level that drops below your elevation is the change from rain to snow. A thick purple band over a snow level below your elevation is the setup for light snow, if the sounding shows the layer is saturated. One model run is one scenario.',
                source: 'University of Washington Atmospheric Sciences, PacNW WRF-GFS 4/3 km', sourceUrl: 'https://a.atmos.washington.edu/mm5rt/rt/',
            },
        },
        frz: {
            page: 'level',
            needs: 'basins',
            label: 'Freezing level',
            models: { ecmwf: 'ECMWF (European)', gefs: 'GEFS (American)' },
            title: (a, st) => `${(a.basins.find(b => b.id === st.basin) || a.basins[0]).label} freezing level: ${st.model === 'gefs' ? 'GEFS' : 'ECMWF'} ensemble`,
            build: (a, st) => {
                const b = a.basins.find(x => x.id === st.basin) || a.basins[0];
                return {
                    urlFor: () => `${CW3E}/${st.model === 'gefs' ? 'gefs' : 'ECMWF'}/freezingLevelImages/${b.id}_current.png`,
                    fallbackUrl: 'https://cw3e.ucsd.edu/DSMaps/DS_freezing.html',
                };
            },
            info: st => ({
                what: `The ${st.model === 'gefs' ? 'GEFS (American)' : 'ECMWF (European)'} ensemble forecast of the freezing level over this watershed. Each light gray line is one ensemble member. The bars show 6-hour precipitation averaged over the watershed, colored by the share of the watershed that gets snow versus rain in that period.`,
                how: 'Tightly spaced lines mean the models agree; widely spaced lines mean more uncertainty. Look at the ensemble mean (light green line) and the &plusmn;1 standard deviation spread (gray shading between the red and blue lines). Where the freezing level sits relative to the pass and base elevations tells you where it rains and where it snows.',
                source: 'CW3E watershed freezing level forecasts', sourceUrl: 'https://cw3e.ucsd.edu/DSMaps/DS_freezing.html',
            }),
        },
    };

    const mount = () => {
        CMWViewer.mount(document.getElementById('viewer'), {
            singleMaxWidth: 760,
            selectors: [
                { key: 'area', label: 'Area', select: true, alwaysShow: true, options: Object.keys(AREAS).filter(k => PAGE === 'precip' || !AREAS[k].region).map(k => ({ value: k, label: AREAS[k].label })) },
                { key: 'product', label: 'Product', options: st => Object.keys(PRODUCTS).filter(k => pageOf(PRODUCTS[k]) === PAGE && !!PRODUCTS[k].region === !!AREAS[st.area].region && (!PRODUCTS[k].needs || AREAS[st.area][PRODUCTS[k].needs]) && (!/^nbm/.test(k) || (nbmData && NBM_SITE[st.area] && (k !== 'nbm_cloud' || nbmData.cloud_time_utc)))).map(k => ({ value: k, label: PRODUCTS[k].label })) },
                { key: 'basin', label: 'Watershed', options: st => st.product === 'frz' && AREAS[st.area].basins ? AREAS[st.area].basins.map(b => ({ value: b.id, label: b.label })) : [{ value: '-', label: '-' }] },
                { key: 'model', label: 'Model', options: st => PRODUCTS[st.product].models ? Object.keys(PRODUCTS[st.product].models).map(m => ({ value: m, label: PRODUCTS[st.product].models[m] })) : [{ value: '-', label: '-' }] },
            ],
            resolve(st) {
                const a = AREAS[st.area], p = PRODUCTS[st.product];
                const info = typeof p.info === 'function' ? p.info(st.product === 'uw_snd' ? a : st) : p.info;
                return Object.assign({ hours: [null], runs: null, runExact: false, title: p.title(a, st), info,
                    latestNote: 'Always the most recent run. The run and valid times are printed on the figure, in Z (UTC).' }, p.build(a, st));
            },
        });
    };
    const getJson = name => fetch(BASE + 'data/' + name, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
    // Links made before the split (#product=frz, uw_snd, uw_lvl on the precipitation page) go to the new page.
    if (PAGE === 'precip' && /[#&]product=(frz|uw_snd|uw_lvl)(&|$)/.test(location.hash)) {
        location.replace(BASE.replace(/assets\/$/, 'tools/model-tools-freezing-level.html') + location.hash);
        return;
    }
    const uwSites = [...new Set(Object.values(AREAS).map(a => a.uw).filter(Boolean))];
    Promise.all([getJson('nbm_plumes.json'), getJson('hires_plumes.json'), Promise.all(uwSites.map(k => CMWSounding.load(k)))])
        .then(([nbm, hires, uw]) => {
            nbmData = nbm; hiresData = hires;
            uwSites.forEach((k, i) => { if (uw[i] && uw[i].frames && uw[i].frames.length) soundings[k] = uw[i]; });
            Object.values(AREAS).forEach(a => { if (a.uw && !soundings[a.uw]) delete a.uw; });   // no data: hide the products for that area
            mount();
        });
}());
