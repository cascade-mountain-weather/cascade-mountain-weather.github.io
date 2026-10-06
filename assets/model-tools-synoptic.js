// Synoptic tools page: product catalog for assets/model-viewer.js.
// CW3E "latest" images do not say which model run they come from, so the run is
// estimated from the clock (flagged as such in the viewer). Utah images carry the
// run in the URL, so those are exact and fall back to earlier runs if the newest is missing.
(function () {
    'use strict';
    const range = (start, end, step) => Array.from({ length: Math.floor((end - start) / step) + 1 }, (_, i) => start + i * step);
    const pad = (n, w) => String(n).padStart(w, '0');

    // Newest cycle (every `cycleH` hours) that should plausibly be posted by now, given a posting lag.
    function estimatedRun(cycleH, lagH) {
        const t = Date.now() - lagH * 3600e3;
        const d = new Date(Math.floor(t / (cycleH * 3600e3)) * cycleH * 3600e3);
        return d;
    }
    function utahRuns(n) {
        const base = Math.floor(Date.now() / (12 * 3600e3)) * 12 * 3600e3;
        return Array.from({ length: n }, (_, i) => new Date(base - i * 12 * 3600e3));
    }
    const ymd = d => `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1, 2)}${pad(d.getUTCDate(), 2)}`;

    const CW3E = 'https://cw3e.ucsd.edu/images';
    const MODELS = {
        gfs: { label: 'GFS', dir: 'gfs', pre: 'GFS', cycle: 6, lag: 5 },
        ecmwf: { label: 'ECMWF', dir: 'ECMWF', pre: 'ECMWF', cycle: 12, lag: 9 },
    };

    function cw3e(prodDir, prodName, region, model, hours, padded) {
        const m = MODELS[model];
        const run = estimatedRun(m.cycle, m.lag);
        return {
            hours, runs: [run], runExact: false,
            urlFor: (r, h) => `${CW3E}/${m.dir}/${prodDir}/${m.pre}_${prodName}_${region}_latest_F${padded ? pad(h, 2) : h}.png`,
            fallbackUrl: 'https://cw3e.ucsd.edu/',
        };
    }

    const PRODUCTS = {
        ivt: {
            label: 'Moisture (IVT)',
            models: ['gfs', 'ecmwf'],
            title: m => `${MODELS[m].label} Integrated Vapor Transport`,
            build: m => cw3e('ivt', 'ivt', 'NEPac', m, range(12, 144, 6), true),
            info: {
                what: 'Integrated vapor transport (IVT) is the total amount of water vapor being carried through the air column, in kg/m/s. It is the standard way to spot atmospheric rivers: long, narrow corridors of IVT aimed at the coast. Values above about 250 mean an atmospheric river; above 500 is strong.',
                how: 'Watch where the plume makes landfall as you step forward. A plume aimed at Washington, especially with high IVT (orange/red), means heavy mountain precipitation. Compare GFS and ECMWF: if they agree on timing and landfall latitude, confidence is higher.',
                source: 'CW3E, UC San Diego', sourceUrl: 'https://cw3e.ucsd.edu/',
            },
        },
        temp850: {
            label: '850 mb temperature',
            models: ['gfs', 'ecmwf'],
            title: m => `${MODELS[m].label} 850 hPa Temperature & Winds`,
            build: m => cw3e('850Temp', '850Temp', 'USWC', m, range(0, 180, 6), false),
            info: {
                what: '850 hPa is about 5,000 feet, near pass level in the Cascades. This shows temperature and wind at that height, so it is a quick read on whether the air feeding a storm is cold enough for snow at pass elevations and how strong the flow is.',
                how: 'A 0&deg;C line near or below the Cascade crest suggests snow levels around pass level; warmer than about +3&deg;C usually means rain at the passes. Strong onshore winds (southwest to west) at 850 hPa mean strong orographic lift on the west slopes.',
                source: 'CW3E, UC San Diego', sourceUrl: 'https://cw3e.ucsd.edu/',
            },
        },
        vort500: {
            label: '500 mb vorticity',
            models: ['gfs', 'ecmwf'],
            title: m => `${MODELS[m].label} 500 hPa Vorticity & Geopotential Height`,
            build: m => cw3e('500Vort', '500Vort', 'NEPac', m, range(0, 180, 6), false),
            info: {
                what: 'The upper-level steering pattern near 18,000 feet. Height contours show ridges and troughs; shading shows vorticity, the spin in the flow, where bright patches mark shortwave troughs that trigger lift and precipitation.',
                how: 'Follow shortwaves (vorticity maxima) as they approach the coast: they often line up with bursts of snow. A trough digging in from the northwest brings colder air than one arriving from the southwest.',
                source: 'CW3E, UC San Diego', sourceUrl: 'https://cw3e.ucsd.edu/',
            },
        },
        utah: {
            label: 'Utah synoptic panels',
            models: ['gfs', 'hres'],
            title: m => m === 'gfs' ? 'GFS 0.25° Synoptic Panels' : 'ECMWF HRES Synoptic Panels',
            build: m => {
                const dir = m === 'gfs' ? 'gfs0p25' : 'hresext';
                const pre = m === 'gfs' ? 'GFSSY_WS' : 'HRESSY_WS';
                return {
                    hours: range(0, 240, 6), runs: utahRuns(4), runExact: true,
                    urlFor: (r, h) => `https://weather.utah.edu/${ymd(r)}/images/models/${dir}/${pre}${ymd(r)}${pad(r.getUTCHours(), 2)}F${pad(h, 3)}.png`,
                    fallbackUrl: 'https://weather.utah.edu/',
                };
            },
            info: {
                what: 'A multi-panel synoptic overview from the University of Utah&rsquo;s weather site, from either the American GFS or the European HRES, out to 10 days. See the source page for the panel layout and map legends.',
                how: 'Use it to see the large-scale pattern past the range of the other products on this page. Treat days 7&ndash;10 as a trend, not a forecast.',
                source: 'University of Utah Atmospheric Sciences', sourceUrl: 'https://weather.utah.edu/',
            },
        },
        arlt: {
            label: 'AR landfall tool',
            models: ['gefs', 'eps'],
            title: m => m === 'gefs' ? 'GEFS Atmospheric River Landfall Tool' : 'ECMWF EPS Atmospheric River Landfall Tool',
            build: m => ({
                hours: [null], runs: null, runExact: false,
                latestNote: 'Always the most recent ensemble run. The run time is printed on the figure.',
                urlFor: () => m === 'gefs'
                    ? `${CW3E}/gefs/v12/LFT/US-west/GEFS_LandfallTool_250_coast_current.png`
                    : `${CW3E}/ECMWF/ensemble/LandfallTool/US-west/ECMWF_LandfallTool_250_coast_current.png`,
                fallbackUrl: 'https://cw3e.ucsd.edu/',
            }),
            info: {
                what: 'An ensemble forecast of IVT arriving along the West Coast over time, one line per ensemble member, by latitude along the coast. It answers: when will the next atmospheric river arrive, how strong, and how sure are we?',
                how: 'Find the latitude band for Washington and look at the spread of members. Tightly bunched lines mean a confident forecast; a wide spread means timing or strength is still uncertain.',
                source: 'CW3E, UC San Diego', sourceUrl: 'https://cw3e.ucsd.edu/',
            },
        },
    };

    const MODEL_LABEL = { gfs: 'GFS', ecmwf: 'ECMWF', hres: 'ECMWF HRES', gefs: 'GEFS (US ensemble)', eps: 'EPS (European ensemble)' };

    CMWViewer.mount(document.getElementById('viewer'), {
        selectors: [
            { key: 'product', label: 'Product', options: Object.keys(PRODUCTS).map(k => ({ value: k, label: PRODUCTS[k].label })) },
            { key: 'model', label: 'Model', options: st => PRODUCTS[st.product].models.map(m => ({ value: m, label: MODEL_LABEL[m] })) },
        ],
        resolve(st) {
            const p = PRODUCTS[st.product];
            const m = p.models.includes(st.model) ? st.model : p.models[0];
            return Object.assign({ title: p.title(m), info: p.info }, p.build(m));
        },
    });
}());
