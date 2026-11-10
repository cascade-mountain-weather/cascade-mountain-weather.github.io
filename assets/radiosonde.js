// Radiosonde / Skew-T tool.
//
// Shows MetPy skew-T composites that scripts/radiosonde_skewt.py pre-renders
// (workflow observations.yml, hourly, so a cycle appears soon after each 00Z/12Z launch) from
// Iowa State's IEM RAOB feed. The page just reads assets/data/radiosonde/manifest.json
// and swaps PNGs, so there is no in-browser Python to wait for. Plotly is only
// used for the history chart.
//
// We track 4 fixed stations. Two have permanent data-availability quirks (see
// STATIONS below); the render script walks back to the newest cycles that
// actually have data, so the manifest simply lists what exists, newest first.

const IEM_RAOB_BASE = 'https://mesonet.agron.iastate.edu/json/raob.py';
const SPC_BASE = 'https://www.spc.noaa.gov/exper/archive/events';
// Set by an inline <script> in tools/radiosonde.html via Liquid, since this
// file itself isn't processed by Jekyll. Falls back to the plain root path
// (correct as long as the site's baseurl stays empty, per _config.yml).
const WRF_URL = window.RADIOSONDE_WRF_URL || '/assets/data/wrf_uil.json';
const MANIFEST_URL = window.RADIOSONDE_MANIFEST_URL || '/assets/data/radiosonde/manifest.json';
const IMAGE_BASE = MANIFEST_URL.replace(/manifest\.json$/, '');
const FORECAST_URL = window.RADIOSONDE_FORECAST_URL || '/assets/data/uw_soundings/dowlx.json';
const HISTORY_URL = window.RADIOSONDE_HISTORY_URL || '/assets/data/radiosonde_history.json';

// Unit conversions for hover text and diagnostics -- pressure is left in
// hPa in both modes since that's the universal unit for upper-air charts
// even in the US.
const UNITS = {
    cToF: c => (c * 9) / 5 + 32,
    cDeltaToF: c => (c * 9) / 5, // for temperature *differences*, no +32 offset
    mToFt: m => m * 3.28084,
    ktToMph: kt => kt * 1.15078,
};

// Only these 4 stations are tracked (per PLAN.md). Each has a short "note"
// describing real, observed quirks in how promptly its data shows up in the
// IEM feed -- discovered by probing the API directly, not guessed at.
const STATIONS = [
    {
        id: 'UIL',
        name: 'Quillayute, WA',
        lat: 47.95,
        lon: -124.56,
        country: 'US',
        note: 'NWS sounding, launched 00Z & 12Z daily. Usually appears in this feed within a few hours.',
    },
    {
        id: 'SLE',
        name: 'Salem, OR',
        lat: 44.91,
        lon: -123.00,
        country: 'US',
        note: 'NWS sounding, launched 00Z & 12Z daily. Usually appears in this feed within a few hours.',
    },
    {
        id: 'OTX',
        name: 'Spokane, WA',
        lat: 47.70,
        lon: -116.40,
        country: 'US',
        note: 'NWS sounding site, but KOTX has been absent from this near-real-time feed for an extended stretch -- a known upstream gap, not a bug in this tool.',
    },
    {
        id: 'CYZT',
        name: 'Port Hardy, BC',
        lat: 50.68,
        lon: -127.30,
        country: 'CA',
        note: 'Environment Canada sounding. This feed typically lags Canadian sites by 4-5 days, so the most recent available sounding here is usually about that old, not same-day.',
    },
];

const state = {
    station: STATIONS[0].id,
    manifestPromise: null, // cached fetch of the pre-rendered manifest
    cycles: [],            // manifest entries for the selected station, newest first
    index: 0,              // position in `cycles` currently shown
    activeRequest: 0,
    units: 'imperial',     // 'metric' | 'imperial' (feet first; the second axis shows the other) -- affects hover text and the diagnostics table
    wrfPromise: null,      // cached fetch of assets/data/wrf_uil.json (WRF-vs-Quillayute overlay + skill scores)
    wrfVar: 'freezing_level_ft',
    wrfLeads: [24, 48],
    skillVar: 'freezing_level_ft',
    skillInit: 'all',
    skillMetric: 'rmse',
    historyPromise: null,  // cached fetch of the shared history JSON (all stations)
    forecastPromise: null, // cached fetch of the UW WRF sounding forecast at Olympex DOW (the Quillayute forecast)
    historyWindow: 'around', // 'around' = 3 days back and 3 ahead, 'week', 'fortnight', 'all'
};

