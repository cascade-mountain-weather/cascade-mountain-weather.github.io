// Precipitation tools page: area x product catalog for assets/model-viewer.js.
(function () {
    'use strict';
    const BASE = (document.currentScript && document.currentScript.src || '').replace(/[^/]*$/, '');
    let nbmData = null; // assets/data/nbm_plumes.json, written by scripts/nbm_plume.py
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
        'mt-baker': { label: 'Mt. Baker (Heather Meadows)', wwrf: 'WA543', utah: 'MTB42', basins: [{ id: '17110005', label: 'Upper Skagit' }] },
        'stevens': { label: 'Stevens Pass', wwrf: 'US2', utah: 'TSTEV', basins: [{ id: '17110009', label: 'Skykomish (west side)' }, { id: '17020011', label: 'Wenatchee (east side)' }] },
        'snoqualmie': { label: 'Snoqualmie Pass', wwrf: 'I90', utah: 'SNO30', basins: [{ id: '17110010', label: 'Snoqualmie (west side)' }, { id: '17030001', label: 'Upper Yakima (east side)' }] },
        'blewett': { label: 'Blewett Pass', wwrf: 'US97', utah: 'MISR', basins: [{ id: '17020011', label: 'Wenatchee' }] },
        'crystal': { label: 'Crystal Mountain', wwrf: 'MRNP', utah: 'CMT', basins: [{ id: '17110014', label: 'Puyallup' }] },
        'paradise': { label: 'Paradise (Mt. Rainier)', wwrf: 'MRNP', utah: 'PVC54', basins: [{ id: '17110015', label: 'Nisqually' }] },
        'white': { label: 'White Pass', wwrf: 'US12', utah: 'WPS45', basins: [{ id: '17080004', label: 'Upper Cowlitz' }] },
        'washington': { label: 'Washington Pass', wwrf: 'WA20', utah: 'WAP55', basins: [{ id: '17020009', label: 'Lake Chelan (west side)' }, { id: '17020008', label: 'Methow (east side)' }] },
    };


    // ---- NBM snowfall plume, drawn as an SVG image so it behaves like the other figures ----
    const NBM_SITE = { 'mt-baker': 'Mt. Baker', stevens: 'Stevens Pass', snoqualmie: 'Snoqualmie Pass', blewett: 'Blewett Pass',
        crystal: 'Crystal', paradise: 'Paradise', white: 'White Pass', washington: 'Washington Pass' };
    const PAC_H = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', hour: 'numeric', hourCycle: 'h23' });
    const PAC_D = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', weekday: 'short', month: 'numeric', day: 'numeric' });
    const num = (v, d) => (v == null ? '\u2013' : (+v).toFixed(d == null ? 1 : d));

    function nbmChart(areaId) {
        const site = nbmData && nbmData.sites[NBM_SITE[areaId]];
        if (!site) return null;
        const ends = nbmData.window_end_utc.map(t => Date.parse(t));
        const W = nbmData.window_hours * 3600e3, n = ends.length;
        const t0 = ends[0] - W, t1 = ends[n - 1];
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
        const maxBar = Math.max(1, ...p75.filter(v => v != null), ...det.filter(v => v != null));
        const maxCum = Math.max(1, cum.hi[cum.hi.length - 1] || 0);
        const nice = m => { const st = m <= 4 ? 1 : m <= 12 ? 2 : m <= 30 ? 5 : 10; return Math.ceil(m / st) * st; };
        const topMax = nice(maxBar * 1.1), botMax = nice(maxCum * 1.05);
        const A = { y0: 44, h: 170 }, B = { y0: 270, h: 170 };
        const YA = v => A.y0 + A.h - v / topMax * A.h, YB = v => B.y0 + B.h - v / botMax * B.h;
        const out = [];
        const grid = (P, M, Y, label) => {
            const st = M <= 4 ? 1 : M <= 12 ? 2 : M <= 30 ? 5 : 10;
            for (let v = 0; v <= M; v += st) out.push(`<line x1="${pad.l}" x2="${W_ - pad.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#e2e8f0"/><text x="${pad.l - 6}" y="${Y(v) + 4}" text-anchor="end" font-size="11" fill="#64748b">${v}</text>`);
            out.push(`<text x="14" y="${P.y0 + P.h / 2}" transform="rotate(-90 14 ${P.y0 + P.h / 2})" text-anchor="middle" font-size="12" fill="#334155">${label}</text>`);
        };
        out.push(`<rect width="${W_}" height="492" fill="#fff"/>`);
        out.push(`<text x="${pad.l}" y="18" font-size="14" font-weight="700" fill="#1e3c72">NBM snowfall</text>`);
        out.push(`<text x="${pad.l}" y="34" font-size="11" fill="#64748b">Bars: median per 6 hours. Whiskers: 25th to 75th percentile. Dot: NBM deterministic.</text>`);
        grid(A, topMax, YA, 'inches per 6 h');
        grid(B, botMax, YB, 'inches accumulated');
        // Pacific midnights and day labels
        for (let t = Math.ceil(t0 / 3600e3) * 3600e3; t <= t1; t += 3600e3) {
            if (+PAC_H.format(t) !== 0) continue;
            for (const P of [A, B]) out.push(`<line x1="${X(t)}" x2="${X(t)}" y1="${P.y0}" y2="${P.y0 + P.h}" stroke="#94a3b8" stroke-dasharray="3 3"/>`);
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
        // cumulative band + median
        if (known > 0) {
            const xs = [t0, ...ends.slice(0, known)].map(X);
            const poly = (a, b) => a.map((v, i) => `${xs[i]},${YB(v)}`).join(' ') + ' ' + b.map((v, i) => `${xs[b.length - 1 - i]},${YB(b[b.length - 1 - i])}`).join(' ');
            out.push(`<polygon points="${poly(cum.hi, cum.lo)}" fill="#3b82f6" opacity="0.18"/>`);
            out.push(`<polyline points="${cum.mid.map((v, i) => `${xs[i]},${YB(v)}`).join(' ')}" fill="none" stroke="#1e3c72" stroke-width="2.4"/>`);
            const lastX = xs[xs.length - 1];
            out.push(`<text x="${Math.min(lastX + 6, W_ - 4)}" y="${YB(cum.mid[known]) - 6}" text-anchor="${lastX > W_ - 120 ? 'end' : 'start'}" font-size="12" font-weight="700" fill="#1e3c72">${num(cum.mid[known])}" (${num(cum.lo[known])}\u2013${num(cum.hi[known])}")</text>`);
        }
        out.push(`<text x="${pad.l}" y="${B.y0 - 6}" font-size="11" fill="#64748b">Accumulation: line is the sum of the medians, shading the sum of the 25th and 75th percentiles (approximate).</text>`);
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W_}" height="492" viewBox="0 0 ${W_} 492" font-family="-apple-system, Segoe UI, Roboto, Arial, sans-serif">${out.join('')}</svg>`;
        return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    }

    const ENSEMBLE_HOW = 'Look at the range of the ensemble members (the ensemble spread) to judge uncertainty in the forecast. A larger spread means lower confidence.';
    const UTAH = 'https://weather.utah.edu/';
    const PRODUCTS = {
        wwrf_snow: {
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
        nbm: {
            label: 'NBM snow (6 h)',
            title: a => `${a.label}: NBM snowfall, 6-hour windows`,
            build: (a, st) => ({
                hours: [null], runs: nbmData ? [new Date(Date.parse(nbmData.cycle_utc))] : null, runExact: true,
                urlFor: () => nbmChart(st.area) || '',
                fallbackUrl: 'https://www.weather.gov/mdl/nbm_home',
            }),
            info: {
                what: 'Snowfall from the National Blend of Models (NBM), NOAA&rsquo;s statistical blend of many models, for the grid cell nearest this area (2.5 km), in 6-hour windows. Bars are the median, whiskers span the 25th to 75th percentile, and the orange dot is the NBM deterministic value. The lower panel adds the windows up. Updated every 6 hours.',
                how: 'A blend like this tends to be smooth and conservative, so compare its total and spread with the West-WRF and Utah ensembles: when they all agree, confidence is high. Percentiles do not add exactly, so the accumulated shading is approximate. Gaps mean the NBM has no snowfall window for that period.',
                source: 'NOAA National Blend of Models, via Herbie', sourceUrl: 'https://www.weather.gov/mdl/nbm_home',
            },
        },
        frz: {
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
            selectors: [
                { key: 'area', label: 'Area', select: true, alwaysShow: true, options: Object.keys(AREAS).map(k => ({ value: k, label: AREAS[k].label })) },
                { key: 'product', label: 'Product', options: st => Object.keys(PRODUCTS).filter(k => !!PRODUCTS[k].region === !!AREAS[st.area].region && (k !== 'nbm' || (nbmData && NBM_SITE[st.area]))).map(k => ({ value: k, label: PRODUCTS[k].label })) },
                { key: 'basin', label: 'Watershed', options: st => st.product === 'frz' && AREAS[st.area].basins ? AREAS[st.area].basins.map(b => ({ value: b.id, label: b.label })) : [{ value: '-', label: '-' }] },
                { key: 'model', label: 'Model', options: st => st.product === 'frz' ? Object.keys(PRODUCTS.frz.models).map(m => ({ value: m, label: PRODUCTS.frz.models[m] })) : [{ value: '-', label: '-' }] },
            ],
            resolve(st) {
                const a = AREAS[st.area], p = PRODUCTS[st.product];
                const info = typeof p.info === 'function' ? p.info(st) : p.info;
                return Object.assign({ hours: [null], runs: null, runExact: false, title: p.title(a, st), info,
                    latestNote: 'Always the most recent run. The run and valid times are printed on the figure, in Z (UTC).' }, p.build(a, st));
            },
        });
    };
    fetch(BASE + 'data/nbm_plumes.json', { cache: 'no-cache' })
        .then(r => (r.ok ? r.json() : null)).catch(() => null)
        .then(d => { nbmData = d; mount(); });
}());
