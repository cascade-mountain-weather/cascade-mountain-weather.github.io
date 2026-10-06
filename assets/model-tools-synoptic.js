// Synoptic tools page: product catalog for assets/model-viewer.js.
// Every image URL carries its model run (YYYYMMDDHH), so run times are exact. The viewer tries
// the newest candidate run first and falls back to earlier ones; frames a source does not have
// are skipped. To fix a broken link, edit the url builders below.
(function () {
    'use strict';
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

    const CW3E = 'https://cw3e.ucsd.edu/images';
    const UTAH = 'https://weather.utah.edu';
    const CW3E_HOME = 'https://cw3e.ucsd.edu/';
    const SRC_CW3E = { source: 'CW3E, UC San Diego', sourceUrl: CW3E_HOME };

    // CW3E map products: /{prod}/v1/{model}/{region}/{run}/1/{prod}__v1__{model}__{region}__{run}__1__F###.png
    function cw3eMap(prod, model, region, cycleH, hours, probeHour) {
        return {
            hours, probeHour, runs: runs(cycleH, 6), runExact: true,
            urlFor: (r, h) => `${CW3E}/${prod}/v1/${model}/${region}/${ymdh(r)}/1/${prod}__v1__${model}__${region}__${ymdh(r)}__1__F${pad(h, 3)}.png`,
            fallbackUrl: CW3E_HOME,
        };
    }
    // AR landfall tool: one image per run covering the whole forecast (F384)
    function landfall(model, cycleH) {
        return {
            hours: [null], runs: runs(cycleH, 6), runExact: true,
            urlFor: r => `${CW3E}/landfalltool_ivt250_probability/v1/${model}/coast/${ymdh(r)}/1/landfalltool_ivt250_probability__v1__${model}__coast__${ymdh(r)}__1__F384.png`,
            fallbackUrl: CW3E_HOME,
        };
    }
    // Utah synoptic panels: /{YYYYMMDD}/images/models/{dir}/{prefix}{YYYYMMDDHH}F###.png
    function utah(dir, prefix, cycleH) {
        return {
            hours: range(0, 240, 6), runs: runs(cycleH, 6), runExact: true,
            urlFor: (r, h) => `${UTAH}/${ymd(r)}/images/models/${dir}/${prefix}${ymdh(r)}F${pad(h, 3)}.png`,
            fallbackUrl: UTAH + '/',
        };
    }

    // Plume location for the ensemble AR outlook (latitude, longitude in degrees east)
    const PLUME = { lat: '47.0', lon: '236.0' };

    const MODELS = {
        gfs: 'GFS', ecmwf: 'ECMWF HRES', aifs: 'ECMWF AIFS (AI)', hres: 'ECMWF HRES',
        gefs: 'GEFS', eps: 'ECMWF ENS', diff: 'ECMWF ENS minus GEFS',
    };
    const modelName = m => MODELS[m];

    const PRODUCTS = {
        ivt: {
            label: 'Moisture (IVT)',
            models: ['gfs', 'ecmwf'],
            title: m => `${modelName(m)} Integrated Vapor Transport`,
            build: m => m === 'gfs'
                ? cw3eMap('ivt_map', 'GFS_25', 'NEPac', 6, range(12, 144, 6), 12)
                : cw3eMap('ivt_map', 'ECMWF_HRes', 'NEPac', 12, range(12, 144, 6), 12),
            info: Object.assign({
                what: 'Integrated vapor transport (IVT) is the total water vapor being carried through the air column, in kg/m/s. It is the standard way to spot atmospheric rivers: long, narrow corridors of IVT aimed at the coast. Values above about 250 mean an atmospheric river; above 500 is strong.',
                how: 'Watch where the plume makes landfall as you step forward. A plume aimed at Washington, especially with high IVT (orange/red), means heavy mountain precipitation. Compare GFS and ECMWF: if they agree on timing and landfall latitude, confidence is higher.',
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
                how: 'A 0&deg;C line near or below the Cascade crest suggests snow levels around pass level; warmer than about +3&deg;C usually means rain at the passes. Compare models: a few degrees of disagreement here is the difference between rain and snow at the passes.',
            }, SRC_CW3E),
        },
        arlt: {
            label: 'AR landfall probability',
            models: ['gefs', 'eps', 'diff'],
            title: m => m === 'diff' ? 'AR landfall probability: ECMWF ENS minus GEFS' : `${modelName(m)} AR landfall probability`,
            build: m => ({ gefs: landfall('GEFS_50', 6), eps: landfall('ECMWF_ENS', 12), diff: landfall('ECMWF_ENS-GEFS_50', 12) })[m],
            info: Object.assign({
                what: 'An ensemble forecast of atmospheric rivers reaching the West Coast: the probability that IVT exceeds 250 kg/m/s, by latitude along the coast and by time over the next 16 days. The third option shows how the European and American ensembles differ.',
                how: 'Find the latitude band for Washington (about 46&ndash;49&deg;N) and read across for when the probability rises. High probability means most ensemble members bring an atmospheric river there at that time. In the difference view, strong colors mean the two ensembles disagree.',
            }, SRC_CW3E),
        },
        plume: {
            label: 'AR outlook (ensemble)',
            models: ['gefs'],
            title: () => 'Ensemble AR outlook: GEFS, ECMWF and West-WRF IVT plumes',
            build: () => ({
                hours: [null], runs: null, runExact: false,
                latestNote: 'Always the most recent run. The run time is printed on the figure, in Z (UTC).',
                urlFor: () => `${CW3E}/wwrf/ensemble/IVTPlumes/GEFS_ECMWF_West-WRF_IVTPlume_7_coast_${PLUME.lat}_${PLUME.lon}.png?t=${Math.floor(Date.now() / 3600e3)}`,
                extraImg: { url: `${CW3E}/gefs/images/Plume_maps/Plume_maps_coast_${PLUME.lat}_${PLUME.lon}.png?t=${Math.floor(Date.now() / 3600e3)}`, caption: 'Location of the point shown in the plume plot.' },
                fallbackUrl: CW3E_HOME,
            }),
            info: Object.assign({
                what: 'IVT plumes for a point on the coast off Washington from the GEFS, ECMWF and West-WRF ensembles together, so you can compare how strong and how well-timed an atmospheric river is across models. The small map shows the point being plotted.',
                how: 'Each line is an ensemble member. Look for when the plumes peak and how far apart the models are. Tight bunching means high confidence in timing and strength.',
            }, SRC_CW3E),
        },
        utah: {
            label: 'Utah synoptic panels',
            models: ['gfs', 'hres', 'aifs'],
            title: m => `${modelName(m)} Synoptic Panels`,
            build: m => ({
                gfs: utah('gfs0p25', 'GFSSY_WS', 6),
                hres: utah('hresext', 'HRESSY_WS', 12),
                aifs: utah('aifs', 'AIFSSY_WS', 6),
            })[m],
            info: {
                what: 'A four-panel synoptic overview from the University of Utah: 500 mb heights and vorticity, sea level pressure and precipitation, 700 mb temperature and humidity, and IVT. Choose the American GFS, the European HRES, or the European AI model (AIFS).',
                how: 'Use it to see the large-scale pattern beyond the range of the other products on this page. Treat days 7&ndash;10 as a trend, not a forecast, and compare the AI model to the physics-based ones: agreement is a good sign.',
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH + '/',
            },
        },
    };

    CMWViewer.mount(document.getElementById('viewer'), {
        selectors: [
            { key: 'product', label: 'Product', options: Object.keys(PRODUCTS).map(k => ({ value: k, label: PRODUCTS[k].label })) },
            { key: 'model', label: 'Model', options: st => PRODUCTS[st.product].models.map(m => ({ value: m, label: modelName(m) })) },
        ],
        resolve(st) {
            const p = PRODUCTS[st.product];
            const m = p.models.includes(st.model) ? st.model : p.models[0];
            return Object.assign({ title: p.title(m), info: p.info }, p.build(m));
        },
    });
}());
