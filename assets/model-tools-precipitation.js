// Precipitation tools page: area x product catalog for assets/model-viewer.js.
(function () {
    'use strict';
    const pad = (n, w) => String(n).padStart(w, '0');
    const ymd = d => `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1, 2)}${pad(d.getUTCDate(), 2)}`;
    // 00Z runs for today and the previous days, newest first (Utah posts one folder per date)
    const utahRuns = n => {
        const base = Math.floor(Date.now() / 864e5) * 864e5;
        return Array.from({ length: n }, (_, i) => new Date(base - i * 864e5));
    };
    const CW3E = 'https://cw3e.ucsd.edu/images';

    // wwrf: West-WRF meteogram panel code; utah: Utah ensemble point code;
    // basins: CW3E watershed freezing-level plots (HUC8 id).
    const AREAS = {
        'mt-baker': { label: 'Mt. Baker (Heather Meadows)', wwrf: 'WA543', utah: 'MTB42', basins: [{ id: '17110005', label: 'Upper Skagit' }] },
        'stevens': { label: 'Stevens Pass', wwrf: 'US2', utah: 'TSTEV', basins: [{ id: '17110009', label: 'Skykomish (west side)' }, { id: '17020011', label: 'Wenatchee (east side)' }] },
        'snoqualmie': { label: 'Snoqualmie Pass', wwrf: 'I90', utah: 'SNO30', basins: [{ id: '17110010', label: 'Snoqualmie (west side)' }, { id: '17030001', label: 'Upper Yakima (east side)' }] },
        'blewett': { label: 'Blewett Pass', wwrf: 'US97', utah: 'MISR', basins: [{ id: '17020011', label: 'Wenatchee' }] },
        'crystal': { label: 'Crystal Mountain', wwrf: 'MRNP', utah: 'CMT', basins: [{ id: '17110014', label: 'Puyallup' }] },
        'paradise': { label: 'Paradise (Mt. Rainier)', wwrf: 'MRNP', utah: 'PVC54', basins: [{ id: '17110015', label: 'Nisqually' }] },
        'white': { label: 'White Pass', wwrf: 'US12', utah: 'WPS45', basins: [{ id: '17080004', label: 'Upper Cowlitz' }] },
        'washington': { label: 'Washington Pass', wwrf: 'WA20', utah: 'WAP55', basins: [{ id: '17020009', label: 'Lake Chelan (west side)' }, { id: '17020008', label: 'Methow (east side)' }] },
    };

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
                runs: utahRuns(3), runExact: true,
                urlFor: r => `https://weather.utah.edu/${ymd(r)}/images/models/ensgefsds/ENSGEFSDSPL_${a.utah}${ymd(r)}00F240.png`,
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
                runs: utahRuns(3), runExact: true,
                urlFor: r => `https://weather.utah.edu/${ymd(r)}/images/models/rrfsqsf/RRFSPL_${a.utah}${ymd(r)}00F060.png`,
                fallbackUrl: UTAH,
            }),
            info: {
                what: 'Accumulated snow and precipitation for this area from the Rapid Refresh Forecast System (RRFS) ensemble, NOAA&rsquo;s next-generation convection-allowing ensemble. It runs out 60 hours at 3 km grid spacing, rerun every 6 hours. Plots are hosted by the University of Utah.',
                how: `${ENSEMBLE_HOW} The bottom-left panel shows the 0.5&deg;C wet-bulb temperature level, which roughly tracks the rain/snow line.`,
                source: 'University of Utah Atmospheric Sciences', sourceUrl: UTAH,
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

    CMWViewer.mount(document.getElementById('viewer'), {
        selectors: [
            { key: 'area', label: 'Area', select: true, alwaysShow: true, options: Object.keys(AREAS).map(k => ({ value: k, label: AREAS[k].label })) },
            { key: 'product', label: 'Product', options: Object.keys(PRODUCTS).map(k => ({ value: k, label: PRODUCTS[k].label })) },
            { key: 'basin', label: 'Watershed', options: st => st.product === 'frz' ? AREAS[st.area].basins.map(b => ({ value: b.id, label: b.label })) : [{ value: '-', label: '-' }] },
            { key: 'model', label: 'Model', options: st => st.product === 'frz' ? Object.keys(PRODUCTS.frz.models).map(m => ({ value: m, label: PRODUCTS.frz.models[m] })) : [{ value: '-', label: '-' }] },
        ],
        resolve(st) {
            const a = AREAS[st.area], p = PRODUCTS[st.product];
            const info = typeof p.info === 'function' ? p.info(st) : p.info;
            return Object.assign({ hours: [null], runs: null, runExact: false, title: p.title(a, st), info,
                latestNote: 'Always the most recent run. The run and valid times are printed on the figure, in Z (UTC).' }, p.build(a, st));
        },
    });
}());
