// Lowland snow tools page: product catalog for assets/model-viewer.js (UW SnowWatch, University of Washington).
// Every image URL carries its model run or observation hour (YYYYMMDDHH). The viewer tries the newest
// candidate first and falls back to earlier ones. To fix a broken link, edit the url builders below.
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

    const SW = 'https://a.atmos.washington.edu/SNOWWATCH';
    const SW_SRC = { source: 'UW SnowWatch', sourceUrl: SW + '/' };
    // Obs plot files are named sw{domain}_...: d2 is the smaller, closer-in domain and d1 the larger one
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
        sw_trend: {
            label: 'Snow level trend (Seattle)', models: ['ksea'], modelLabels: { ksea: 'Sea-Tac (KSEA)' },
            title: () => 'UW SnowWatch Seattle freezing level and snow level trend',
            build: () => ({
                hours: [null], runs: null, runExact: false,
                latestNote: 'Always the latest. The update time is printed on the figure, in Pacific time.',
                urlFor: () => `${SW}/plots_fzlev_trend/KSEA_fzlev_trend.png?_=${Math.floor(Date.now() / 600e3)}`,
                fallbackUrl: SW + '/',
            }),
            info: Object.assign({
                what: 'The last day or so of freezing level and snow level over Seattle, from the UW SnowWatch page. The top panel shows the freezing level estimated from aircraft observations against Capitol Hill, Downtown and sea level; the bottom shows the air and road surface temperature range, with the 32&deg;F line.',
                how: 'A freezing level (red dots) that is falling toward the hills and downtown during precipitation is the signal for lowland snow. Grey marks mean there is too little aircraft data for an estimate, and a freezing level at the top of the chart (3,000 ft or higher) means rain at any low elevation.',
            }, SW_SRC),
        },
        sw_obs: {
            label: 'Observed temperature', models: ['temp_d2', 'trend_d2', 'temp_d1', 'trend_d1'],
            modelLabels: { temp_d2: 'Temperature, close-in (d2)', trend_d2: '3-hour trend, close-in (d2)', temp_d1: 'Temperature, larger area (d1)', trend_d1: '3-hour trend, larger area (d1)' },
            title: m => `UW SnowWatch ${m.startsWith('temp') ? 'temperature' : '3-hour temperature trend'}, ${m.endsWith('d2') ? 'close-in (d2)' : 'larger (d1)'} domain`,
            build: m => {
                const dom = m.slice(-2), kind = m.startsWith('temp') ? 't' : 'trend3hr';
                return hourlyObs(r => `plots_obs/sw${dom}_${kind}_${ymdh(r)}.png`, 'Observation time');
            },
            info: Object.assign({
                what: 'Recent observed temperature, or how much it has changed over the last 3 hours, from the UW SnowWatch page, updated hourly. The d2 plots cover the smaller, closer-in domain and d1 the larger one.',
                how: 'Use it to check whether the cold air a forecast needs is actually in place: a falling temperature trend while precipitation arrives is what turns rain to snow at low elevation.',
            }, SW_SRC),
        },
    };

    const PRODUCTS = LOW_PRODUCTS;
    CMWViewer.mount(document.getElementById('viewer'), {
        selectors: [
            { key: 'product', label: 'Product', options: Object.keys(PRODUCTS).map(k => ({ value: k, label: PRODUCTS[k].label })) },
            { key: 'model', label: 'Option', options: st => PRODUCTS[st.product].models.map(m => ({ value: m, label: PRODUCTS[st.product].modelLabels[m] })) },
        ],
        resolve(st) {
            const p = PRODUCTS[st.product];
            const m = p.models.includes(st.model) ? st.model : p.models[0];
            return Object.assign({ title: p.title(m), info: p.info }, p.build(m));
        },
    });
}());