const els = {};

document.addEventListener('DOMContentLoaded', () => {
    Object.assign(els, {
        stationButtons: document.getElementById('station-buttons'),
        unitMetric: document.getElementById('unit-metric'),
        unitImperial: document.getElementById('unit-imperial'),
        older: document.getElementById('cycle-older'),
        newer: document.getElementById('cycle-newer'),
        cycleLabel: document.getElementById('selected-cycle'),
        status: document.getElementById('sounding-status'),
        stationNote: document.getElementById('station-note'),
        output: document.getElementById('skewt-output'),
        placeholder: document.getElementById('plot-placeholder'),
        diagnostics: document.getElementById('sounding-diagnostics'),
        meltingNote: document.getElementById('melting-note'),
        dataSource: document.getElementById('data-source-link'),
        spcSource: document.getElementById('spc-source-link'),
        historyPlot: document.getElementById('history-plot'),
        historyEmpty: document.getElementById('history-empty'),
    });

    if (!els.stationButtons || !els.output) return;

    renderStationButtons();
    initWrfControls();
    renderWrfSkill();
    els.older.addEventListener('click', () => stepCycle(-1));
    els.newer.addEventListener('click', () => stepCycle(1));
    if (els.unitMetric && els.unitImperial) {
        els.unitMetric.addEventListener('click', () => setUnits('metric'));
        els.unitImperial.addEventListener('click', () => setUnits('imperial'));
    }
    document.addEventListener('click', event => {
        document.querySelectorAll('#sounding-diagnostics .info-popup').forEach(popup => {
            if (popup.style.display === 'block' && !popup.contains(event.target) && !event.target.closest('.info-icon')) {
                popup.style.display = 'none';
            }
        });
    });

    selectStation(getStationRequestedInUrl() || state.station);
});

function setUnits(units) {
    if (state.units === units) return;
    state.units = units;
    if (els.unitMetric) els.unitMetric.setAttribute('aria-pressed', String(units === 'metric'));
    if (els.unitImperial) els.unitImperial.setAttribute('aria-pressed', String(units === 'imperial'));
    const shown = state.cycles[state.index];
    if (shown) renderDiagnostics(shown.diagnostics, state.units);
    renderHistoryChart(state.station);
    renderWrfSkill();
}

// Diagnostic info-icon popups (mirrors the showInfo/hideInfo pattern used
// on the homepage's DGZ tool-cards, scoped to .diagnostic-item instead of
// .tool-card).
function showDiagInfo(event) {
    event.stopPropagation();
    const item = event.target.closest('.diagnostic-item');
    if (!item) return;
    document.querySelectorAll('#sounding-diagnostics .info-popup').forEach(popup => {
        if (popup !== item.querySelector('.info-popup')) popup.style.display = 'none';
    });
    const popup = item.querySelector('.info-popup');
    if (popup) popup.style.display = 'block';
}

function hideDiagInfo(event) {
    event.stopPropagation();
    const popup = event.target.closest('.info-popup');
    if (popup) popup.style.display = 'none';
}

function getStationRequestedInUrl() {
    const requested = new URLSearchParams(window.location.search).get('station')?.toUpperCase();
    return STATIONS.some(s => s.id === requested) ? requested : null;
}

function getStationMeta(id) {
    return STATIONS.find(s => s.id === id);
}

function pad(value) {
    return String(value).padStart(2, '0');
}

// '202610301200' -> { timestamp, label, spcUrlStem } for the raw-data and SPC links.
function cycleLinks(timestamp) {
    const yyyy = timestamp.slice(0, 4), mm = timestamp.slice(4, 6), dd = timestamp.slice(6, 8), hh = timestamp.slice(8, 10);
    return `${SPC_BASE}/${yyyy}${mm}${dd}/soundings/${yyyy.slice(2)}${mm}${dd}${hh}_SNDG`;
}

function setStatus(message) {
    els.status.textContent = message;
}

