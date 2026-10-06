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


    // ---- UW WRF (University of Washington Atmospheric Sciences) ----
    // Deterministic: /wrfrt/data/{YYYYMMDDHH}/images_d4/wa_{var}.{FF}.0000.gif
    // Ensemble mean: /mm5rt/ensembles/{YYYYMMDDHH}/images_d3/{var}.{FF}.mean.gif
    const UW = 'https://a.atmos.washington.edu';
    const UW_SRC = { source: 'UW Atmospheric Sciences', sourceUrl: UW + '/wrfrt/' };
    const uwDet = (v, hours, probeHour) => ({
        hours, probeHour, runs: runs(12, 6), runExact: true,
        urlFor: (r, h) => `${UW}/wrfrt/data/${ymdh(r)}/images_d4/wa_${v}.${pad(h, 2)}.0000.gif`,
        fallbackUrl: UW + '/wrfrt/',
    });
    const uwEns = (v, hours, probeHour) => ({
        hours, probeHour, runs: runs(12, 6), runExact: true,
        urlFor: (r, h) => `${UW}/mm5rt/ensembles/${ymdh(r)}/images_d3/${v}.${pad(h, 2)}.mean.gif`,
        fallbackUrl: UW + '/mm5rt/ensembles/',
    });
    const HOURLY48 = range(1, 48, 1), HOURLY_ENS = range(3, 84, 3);
    const ENS_NOTE = 'The ensemble mean averages every member, so it smooths out the extremes. Use it for the most likely pattern, and use the individual-member plume plots for the spread.';

    const UW_PRODUCTS = {
        uw_snow: {
            label: 'Snow', models: ['acc', 'p3', 'ens'],
            modelLabels: { acc: 'Accumulated (WRF)', p3: '3-hour (WRF)', ens: '24-hour (ensemble mean)' },
            title: m => ({ acc: 'UW WRF accumulated snowfall', p3: 'UW WRF 3-hour snowfall', ens: 'UW WRF ensemble mean 24-hour snowfall' })[m],
            build: m => ({ acc: uwDet('snowacc', HOURLY48, 3), p3: uwDet('snow3', range(3, 48, 3), 3), ens: uwEns('msnow24', HOURLY_ENS, 24) })[m],
            info: Object.assign({
                what: 'Snowfall from the University of Washington WRF model over Washington. The deterministic WRF (the 1.33 km domain) shows either the snow total accumulated through each forecast hour or the snow that falls in each 3-hour period. The ensemble option is the mean of the UW WRF ensemble&rsquo;s 24-hour snowfall.',
                how: 'Use the accumulated map for totals and the 3-hour map to see when the heaviest bursts hit. Compare the WRF with the ensemble mean: if a single run shows much more snow than the mean, treat it as the high end. ' + ENS_NOTE,
            }, UW_SRC),
        },
        uw_precip: {
            label: 'Total precip', models: ['det'], modelLabels: { det: 'WRF 1.33 km' },
            title: () => 'UW WRF total accumulated precipitation',
            build: () => uwDet('pcpt', HOURLY48, 3),
            info: Object.assign({
                what: 'Total accumulated precipitation (rain plus the water in snow) through each forecast hour from the UW WRF model over Washington.',
                how: 'Compare it with the snow map: where precipitation is high but snow is low, the model has rain or a high snow level. Totals are heavily shaped by terrain, so look at the Cascade crest and windward slopes.',
            }, UW_SRC),
        },
        uw_radar: {
            label: 'Radar', models: ['det'], modelLabels: { det: 'WRF 1.33 km' },
            title: () => 'UW WRF simulated radar reflectivity',
            build: () => uwDet('dbz', HOURLY48, 3),
            info: Object.assign({
                what: 'Simulated radar reflectivity from the UW WRF model: what the radar would show if the model were right.',
                how: 'Step through to see timing of bands and fronts. It is good for the shape and timing of precipitation, but individual bands will not verify exactly, so use it for the pattern.',
            }, UW_SRC),
        },
        uw_wind: {
            label: 'Wind', models: ['wssfc', 'wsmax', 'jet'],
            modelLabels: { wssfc: 'Surface wind', wsmax: 'Max wind (gusts)', jet: 'Jet level, 250 mb (ens. mean)' },
            title: m => ({ wssfc: 'UW WRF surface wind speed and direction', wsmax: 'UW WRF maximum wind', jet: 'UW WRF ensemble mean maximum wind at 250 mb' })[m],
            build: m => ({ wssfc: uwDet('wssfc', range(0, 48, 1), 0), wsmax: uwDet('wsmax', HOURLY48, 1), jet: uwEns('maxwind250', range(0, 84, 3), 0) })[m],
            info: Object.assign({
                what: 'Wind from the UW WRF model: surface wind speed and direction, the maximum (gust-type) wind, or the ensemble mean of the strongest wind at the 250 mb jet level.',
                how: 'Surface and gust maps show where the wind will be strong at ridgetop and pass level; strong ridgetop wind moves snow and affects lifts. The jet-level map shows the position of the jet stream steering the storms.',
            }, UW_SRC),
        },
        uw_t850: {
            label: '850 mb temp', models: ['det'], modelLabels: { det: 'WRF 1.33 km' },
            title: () => 'UW WRF 850 hPa temperature',
            build: () => uwDet('850t', range(0, 48, 1), 0),
            info: Object.assign({
                what: 'Temperature at 850 hPa (about 5,000 feet, near pass level in the Cascades) from the UW WRF model.',
                how: 'A 0&deg;C line near or below the Cascade crest suggests snow at pass level; warmer than about +3&deg;C usually means rain. Compare it with the CW3E 850 mb maps for the larger pattern.',
            }, UW_SRC),
        },
        uw_cloud: {
            label: 'Clouds', models: ['low', 'mid', 'high'],
            modelLabels: { low: '0-3,000 ft', mid: '3,000-10,000 ft', high: '10,000-20,000 ft' },
            title: m => ({ low: 'UW WRF ensemble mean cloud water, 0-3,000 ft', mid: 'UW WRF ensemble mean cloud water, 3,000-10,000 ft', high: 'UW WRF ensemble mean cloud water, 10,000-20,000 ft' })[m],
            build: m => ({ low: uwEns('qclst', HOURLY_ENS.concat([0]).sort((a, b) => a - b), 0), mid: uwEns('qcll', HOURLY_ENS.concat([0]).sort((a, b) => a - b), 0), high: uwEns('qclm', HOURLY_ENS.concat([0]).sort((a, b) => a - b), 0) })[m],
            info: Object.assign({
                what: 'Ensemble mean cloud water in three layers: the lowest 3,000 ft (valley fog and low stratus), 3,000 to 10,000 ft (the layer covering ski terrain), and 10,000 to 20,000 ft (higher cloud).',
                how: 'Use the middle layer to see whether the terrain will be in cloud, the low layer to judge valley fog and inversions, and the high layer to judge sunshine and sky color. ' + ENS_NOTE,
            }, UW_SRC),
        },
    };


    // ---- Lowland snow: UW SnowWatch (University of Washington Atmospheric Sciences) ----
    const SW = 'https://a.atmos.washington.edu/SNOWWATCH';
    const SW_SRC = { source: 'UW SnowWatch', sourceUrl: SW + '/' };
    const SW_STATION = 'swd2'; // observing station for the temperature plots; change here if you want another
    const hourlyObs = (path, label) => ({
        hours: [null], runs: runs(1, 12), runExact: true, runLabel: label,
        urlFor: r => `${SW}/${path(r)}`,
        fallbackUrl: SW + '/',
    });
    const LOW_PRODUCTS = {
        sw_ens: {
            label: 'Ensemble', models: ['latest'], modelLabels: { latest: 'Latest' },
            title: () => 'UW SnowWatch real-time ensemble',
            build: () => ({
                hours: [null], runs: null, runExact: false,
                latestNote: 'Always the latest. The time is printed on the figure.',
                urlFor: () => `${SW}/plots_rtens/latest.png?t=${Math.floor(Date.now() / 600e3)}`,
                fallbackUrl: SW + '/',
            }),
            info: Object.assign({
                what: 'The UW SnowWatch real-time ensemble for lowland snow around Puget Sound, from the University of Washington. It is aimed at the forecast questions that matter on a marginal day: will it snow at sea level, and how much?',
                how: 'Look at how many ensemble members bring snow and how much they disagree. Most members snowing means lowland snow is likely; a split means a marginal setup that can go either way.',
            }, SW_SRC),
        },
        sw_wrf: {
            label: 'WRF snow forecast', models: ['d4'], modelLabels: { d4: 'WRF 1.33 km' },
            title: () => 'UW WRF lowland snow forecast',
            build: () => ({
                hours: range(3, 48, 3), probeHour: 24, runs: runs(12, 6), runExact: true,
                urlFor: (r, h) => `${SW}/plots_forecasts/WRF_${ymdh(r)}_d4_f${pad(h, 3)}_Z3_SNOW3.png`,
                fallbackUrl: SW + '/',
            }),
            info: Object.assign({
                what: 'Forecast snowfall from the UW WRF model, zoomed on the lowlands of western Washington, from the SnowWatch page.',
                how: 'Step through the hours to see when and where the snow is forecast to fall at low elevation. A single model run is a single scenario: check it against the ensemble before trusting it.',
            }, SW_SRC),
        },
        sw_frz: {
            label: 'Temp and height (KSEA)', models: ['ksea'], modelLabels: { ksea: 'Sea-Tac (KSEA)' },
            title: () => 'UW SnowWatch temperature and height, Sea-Tac',
            build: () => hourlyObs(r => `plots_temp_ht/KSEA_${ymdh(r)}.png`, 'Observation time'),
            info: Object.assign({
                what: 'Temperature versus height over Sea-Tac (KSEA) from the UW SnowWatch page, updated every hour.',
                how: 'Where the temperature profile crosses freezing tells you the freezing level and how deep any cold or warm layer is. A shallow warm layer above a cold surface is the classic setup for freezing rain or sleet.',
            }, SW_SRC),
        },
        sw_obs: {
            label: 'Observed temperature', models: ['temp', 'trend'],
            modelLabels: { temp: 'Temperature', trend: '3-hour trend' },
            title: m => `UW SnowWatch ${m === 'temp' ? 'temperature' : '3-hour temperature trend'}, station ${SW_STATION.toUpperCase()}`,
            build: m => hourlyObs(r => m === 'temp' ? `plots_obs/${SW_STATION}_t_${ymdh(r)}.png` : `plots_obs/${SW_STATION}_trend3hr_${ymdh(r)}.png`, 'Observation time'),
            info: Object.assign({
                what: 'Recent observed temperature, or how much it has changed over the last 3 hours, at a lowland station from the UW SnowWatch page, updated hourly.',
                how: 'Use it to check whether the cold air a forecast needs is actually in place: a falling temperature trend while precipitation arrives is what turns rain to snow at low elevation.',
            }, SW_SRC),
        },
    };

    const GROUPS = { syn: PRODUCTS, uw: UW_PRODUCTS, low: LOW_PRODUCTS };
    const labelOf = (p, m) => (p.modelLabels || MODELS)[m];
    CMWViewer.mount(document.getElementById('viewer'), {
        selectors: [
            { key: 'src', label: 'Source', options: [{ value: 'syn', label: 'Large-scale models' }, { value: 'uw', label: 'UW WRF (Washington)' }, { value: 'low', label: 'Lowland snow' }] },
            { key: 'product', label: 'Product', options: st => Object.keys(GROUPS[st.src]).map(k => ({ value: k, label: GROUPS[st.src][k].label })) },
            { key: 'model', label: 'Model', options: st => GROUPS[st.src][st.product].models.map(m => ({ value: m, label: labelOf(GROUPS[st.src][st.product], m) })) },
        ],
        resolve(st) {
            const p = GROUPS[st.src][st.product];
            const m = p.models.includes(st.model) ? st.model : p.models[0];
            return Object.assign({ title: p.title(m), info: p.info }, p.build(m));
        },
    });
}());
