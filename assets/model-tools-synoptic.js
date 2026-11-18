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

    // WeatherNext 3 maps from AI Weather Guy: {path}/frames/{field}/f###.jpg?t=<run ISO>|<style>. The server always sends its newest
    // run for any `t` and caches the answer for a year, so `t` must be a run that is already out: never ask for one that is not,
    // or the old frames get cached under the new key. Runs come every 12 h (00Z, 12Z) and the 12Z maps were last modified about
    // 7 h after the run time, so a run is only offered WN_DELAY_H hours after its run time. If the cycle ever changes, edit here.
    const WN = 'https://maps.ai-weather-guy.com';
    const WN_DELAY_H = 9;
    const WN_HOME = 'https://maps.ai-weather-guy.com/';
    function wnRuns() {
        const ready = Date.now() - WN_DELAY_H * 3600e3, step = 12 * 3600e3, base = Math.floor(ready / step) * step;
        return [new Date(base)];
    }
    function wn3(field, style, region, hours, probeHour) {
        return {
            hours, probeHour, runs: wnRuns(), runExact: true,
            urlFor: (r, h) => `${WN}${region || ''}/frames/${field}/f${pad(h, 3)}.jpg?t=${encodeURIComponent(r.toISOString().replace('.000Z', 'Z'))}${encodeURIComponent('|' + style)}`,
            fallbackUrl: WN_HOME,
        };
    }
    const WN_HOURS = range(6, 360, 6);
    const SRC_WN = { source: 'AI Weather Guy, WeatherNext 3', sourceUrl: WN_HOME };

    // UW WRF 4 km (d3) 850 hPa temperature: /wrfrt/data/{YYYYMMDDHH}/images_d3/wa_850t.##.0000.gif, hourly to 120 h, runs every 12 h
    const UW = 'https://a.atmos.washington.edu/wrfrt/data';
    function uwT850() {
        return {
            hours: range(0, 120, 3), probeHour: 3, runs: runs(12, 6), runExact: true,
            urlFor: (r, h) => `${UW}/${ymdh(r)}/images_d3/wa_850t.${pad(h, 2)}.0000.gif`,
            fallbackUrl: 'https://a.atmos.washington.edu/wrfrt/',
        };
    }

    // UW WRF 10 m wind maps (ww_ files over Washington): hourly, 120 h on the 4 km domain (d3), 72 h on the 1.33 km nest (d4), speeds in knots
    function uwWind(v, domain) {
        return {
            hours: domain === 'd4' ? range(1, 72, 1) : range(1, 120, 1), probeHour: 3, runs: runs(6, 8), runExact: true,
            urlFor: (r, h) => `${UW}/${ymdh(r)}/images_${domain}/ww_${v}.${pad(h, 2)}.0000.gif`,
            fallbackUrl: 'https://a.atmos.washington.edu/wrfrt/',
        };
    }
    const SRC_UW = { source: 'University of Washington Atmospheric Sciences WRF', sourceUrl: 'https://a.atmos.washington.edu/wrfrt/' };
    const uwWindProduct = (v, label, title, what, how) => ({
        label: 'UW WRF ' + label,
        models: ['uw4', 'uw133'],
        title: m => `${title} (${m === 'uw133' ? '1.33 km' : '4 km'})`,
        build: m => uwWind(v, m === 'uw133' ? 'd4' : 'd3'),
        info: Object.assign({ what, how }, SRC_UW),
    });

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

    // The product list is grouped by the main field each product shows, in this order; the chips carry the group names.
    const GROUPS = [
        ['Synoptic overview (University of Utah)', ['utah']],
        ['Upper level products', ['z500', 'trop']],
        ['Mid and surface level products', ['temp850', 'mslp', 'uw_wind', 'uw_gust', 'uw_gustmax', 'sst']],
        ['Moisture and atmospheric rivers', ['ivt', 'arlt', 'plume']],
    ];
    const groupOf = k => { const g = GROUPS.find(x => x[1].includes(k)); return g ? g[0] : 'Other'; };
    function organize() {
        const ordered = [];
        GROUPS.forEach(([, keys]) => keys.forEach(k => { if (PRODUCTS[k]) ordered.push(k); }));
        Object.keys(PRODUCTS).forEach(k => { if (!ordered.includes(k)) ordered.push(k); });
        const copy = Object.assign({}, PRODUCTS);
        Object.keys(PRODUCTS).forEach(k => delete PRODUCTS[k]);
        ordered.forEach(k => { PRODUCTS[k] = copy[k]; });
    }

    const MODELS = {
        oisst: 'NOAA OISST',
        wn3: 'WeatherNext 3 (AI ensemble)', wn3sd: 'WeatherNext 3 spread (std. dev.)', uw4: 'UW WRF 4 km (120 h)', uw133: 'UW WRF 1.33 km (72 h)',
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
        trop: {
            label: '2 PVU (tropopause)',
            models: ['wn3'],
            title: () => 'WeatherNext 3 dynamic tropopause (2 PVU), out to 15 days',
            build: () => wn3('trop', 'trop|fill|corner|smooth', '', WN_HOURS, 6),
            info: Object.assign({
                what: 'The 2 PVU surface is the approximate level of the dynamic tropopause, the boundary between the lower atmosphere and the stratosphere. Troughs show up as places where it dips low (cold, low-pressure air aloft seeps into the troposphere) and ridges where it bulges high. Forecast is from WeatherNext 3, an AI model, every 6 hours out to 15 days. Produced by <a href="https://ai-weather-guy.com" target="_blank" rel="noopener noreferrer">ai-weather-guy.com</a>.',
                how: 'Follow the dips and rises: a deep dip usually means a stronger system. Compare the pattern to the 500 hPa height and spread maps. Beyond about a week, treat the details as a pattern hint only.',
            }, SRC_WN),
        },
        z500: {
            label: '500 mb height and spread',
            models: ['wn3', 'wn3sd'],
            title: m => m === 'wn3sd' ? 'WeatherNext 3 500 hPa height: ensemble spread (standard deviation)' : 'WeatherNext 3 500 hPa height',
            build: m => m === 'wn3sd' ? wn3('z500sd', 'fill|corner|smooth', '', WN_HOURS, 6) : wn3('z500', 'hgt|fill|corner|smooth', '', WN_HOURS, 6),
            info: m => Object.assign(m === 'wn3sd' ? {
                what: 'How much the ensemble members disagree about the 500 hPa height (about 18,000 ft), as a standard deviation. Small values mean the members agree on the pattern; large values mean they do not.',
                how: 'Use it as a confidence map. High spread means the storm track a few days later is uncertain, so expect the forecast to change. Low spread means the pattern is well established. Try Side by side with the height map. Produced by <a href="https://ai-weather-guy.com" target="_blank" rel="noopener noreferrer">ai-weather-guy.com</a>.',
            } : {
                what: 'The height of the 500 hPa surface (about 18,000 ft), the standard way to see troughs and ridges steering storms. Low heights are troughs, high heights are ridges. From WeatherNext 3, an AI model, every 6 hours out to 15 days. Produced by <a href="https://ai-weather-guy.com" target="_blank" rel="noopener noreferrer">ai-weather-guy.com</a>.',
                how: 'This is a standard level for analyzing atmospheric flows because the ground surface has no influence on here. Check the spread map (standard deviation) to see how much to trust the pattern at that time. More color means more uncertainty.',
            }, SRC_WN), 
        },
        mslp: {
            label: 'Surface pressure (spaghetti)',
            models: ['wn3'],
            title: () => 'WeatherNext 3 sea level pressure spaghetti plot',
            build: () => wn3('mslp', 'mslp3|corner|smooth', '', WN_HOURS, 6),
            info: Object.assign({
                what: 'Selected sea level pressure contours drawn for every ensemble member at once (a spaghetti plot). Each line is one member&rsquo;s version of the same pressure contour. From WeatherNext 3, an AI model, every 6 hours out to 15 days. Produced by <a href="https://ai-weather-guy.com" target="_blank" rel="noopener noreferrer">ai-weather-guy.com</a>.',
                how: 'Where the lines bunch together the members agree on where a surface low will be; when they are jumbled, there is model disagreement. Some frames may be missing; the viewer skips them.',
            }, SRC_WN),
        },
        temp850: {
            label: '850 mb temperature',
            models: ['wn3', 'uw4', 'gfs', 'ecmwf'],
            title: m => m === 'wn3' ? 'WeatherNext 3 850 hPa Temperature (Pacific Northwest)' : `${modelName(m)} 850 hPa Temperature`,
            build: m => m === 'wn3' ? wn3('t850', 'wb|fill|corner|smooth', '/pnw', WN_HOURS, 6)
                : m === 'uw4' ? uwT850()
                : m === 'gfs'
                    ? cw3eMap('850hpa_temperature_map', 'GFS_25', 'NEPac', 6, range(0, 240, 6), 0)
                    : cw3eMap('850hpa_temperature_map', 'ECMWF_HRes', 'NEPac', 12, range(0, 240, 3), 0),
            info: m => Object.assign({
                what: 'This map shows the temperature at 850 hPa (about 5,000 feet). Because most of our storms come from the ocean, this level provides a good indication of whether cold/warm air will move into the mountains.'
                    + (m === 'wn3' ? ' This one is the WeatherNext 3 AI model zoomed on the Pacific Northwest, out to 15 days.' : m === 'uw4' ? ' This one is the UW WRF at 4 km, out to 5 days, covering Washington.' : ''),
                how: 'A 0&deg;C line near or below the Cascade crest suggests snow levels may be around pass level. Compare models: a few degrees of disagreement here is the difference between rain and snow.',
            }, m === 'wn3' ? SRC_WN : m === 'uw4' ? { source: 'University of Washington Atmospheric Sciences WRF', sourceUrl: 'https://a.atmos.washington.edu/wrfrt/' } : SRC_CW3E),
        },
        uw_wind: uwWindProduct('wssfc', 'UW WRF wind speed', 'UW WRF wind speed',
            'Wind speed at 10 m (about 33 ft) above the ground, shaded in knots (1 knot = 1.15 mph), with wind barbs (a full barb is 10 knots) and sea level pressure contours, from the University of Washington WRF.',
            'Look for the tight pressure gradients (contours packed together) and where the shading goes above 25 to 30 knots: those are the windy corridors, usually the coast, the Strait of Juan de Fuca, the Cascade Crest and the passes.'),
        uw_gust: uwWindProduct('wgsfc', 'wind gusts', 'UW WRF wind gusts',
            'The forecast 10 m wind gust at each hour, shaded in knots (1 knot = 1.15 mph), with wind barbs and sea level pressure contours, from the University of Washington WRF over Washington.',
            'Higher gust potential indicates greater chance for snow transport, visibility issues, and wind holds at resorts. Above about 40 knots (46 mph) is damaging. This is the maximum estimated gust in one hour, not the strongest gust in a forecast period (see the maximum gust product).'),
        uw_gustmax: uwWindProduct('wgmax', 'maximum accumulated wind gust', 'UW WRF maximum accumulated wind gust',
            'The strongest 10 m wind gust the model produces at each point from the start of the run through the forecast hour you pick, shaded in knots (1 knot = 1.15 mph), from the University of Washington WRF.',
            'Accumulated maximum gusts are useful for seeing when and where the strongest gusts will be. If values no longer increase, the maximum gust at that point has passed.'),
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
                what: 'How much warmer or colder than the 1991&ndash;2020 average the surface of the North Pacific is, from NOAA&rsquo;s daily optimum interpolation SST analysis (OISST v2.1, 0.25&deg; grid). It covers the whole Northern Pacific from Japan to the Washington coast, with a map every few days over the past two months, ending with the latest day. Grey is land or missing data.',
                how: 'The ocean fuels the storms we get, so look at the anomalies in the Gulf of Alaska and Central North Pacific. Step through the maps to see whether the pattern is growing or fading. It changes slowly, so read it as background for the season, not the next storm.',
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
            { key: 'product', label: 'Product', options: Object.keys(PRODUCTS).map(k => ({ value: k, label: PRODUCTS[k].label, group: groupOf(k) })) },
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
    getManifest(BASE + 'data/sst/manifest.json').then(m => {
        if (m && m.dates && m.dates.length) { sst = m; PRODUCTS.sst = SST_PRODUCT; }
        organize();
        mount();
    });
}());