async function fetchJson(url) {
    const separator = url.includes('?') ? '&' : '?';
    const response = await fetch(`${url}${separator}cachebust=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

function loadManifest() {
    if (!state.manifestPromise) {
        state.manifestPromise = fetchJson(MANIFEST_URL).catch(error => {
            console.error('Skew-T manifest fetch failed:', error);
            state.manifestPromise = null;
            return null;
        });
    }
    return state.manifestPromise;
}

const stationMarkers = new Map(); // station id -> Leaflet marker

function stationIcon(selected) {
    return L.divIcon({
        className: '',
        html: `<div class="radiosonde-map-pin${selected ? ' is-selected' : ''}"></div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
    });
}

function renderStationButtons() {
    if (typeof L === 'undefined') {
        els.stationButtons.textContent = 'Map failed to load.';
        return;
    }
    const map = L.map(els.stationButtons, { scrollWheelZoom: false, attributionControl: true });
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri',
        maxZoom: 10,
    }).addTo(map);

    STATIONS.forEach(station => {
        const marker = L.marker([station.lat, station.lon], {
            icon: stationIcon(station.id === state.station),
            title: `${station.id} - ${station.name}`,
            alt: `${station.id} - ${station.name}`,
        }).addTo(map);
        marker.bindTooltip(`<strong>${station.id}</strong> ${station.name}`, { direction: 'top', offset: [0, -10] });
        marker.on('click', () => selectStation(station.id));
        stationMarkers.set(station.id, marker);
    });
    map.fitBounds(L.latLngBounds(STATIONS.map(s => [s.lat, s.lon])), { padding: [24, 24] });
}

function updateStationButtonStates() {
    stationMarkers.forEach((marker, id) => marker.setIcon(stationIcon(id === state.station)));
}

async function selectStation(stationId) {
    state.station = stationId;
    const meta = getStationMeta(stationId);
    updateStationButtonStates();
    els.stationNote.textContent = meta.note;
    renderHistoryChart(stationId);
    els.older.disabled = true;
    els.newer.disabled = true;
    setStatus(`Loading the most recent ${stationId} sounding...`);
    els.placeholder.classList.add('is-visible');
    els.placeholder.textContent = `Loading the most recent ${stationId} sounding...`;
    els.output.classList.remove('is-visible');
    els.diagnostics.hidden = true;

    const requestId = ++state.activeRequest;
    const manifest = await loadManifest();
    if (requestId !== state.activeRequest) return;

    state.cycles = (manifest && manifest.stations && manifest.stations[stationId]) || [];
    state.index = 0;
    if (!state.cycles.length) {
        els.placeholder.textContent = manifest
            ? `No recent ${stationId} sounding available.`
            : 'Could not load the sounding images. Try reloading the page.';
        setStatus('Select another station.');
        els.cycleLabel.textContent = 'Cycle: unavailable';
        return;
    }
    showEntry();
}

// Older = further down the newest-first list.
function stepCycle(direction) {
    const next = state.index - direction;
    if (next < 0 || next >= state.cycles.length) return;
    state.index = next;
    showEntry();
}

function formatHeightValue(m, units) {
    if (m == null || Number.isNaN(m)) return null;
    const converted = units === 'imperial' ? UNITS.mToFt(m) : m;
    const label = units === 'imperial' ? 'ft' : 'm';
    return `${Math.round(converted).toLocaleString()} ${label}`;
}

function renderDiagnostics(values, units) {
    const formatCape = value => (value == null ? 'Unavailable' : `${value} J/kg`);
    const aglText = m => (m == null ? 'Unavailable' : `${formatHeightValue(m, units)} AGL`);
    const diagnostics = {
        snow_level: aglText(values.snow_level_m),
        snow_level_saturated: aglText(values.snow_level_saturated_m),
        freezing_level: aglText(values.freezing_level_m),
        advection: values.advection,
        dgz: values.dgz,
        mucape: values.mucape == null ? 'Unavailable' : `${formatCape(values.mucape)} · ${aglText(values.mu_height)}`,
        mlcape: formatCape(values.mlcape),
    };
    els.diagnostics.querySelectorAll('[data-diagnostic]').forEach(element => {
        element.textContent = diagnostics[element.dataset.diagnostic] || 'Unavailable';
    });
    els.diagnostics.hidden = false;

    if (els.meltingNote) {
        if (values.melting_note) {
            els.meltingNote.textContent = values.melting_note;
            els.meltingNote.hidden = false;
        } else {
            els.meltingNote.hidden = true;
        }
    }
}

