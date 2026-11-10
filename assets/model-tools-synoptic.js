// Synoptic tools page: product catalog for assets/model-viewer.js.
// Every image URL carries its model run (YYYYMMDDHH), so run times are exact. The viewer tries
// the newest candidate run first and falls back to earlier ones; frames a source does not have
// are skipped. To fix a broken link, edit the url builders below.
(function () {
    'use strict';
    const BASE = (document.currentScript && document.currentScript.src || '').replace(/[^/]*$/, '');
    const range = (start, end, step) => Array.from({ length: Math.floor((end - start) / step) + 1 }, (_, i) => start + i * step);
    const pad = (n, w) => String(n).padStart(w, '0');
    const ymd = d => `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1, 2)}${pad(d.getUTCDate(), 2)}`;
    const ymdh = d => ymd(d) + pad(d.getUTCHours(), 2);

    // Newest-first candidate runs on a fixed cycle (every `cycleH` hours), starting from now.
    function runs(cycleH, n) {
        const step = cycleH * 3600e3;
        const base = Math.floor(Date.now() / step) * step;
        return Array.from({ length: n }, (_, i) => new Date(base - i * step));
    }

    const CW3E = 'https://cw3e-sites.ucsd.edu/images';
    const UTAH = 'https://weather.utah.edu';
    const CW3E_HOME = 'https://cw3e.ucsd.edu/';
    const SRC_CW3E = { source: 'CW3E, UC San Diego', sourceUrl: CW3E_HOME };

    // CW3E map products: /{prod}/v1/{model}/{region}/{run}/1/{prod}__v1__{model}__{region}__{run}__1__F###.png
    function cw3eMap(prod, model, region, cycleH, hours, probeHour) {
        return {
            hours, probeHour, runs: runs(cycleH, 8), runExact: true,
            urlFor: (r, h) => `${CW3E}/${prod}/v1/${model}/${region}/${ymdh(r)}/1/${prod}__v1__${model}__${region}__${ymdh(r)}__1__F${pad(h, 3)}.png`,
            fallbackUrl: CW3E_HOME,
        };
    }
    // CW3E West-WRF maps carry the cold season in the path: /{prod}/{season}/{model}/{region}/{run}/1/{prod}__{season}__{model}__{region}__{run}__1__F###.png
    const season = d => { const y = d.getUTCFullYear(), s = d.getUTCMonth() >= 6 ? y : y - 1; return `${s}-${s + 1}`; };
    function wwrfMap(prod, model, region, cycleH, hours, probeHour) {
        return {
            hours, probeHour, runs: runs(cycleH, 8), runExact: true,
            urlFor: (r, h) => `${CW3E}/${prod}/${season(r)}/${model}/${region}/${ymdh(r)}/1/${prod}__${season(r)}__${model}__${region}__${ymdh(r)}__1__F${pad(h, 3)}.png`,
            fallbackUrl: CW3E_HOME,
        };
    }
    // AR landfall tool: one image per run covering the whole forecast (F384)
    function landfall(model, cycleH) {
        return {
            hours: [null], runs: runs(cycleH, 8), runExact: true,
            urlFor: r => `${CW3E}/landfalltool_ivt250_probability/v1/${model}/coast/${ymdh(r)}/1/landfalltool_ivt250_probability__v1__${model}__coast__${ymdh(r)}__1__F384.png`,
            fallbackUrl: CW3E_HOME,
        };
    }
    // Utah synoptic panels: /{YYYYMMDD}/images/models/{dir}/{prefix}{YYYYMMDDHH}F###.png
    function utah(dir, prefix, cycleH) {
        return {
            hours: range(0, 240, 6), runs: runs(cycleH, 8), runExact: true,
            urlFor: (r, h) => `${UTAH}/${ymd(r)}/images/models/${dir}/${prefix}${ymdh(r)}F${pad(h, 3)}.png`,
            fallbackUrl: UTAH + '/',
        };
    }

    // Point for the ensemble AR plume (off the Washington coast) and how far out it looks: F240 is the 10-day version
    const PLUME = { point: '47.0N_124.0W', hours: 240 };

    // North Pacific SST anomaly (scripts/sst_anomaly_maps.py): one map every few days plus the latest, listed in a manifest.
    // Frames are dates, not forecast hours, so hours are the day offsets from the first date (the run is noon UTC on that date).
    let sst = null;
    function sstView() {
        const ds = sst.dates.map(d => Date.UTC(+d.slice(0, 4), +d.slice(4, 6) - 1, +d.slice(6, 8), 12));
        return {
            hours: ds.map(t => (t - ds[0]) / 3600e3), runs: [new Date(ds[0])], runExact: true,
            urlFor: (r, h) => { const d = new Date(r.getTime() + h * 3600e3), p = (n, w) => String(n).padStart(w, '0');
                return `${BASE}data/sst/${sst.file.replace('{date}', `${d.getUTCFullYear()}${p(d.getUTCMonth() + 1, 2)}${p(d.getUTCDate(), 2)}`)}`; },
            observed: 'Daily analysis (observations), not a forecast. The newest map is a day or two old. Frames are spaced a few days apart.',
            fallbackUrl: 'https://www.ncei.noaa.gov/products/optimum-interpolation-sst',
        };
    }

    // ECMWF Open Charts (charts.ecmwf.int, CC-BY-4.0), cropped to the North Pacific (100E to 100W) and pre-rendered twice a day by
    // scripts/fetch_ecmwf_charts.py (workflow ecmwf_charts.yml) onto the ecmwf-charts branch; the viewer reads that branch's manifest.json.
    // HRES reaches 10 days, the AI models 15; frames are 6 hours apart to day 6, then 12 hours to day 10, then daily. A product shows only when its manifest entry exists.
    let charts = null;
    const CHARTS_URL = (window.ECMWF_CHARTS_URL || '').replace(/\/$/, '') + '/';
    // before the ecmwf-charts branch exists (or when previewing locally), fall back to assets/data/ecmwf_charts/ (scripts/fetch_ecmwf_charts.py --out assets/data/ecmwf_charts)
    const CHARTS_LOCAL = BASE + 'data/ecmwf_charts/';
    let chartsBase = CHARTS_URL;
    function chartView(key, m) {
        const c = charts.charts[key][m], b = c.base;
        return {
            hours: c.hours, runs: [new Date(Date.UTC(+b.slice(0, 4), +b.slice(4, 6) - 1, +b.slice(6, 8), +b.slice(8, 10)))], runExact: true,
            urlFor: (r, h) => chartsBase + charts.file.replace('{product}', key).replace('{model}', m).replace('{base}', b).replace('{hour}', pad(h, 3)),
            fallbackUrl: 'https://charts.ecmwf.int/',
        };
    }
    const OC_SRC = { source: 'ECMWF Open Charts (CC-BY-4.0)', sourceUrl: 'https://charts.ecmwf.int/' };
    const OC_AI = ' The AIFS is ECMWF&rsquo;s AI model; the AIFS ensemble line is its control run (one member), not the ensemble mean. When the AI and physics-based runs agree on the pattern, confidence is higher. The star marks the central Washington coast. Cropped from ECMWF&rsquo;s Open Charts, updated twice a day.';
    const OC_DEFS = {
        jet200: ['Jet stream (200 hPa wind)', 'sea level pressure and 200 hPa wind',
            'Sea level pressure (lines) and the wind at 200 hPa (shading), about 39,000 feet, the level of the jet stream, over the North Pacific from eastern Siberia to the Rockies.',
            'Find the jet core (the strongest wind) and where it is aimed. A jet pointed at Washington brings storms; a jet that splits or dives south of the state means a colder or drier pattern; a ridge with the jet far to the north means dry. Step forward to see whether the jet is extending or retracting across the Pacific.'],
        z500: ['500 hPa height and wind', '500 hPa height and wind',
            'Geopotential height (lines) and wind (shading) at 500 hPa, about 18,000 feet, the standard level for reading ridges and troughs, over the North Pacific.',
            'Troughs (low heights, lines dipping south) near the coast bring storms; ridges (heights bulging north) bring dry weather. Look for a trough digging toward Washington, and for blocking ridges over the Gulf of Alaska.'],
        wind850: ['MSLP and 850 hPa wind', 'sea level pressure and 850 hPa wind',
            'Sea level pressure (lines) and the wind at 850 hPa (shading), about 5,000 feet, the level that feeds moisture into the Cascades.',
            'Strong 850 hPa wind aimed at the coast is the low-level push behind heavy mountain precipitation (compare the Moisture product). Wind from the southwest tends to be milder; wind from the northwest is colder and showery.'],
        z500t850: ['500 hPa height and 850 hPa temp', '500 hPa height and 850 hPa temperature',
            '500 hPa height (lines) with 850 hPa temperature (colors) over the North Pacific, a one-glance view of the pattern aloft and how cold the air at pass level is.',
            'A trough over the Northwest with the 0&deg;C color line at or below pass level is the snow setup. For a closer look at the temperature alone, see the 850 mb temperature product.'],
    };
    const OC_ORDER = ['hres', 'aifs', 'aifs_ens'];

    // add the chart products that the manifest has, right after the 850 mb temperature product
    function addChartProducts() {
        const entries = Object.entries(PRODUCTS);
        Object.keys(PRODUCTS).forEach(k => delete PRODUCTS[k]);
        entries.forEach(([k, v]) => {
            PRODUCTS[k] = v;
            if (k !== 'temp850') return;
            Object.keys(OC_DEFS).forEach(key => {
                if (!charts) return;
                const have = OC_ORDER.filter(m => charts.charts[key] && charts.charts[key][m]);
                if (!have.length) return;
                const [label, title, what, how] = OC_DEFS[key];
                PRODUCTS[key] = { label, models: have, title: m => `${modelName(m)}: ${title}`, build: m => chartView(key, m), info: Object.assign({ what: what + OC_AI, how }, OC_SRC) };
            });
        });
    }

    const MODELS = {
        oisst: 'NOAA OISST', aifs_ens: 'ECMWF AIFS ensemble (control)',
        gfs: 'GFS', ecmwf: 'ECMWF HRES', aifs: 'ECMWF AIFS (AI)', hres: 'ECMWF HRES',
        gefs: 'GEFS', eps: 'ECMWF ENS', diff: 'ECMWF ENS minus GEFS',
        wwrf_ecmwf: 'West-WRF (ECMWF-driven)', wwrf_gfs: 'West-WRF (GFS-driven)',
        wwrf_p500: 'West-WRF ensemble: IVT above 500', wwrf_p250: 'West-WRF ensemble: IVT above 250',
    };
    const modelName = m => MODELS[m];
    // Side by side pairs a model with a sibling from the same family first (West-WRF with West-WRF, the global models together)
    const family = m => (/^wwrf_p/.test(m) ? 'prob' : /^wwrf/.test(m) ? 'wwrf' : 'global');
    const partners = (list, m) => list.filter(x => x !== m).sort((a, b) => (family(b) === family(m)) - (family(a) === family(m)));

    const PRODUCTS = {
        ivt: {
            label: 'Moisture (IVT)',
            models: ['gfs', 'ecmwf', 'wwrf_gfs', 'wwrf_ecmwf', 'wwrf_p500', 'wwrf_p250'],
            title: m => /^wwrf_p/.test(m) ? `West-WRF ensemble: probability that IVT is above ${m === 'wwrf_p250' ? 250 : 500} kg/m/s` : /^wwrf/.test(m) ? `${modelName(m)} integrated vapor transport and sea level pressure (9 km)` : `${modelName(m)} Integrated Vapor Transport`,
            build: m => ({
                gfs: () => cw3eMap('ivt_map', 'GFS_25', 'NEPac', 6, range(12, 240, 6), 12),
                ecmwf: () => cw3eMap('ivt_map', 'ECMWF_HRes', 'NEPac', 12, range(12, 240, 6), 12),
                wwrf_gfs: () => wwrfMap('ivt_map', 'WWRF_9km_GFS', 'NEPac', 12, range(0, 240, 6), 0),
                wwrf_ecmwf: () => wwrfMap('ivt_map', 'WWRF_9km_ECMWF', 'NEPac', 12, range(0, 240, 3), 0),
                wwrf_p500: () => wwrfMap('ivt500_probability_map', 'WWRF_9km_ENS', 'NEPac', 24, range(0, 168, 6), 0),
                wwrf_p250: () => wwrfMap('ivt250_probability_map', 'WWRF_9km_ENS', 'NEPac', 24, range(0, 168, 6), 0),
            })[m](),
            info: m => /^wwrf_p/.test(m) ? Object.assign({
                what: `The chance, from the West-WRF ensemble, that integrated vapor transport (IVT) is above ${m === 'wwrf_p250' ? '250 kg/m/s, a common threshold for an atmospheric river' : '500 kg/m/s, which marks a strong atmospheric river'}. It is issued once a day from the 00Z run and reaches 7 days. Pick the 500 or the 250 threshold.`,
                how: 'High probabilities over or just upwind of Washington mean many ensemble members bring that much moisture there at that time. Low probabilities do not rule out moisture; they mean few members reach the threshold. The 500 map is the one to watch for heavy, flood-producing rain. Try Side by side to put it next to the model maps.',
            }, SRC_CW3E) : Object.assign({
                what: 'Integrated vapor transport (IVT) is the total water vapor being carried through the air column, in kg/m/s. It is the standard way to spot atmospheric rivers: long, narrow corridors of IVT aimed at the coast. Values above about 250 are indicative of atmospheric river conditions.'
                    + (/^wwrf/.test(m) ? ' The West-WRF maps come from the regional model run by CW3E at 9 km grid spacing, driven by the ' + (m === 'wwrf_gfs' ? 'GFS' : 'ECMWF') + ', and add sea level pressure.' : ''),
                how: 'Watch where the plume makes landfall as you step forward. A plume aimed at Washington, especially with high IVT (orange/red), likely means heavy mountain precipitation. Compare models: if they agree on timing and landfall latitude, confidence is higher. Try Side by side to play two at once.',
            }, SRC_CW3E),
        },
        temp850: {
            label: '850 mb temperature',
            models: ['gfs', 'ecmwf'],
            title: m => `${modelName(m)} 850 hPa Temperature`,
            build: m => m === 'gfs'
                ? cw3eMap('850hpa_temperature_map', 'GFS_25', 'NEPac', 6, range(0, 240, 6), 0)
                : cw3eMap('850hpa_temperature_map', 'ECMWF_HRes', 'NEPac', 12, range(0, 240, 3), 0),
            info: Object.assign({
                what: '850 hPa is about 5,000 feet, near pass level in the Cascades. This map shows the temperature there, a quick read on whether the air feeding a storm is cold enough for snow at pass elevations.',
                how: 'A 0&deg;C line near or below the Cascade crest suggests snow levels may be around pass level. Compare models: a few degrees of disagreement here is the difference between rain and snow at the passes.',
            }, SRC_CW3E),
        },
        arlt: {
            noCompare: true,
            label: 'AR landfall probability',
            models: ['gefs', 'eps', 'diff'],
            title: m => m === 'diff' ? 'AR landfall probability: ECMWF ENS minus GEFS' : `${modelName(m)} AR landfall probability`,
            build: m => ({ gefs: landfall('GEFS_50', 6), eps: landfall('ECMWF_ENS', 12), diff: landfall('ECMWF_ENS-GEFS_50', 12) })[m],
            info: Object.assign({
                what: 'An ensemble forecast of atmospheric rivers reaching the West Coast: the probability that IVT exceeds 250 kg/m/s, by latitude along the coast and by time over the next 16 days. The third option shows how the European and American ensembles differ.',
                how: 'In our region, storms originate in the Pacific and travel from the west towards the coast. Treat this plot like you are looking at storms approaching the West Coast. Find the latitude band for Washington (about 46&ndash;49&deg;N) and read across from right to left (time axis). Look for whenever the probability rises. High probability means most ensemble members bring an atmospheric river there at that time. In the difference view, strong colors mean the two ensembles disagree.',
            }, SRC_CW3E),
        },
        plume: {
            label: 'AR outlook (ensemble)',
            models: ['gefs'],
            title: () => 'Ensemble AR outlook: GEFS and ECMWF IVT plumes, 10 days',
            build: () => ({
                hours: [null], runs: runs(12, 8), runExact: true,
                urlFor: r => `${CW3E}/ivt_ensembleplumes/v1/GEFS_50_ECMWF_ENS/${PLUME.point}/${ymdh(r)}/1/ivt_ensembleplumes__v1__GEFS_50_ECMWF_ENS__${PLUME.point}__${ymdh(r)}__1__F${PLUME.hours}.png`,
                fallbackUrl: CW3E_HOME,
            }),
            info: Object.assign({
                what: 'IVT plumes out to 10 days for a point on the coast off Washington (47.0N, 124.0W) from the GEFS and ECMWF ensembles together, so you can compare how strong and how well-timed an atmospheric river is across models.',
                how: 'Each line is an ensemble member. Look for when the plumes peak and how far apart the models are. Tight bunching means high confidence in timing and strength.',
            }, SRC_CW3E),
        },
        sst: {
            noCompare: true,
            label: 'North Pacific SST anomaly',
            models: ['oisst'],
            title: () => 'North Pacific sea surface temperature anomaly, Japan to the Washington coast',
            build: () => sstView(),
            info: {
                what: 'How much warmer or colder than the 1991&ndash;2020 average the surface of the North Pacific is, from NOAA&rsquo;s daily optimum interpolation SST analysis (OISST v2.1, 0.25&deg; grid). It covers the whole basin from Japan to the Washington coast, with a map every few days over the past two months, ending with the latest day. Grey is land or missing data.',
                how: 'The ocean sets the temperature of the air that crosses it, so look at the water under the storm track. Warm water in the Gulf of Alaska and off the Northwest coast favors milder, higher snow-level storms; cold water favors colder air and lower snow levels. A big warm patch in the central Pacific near 40&deg;N (a marine heat wave) tends to go with a ridge aloft there. Step through the maps to see whether the pattern is growing or fading. It changes slowly, so read it as background for the season, not the next storm.',
                source: 'NOAA NCEI OISST v2.1', sourceUrl: 'https://www.ncei.noaa.gov/products/optimum-interpolation-sst',
            },
        },
        utah: {
            label: 'Utah synoptic panels',
            models: ['gfs', 'hres', 'aifs'],
            title: m => `${modelName(m)} Synoptic Panels`,
            build: m => ({
                gfs: utah('gfs0p25', 'GFSSY_WS', 6),
                hres: utah('hres', 'HRESSY_WS', 12),
                aifs: utah('aifs', 'AIFSSY_WS', 6),
            })[m],
            info: {
                what: 'A four-panel synoptic overview from the University of Utah: 500 mb heights and vorticity, sea level pressure and precipitation, 700 mb temperature and humidity, and IVT. Choose the American GFS, the European HRES, or the European AI model (AIFS).',
                how: 'Use it to see the large-scale pattern beyond the range of the other products on this page. Treat the longer range forecast with greater caution, and compare the AI model to the physics-based ones: agreement is a good sign.',
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH + '/',
            },
        },
    };

    // Side by side needs a product with a time slider and a second model to pair with
    const canCompare = st => { const p = PRODUCTS[st.product]; return !p.noCompare && p.models.length > 1 && p.build(p.models[0]).hours.length > 1; };
    const modelsOf = st => PRODUCTS[st.product].models;
    const mount = () => CMWViewer.mount(document.getElementById('viewer'), {
        selectors: [
            { key: 'product', label: 'Product', options: Object.keys(PRODUCTS).map(k => ({ value: k, label: PRODUCTS[k].label })) },
            { key: 'model', label: 'Model', options: st => modelsOf(st).map(m => ({ value: m, label: modelName(m) })) },
            { key: 'layout', label: 'Layout (testing)', options: st => canCompare(st) ? [{ value: 'single', label: 'One map' }, { value: 'compare', label: 'Side by side' }] : [{ value: 'single', label: '-' }] },
            { key: 'vs', label: 'Compare with', options: st => st.layout === 'compare' && canCompare(st) ? partners(modelsOf(st), modelsOf(st).includes(st.model) ? st.model : modelsOf(st)[0]).map(m => ({ value: m, label: modelName(m) })) : [{ value: '-', label: '-' }] },
        ],
        resolve(st) {
            const p = PRODUCTS[st.product];
            const m = p.models.includes(st.model) ? st.model : p.models[0];
            const info = typeof p.info === 'function' ? p.info(m) : p.info;
            const view = Object.assign({ title: p.title(m), info }, p.build(m));
            if (st.layout === 'compare' && canCompare(st)) {
                const opts = partners(p.models, m), m2 = opts.includes(st.vs) ? st.vs : opts[0];
                Object.assign(view, {
                    title: `${p.title(m)} vs ${modelName(m2)}`,
                    compare: [{ label: modelName(m), view: p.build(m) }, { label: modelName(m2), view: p.build(m2) }],
                });
            }
            return view;
        },
    });
    // The SST product needs its manifest; without it the rest of the page still works
    const SST_PRODUCT = PRODUCTS.sst;
    delete PRODUCTS.sst;
    const getManifest = url => fetch(url, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
    Promise.all([
        getManifest(BASE + 'data/sst/manifest.json'),
        (window.ECMWF_CHARTS_URL ? getManifest(CHARTS_URL + 'manifest.json') : Promise.resolve(null))
            .then(m => m || getManifest(CHARTS_LOCAL + 'manifest.json').then(l => { if (l) chartsBase = CHARTS_LOCAL; return l; })),
    ]).then(([m, c]) => {
        if (m && m.dates && m.dates.length) { sst = m; PRODUCTS.sst = SST_PRODUCT; }
        if (c && c.charts && c.file) charts = c;
        if (charts) addChartProducts();
        mount();
    });
}());
