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
    let plumeData = null; // assets/data/plume_live.json (NBM, HRRR, RRFS, HRDPS on shared windows), written by scripts/plume_live.py
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
        hours, runs: utahRuns(12), runExact: true,
        urlFor: (r, h) => `https://weather.utah.edu/${ymd(r)}/images/models/${dir}/${prefix}_NW${ymdh(r)}F${pad(h, 3)}.png`,
        fallbackUrl: 'https://weather.utah.edu/',
    });
    const CW3E = 'https://cw3e-sites.ucsd.edu/images';
    const CW3E_MAIN = 'https://cw3e.ucsd.edu/images';

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
        'crystal': { label: 'Crystal Mountain', uw: 'pvc55', utah: 'CMT', basins: [{ id: '17110014', label: 'Puyallup' }] },
        'paradise': { label: 'Paradise (Mt. Rainier)', uw: 'pvc55', wwrf: 'MRNP', utah: 'PVC54', basins: [{ id: '17110015', label: 'Nisqually' }] },
        'mt-hood': { label: 'Mt. Hood (Timberline)', uw: 'heheb', utah: 'TIM59', basins: [{ id: '17070105', label: 'Hood River' }] },
        'white': { label: 'White Pass', uw: 'rimrk', wwrf: 'US12', utah: 'WPS45', basins: [{ id: '17080004', label: 'Upper Cowlitz' }] },
        'washington': { label: 'Washington Pass', uw: 'mtwpm', wwrf: 'WA20', utah: 'WAP55', basins: [{ id: '17020009', label: 'Lake Chelan (west side)' }, { id: '17020008', label: 'Methow (east side)' }] },
    };


    // ---- NBM snowfall plume, drawn as an SVG image so it behaves like the other figures ----
    const NBM_SITE = { 'mt-baker': 'Mt. Baker', stevens: 'Stevens Pass', snoqualmie: 'Snoqualmie Pass', blewett: 'Blewett Pass',
        crystal: 'Crystal', paradise: 'Paradise', white: 'White Pass', washington: 'Washington Pass',
        hurricane: 'Hurricane Ridge', winthrop: 'Winthrop', 'mt-hood': 'Mt. Hood' };
    const num = (v, d) => (v == null ? '\u2013' : (+v).toFixed(d == null ? 1 : d));

    // The same plume chart the forecast posts use (assets/post-plume-map.js), for one area, as an SVG image.
    function plumeChart(areaId, product) {
        const out = window.CMWPlume && plumeData && window.CMWPlume.chartSvg(plumeData, NBM_SITE[areaId], product);
        return out ? 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(out.svg) : '';
    }
    const plumeInfo = what => ({
        what: `The forecast ${what} for this area from four models on one set of 6-hour windows for the next four forecast days: the National Blend of Models (bars are the median, whiskers the 25th to 75th percentile), HRRR, RRFS and HRDPS (dots). The lines below the bars are the running total.`,
        how: 'Where the dots and bars line up, the models agree. A dot far from the NBM range means one model is an outlier. HRRR and HRDPS only run 48 hours, so their dots stop early. HRDPS snowfall assumes a 10:1 ratio and values are at the nearest grid point, not corrected for elevation. This is the same plot used in the forecast posts, but live.',
        source: 'NBM, HRRR, RRFS and HRDPS, via Herbie', sourceUrl: 'https://www.weather.gov/mdl/nbm_home',
    });

    function cloudChart(areaId) {
        const svg = window.CMWCloud && window.CMWCloud.chartSvg(nbmData, NBM_SITE[areaId]);
        return svg ? 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg) : null;
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
    // ---- CW3E West-WRF 3 km snowfall maps (West Coast): runs at 00Z and 12Z, forecast hours every 6 h out to 120 ----
    // /images/snow_{W}h_map/{season}/WWRF_3km_{GFS|ECMWF}/WCQPF/{YYYYMMDDHH}/1/snow_{W}h_map__{season}__WWRF_3km_{M}__WCQPF__{YYYYMMDDHH}__1__F{HHH}.png
    // An accumulation window W exists only from forecast hour W on (a 72-hour total needs 72 hours of run).
    const cw3eRuns = n => {
        const step = 12 * 3600e3, base = Math.floor(Date.now() / step) * step;
        return Array.from({ length: n }, (_, i) => new Date(base - i * step));
    };
    const cw3eSeason = d => { const y = d.getUTCFullYear(), s = d.getUTCMonth() >= 6 ? y : y - 1; return `${s}-${s + 1}`; };
    // kind is 'snow' or 'qpf' (precipitation); the 72-hour precipitation total exists only from forecast hour 72 on
    const cw3eMap = (kind, model, w) => ({
        hours: range(w, 120, 6), probeHour: w, runs: cw3eRuns(8), runExact: true,
        urlFor: (r, h) => `${CW3E_MAIN}/${kind}_${w}h_map/${cw3eSeason(r)}/WWRF_3km_${model}/WCQPF/${ymdh(r)}/1/${kind}_${w}h_map__${cw3eSeason(r)}__WWRF_3km_${model}__WCQPF__${ymdh(r)}__1__F${pad(h, 3)}.png`,
        fallbackUrl: 'https://cw3e.ucsd.edu/',
    });
    const cw3eSnow = (model, w) => cw3eMap('snow', model, w);
    // /images/fzllevel_slp_10mwind_map/{season}/WWRF_3km_{GFS|ECMWF}/USWC2/{YYYYMMDDHH}/1/...__F{HHH}.png: every hour to 120 h for the ECMWF-driven run, every 6 h for the GFS-driven one
    // The 9 km run covers the Northeast Pacific out 10 days: /images/fzllevel_slp_10mwind_map/{season}/WWRF_9km_{GFS|ECMWF}/NEPac/...
    const cw3eFzl = (model, grid) => {
        const g = grid === '9km' ? { res: '9km', region: 'NEPac', last: 240 } : { res: '3km', region: 'USWC2', last: 120 };
        return {
            hours: model === 'ECMWF' ? range(0, g.last, 3) : range(0, g.last, 6), probeHour: 0, runs: cw3eRuns(8), runExact: true,
            urlFor: (r, h) => `${CW3E}/fzllevel_slp_10mwind_map/${cw3eSeason(r)}/WWRF_${g.res}_${model}/${g.region}/${ymdh(r)}/1/fzllevel_slp_10mwind_map__${cw3eSeason(r)}__WWRF_${g.res}_${model}__${g.region}__${ymdh(r)}__1__F${pad(h, 3)}.png`,
            fallbackUrl: 'https://cw3e.ucsd.edu/',
        };
    };
    // Storm-total snow plot for one point (West-WRF ensemble, 00Z run only, one image per run reaching 7 days)
    const cw3eStorm = code => ({
        hours: [null], runs: Array.from({ length: 4 }, (_, i) => new Date(Math.floor(Date.now() / 864e5) * 864e5 - i * 864e5)), runExact: true,
        urlFor: r => `${CW3E}/snow_storm_total_meteogram/${cw3eSeason(r)}/WWRF_9km_ENS/${code}/${ymdh(r)}/1/snow_storm_total_meteogram__${cw3eSeason(r)}__WWRF_9km_ENS__${code}__${ymdh(r)}__1__F168.png`,
        fallbackUrl: 'https://cw3e.ucsd.edu/west-wrf_ensemble_meteograms',
    });
    const HOURLY48 = range(1, 48, 1), HOURLY_ENS = range(3, 84, 3);
    const ENS_NOTE = 'The ensemble mean averages every member, so it smooths out the extremes. Use it for the most likely pattern, and use the individual-member plume plots for the spread.';


    // Utah-hosted maps (HRRR, RRFS, the Utah ensemble): the total accumulated since the run start, or the amount in each 1, 6 or 24-hour window.
    // File names: {HRRR48H|HRRR24H|HRRR6H|HRRR1H|RRFS60H|RRFS24H|RRFS6H|ENSGEFSDS240H|ENSGEFSDS24H|ENSGEFSDS6H}{S snow | P precipitation}_NW{YYYYMMDDHH}F###.png
    // Other maps: {HRRR|RRFS|ENSGEFSDS}{SR snow-liquid ratio | WBZ 0.5 C wet-bulb height}, HRRRPTYPE (precipitation type).
    const ACC_LABELS = { acc: 'Accumulated since the run start', h24: '24-hour total', h6: '6-hour total', h1: '1-hour total' };   // 'h6', not 6: integer keys would sort first
    const accSet = keys => Object.fromEntries(keys.map(k => [k, ACC_LABELS[k]]));
    const UTAH_FAM = {
        hrrr: { dir: 'hrrrqsf', pre: 'HRRR', win: { acc: 'HRRR48H', h24: 'HRRR24H', h6: 'HRRR6H', h1: 'HRRR1H' }, accums: accSet(['acc', 'h24', 'h6', 'h1']), hours: range(1, 48, 1), name: 'HRRR', span: '48 hours',
                blurb: 'the HRRR, NOAA&rsquo;s hourly-updated 3 km model' },
        rrfs: { dir: 'rrfsqsf', pre: 'RRFS', win: { acc: 'RRFS60H', h24: 'RRFS24H', h6: 'RRFS6H' }, accums: accSet(['acc', 'h24', 'h6']), hours: range(1, 60, 1), name: 'RRFS', span: '60 hours',
                blurb: 'the Rapid Refresh Forecast System (RRFS), NOAA&rsquo;s next-generation 3 km convection-allowing model' },
        ens: { dir: 'ensgefsds', pre: 'ENSGEFSDS', win: { acc: 'ENSGEFSDS240H', h24: 'ENSGEFSDS24H', h6: 'ENSGEFSDS6H' }, accums: accSet(['acc', 'h24', 'h6']), hours: range(6, 240, 6), name: 'Utah ensemble', span: '10 days',
               blurb: 'the University of Utah snow ensemble, which combines GEFS and ECMWF ensemble members with statistical downscaling, out to 10 days' },
    };
    const utahFam = (f, kind, accum) => utahMap(f.dir, (f.win[accum] || f.win.acc) + kind, f.hours);
    const famTitle = (f, word, accum) => `${f.name} ${word}, ${accum && accum !== 'acc' && f.win[accum] ? ACC_LABELS[accum].replace(' total', '') + ' totals' : 'accumulated through ' + f.span}`;
    const famInfo = (k, snow) => ({
        what: `Map of forecast ${snow ? 'snowfall' : 'precipitation (rain plus the water in snow)'} over the Northwest from ${UTAH_FAM[k].blurb}: either the total accumulated since the start of the run, or the amount that falls in each ${k === 'hrrr' ? '1, 6 or 24-hour' : '6 or 24-hour'} window. Plots are hosted by the University of Utah.`,
        how: (k === 'ens' ? `Use it for the longer-range pattern beyond what the HRRR and RRFS cover; totals this far out show where ${snow ? 'snow' : 'precipitation'} is favored, not a point forecast. ` : 'A single run is best in the first day or so. ')
            + 'Use the accumulated map for totals, the 24-hour map for how a storm is split across days, and the shorter windows for timing.'
            + (snow ? '' : ' Compare it with the snow map: where precipitation is high but snow is low, expect rain or a high snow level.')
            + ' Choose Side by side to put another model next to it.',
        source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
    });
    const famProduct = (k, kind, label) => ({
        cat: kind === 'S' ? 'snow' : 'precip', region: true, label, accums: UTAH_FAM[k].accums,
        title: (a, st) => famTitle(UTAH_FAM[k], kind === 'S' ? 'snowfall' : 'precipitation', st.accum),
        build: (a, st) => utahFam(UTAH_FAM[k], kind, st.accum),
        info: famInfo(k, kind === 'S'),
    });

    const PRODUCTS = {
        wwrf_snow: {
            cat: 'snow',
            needs: 'wwrf',
            label: 'Snow (West-WRF)',
            title: (a, st) => `${a.label}: West-WRF ensemble ${st.sub === 'storm' ? 'storm-total' : 'accumulated'} snow`,
            subLabel: 'Snowfall',
            subs: { period: 'Forecast total', storm: 'Storm total' },
            build: (a, st) => st.sub === 'storm' ? cw3eStorm(a.wwrf) : ({ urlFor: () => `${CW3E}/wwrf/images/ensemble/West-WRF_AccSnow_Meteogram_Panel_${a.wwrf}.png`, fallbackUrl: 'https://cw3e.ucsd.edu/west-wrf_ensemble_meteograms' }),
            info: st => st.sub === 'storm' ? {
                what: 'Storm-total snowfall for this area from the West-WRF ensemble at CW3E, UC San Diego. The top-left panel is the spread of the ensemble members (box and whiskers, with the mean as a line), the lower-left panel is the chance of reaching each snowfall total, and the right panel shows every member (ECMWF-driven members on top, GFS-driven below). It is marked experimental by CW3E, runs from the 00Z cycle only, and reaches 7 days.',
                how: 'Use it for how much a single storm could add up to, rather than the running total of the whole forecast period. Read the lower-left panel for odds (for example, the chance of at least 12 inches), and the member panel to see whether the models agree on when it falls. A wide spread means low confidence. Switch to Forecast total for the period accumulation.',
                source: 'CW3E West-WRF ensemble meteograms', sourceUrl: 'https://cw3e.ucsd.edu/west-wrf_ensemble_meteograms',
            } : {
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
            cat: 'snow',
            needs: 'utah',
            label: 'Utah 10-day ensemble',
            title: a => `${a.label}: Utah snow ensemble, 10 days`,
            build: a => ({
                runs: utahRuns(12), runExact: true,
                urlFor: r => `https://weather.utah.edu/${ymd(r)}/images/models/ensgefsds/ENSGEFSDSPL_${a.utah}${ymdh(r)}F240.png`,
                fallbackUrl: UTAH,
            }),
            info: {
                what: 'Accumulated snow and precipitation for this area from the University of Utah snow ensemble. It combines the GEFS (US) and ECMWF EPS (European) ensembles and applies statistical downscaling to bring them to the mountain.',
                how: `${ENSEMBLE_HOW} The bottom-left panel shows the 0.5&deg;C wet-bulb temperature level, which roughly tracks the rain/snow line.`,
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
            },
        },
        utah_ens_p: {
            cat: 'precip',
            needs: 'utah',
            label: 'Utah 10-day ensemble',
            title: a => `${a.label}: Utah ensemble precipitation, 10 days`,
            build: a => ({
                runs: utahRuns(12), runExact: true,
                urlFor: r => `https://weather.utah.edu/${ymd(r)}/images/models/ensgefsds/ENSGEFSDSPL_${a.utah}${ymdh(r)}F240.png`,
                fallbackUrl: UTAH,
            }),
            info: {
                what: 'The same point plot as in Snow Products: accumulated precipitation (and snow) for this area from the University of Utah snow ensemble. It combines the GEFS (US) and ECMWF EPS (European) ensembles and applies statistical downscaling to bring them to the mountain.',
                how: `${ENSEMBLE_HOW} The bottom-left panel shows the 0.5&deg;C wet-bulb temperature level, which roughly tracks the rain/snow line.`,
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
            },
        },
        rrfs: {
            cat: 'snow',
            needs: 'utah',
            label: 'RRFS 2.5-day ensemble',
            title: a => `${a.label}: RRFS snow ensemble, 2.5 days`,
            build: a => ({
                runs: utahRuns(12), runExact: true,
                urlFor: r => `https://weather.utah.edu/${ymd(r)}/images/models/rrfsqsf/RRFSPL_${a.utah}${ymdh(r)}F060.png`,
                fallbackUrl: UTAH,
            }),
            info: {
                what: 'Accumulated snow and precipitation for this area from the Rapid Refresh Forecast System (RRFS) ensemble, NOAA&rsquo;s next-generation convection-allowing ensemble. It runs out 60 hours at 3 km grid spacing, rerun every 6 hours. Plots are hosted by the University of Utah.',
                how: `${ENSEMBLE_HOW} The bottom-left panel shows the 0.5&deg;C wet-bulb temperature level, which roughly tracks the rain/snow line.`,
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
            },
        },
        hrrr: famProduct('hrrr', 'S', 'HRRR snow'),
        rrfs_map: famProduct('rrfs', 'S', 'RRFS snow'),
        utah_map: famProduct('ens', 'S', 'Utah snow ensemble'),
        hrrr_p: famProduct('hrrr', 'P', 'HRRR precipitation'),
        rrfs_p: famProduct('rrfs', 'P', 'RRFS precipitation'),
        utah_p: famProduct('ens', 'P', 'Utah precipitation ensemble'),
        uw_snow: {
            cat: 'snow',
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
        cw3e_snow: {
            cat: 'snow',
            region: true, compare: true, label: 'West-WRF 3 km snow (CW3E)',
            models: { GFS: 'GFS-driven', ECMWF: 'ECMWF-driven' },
            accums: { 6: '6 hours', 24: '24 hours', 48: '48 hours', 72: '72 hours' },
            title: (a, st) => `West-WRF 3 km snowfall, ${st.accum || 24}-hour accumulation (${st.model === 'ECMWF' ? 'ECMWF' : 'GFS'}-driven)`,
            build: (a, st) => cw3eSnow(st.model === 'ECMWF' ? 'ECMWF' : 'GFS', +st.accum || 24),
            info: {
                what: 'Maps of forecast snowfall for the whole West Coast from West-WRF, the regional model run by the Center for Western Weather and Water Extremes (CW3E) at UC San Diego at 3 km grid spacing. It is run twice a day, once driven by the GFS (American) and once by the ECMWF (European) global model, out to 5 days. You can show the snow that falls in each 6 hours, or the total over the last 24, 48 or 72 hours, ending at the forecast hour you pick. Runs from October to March.',
                how: 'The two drivers give two views of the same storm: where the GFS-driven and ECMWF-driven maps agree on the snow axis and the totals, confidence is higher, and where they differ the uncertainty is real. Compare 24, 48 and 72-hour totals to see how much of a storm total comes in the first day. The model needs a few hours after its run time to post, so the newest run may not be there yet; this page falls back to the previous run automatically.',
                source: 'CW3E West-WRF forecasts', sourceUrl: 'https://cw3e.ucsd.edu/',
            },
        },
        cw3e_qpf: {
            cat: 'precip', region: true, compare: true, label: 'West-WRF 3 km precip (CW3E)',
            models: { GFS: 'GFS-driven', ECMWF: 'ECMWF-driven' },
            accums: { 6: '6 hours', 72: '72 hours' },
            title: (a, st) => `West-WRF 3 km precipitation, ${st.accum || 6}-hour accumulation (${st.model === 'ECMWF' ? 'ECMWF' : 'GFS'}-driven)`,
            build: (a, st) => cw3eMap('qpf', st.model === 'ECMWF' ? 'ECMWF' : 'GFS', +st.accum || 6),
            info: {
                what: 'Maps of forecast precipitation (rain plus the water in snow) for the whole West Coast from West-WRF, the regional model run by the Center for Western Weather and Water Extremes (CW3E) at UC San Diego at 3 km grid spacing. It is run twice a day, once driven by the GFS (American) and once by the ECMWF (European) global model, out to 5 days. Choose the 6-hour amount for timing or the 72-hour total for the whole storm.',
                how: 'Where the GFS-driven and ECMWF-driven maps agree on where the heaviest precipitation falls, confidence is higher. Compare it with the snow map: where precipitation is heavy but snow is light, the model has rain or a high snow level. The 72-hour total is only available from forecast hour 72 on.',
                source: 'CW3E West-WRF forecasts', sourceUrl: 'https://cw3e.ucsd.edu/',
            },
        },
        uw_cloud: {
            cat: 'cloud',
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
        plume_snow: {
            cat: 'snow',
            label: 'Model plume (snow)',
            title: a => `${a.label}: snowfall plume, NBM, HRRR, RRFS and HRDPS`,
            build: (a, st) => ({
                hours: [null], runs: plumeData ? [new Date(Date.parse(plumeData.cycles.nbm))] : null, runExact: true,
                urlFor: () => plumeChart(st.area, 'snow'),
                fallbackUrl: 'https://www.weather.gov/mdl/nbm_home',
            }),
            info: plumeInfo('snowfall'),
        },
        plume_precip: {
            cat: 'precip',
            label: 'Model plume (precip)',
            title: a => `${a.label}: liquid precipitation plume, NBM, HRRR, RRFS and HRDPS`,
            build: (a, st) => ({
                hours: [null], runs: plumeData ? [new Date(Date.parse(plumeData.cycles.nbm))] : null, runExact: true,
                urlFor: () => plumeChart(st.area, 'precip'),
                fallbackUrl: 'https://www.weather.gov/mdl/nbm_home',
            }),
            info: plumeInfo('liquid precipitation'),
        },
        nbm_cloud: {
            cat: 'cloud',
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
            title: a => `${a.label}: UW WRF forecast sounding (${soundings[a.uw].name.replace(/,(WA|OR)$/, '')}, ${Math.round(soundings[a.uw].elevation_ft).toLocaleString('en-US')} ft)`,
            build: a => {
                const site = soundings[a.uw];
                return {
                    hours: site.frames.map(f => f.hour), runs: [CMWSounding.initDate(site)], runExact: true, maxWidth: 640,
                    urlFor: (r, h) => CMWSounding.skewT(site, Math.max(0, site.frames.findIndex(f => f.hour === h))),
                    fallbackUrl: 'https://a.atmos.washington.edu/mm5rt/rt/',
                };
            },
            info: a => ({
                what: `A forecast sounding from the University of Washington WRF model at ${soundings[a.uw].name.replace(/,(WA|OR)$/, '')}, the nearest UW sounding point to this area${a.uw === 'heheb' ? ' (about 27 miles south-southeast of Timberline, on the dry east side of Mt. Hood and roughly 3,000 ft lower, so read it as an analog for the freezing level and snow level, not a point forecast for the ski area; it comes from the 12 km UW WRF grid, since Oregon is outside the 4/3 km one)' : ''}: temperature (red) and dew point (green) up through the atmosphere, drawn on a skew-T. The blue line is 0&deg;C and the purple band is the dendritic growth zone, the layer between -12 and -18&deg;C where the best powder-making snow crystals grow. Dashed lines mark the freezing level and the snow level, the height where the wet-bulb temperature reaches 0&deg;C. When the surface is already below freezing, the level is below the ground and the label says so.`,
                how: 'Press play to watch the column evolve every 3 hours. Where the red and green lines touch the air is saturated (cloud or precipitation). Snow reaches the ground when the temperature below the cloud stays near or under freezing; a snow level well above the sounding point means rain there. A saturated layer (red and green lines together) inside the purple band supports the formation of fluffy dendrites. Treat one model run as a single scenario, and check it against the NBM, HRRR and ensembles.',
                source: 'University of Washington Atmospheric Sciences, PacNW WRF-GFS 4/3 km', sourceUrl: 'https://a.atmos.washington.edu/mm5rt/rt/',
            }),
        },
        uw_lvl: {
            page: 'level',
            needs: 'uw',
            label: 'UW WRF levels over time',
            title: a => `${a.label}: UW WRF freezing level, snow level and dendritic growth zone (${soundings[a.uw].name.replace(/,(WA|OR)$/, '')})`,
            build: a => {
                const site = soundings[a.uw];
                return {
                    hours: [null], runs: [CMWSounding.initDate(site)], runExact: true,
                    urlFor: () => CMWSounding.levels(site),
                    fallbackUrl: 'https://a.atmos.washington.edu/mm5rt/rt/',
                };
            },
            info: a => ({
                what: 'The freezing level (blue), the snow level (orange; the height where the wet-bulb temperature reaches 0&deg;C) and the dendritic growth zone (purple band, from its base to its top) from the UW WRF forecast soundings at the nearest UW sounding point' + (a.uw === 'heheb' ? ' (Hehe Butte, about 27 miles south-southeast of Timberline, on the dry east side of Mt. Hood and roughly 3,000 ft lower, so treat it as an analog for the levels, not a point forecast for the ski area)' : '') + ', every 3 hours for 72 hours. The growth zone is the layer between -12 and -18&deg;C, and it only makes powder where the air in it is moist, so check the sounding for saturation.',
                how: 'Compare the snow level with the elevation you plan to ski (the dashed line is the sounding point itself). A snow level that drops below your elevation is the change from rain to snow. Hollow dots are levels below the sounding point&rsquo;s ground, extended downward at 6.5&deg;C per km. A thick purple band over a snow level below your elevation is the setup for light snow, if the sounding shows the layer is saturated. One model run is one scenario.',
                source: 'University of Washington Atmospheric Sciences, PacNW WRF-GFS 4/3 km', sourceUrl: 'https://a.atmos.washington.edu/mm5rt/rt/',
            }),
        },
        cw3e_fzl: {
            page: 'level', region: true, compare: true, label: 'West-WRF freezing level (CW3E)',
            models: { ECMWF: 'ECMWF-driven', GFS: 'GFS-driven' },
            subLabel: 'Grid',
            subs: { '3km': 'US West Coast, 3 km (5 days)', '9km': 'Northeast Pacific, 9 km (10 days)' },
            title: (a, st) => `West-WRF ${st.sub === '9km' ? '9 km' : '3 km'} freezing level, sea level pressure and 10 m wind (${st.model === 'GFS' ? 'GFS' : 'ECMWF'}-driven)`,
            build: (a, st, model) => cw3eFzl(model || (st.model === 'GFS' ? 'GFS' : 'ECMWF'), st.sub),
            info: {
                what: 'Maps of the forecast freezing level, sea level pressure and 10 m wind from West-WRF, the regional model run by the Center for Western Weather and Water Extremes (CW3E) at UC San Diego. The 3 km grid covers the US West Coast out 5 days; the 9 km grid covers the Northeast Pacific out 10 days, so you can see the storms before they arrive. It is run twice a day, driven either by the ECMWF or by the GFS.',
                how: 'Step through time and watch the freezing level over the Cascades: when it falls below pass level the precipitation turns to snow. Compare the ECMWF-driven and GFS-driven runs; where they agree on the timing of the drop, confidence is higher. Try Side by side to play both at once.',
                source: 'CW3E West-WRF forecasts', sourceUrl: 'https://cw3e.ucsd.edu/',
            },
        },
        hrrr_ptype: {
            cat: 'precip', region: true, label: 'HRRR precipitation type',
            title: () => 'HRRR precipitation type',
            build: () => utahMap('hrrrqsf', 'HRRRPTYPE', range(1, 48, 1)),
            info: {
                what: 'The precipitation type the HRRR forecasts at each hour (rain, snow, freezing rain, sleet) over the Northwest, hosted by the University of Utah.',
                how: 'Use it with the snow and precipitation maps: it shows where the model has snow and where it has rain at a given hour, which is the quickest way to see the rain-snow line move. It is the model&rsquo;s own call at the surface, so mountain valleys and ridges can differ from what falls on the slopes.',
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
            },
        },
        utah_wbz: {
            page: 'level', region: true, compare: true, label: 'Wet-bulb 0.5°C height (Utah)',
            models: { hrrr: 'HRRR (48 h)', rrfs: 'RRFS (60 h)', ens: 'Utah ensemble (10 days)' },
            title: (a, st) => `${UTAH_FAM[st.model] ? UTAH_FAM[st.model].name : 'HRRR'}: height of the 0.5°C wet-bulb level above ground`,
            build: (a, st, model) => { const f = UTAH_FAM[model || st.model] || UTAH_FAM.hrrr; return utahMap(f.dir, f.pre + 'WBZ', f.hours); },
            info: {
                what: 'The height above the ground of the 0.5&deg;C wet-bulb temperature, which roughly tracks the rain-snow line, from the University of Utah&rsquo;s HRRR, RRFS and snow-ensemble maps. Low values mean the snow level is close to the ground; high values mean rain reaches high up the slopes.',
                how: 'Compare the height with the elevation of the pass or ski area above its valley: a height under a few hundred feet means snow right down to the ground, while thousands of feet means rain. Try Side by side to see how the models agree on the timing of the drop.',
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
            },
        },
        utah_slr: {
            page: 'level', region: true, compare: true, label: 'Snow-liquid ratio (Utah)',
            models: { ens: 'Utah ensemble (10 days)', hrrr: 'HRRR (48 h)', rrfs: 'RRFS (60 h)' },
            title: (a, st) => `${UTAH_FAM[st.model] ? UTAH_FAM[st.model].name : 'Utah ensemble'}: snow-to-liquid ratio`,
            build: (a, st, model) => { const f = UTAH_FAM[model || st.model] || UTAH_FAM.ens; return utahMap(f.dir, f.pre + 'SR', f.hours); },
            info: {
                what: 'Forecast snow-to-liquid ratio, the inches of snow that one inch of water makes, from the University of Utah snow ensemble, the HRRR or the RRFS. The ensemble map has four panels: the control member, the ensemble mean, the minimum and the maximum of the members. The colors are drawn only where snow is falling.',
                how: 'About 10 is typical. Lower numbers (under 8) mean wet, dense snow near freezing; higher numbers (15 or more) mean cold, dry, fluffy snow. Multiply the precipitation by the ratio to estimate snowfall, and compare the minimum and maximum panels to see how uncertain the ratio is. It pairs with the freezing level and the dendritic growth zone above.',
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
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

    // Products are split into "Precipitation Products", "Snow Products" and "Cloud Cover Products" (a Type chip before Product).
    // Two map products of the same Type (snow or precipitation) can be played side by side: the viewer keeps the forecast times both have.
    // The freezing-level page has only one kind, so its Type chip is hidden.
    const CATS = [{ value: 'precip', label: 'Precipitation Products' }, { value: 'snow', label: 'Snow Products' }, { value: 'cloud', label: 'Cloud Cover Products' }, { value: 'level', label: 'Levels' }];
    const catOf = p => p.cat || (pageOf(p) === 'level' ? 'level' : 'precip');
    const productsFor = area => Object.keys(PRODUCTS).filter(k => pageOf(PRODUCTS[k]) === PAGE && !!PRODUCTS[k].region === !!AREAS[area].region && (!PRODUCTS[k].needs || AREAS[area][PRODUCTS[k].needs]) && (!/^nbm/.test(k) || (nbmData && NBM_SITE[area] && nbmData.sites[NBM_SITE[area]] && (k !== 'nbm_cloud' || nbmData.cloud_time_utc))) && (!/^plume/.test(k) || (plumeData && window.CMWPlume && NBM_SITE[area] && plumeData.sites[NBM_SITE[area]])));
    // Links made before the split (#product=uw_cloud or nbm_cloud) pick their type.
    (() => {
        const h = new URLSearchParams(location.hash.slice(1));
        if (h.get('product') && PRODUCTS[h.get('product')] && h.get('cat') !== catOf(PRODUCTS[h.get('product')])) { h.set('cat', catOf(PRODUCTS[h.get('product')])); history.replaceState(null, '', '#' + h.toString()); }
    })();

    // Other map products of the same Type that this one can be compared with (snow with snow, precipitation with precipitation)
    const partnersOf = st => (['snow', 'precip'].includes(catOf(PRODUCTS[st.product])) && PRODUCTS[st.product].region)
        ? productsFor(st.area).filter(k => k !== st.product && PRODUCTS[k].region && catOf(PRODUCTS[k]) === catOf(PRODUCTS[st.product])) : [];
    const canCompare = st => !!PRODUCTS[st.product].compare || partnersOf(st).length > 0;
    const firstKey = o => (o ? Object.keys(o)[0] : undefined);
    // the same accumulation in the other product where it has one (6-hour is 'h6' for the Utah-hosted maps and '6' for West-WRF)
    const matchAccum = (q, want) => {
        const norm = k => String(k).replace(/^h/, '');
        return Object.keys(q.accums).find(k => norm(k) === norm(want)) || firstKey(q.accums);
    };
    const accumText = (q, ac) => (q.accums && q.accums[ac] ? ` (${q.accums[ac]})` : '');

    const mount = () => {
        CMWViewer.mount(document.getElementById('viewer'), {
            singleMaxWidth: 760,
            selectors: [
                { key: 'area', label: 'Area', select: true, alwaysShow: true, options: Object.keys(AREAS).sort((x, y) => PAGE === 'level' ? !!AREAS[x].region - !!AREAS[y].region : 0).map(k => ({ value: k, label: AREAS[k].label })) },
                { key: 'cat', label: 'Type', options: st => CATS.filter(c => productsFor(st.area).some(k => catOf(PRODUCTS[k]) === c.value)) },
                { key: 'product', label: 'Product', options: st => productsFor(st.area).filter(k => catOf(PRODUCTS[k]) === st.cat).map(k => ({ value: k, label: PRODUCTS[k].label })) },
                { key: 'basin', label: 'Watershed', options: st => st.product === 'frz' && AREAS[st.area].basins ? AREAS[st.area].basins.map(b => ({ value: b.id, label: b.label })) : [{ value: '-', label: '-' }] },
                { key: 'model', label: 'Model', options: st => PRODUCTS[st.product].models ? Object.keys(PRODUCTS[st.product].models).map(m => ({ value: m, label: PRODUCTS[st.product].models[m] })) : [{ value: '-', label: '-' }] },
                { key: 'sub', label: st => PRODUCTS[st.product].subLabel || '', options: st => PRODUCTS[st.product].subs ? Object.keys(PRODUCTS[st.product].subs).map(m => ({ value: m, label: PRODUCTS[st.product].subs[m] })) : [{ value: '-', label: '-' }] },
                { key: 'accum', label: 'Accumulation', options: st => PRODUCTS[st.product].accums ? Object.keys(PRODUCTS[st.product].accums).map(m => ({ value: m, label: PRODUCTS[st.product].accums[m] })) : [{ value: '-', label: '-' }] },
                { key: 'layout', label: 'Layout', options: st => canCompare(st) ? [{ value: 'single', label: 'One map' }, { value: 'compare', label: 'Side by side' }] : [{ value: 'single', label: '-' }] },
                { key: 'vs', label: 'Compare with', options: st => {
                    const p = PRODUCTS[st.product];
                    if (st.layout !== 'compare') return [{ value: '-', label: '-' }];
                    const own = p.compare ? Object.keys(p.models).filter(m => m !== st.model).map(m => ({ value: m, label: p.models[m] })) : [];
                    const other = partnersOf(st).map(k => ({ value: 'p:' + k, label: PRODUCTS[k].label }));
                    return own.concat(other).length ? own.concat(other) : [{ value: '-', label: '-' }];
                } },
            ],
            resolve(st) {
                const a = AREAS[st.area], p = PRODUCTS[st.product];
                const info = typeof p.info === 'function' ? p.info(st.product === 'uw_snd' || st.product === 'uw_lvl' ? a : st) : p.info;
                const view = Object.assign({ hours: [null], runs: null, runExact: false, title: p.title(a, st), info,
                    latestNote: 'Always the most recent run. The run and valid times are printed on the figure, in Z (UTC).' }, p.build(a, st));
                if (st.layout === 'compare' && st.vs && st.vs !== '-' && view.hours.length > 1) {
                    if (/^p:/.test(st.vs) && PRODUCTS[st.vs.slice(2)]) {
                        // another product of the same Type: its first model and, where it has the same accumulation, the same accumulation
                        const qk = st.vs.slice(2), q = PRODUCTS[qk];
                        const st2 = Object.assign({}, st, { product: qk, model: firstKey(q.models), sub: firstKey(q.subs),
                            accum: q.accums ? matchAccum(q, st.accum) : undefined });
                        const lab1 = (p.compare && p.models ? p.models[st.model] + ' ' : '') + p.label + accumText(p, st.accum);
                        const lab2 = (q.compare && q.models ? q.models[st2.model] + ' ' : '') + q.label + accumText(q, st2.accum);
                        view.title = `${lab1} vs ${lab2}`;
                        view.compare = [{ label: lab1, view: p.build(a, st, st.model) }, { label: lab2, view: q.build(a, st2, st2.model) }];
                    } else if (p.compare && p.models[st.vs] && st.vs !== st.model) {
                        // one view per model; for the freezing-level maps the model key is also the build argument
                        const ids = [st.model, st.vs];
                        view.title = `${p.title(a, st).replace(/ \((?:GFS|ECMWF)-driven\)$/, '')}: ${p.models[st.model]} vs ${p.models[st.vs]}`;
                        view.compare = ids.map(m => ({ label: p.models[m], view: p.build(a, Object.assign({}, st, { model: m }), m) }));
                    }
                }
                return view;
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
    Promise.all([getJson('nbm_plumes.json'), getJson('plume_live.json'), Promise.all(uwSites.map(k => CMWSounding.load(k)))])
        .then(([nbm, plume, uw]) => {
            nbmData = nbm; plumeData = plume;
            uwSites.forEach((k, i) => { if (uw[i] && uw[i].frames && uw[i].frames.length) soundings[k] = uw[i]; });
            Object.values(AREAS).forEach(a => { if (a.uw && !soundings[a.uw]) delete a.uw; });   // no data: hide the products for that area
            mount();
        });
}());