function showEntry() {
    const entry = state.cycles[state.index];
    const stationId = state.station;
    const meta = getStationMeta(stationId);
    els.cycleLabel.textContent = `Cycle: ${entry.label}`;
    els.dataSource.href = `${IEM_RAOB_BASE}?ts=${entry.cycle}&station=${stationId}`;
    if (meta.country === 'US') {
        els.spcSource.href = `${cycleLinks(entry.cycle)}/${stationId}.gif`;
        els.spcSource.hidden = false;
    } else {
        els.spcSource.hidden = true;
    }

    els.older.disabled = state.index >= state.cycles.length - 1;
    els.newer.disabled = state.index <= 0;
    els.output.alt = `MetPy skew-T analysis for ${stationId} at ${entry.label} (skew-T, hodograph, wind barbs, thermal advection)`;
    els.output.src = IMAGE_BASE + entry.image;
    // the previous image stays visible until the new one has loaded, so stepping through cycles does not flash
    els.output.classList.add('is-visible');
    els.placeholder.classList.remove('is-visible');

    renderDiagnostics(entry.diagnostics, state.units);
    setStatus(`Showing ${stationId} from ${entry.label}.`);
}

// --- History trend chart (freezing level / wet-bulb zero / snow level) ----
// Fetches the small, bot-updated JSON asset that scripts/collect_radiosonde_history.py
// appends to on a schedule (see .github/workflows/observations.yml),
// mirroring the same pattern already used for the satellite looper's
// manifest.json. Cached once per page load since it covers all stations.
function loadHistory() {
    if (!state.historyPromise) {
        state.historyPromise = fetchJson(HISTORY_URL).catch(error => {
            console.error('Radiosonde history fetch failed:', error);
            return null;
        });
    }
    return state.historyPromise;
}

function buildHistoryTraces(entries, units) {
    const isImperial = units === 'imperial';
    const heightUnit = isImperial ? 'ft' : 'm';
    const conv = m => (m == null ? null : (isImperial ? UNITS.mToFt(m) : m));
    const x = entries.map(entry => entry.valid);
    const series = [
        { key: 'freezing_level_m', name: 'Freezing level', color: '#2563eb' },
        { key: 'snow_level_saturated_m', name: 'Snow level (saturated column)', color: '#f9a8d4' },
        { key: 'snow_level_m', name: 'Snow level (modeled)', color: '#db2777' },
    ];
    return series.map(series_item => ({
        x, y: entries.map(entry => conv(entry[series_item.key])),
        mode: 'lines+markers', name: series_item.name,
        line: { color: series_item.color, width: 2 }, marker: { size: 5 },
        connectgaps: false,
        hovertemplate: `%{x|%b %d %HZ}<br>${series_item.name}: %{y:.0f} ${heightUnit} AGL<extra></extra>`,
    }));
}

// Window choices: days back and days ahead of now ('all' leaves the axis to the data)
const HISTORY_WINDOWS = { around: [3, 3], week: [7, 1], fortnight: [14, 1], all: null };

function loadForecast() {
    if (!state.forecastPromise) {
        state.forecastPromise = fetchJson(FORECAST_URL).catch(error => {
            console.error('UW WRF forecast fetch failed:', error);
            return null;
        });
    }
    return state.forecastPromise;
}

// Latest UW WRF run at the Quillayute point (assets/data/uw_soundings/dowlx.json, every 3 h for 72 h, feet MSL),
// shown after "now" like the CW3E freezing-level verification chart. Subtracting the station height keeps it
// in AGL like the soundings.
function buildForecastTraces(fc, wrf, units) {
    const surface = wrf.uil_surface_ft || 0;
    const frames = (fc.frames || []).filter(f => f.valid_utc && Date.parse(f.valid_utc) >= Date.now() - 3 * 3600e3);   // the part still ahead of us
    const x = frames.map(f => f.valid_utc);
    const unit = wrfUnitLabel('level_ft', units);
    const init = String(fc.init_utc || '');
    const initLabel = init.length === 10 ? `${init.slice(0, 4)}-${init.slice(4, 6)}-${init.slice(6, 8)} ${init.slice(8)}Z` : 'latest';
    return [
        ['freezing_level_ft', 'Forecast freezing level', '#0f172a', 'solid', 3.5],
        ['snow_level_ft', 'Forecast snow level (0\u00b0C wet-bulb)', '#db2777', 'dot', 2.5],
    ].map(([key, name, color, dash, width]) => ({
        x, y: frames.map(f => (f[key] == null ? null : wrfConvert('level_ft', Math.max(0, f[key] - surface), units))),
        mode: 'lines', name: `${name} (UW WRF ${initLabel} run)`,
        line: { color, width, dash },
        hovertemplate: `%{x|%a %b %d %HZ}<br>${name}: %{y:.0f} ${unit} AGL<extra></extra>`,
    }));
}

function renderHistoryChart(stationId) {
    if (!els.historyPlot || !window.Plotly) return;
    const isUil = stationId === 'UIL';
    Promise.all([loadHistory(), isUil ? loadWrf() : null, isUil ? loadForecast() : null]).then(([data, wrf, fc]) => {
        if (state.station !== stationId) return;
        const entries = data && data.stations && data.stations[stationId];
        if (!entries || !entries.length) {
            els.historyPlot.classList.remove('is-visible');
            if (els.historyEmpty) els.historyEmpty.hidden = false;
            return;
        }
        if (els.historyEmpty) els.historyEmpty.hidden = true;
        const controls = document.getElementById('wrf-controls');
        if (controls) controls.hidden = !isUil;

        const units = state.units;
        const traces = buildHistoryTraces(entries, units)
            .concat(isUil && wrf ? buildWrfTraces(wrf, units) : [])
            .concat(isUil && wrf && fc ? buildForecastTraces(fc, wrf, units) : []);
        const hasForecast = isUil && wrf && fc && (fc.frames || []).length > 0;

        // x range: days back and ahead of now
        const now = Date.now(), day = 864e5;
        let win = HISTORY_WINDOWS[state.historyWindow];
        // nothing recorded inside the chosen window (the bot is behind, or this station's feed lags): show everything instead of an empty plot
        const noteEl = document.getElementById('history-note');
        const hasObs = win && entries.some(en => Date.parse(en.valid) >= now - win[0] * day);
        if (win && !hasObs) win = null;
        if (noteEl) { noteEl.hidden = !(HISTORY_WINDOWS[state.historyWindow] && !hasObs); noteEl.textContent = 'No soundings were recorded in this window for this station, so everything recorded is shown.'; }
        const xRange = win ? [new Date(now - win[0] * day).toISOString(), new Date(now + win[1] * day).toISOString()] : null;
        const nowIso = new Date(now).toISOString();
        // y range from what is in view, so the metres/feet axes can share one scale
        const lo = xRange ? Date.parse(xRange[0]) : -Infinity, hi = xRange ? Date.parse(xRange[1]) : Infinity;
        let ymax = 0;
        traces.forEach(tr => tr.x.forEach((xv, i) => { const t = Date.parse(xv), v = tr.y[i]; if (t >= lo && t <= hi && v != null && v > ymax) ymax = v; }));
        ymax = Math.max(ymax * 1.1, units === 'imperial' ? 3000 : 1000);
        // round the top up to a whole major step so both axes end on a gridline; the right axis is the same range in the other unit
        const major = units === 'imperial' ? 1000 : 500, minor = units === 'imperial' ? 500 : 100;
        ymax = Math.ceil(ymax / major) * major;
        const narrow = window.innerWidth < 700;
        const toOther = v => (units === 'imperial' ? v / 3.28084 : v * 3.28084);

        // an invisible point on the second axis so the other unit's scale is drawn
        traces.push({ x: [nowIso], y: [null], yaxis: 'y2', mode: 'markers', showlegend: false, hoverinfo: 'skip' });

        const layout = {
            margin: { l: 58, r: 66, t: 34, b: narrow ? 90 : 40 },
            xaxis: Object.assign({ type: 'date', tickformat: '%b %d', gridcolor: '#cbd5e1', minor: { dtick: 6 * 3600e3, showgrid: true, gridcolor: '#eef2f7', ticks: '' } }, xRange ? { range: xRange } : {}),
            yaxis: { title: units === 'imperial' ? 'Feet above ground' : 'Meters above ground', range: [0, ymax], gridcolor: '#cbd5e1', tickformat: ',.0f', dtick: major, minor: { dtick: minor, showgrid: true, gridcolor: '#eef2f7', ticks: '' } },
            yaxis2: { title: units === 'imperial' ? 'Meters' : 'Feet', overlaying: 'y', side: 'right', range: [0, toOther(ymax)], showgrid: false, tickformat: ',.0f', dtick: units === 'imperial' ? 250 : 1000 },
            legend: { orientation: 'h', y: narrow ? -0.28 : -0.2 },
            dragmode: 'zoom',
            hovermode: 'closest',
            shapes: [{ type: 'line', xref: 'x', yref: 'paper', x0: nowIso, x1: nowIso, y0: 0, y1: 1, line: { color: '#0f172a', width: 2 } }],
            annotations: [
                { xref: 'x', yref: 'paper', x: nowIso, y: 1.02, xanchor: 'right', yanchor: 'bottom', text: '\u25c0 Observed (soundings)', showarrow: false, font: { size: 12, color: '#334155' } },
                { xref: 'x', yref: 'paper', x: nowIso, y: 1.02, xanchor: 'left', yanchor: 'bottom', text: hasForecast ? 'Forecast (UW WRF) \u25b6' : 'Forecast: Quillayute only \u25b6', showarrow: false, font: { size: 12, color: '#334155' } },
            ],
        };
        // visible first: Plotly sizes itself from the container, and a display:none one falls back to 700px wide
        els.historyPlot.classList.add('is-visible');
        Plotly.react(els.historyPlot, traces, layout, { responsive: true, displaylogo: false, displayModeBar: true, scrollZoom: false, modeBarButtonsToRemove: ['select2d', 'lasso2d'] });
    });
}


// --- WRF overlay and skill scores (Quillayute only) -----------------------
// assets/data/wrf_uil.json is written by scripts/wrf_uil_verify.py: the UW WRF
// value for each observed 00Z/12Z launch time from the runs 12/24/48/72 h
// earlier (overlay), and season-long bias/MAE/RMSE by lead and init time.
// Levels there are feet MSL; the observed history above is AGL, so the
// overlay subtracts the Quillayute station elevation.
function loadWrf() {
    if (!state.wrfPromise) {
        state.wrfPromise = fetchJson(WRF_URL).catch(error => {
            console.error('WRF verification fetch failed:', error);
            return null;
        });
    }
    return state.wrfPromise;
}

const LEAD_COLORS = { 12: '#7c3aed', 24: '#0d9488', 48: '#ca8a04', 72: '#64748b' };

function wrfConvert(key, value, units, delta) {
    if (value == null) return null;
    if (key.endsWith('_ft')) return units === 'metric' ? value * 0.3048 : value;
    if (key.endsWith('_c')) return units === 'imperial' ? (delta ? value * 1.8 : value * 1.8 + 32) : value;
    return value;
}

function wrfUnitLabel(key, units) {
    if (key.endsWith('_ft')) return units === 'metric' ? 'm' : 'ft';
    if (key.endsWith('_c')) return units === 'imperial' ? '°F' : '°C';
    return '';
}

function buildWrfTraces(wrf, units) {
    const key = state.wrfVar;
    const surface = wrf.uil_surface_ft || 0;
    const label = wrf.variables[key].label;
    const unit = wrfUnitLabel(key, units);
    return state.wrfLeads.slice().sort((a, b) => a - b).map(lead => {
        const rows = wrf.recent.filter(r => r.wrf[String(lead)] && r.wrf[String(lead)][key] != null);
        return {
            x: rows.map(r => r.valid),
            y: rows.map(r => wrfConvert(key, r.wrf[String(lead)][key] - surface, units)),
            mode: 'lines+markers', name: `WRF ${lead} h: ${label}`,
            line: { color: LEAD_COLORS[lead] || '#475569', width: 2, dash: 'dash' }, marker: { size: 5, symbol: 'diamond' },
            hovertemplate: `%{x|%b %d %HZ}<br>WRF ${lead} h ${label}: %{y:.0f} ${unit} AGL<extra></extra>`,
        };
    });
}

function initWrfControls() {
    const winSel = document.getElementById('history-window');
    if (winSel) winSel.addEventListener('change', () => { state.historyWindow = winSel.value; renderHistoryChart(state.station); });
    const varSel = document.getElementById('wrf-var');
    if (varSel) varSel.addEventListener('change', () => { state.wrfVar = varSel.value; renderHistoryChart(state.station); });
    document.querySelectorAll('input[name="wrf-lead"]').forEach(box => {
        box.addEventListener('change', () => {
            state.wrfLeads = Array.from(document.querySelectorAll('input[name="wrf-lead"]:checked')).map(b => Number(b.value));
            renderHistoryChart(state.station);
        });
    });
    [['skill-var', 'skillVar'], ['skill-init', 'skillInit'], ['skill-metric', 'skillMetric']].forEach(([id, prop]) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', () => { state[prop] = el.value; renderWrfSkill(); });
    });
}

function renderWrfSkill() {
    const section = document.getElementById('wrf-skill');
    if (!section) return;
    loadWrf().then(wrf => {
        const seasons = wrf && wrf.metrics ? Object.keys(wrf.metrics).sort() : [];
        if (!seasons.length) { section.hidden = true; return; }
        section.hidden = false;
        const season = seasons[seasons.length - 1];
        const key = state.skillVar;
        const units = state.units;
        const unit = wrfUnitLabel(key, units);
        const data = wrf.metrics[season];
        document.getElementById('wrf-skill-season').textContent = season;

        // Table: one row per lead for the chosen init time; lowest RMSE is highlighted.
        const cells = data.overall[key].filter(c => c.init === state.skillInit);
        const best = cells.length ? Math.min(...cells.map(c => c.rmse)) : null;
        const digits = key.endsWith('_ft') ? 0 : 1;
        const fmt = v => (v == null ? '&ndash;' : wrfConvert(key, v, units, true).toFixed(digits));
        document.getElementById('wrf-skill-table').innerHTML =
            `<thead><tr><th>Lead</th><th>n</th><th>Bias (${unit})</th><th>MAE (${unit})</th><th>RMSE (${unit})</th><th>r</th></tr></thead><tbody>` +
            cells.map(c => `<tr${c.rmse === best ? ' class="is-best"' : ''}><td>${c.lead} h</td><td>${c.n}</td>` +
                `<td>${fmt(c.bias)}</td><td>${fmt(c.mae)}</td><td>${fmt(c.rmse)}</td>` +
                `<td>${c.r == null ? '&ndash;' : c.r.toFixed(2)}</td></tr>`).join('') + '</tbody>';

        // Weekly chart of the chosen metric, one line per lead.
        const metric = state.skillMetric;
        const byLead = {};
        data.weekly[key].forEach(w => { (byLead[w.lead] = byLead[w.lead] || []).push(w); });
        const palette = ['#94a3b8', '#7c3aed', '#2563eb', '#0d9488', '#65a30d', '#ca8a04', '#dc2626'];
        const traces = Object.keys(byLead).map((lead, i) => ({
            x: byLead[lead].map(w => w.week),
            y: byLead[lead].map(w => wrfConvert(key, w[metric], units, true)),
            mode: 'lines+markers', name: `${lead} h`,
            line: { color: palette[i % palette.length], width: 2 }, marker: { size: 5 },
            hovertemplate: `Week of %{x|%b %d}<br>${lead} h ${metric.toUpperCase()}: %{y:.${digits}f} ${unit}<extra></extra>`,
        }));
        const plot = document.getElementById('wrf-skill-plot');
        if (window.Plotly && plot) {
            Plotly.react(plot, traces, {
                margin: { l: 55, r: 15, t: 10, b: 40 },
                xaxis: { type: 'date', title: 'Week starting' },
                yaxis: { title: `${metric === 'rmse' ? 'RMSE' : 'Bias (WRF - observed)'} (${unit})`, zeroline: true },
                legend: { orientation: 'h', y: -0.25 }, hovermode: 'closest',
            }, { responsive: true, displaylogo: false });
        }
    });
}
