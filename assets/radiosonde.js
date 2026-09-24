// Radiosonde / Skew-T tool.
//
// Renders MetPy skew-T diagrams entirely in the browser via Pyodide (Python
// compiled to WebAssembly) -- no server or scheduled job needed. Sounding
// data comes from Iowa State's IEM RAOB JSON API. Technique and most of the
// Python plotting code below are adapted from Clinton Alden's own tool at
// https://github.com/clinton-alden/clinton-alden.github.io/blob/main/assets/radiosonde.js
// (Clinton is a Cascade Mountain Weather co-founder; see PLAN.md).
//
// Unlike that CONUS-wide version, we only track 4 fixed stations, so instead
// of bulk-preloading every recent cycle for every station, each station is
// fetched lazily (only when selected) and we walk backward/forward in 6-hour
// steps to find the nearest cycle that actually has data. This matters
// because two of our four stations have real, permanent data-availability
// quirks (see STATIONS below) that a fixed 3-day lookback would miss.
//
// The primary diagram is an interactive Plotly chart, not a static image.
// MetPy still does all of the actual thermodynamics (dry/moist adiabats,
// mixing lines, parcel lifts, LCL) via its normal matplotlib SkewT axes --
// we just never rasterize that axes to a PNG for the main view. Instead we
// read each MetPy-generated line/curve back out in its original (T, P) data
// coordinates and run it through that same axes' `transData` (the object
// that actually implements the skew + log-pressure projection) to get pixel
// coordinates, which we hand to Plotly as plain x/y numbers with the axes
// hidden and a locked aspect ratio. That reproduces MetPy's exact skew-T
// geometry without having to reimplement the skew transform by hand, while
// letting Plotly provide hover tooltips (temperature/dew point/parcel value
// and parcel-vs-environment difference at any level) and pan/zoom. The full
// composite image (hodograph, wind barbs, implied thermal advection) is
// still rendered as a static PNG, available behind a "full analysis" toggle.

const IEM_RAOB_BASE = 'https://mesonet.agron.iastate.edu/json/raob.py';
const PYODIDE_VERSION = 'v0.26.4';
const SPC_BASE = 'https://www.spc.noaa.gov/exper/archive/events';
// Set by an inline <script> in tools/radiosonde.html via Liquid, since this
// file itself isn't processed by Jekyll. Falls back to the plain root path
// (correct as long as the site's baseurl stays empty, per _config.yml).
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
        maxLookbackSteps: 12, // 3 days of 6-hourly cycles
        note: 'NWS sounding, launched 00Z & 12Z daily. Usually appears in this feed within a few hours.',
    },
    {
        id: 'SLE',
        name: 'Salem, OR',
        lat: 44.91,
        lon: -123.00,
        country: 'US',
        maxLookbackSteps: 12,
        note: 'NWS sounding, launched 00Z & 12Z daily. Usually appears in this feed within a few hours.',
    },
    {
        id: 'OTX',
        name: 'Spokane, WA',
        lat: 47.70,
        lon: -116.40,
        country: 'US',
        maxLookbackSteps: 12,
        note: 'NWS sounding site, but KOTX has been absent from this near-real-time feed for an extended stretch -- a known upstream gap, not a bug in this tool.',
    },
    {
        id: 'CYZT',
        name: 'Port Hardy, BC',
        lat: 50.68,
        lon: -127.30,
        country: 'CA',
        maxLookbackSteps: 48, // ~12 days, to comfortably clear the lag below
        note: 'Environment Canada sounding. This feed typically lags Canadian sites by 4-5 days, so the most recent available sounding here is usually about that old, not same-day.',
    },
];

const state = {
    pyodide: null,
    pyReady: null,
    cycleCache: new Map(), // `${station}|${timestamp}` -> profile rows array, or null if confirmed empty
    plotCache: new Map(),  // `${station}|${timestamp}` -> { image, diagnostics, interactive }
    station: STATIONS[0].id,
    displayedCycle: null,  // the cycle object currently shown
    activeRequest: 0,
    units: 'metric',       // 'metric' | 'imperial' -- affects hover text and the diagnostics table
    current: null,         // { stationId, cycle, result } for the plot currently on screen, for unit-toggle re-renders
    historyPromise: null,  // cached fetch of the shared history JSON (all stations)
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
        plotContainer: document.getElementById('skewt-plot'),
        output: document.getElementById('skewt-output'),
        placeholder: document.getElementById('plot-placeholder'),
        detailToggle: document.getElementById('detail-toggle'),
        detailImage: document.getElementById('skewt-detail-image'),
        diagnostics: document.getElementById('sounding-diagnostics'),
        meltingNote: document.getElementById('melting-note'),
        dataSource: document.getElementById('data-source-link'),
        spcSource: document.getElementById('spc-source-link'),
        historyPlot: document.getElementById('history-plot'),
        historyEmpty: document.getElementById('history-empty'),
    });

    if (!els.stationButtons || !els.output) return;

    renderStationButtons();
    els.older.addEventListener('click', () => stepCycle(-1));
    els.newer.addEventListener('click', () => stepCycle(1));
    els.detailToggle.addEventListener('click', () => {
        const showing = els.detailImage.classList.toggle('is-visible');
        els.detailToggle.textContent = showing
            ? 'Hide full analysis'
            : 'Show full analysis (hodograph, wind barbs, thermal advection)';
    });
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
    if (state.current) {
        showPlot(state.current.stationId, state.current.cycle, state.current.result);
    }
    renderHistoryChart(state.station);
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

function makeCycle(date) {
    const yyyy = date.getUTCFullYear();
    const mm = pad(date.getUTCMonth() + 1);
    const dd = pad(date.getUTCDate());
    const hh = pad(date.getUTCHours());
    return {
        date,
        timestamp: `${yyyy}${mm}${dd}${hh}00`,
        label: `${yyyy}-${mm}-${dd} ${hh}Z`,
        spcUrlStem: `${SPC_BASE}/${yyyy}${mm}${dd}/soundings/${String(yyyy).slice(2)}${mm}${dd}${hh}_SNDG`,
    };
}

// Most recent synoptic hour (00/06/12/18Z) that has already happened.
function latestCompletedCycle() {
    const now = new Date();
    const hour = Math.floor(now.getUTCHours() / 6) * 6;
    const floored = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), hour));
    return makeCycle(floored);
}

function stepCycleDate(cycle, deltaSteps) {
    const next = new Date(cycle.date.getTime() + deltaSteps * 6 * 60 * 60 * 1000);
    return makeCycle(next);
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

// Fetch (and cache) the profile for one station at one cycle. Returns the
// profile rows array, or null if that cycle has no data for this station.
async function fetchStationCycle(stationId, cycle) {
    const key = `${stationId}|${cycle.timestamp}`;
    if (state.cycleCache.has(key)) return state.cycleCache.get(key);

    let profile = null;
    try {
        const data = await fetchJson(`${IEM_RAOB_BASE}?ts=${cycle.timestamp}&station=${stationId}`);
        const record = (data.profiles || [])[0];
        if (record && Array.isArray(record.profile) && record.profile.length >= 6) {
            profile = record.profile;
        }
    } catch (error) {
        console.error(`Sounding fetch failed for ${stationId} at ${cycle.label}:`, error);
    }

    state.cycleCache.set(key, profile);
    return profile;
}

// Walk from `startCycle` in steps of `direction` (+1 = newer, -1 = older)
// looking for the first cycle with data, up to maxSteps cycles away. Never
// steps into the future.
async function findAvailableCycle(stationId, startCycle, direction, maxSteps) {
    const now = latestCompletedCycle();
    let cycle = startCycle;
    for (let i = 0; i <= maxSteps; i += 1) {
        if (cycle.date > now.date) {
            cycle = stepCycleDate(cycle, -1);
            continue;
        }
        const profile = await fetchStationCycle(stationId, cycle);
        if (profile) return { cycle, profile };
        cycle = stepCycleDate(cycle, direction);
    }
    return null;
}

function renderStationButtons() {
    els.stationButtons.innerHTML = '';
    STATIONS.forEach(station => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'radiosonde-station-btn';
        button.dataset.station = station.id;
        button.setAttribute('aria-pressed', String(station.id === state.station));
        button.innerHTML = `<strong>${station.id}</strong><span>${station.name}</span>`;
        button.addEventListener('click', () => selectStation(station.id));
        els.stationButtons.appendChild(button);
    });
}

function updateStationButtonStates() {
    els.stationButtons.querySelectorAll('.radiosonde-station-btn').forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.station === state.station));
    });
}

async function selectStation(stationId) {
    state.station = stationId;
    const meta = getStationMeta(stationId);
    updateStationButtonStates();
    els.stationNote.textContent = meta.note;
    renderHistoryChart(stationId);
    els.older.disabled = true;
    els.newer.disabled = true;
    setStatus(`Looking for the most recent ${stationId} sounding...`);
    els.placeholder.classList.add('is-visible');
    els.placeholder.textContent = `Looking for the most recent ${stationId} sounding...`;
    els.output.classList.remove('is-visible');
    els.plotContainer.classList.remove('is-visible');
    els.detailImage.classList.remove('is-visible');
    els.detailToggle.hidden = true;
    els.diagnostics.hidden = true;

    const requestId = ++state.activeRequest;
    const found = await findAvailableCycle(stationId, latestCompletedCycle(), -1, meta.maxLookbackSteps);
    if (requestId !== state.activeRequest) return;

    if (!found) {
        const days = Math.round(meta.maxLookbackSteps / 4);
        els.placeholder.textContent = `No ${stationId} sounding found in the last ${days} days.`;
        setStatus('Select another station.');
        els.cycleLabel.textContent = 'Cycle: unavailable';
        return;
    }

    state.displayedCycle = found.cycle;
    await renderCycle(stationId, found.cycle, found.profile);
}

async function stepCycle(direction) {
    if (!state.displayedCycle) return;
    const meta = getStationMeta(state.station);
    els.older.disabled = true;
    els.newer.disabled = true;
    setStatus(direction < 0 ? 'Looking for an older sounding...' : 'Looking for a newer sounding...');

    const requestId = ++state.activeRequest;
    const start = stepCycleDate(state.displayedCycle, direction);
    const found = await findAvailableCycle(state.station, start, direction, meta.maxLookbackSteps);
    if (requestId !== state.activeRequest) return;

    if (!found) {
        setStatus(direction < 0 ? 'No older sounding found in range.' : 'Already at the most recent sounding.');
        els.older.disabled = false;
        els.newer.disabled = false;
        return;
    }

    state.displayedCycle = found.cycle;
    await renderCycle(state.station, found.cycle, found.profile);
}

async function loadMetPy() {
    if (state.pyReady) return state.pyReady;
    state.pyReady = (async () => {
        const pyodide = await loadPyodide({
            indexURL: `https://cdn.jsdelivr.net/pyodide/${PYODIDE_VERSION}/full/`,
        });
        await pyodide.loadPackage(['micropip', 'matplotlib', 'numpy', 'scipy', 'pandas', 'packaging', 'pyproj', 'lzma']);
        await pyodide.runPythonAsync(`
import micropip
await micropip.install(["pint", "pooch", "traitlets", "xarray"])
await micropip.install("metpy==1.6.3", deps=False)
`);
        await pyodide.runPythonAsync(`
import base64
import io
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from metpy.plots import Hodograph, SkewT
from metpy.units import units
from metpy.calc import (
    lcl,
    mixed_layer_cape_cin,
    mixed_parcel,
    most_unstable_cape_cin,
    most_unstable_parcel,
    parcel_profile,
    wind_components,
)


def parse_iem_profile(profile_json):
    rows = []
    for row in json.loads(profile_json):
        p = row.get("pres")
        h = row.get("hght")
        t = row.get("tmpc")
        td = row.get("dwpc")
        wd = row.get("drct")
        ws = row.get("sknt")
        if p is None or t is None or td is None:
            continue
        rows.append((
            float(p),
            np.nan if h is None else float(h),
            float(t),
            float(td),
            np.nan if wd is None else float(wd),
            np.nan if ws is None else float(ws),
        ))
    if len(rows) < 6:
        raise ValueError("Could not parse enough pressure-level rows from IEM RAOB JSON.")
    arr = np.array(rows, dtype=float)
    arr = arr[np.argsort(arr[:, 0])[::-1]]
    _, unique_idx = np.unique(arr[:, 0], return_index=True)
    return arr[np.sort(unique_idx)]


def calculate_diagnostics(arr, p, t, td):
    diagnostics = {
        "mucape": None,
        "mu_height": None,
        "mlcape": None,
        "advection": "Unavailable",
        "dgz": "Unavailable",
        "dgz_p_bottom": None,
        "dgz_p_top": None,
    }

    def cape_value(calculation):
        try:
            value = calculation()
            if isinstance(value, tuple):
                value = value[0]
            return int(round(max(0.0, float(value.to("J/kg").magnitude))))
        except Exception:
            return None

    # Only MLCAPE and MUCAPE are surfaced in the UI: MLCAPE is the more
    # conservative, generally-preferred severe-weather value (it reflects
    # what the boundary layer as a whole is doing), while MUCAPE is the
    # absolute ceiling on convective potential even when the most unstable
    # air isn't at the surface. SBCAPE/DCAPE aren't shown, so they aren't
    # computed here either.
    diagnostics["mucape"] = cape_value(lambda: most_unstable_cape_cin(p, t, td))
    diagnostics["mlcape"] = cape_value(lambda: mixed_layer_cape_cin(p, t, td))

    try:
        _, _, _, mu_index = most_unstable_parcel(p, t, td)
        heights = arr[:, 1]
        surface_height = heights[np.isfinite(heights)][0]
        mu_height = heights[mu_index]
        if np.isfinite(mu_height):
            diagnostics["mu_height"] = int(round(max(0.0, mu_height - surface_height)))
    except Exception:
        pass

    try:
        wind_mask = np.isfinite(arr[:, 4]) & np.isfinite(arr[:, 5])
        wind_p = arr[wind_mask, 0]
        wind_u, wind_v = wind_components(
            arr[wind_mask, 5] * units.knots,
            arr[wind_mask, 4] * units.degrees,
        )
        surface_p = float(p[0].magnitude)
        low = (wind_p <= surface_p) & (wind_p >= surface_p - 100)
        middle = (wind_p < surface_p - 100) & (wind_p >= surface_p - 250)
        if np.count_nonzero(low) and np.count_nonzero(middle):
            def vector_direction(u_values, v_values):
                mean_u = float(np.mean(u_values.magnitude))
                mean_v = float(np.mean(v_values.magnitude))
                return (np.degrees(np.arctan2(-mean_u, -mean_v)) + 360) % 360

            low_direction = vector_direction(wind_u[low], wind_v[low])
            middle_direction = vector_direction(wind_u[middle], wind_v[middle])
            turning = (middle_direction - low_direction + 180) % 360 - 180
            if turning >= 15:
                diagnostics["advection"] = f"Warm advection implied (veering {turning:.0f} deg)"
            elif turning <= -15:
                diagnostics["advection"] = f"Cold advection implied (backing {abs(turning):.0f} deg)"
            else:
                diagnostics["advection"] = f"Little directional turning ({turning:+.0f} deg)"
    except Exception:
        pass

    dgz_mask = (
        (arr[:, 2] >= -18)
        & (arr[:, 2] <= -12)
        & np.isfinite(arr[:, 1])
    )
    if np.count_nonzero(dgz_mask) >= 2:
        surface_height = arr[np.isfinite(arr[:, 1]), 1][0]
        base = max(0.0, float(np.min(arr[dgz_mask, 1]) - surface_height))
        top = max(base, float(np.max(arr[dgz_mask, 1]) - surface_height))
        diagnostics["dgz"] = f"{base / 1000:.1f}-{top / 1000:.1f} km AGL"
        diagnostics["dgz_p_bottom"] = float(np.max(arr[dgz_mask, 0]))
        diagnostics["dgz_p_top"] = float(np.min(arr[dgz_mask, 0]))

    return diagnostics


def temperature_advection_profile(arr, latitude):
    wind_mask = np.isfinite(arr[:, 4]) & np.isfinite(arr[:, 5])
    if np.count_nonzero(wind_mask) < 6:
        return np.array([]), np.array([]), np.array([]), np.array([])

    wind_p = arr[wind_mask, 0]
    wind_u, wind_v = wind_components(
        arr[wind_mask, 5] * units.knots,
        arr[wind_mask, 4] * units.degrees,
    )
    wind_u = wind_u.to("m/s").magnitude
    wind_v = wind_v.to("m/s").magnitude

    surface_level = np.floor(wind_p[0] / 50) * 50
    bottom_level = max(100, np.ceil(wind_p[-1] / 50) * 50)
    target_p = np.arange(surface_level, bottom_level - 1, -50)
    if target_p.size < 4:
        return np.array([]), np.array([]), np.array([]), np.array([])

    log_wind_p = np.log(wind_p[::-1])
    log_target_p = np.log(target_p)
    u_interp = np.interp(log_target_p, log_wind_p, wind_u[::-1])
    v_interp = np.interp(log_target_p, log_wind_p, wind_v[::-1])

    du_dlnp = np.gradient(u_interp, log_target_p)
    dv_dlnp = np.gradient(v_interp, log_target_p)
    coriolis = 2 * 7.2921159e-5 * np.sin(np.radians(latitude))
    dry_air_gas_constant = 287.05
    advection = (
        coriolis
        / dry_air_gas_constant
        * (u_interp * dv_dlnp - v_interp * du_dlnp)
        * 3600
    )

    if advection.size >= 3:
        advection = np.convolve(advection, np.ones(3) / 3, mode="same")
    return target_p, advection, u_interp, v_interp


def _mag(value):
    return value.magnitude if hasattr(value, "magnitude") else value


def _clean(value):
    value = float(value)
    if np.isnan(value) or np.isinf(value):
        return None
    return value


def _clean_list(seq):
    return [_clean(v) for v in np.asarray(_mag(seq), dtype=float)]


def _transform_xy(transform, xs, ys):
    # Runs a set of (x, y) data-space points (e.g. temperature-in-degC,
    # pressure-in-hPa) through a matplotlib SkewT axes' transData, which is
    # what actually implements the skew-T's skew + log-pressure projection.
    # The result is plain pixel coordinates that reproduce MetPy's geometry
    # without us having to hand-derive the skew transform ourselves.
    pts = np.column_stack([
        np.asarray(_mag(xs), dtype=float),
        np.asarray(_mag(ys), dtype=float),
    ])
    finite = np.isfinite(pts).all(axis=1)
    out_x = [None] * len(pts)
    out_y = [None] * len(pts)
    if np.any(finite):
        transformed = transform.transform(pts[finite])
        for idx, (px, py) in zip(np.nonzero(finite)[0], transformed):
            out_x[int(idx)] = _clean(px)
            out_y[int(idx)] = _clean(py)
    return out_x, out_y


def _segments_pixel(collection, transform):
    lines = []
    for seg in collection.get_segments():
        xs, ys = _transform_xy(transform, seg[:, 0], seg[:, 1])
        lines.append({"x": xs, "y": ys})
    return lines


# --- Snow level / melting-layer model -------------------------------------
# Simplified Matsuo & Sasyo (1981) melting-rate model: below the height
# where wet-bulb temperature (Tw) first exceeds 0 C, a falling ice sphere's
# radius shrinks at a rate set by the balance of sensible heat transfer in
# from the surrounding (positive-Tw) air against the latent heat needed to
# melt it:
#
#     -dR/dt = (C_vent * K_eff * Tw) / (rho_s * L_f * R)      for Tw > 0, R > 0
#              0                                              otherwise
#
# Note the 1/R term: heat conduction to a sphere in steady state scales
# with its radius (not radius^2), so this term is required for the units
# to work out to a rate of change of R at all (W/(m*K) * K / (kg/m^3 *
# J/kg) alone reduces to m^2/s, not m/s) -- it's also what the underlying
# Mason (1956) melting-sphere derivation that Matsuo & Sasyo build on
# actually has. Leaving it out makes flakes melt roughly a thousand times
# too slowly (tested against a synthetic sounding: a medium flake took
# ~223 hours to melt without it, vs. ~10 minutes/~600 m of fall with it --
# the latter matches the few-hundred-meter snow-level-below-wet-bulb-zero
# gap forecasters typically see). It's included here on that basis.
#
# This tells us more than the plain 0 C freezing level (where the dry-bulb
# temperature crosses 0 C): it estimates the "snow level" -- the altitude
# where a representative ensemble of snowflakes has actually finished
# melting into rain -- which is normally noticeably lower than both the
# freezing level and the wet-bulb-zero height.
_MELT_RHO_SNOW = 100.0          # kg/m^3, bulk density for a 10:1 snow:liquid ratio
_MELT_LATENT_FUSION = 3.34e5    # J/kg, latent heat of fusion
_MELT_K_EFF = 2.6e-2            # W/(m*K), combined conductive/diffusive proxy
_MELT_C_VENT = 1.2              # dimensionless ventilation factor (~1 m/s fall speed)
_MELT_FALL_SPEED = 1.0          # m/s, constant terminal fall speed for the ensemble
_MELT_GRID_STEP_M = 5.0         # m, vertical resolution of the integration grid
_MELT_ENSEMBLE_DIAMETERS_MM = (1.5, 3.0, 5.0)  # small / medium / large snowflakes


def compute_melting_layer(arr):
    """Estimate the freezing level, wet-bulb-zero height, and true snow
    level from one sounding, using the melting model described above.

    Heights are reported in meters AGL (above the sounding's lowest
    reported level). Returns a dict of Nones (with an explanatory "note")
    if the profile doesn't support the calculation -- e.g. an entirely
    sub-freezing column, or one with no sub-cloud melting layer at all.
    """
    result = {
        "freezing_level_m": None,
        "wet_bulb_zero_m": None,
        "snow_level_m": None,
        "total_melting_distance_m": None,
        "note": None,
    }

    height_mask = np.isfinite(arr[:, 1])
    if np.count_nonzero(height_mask) < 6:
        result["note"] = "Not enough height data in this sounding to estimate a melting layer."
        return result

    heights = arr[height_mask, 1]
    temps = arr[height_mask, 2]
    dewpoints = arr[height_mask, 3]
    order = np.argsort(heights)
    heights, temps, dewpoints = heights[order], temps[order], dewpoints[order]
    _, unique_idx = np.unique(heights, return_index=True)
    heights, temps, dewpoints = heights[unique_idx], temps[unique_idx], dewpoints[unique_idx]

    heights_agl = heights - heights[0]
    if heights_agl.size < 6 or heights_agl[-1] < 50:
        result["note"] = "Sounding does not extend high enough to locate a melting layer."
        return result

    # Interpolate to a high-resolution grid for numerical stability, then
    # approximate the wet-bulb temperature with the standard psychrometric
    # proxy Tw ~= T - 1/3*(T - Td) (adequate for locating the melting-layer
    # boundaries without a full iterative wet-bulb solve).
    grid = np.arange(0.0, heights_agl[-1] + _MELT_GRID_STEP_M, _MELT_GRID_STEP_M)
    t_grid = np.interp(grid, heights_agl, temps)
    td_grid = np.interp(grid, heights_agl, dewpoints)
    tw_grid = t_grid - (t_grid - td_grid) / 3.0

    # Freezing level: lowest AGL height (ascending from the surface) where
    # the dry-bulb temperature is at or below 0 C.
    if not np.any(t_grid <= 0.0):
        result["note"] = "Entire profile is above freezing -- no freezing level found."
        return result
    freezing_idx = int(np.argmax(t_grid <= 0.0))
    result["freezing_level_m"] = float(grid[freezing_idx])

    # Wet-bulb zero: same logic using Tw. Since Tw <= T everywhere, this is
    # always at or below the freezing level -- and it's where melting of a
    # falling snowflake actually begins.
    if not np.any(tw_grid <= 0.0):
        result["note"] = "No sub-cloud melting layer found (dry air aloft keeps the wet-bulb temperature above 0 C)."
        return result
    wbz_idx = int(np.argmax(tw_grid <= 0.0))
    result["wet_bulb_zero_m"] = float(grid[wbz_idx])

    # Integrate a 3-size snowflake ensemble downward from the wet-bulb-zero
    # height to the surface, shrinking each flake's radius per the melting
    # equation above at each 5-m grid step (dt = dz / fall speed).
    radii0 = np.array([d / 2000.0 for d in _MELT_ENSEMBLE_DIAMETERS_MM])  # mm diameter -> m radius
    radii = radii0.copy()
    total_volume0 = float(np.sum(radii0 ** 3))
    dt = _MELT_GRID_STEP_M / _MELT_FALL_SPEED
    melted_height = np.full(radii.shape, np.nan)
    snow_level = None

    for i in range(wbz_idx, -1, -1):
        tw = max(0.0, float(tw_grid[i]))
        if tw > 0.0:
            safe_radii = np.maximum(radii, 1e-9)  # avoid divide-by-zero for already-melted flakes
            rate = (_MELT_C_VENT * _MELT_K_EFF * tw) / (_MELT_RHO_SNOW * _MELT_LATENT_FUSION * safe_radii)
            radii = np.maximum(0.0, radii - rate * dt)
        newly_melted = np.isnan(melted_height) & (radii <= 1e-9)
        melted_height[newly_melted] = grid[i]

        # Mass (volume, at constant density) fraction melted so far, across
        # the whole ensemble -- this is what "95% melted" is measured on,
        # not a simple 1-of-3-flakes count.
        melted_fraction = 1.0 - (np.sum(radii ** 3) / total_volume0)
        if snow_level is None and melted_fraction >= 0.95:
            snow_level = float(grid[i])
        if np.all(radii <= 1e-9):
            break

    if snow_level is None:
        # Ran out of profile (reached the surface) before 95% melted --
        # this model says snow could still be reaching the ground.
        snow_level = float(grid[0])
        result["note"] = (
            "The snowflake ensemble was not fully melted by the surface in this model -- "
            "snow may be reaching the ground despite above-freezing surface air."
        )
    result["snow_level_m"] = snow_level

    medium_melted_height = melted_height[1]  # index 1 = medium (3.0 mm) flake
    if np.isfinite(medium_melted_height):
        result["total_melting_distance_m"] = float(result["wet_bulb_zero_m"] - medium_melted_height)
    else:
        result["total_melting_distance_m"] = float(result["wet_bulb_zero_m"] - grid[0])
        extra_note = "The medium-size (3 mm) snowflake did not fully melt within this profile."
        result["note"] = f"{result['note']} {extra_note}" if result["note"] else extra_note

    return result


def _agl_height_to_pressure(arr, height_agl):
    # Translates one of compute_melting_layer's AGL heights back to a
    # pressure level, so it can be drawn as a horizontal line on a
    # pressure-coordinate skew-T.
    if height_agl is None:
        return None
    mask = np.isfinite(arr[:, 1])
    if np.count_nonzero(mask) < 2:
        return None
    heights = arr[mask, 1]
    pressures = arr[mask, 0]
    order = np.argsort(heights)
    heights, pressures = heights[order], pressures[order]
    heights_agl = heights - heights[0]
    return float(np.interp(height_agl, heights_agl, pressures))


def make_skewt(profile_json, station, cycle_label, station_latitude):
    arr = parse_iem_profile(profile_json)
    p = arr[:, 0] * units.hPa
    t = arr[:, 2] * units.degC
    td = arr[:, 3] * units.degC
    diagnostics = calculate_diagnostics(arr, p, t, td)
    melting = compute_melting_layer(arr)
    diagnostics["freezing_level_m"] = melting["freezing_level_m"]
    diagnostics["wet_bulb_zero_m"] = melting["wet_bulb_zero_m"]
    diagnostics["snow_level_m"] = melting["snow_level_m"]
    diagnostics["total_melting_distance_m"] = melting["total_melting_distance_m"]
    diagnostics["melting_note"] = melting["note"]

    # This sounding's dewpoint profile is a snapshot at launch time -- if it
    # was dry/non-precipitating, the sub-cloud air is drier (and the
    # computed snow level lower) than it would be once precipitation has
    # actually been falling for a while, since evaporative cooling from the
    # falling hydrometeors saturates and cools that layer over time. As a
    # sensitivity check, rerun the same model assuming a fully saturated
    # column (Td = T everywhere, i.e. Tw = T) -- the limiting case of
    # sustained precipitation having already conditioned the profile. This
    # gives a second, generally higher snow-level estimate, and the gap
    # between the two tells us how much this sounding's moisture (rather
    # than its temperature) is driving the result.
    arr_saturated = arr.copy()
    arr_saturated[:, 3] = arr_saturated[:, 2]
    melting_saturated = compute_melting_layer(arr_saturated)
    diagnostics["snow_level_saturated_m"] = melting_saturated["snow_level_m"]

    saturation_gap = None
    if melting["snow_level_m"] is not None and melting_saturated["snow_level_m"] is not None:
        saturation_gap = melting_saturated["snow_level_m"] - melting["snow_level_m"]
    if saturation_gap is not None and saturation_gap >= 300:
        gap_note = (
            f"This sounding's sub-cloud air looks fairly dry (the as-observed and saturated-column "
            f"snow-level estimates differ by about {int(round(saturation_gap))} m), consistent with "
            "non-precipitating conditions when the balloon launched. If precipitation is actually "
            "falling now (or becomes steady/heavy), evaporative cooling would moisten and cool that "
            "layer, pushing the real snow level up toward the Snow Level (Saturated Column) estimate "
            "-- check current radar/precip intensity to judge which applies."
        )
        diagnostics["melting_note"] = (
            f"{diagnostics['melting_note']} {gap_note}" if diagnostics["melting_note"] else gap_note
        )

    advection_p, advection, grid_u, grid_v = temperature_advection_profile(
        arr,
        station_latitude,
    )

    fig = plt.figure(figsize=(10.5, 9), dpi=150)
    skew = SkewT(fig, rotation=45, rect=(0.065, 0.055, 0.68, 0.91))
    skew.plot(p, t, color="#d95f02", linewidth=2.0, label="Temperature")
    skew.plot(p, td, color="#1b9e77", linewidth=2.0, label="Dew point")

    surface_parcel_geo = None
    try:
        lcl_p, lcl_t = lcl(p[0], t[0], td[0])
        prof = parcel_profile(p, t[0], td[0]).to("degC")
        skew.plot(p, prof, color="#7570b3", linewidth=1.5, linestyle="--", label="Surface parcel")
        skew.ax.plot(lcl_t, lcl_p, marker="o", color="#7570b3", markersize=5)
        surface_parcel_geo = {
            "p_raw": _mag(p),
            "t_raw": _mag(prof),
            "diff_raw": _mag(prof) - _mag(t),
            "lcl_p_raw": _mag(lcl_p),
            "lcl_t_raw": _mag(lcl_t.to("degC")),
        }
    except Exception:
        pass

    mixed_parcel_geo = None
    try:
        _, mixed_t, mixed_td = mixed_parcel(p, t, td, depth=100 * units.hPa)
        mixed_prof = parcel_profile(p, mixed_t, mixed_td).to("degC")
        skew.plot(
            p, mixed_prof, color="#7570b3", linewidth=1.5, linestyle=":",
            label="100-hPa mixed parcel",
        )
        mixed_parcel_geo = {"p_raw": _mag(p), "t_raw": _mag(mixed_prof)}
    except Exception:
        pass

    skew.ax.set_ylim(1050, 150)
    skew.ax.set_xlim(-40, 45)
    dry_collection = skew.plot_dry_adiabats(alpha=0.35, linewidth=0.7)
    moist_collection = skew.plot_moist_adiabats(alpha=0.35, linewidth=0.7)
    mixing_collection = skew.plot_mixing_lines(alpha=0.25, linewidth=0.7)
    if diagnostics["dgz_p_bottom"] is not None:
        skew.ax.axhspan(
            diagnostics["dgz_p_top"], diagnostics["dgz_p_bottom"],
            color="#56b4e9", alpha=0.14, label="DGZ (-12 to -18 C)",
        )
    skew.ax.axvline(0, color="#444444", linewidth=1.0)

    reference_specs = (
        ("Freezing level", "#2563eb", melting["freezing_level_m"]),
        ("Wet-bulb zero", "#0891b2", melting["wet_bulb_zero_m"]),
        ("Snow level", "#db2777", melting["snow_level_m"]),
        ("Snow level (saturated)", "#f9a8d4", melting_saturated["snow_level_m"]),
    )
    for ref_label, ref_color, ref_height_agl in reference_specs:
        ref_p = _agl_height_to_pressure(arr, ref_height_agl)
        if ref_p is None:
            continue
        skew.ax.axhline(ref_p, color=ref_color, linewidth=1.3, linestyle="--", alpha=0.85, zorder=5)
        skew.ax.text(
            skew.ax.get_xlim()[0] + 1, ref_p, ref_label, color=ref_color,
            fontsize=8, va="bottom", ha="left", fontweight="bold",
        )

    skew.ax.set_title(f"{station} Observed Sounding - {cycle_label}", loc="left", fontsize=13)
    skew.ax.set_xlabel("Temperature (deg C)")
    skew.ax.set_ylabel("Pressure (hPa)")
    skew.ax.legend(loc="upper right", fontsize=9)

    try:
        hodo_mask = np.isfinite(arr[:, 1]) & np.isfinite(arr[:, 4]) & np.isfinite(arr[:, 5])
        hodo_height = arr[hodo_mask, 1]
        surface_height = hodo_height[0]
        hodo_height = hodo_height - surface_height
        hodo_u, hodo_v = wind_components(
            arr[hodo_mask, 5] * units.knots,
            arr[hodo_mask, 4] * units.degrees,
        )
        hodo_u = hodo_u.to("knots").magnitude
        hodo_v = hodo_v.to("knots").magnitude
        hodo_keep = (hodo_height >= 0) & (hodo_height <= 12000)
        hodo_height = hodo_height[hodo_keep]
        hodo_u = hodo_u[hodo_keep]
        hodo_v = hodo_v[hodo_keep]
        hodo_order = np.argsort(hodo_height)
        hodo_height = hodo_height[hodo_order]
        hodo_u = hodo_u[hodo_order]
        hodo_v = hodo_v[hodo_order]

        if hodo_height.size >= 4:
            component_peak = np.nanpercentile(np.abs(np.concatenate((hodo_u, hodo_v))), 98)
            component_range = max(40, int(np.ceil(component_peak / 20)) * 20)
            hodo_ax = skew.ax.inset_axes([0.035, 0.755, 0.21, 0.21], zorder=10)
            hodo_ax.set_facecolor((1, 1, 1, 0.92))
            hodo = Hodograph(hodo_ax, component_range=component_range)
            hodo.add_grid(increment=20, color="#64748b", linewidth=0.55, alpha=0.55)
            hodo.plot_colormapped(hodo_u, hodo_v, hodo_height, cmap="turbo", linewidth=2.2)
            for marker_km in (1, 3, 6, 9):
                marker_height = marker_km * 1000
                if marker_height > hodo_height[-1]:
                    continue
                marker_u = np.interp(marker_height, hodo_height, hodo_u)
                marker_v = np.interp(marker_height, hodo_height, hodo_v)
                hodo_ax.plot(marker_u, marker_v, marker="o", markersize=2.6, color="#111827")
                hodo_ax.annotate(
                    str(marker_km), (marker_u, marker_v), xytext=(3, 2),
                    textcoords="offset points", fontsize=5, color="#111827",
                )
            hodo_ax.tick_params(labelsize=5, length=1.5, pad=1)
            hodo_ax.set_title("Hodograph (kt)", fontsize=7, pad=1)
            for spine in hodo_ax.spines.values():
                spine.set_color("#475569")
                spine.set_linewidth(0.8)
    except Exception:
        pass

    fig.canvas.draw()

    # Build the interactive-plot geometry by running MetPy's already-computed
    # curves (dry/moist adiabats, mixing lines, the observed profile, parcel
    # paths) through this axes' transData -- see _transform_xy for why.
    transform = skew.ax.transData
    xlim = skew.ax.get_xlim()
    ylim = skew.ax.get_ylim()
    bbox = skew.ax.get_window_extent()

    interactive = {
        "dry_adiabats": _segments_pixel(dry_collection, transform),
        "moist_adiabats": _segments_pixel(moist_collection, transform),
        "mixing_lines": _segments_pixel(mixing_collection, transform),
        "frame": {
            "x0": float(bbox.x0), "x1": float(bbox.x1),
            "y0": float(bbox.y0), "y1": float(bbox.y1),
        },
    }

    isobars = []
    for level in (1000, 850, 700, 500, 400, 300, 250, 200, 150):
        xs, ys = _transform_xy(transform, [xlim[0], xlim[1]], [level, level])
        isobars.append({"p": level, "x0": xs[0], "x1": xs[1], "y": ys[0]})
    interactive["isobars"] = isobars

    isotherms = []
    for temp_c in range(-40, 41, 10):
        xs, ys = _transform_xy(transform, [temp_c, temp_c], [ylim[0], ylim[1]])
        isotherms.append({"t": temp_c, "x0": xs[0], "y0": ys[0], "x1": xs[1], "y1": ys[1]})
    interactive["isotherms"] = isotherms

    # MetPy's dry/moist adiabat & mixing-line collections are already
    # bounded to the axes' ylim (they're computed from p=linspace(*ylim)),
    # and so is the static PNG (matplotlib clips drawing to the axes box
    # automatically). But these next few traces are built straight from the
    # observed profile/parcel arrays, which usually extend well above our
    # 150 hPa display cutoff -- and since we hand Plotly raw pixel numbers
    # with no axes of its own to clip to, an unmasked point above the
    # cutoff would just push Plotly's autorange up past it, making the grid
    # appear to stop at 150 hPa while the data lines keep going. So mask
    # every one of them to the plotted pressure range first.
    def _within_plot(pressures):
        pressures = np.asarray(pressures, dtype=float)
        return (pressures >= ylim[1]) & (pressures <= ylim[0])

    plot_mask = _within_plot(arr[:, 0])
    env_x, env_y = _transform_xy(transform, arr[plot_mask, 2], arr[plot_mask, 0])
    interactive["temperature"] = {
        "x": env_x, "y": env_y,
        "p": _clean_list(arr[plot_mask, 0]), "t": _clean_list(arr[plot_mask, 2]),
        "h": _clean_list(arr[plot_mask, 1]), "wd": _clean_list(arr[plot_mask, 4]), "ws": _clean_list(arr[plot_mask, 5]),
    }
    dew_x, dew_y = _transform_xy(transform, arr[plot_mask, 3], arr[plot_mask, 0])
    interactive["dewpoint"] = {
        "x": dew_x, "y": dew_y,
        "p": _clean_list(arr[plot_mask, 0]), "td": _clean_list(arr[plot_mask, 3]),
    }

    interactive["surface_parcel"] = None
    if surface_parcel_geo is not None:
        parcel_mask = _within_plot(surface_parcel_geo["p_raw"])
        px, py = _transform_xy(
            transform, surface_parcel_geo["t_raw"][parcel_mask], surface_parcel_geo["p_raw"][parcel_mask],
        )
        lcl_x, lcl_y = _transform_xy(
            transform, [surface_parcel_geo["lcl_t_raw"]], [surface_parcel_geo["lcl_p_raw"]],
        )
        interactive["surface_parcel"] = {
            "x": px, "y": py,
            "p": _clean_list(surface_parcel_geo["p_raw"][parcel_mask]),
            "t": _clean_list(surface_parcel_geo["t_raw"][parcel_mask]),
            "diff": _clean_list(surface_parcel_geo["diff_raw"][parcel_mask]),
            "lcl": {
                "x": lcl_x[0], "y": lcl_y[0],
                "p": _clean(surface_parcel_geo["lcl_p_raw"]),
                "t": _clean(surface_parcel_geo["lcl_t_raw"]),
            },
        }

    interactive["mixed_parcel"] = None
    if mixed_parcel_geo is not None:
        mixed_mask = _within_plot(mixed_parcel_geo["p_raw"])
        mx, my = _transform_xy(
            transform, mixed_parcel_geo["t_raw"][mixed_mask], mixed_parcel_geo["p_raw"][mixed_mask],
        )
        interactive["mixed_parcel"] = {
            "x": mx, "y": my,
            "p": _clean_list(mixed_parcel_geo["p_raw"][mixed_mask]),
            "t": _clean_list(mixed_parcel_geo["t_raw"][mixed_mask]),
        }

    interactive["dgz_rect"] = None
    if diagnostics["dgz_p_bottom"] is not None:
        _, y_bottom = _transform_xy(transform, [xlim[0]], [diagnostics["dgz_p_bottom"]])
        _, y_top = _transform_xy(transform, [xlim[0]], [diagnostics["dgz_p_top"]])
        interactive["dgz_rect"] = {
            "x0": float(bbox.x0), "x1": float(bbox.x1),
            "y0": y_bottom[0], "y1": y_top[0],
        }

    def _reference_line(label, color, height_agl):
        p_level = _agl_height_to_pressure(arr, height_agl)
        if p_level is None:
            return None
        xs, ys = _transform_xy(transform, [xlim[0], xlim[1]], [p_level, p_level])
        return {
            "label": label, "color": color, "p": _clean(p_level),
            "height_m": _clean(height_agl), "x0": xs[0], "x1": xs[1], "y": ys[0],
        }

    interactive["reference_lines"] = [
        line for line in (
            _reference_line("Freezing level", "#2563eb", melting["freezing_level_m"]),
            _reference_line("Wet-bulb zero", "#0891b2", melting["wet_bulb_zero_m"]),
            _reference_line("Snow level", "#db2777", melting["snow_level_m"]),
            _reference_line("Snow level (saturated column)", "#f9a8d4", melting_saturated["snow_level_m"]),
        )
        if line is not None
    ]

    skew_position = skew.ax.get_position()
    barb_left = skew_position.x1 + 0.012
    barb_width = 0.07
    advection_left = barb_left + barb_width + 0.012
    advection_width = max(0.11, 0.98 - advection_left)

    barb_ax = fig.add_axes([barb_left, skew_position.y0, barb_width, skew_position.height], sharey=skew.ax)
    barb_ax.set_xlim(0, 1)
    barb_ax.set_ylim(1050, 150)
    barb_ax.set_axis_off()
    for guide_pressure in np.arange(100, 1001, 100):
        barb_ax.axhline(guide_pressure, color="#94a3b8", linewidth=0.5, alpha=0.22)
    barb_ax.barbs(
        np.full(advection_p.shape, 0.5), advection_p,
        grid_u * 1.943844, grid_v * 1.943844,
        length=7.0, linewidth=1.05, pivot="middle",
        sizes={"emptybarb": 0.18, "spacing": 0.22, "height": 0.45},
    )

    advection_ax = fig.add_axes([advection_left, skew_position.y0, advection_width, skew_position.height], sharey=skew.ax)
    advection_ax.axvline(0, color="#475569", linewidth=0.8)
    if advection.size:
        advection_ax.plot(advection, advection_p, color="#334155", linewidth=1.0)
        advection_ax.fill_betweenx(
            advection_p, 0, advection, where=advection >= 0,
            color="#dc2626", alpha=0.72, interpolate=True,
        )
        advection_ax.fill_betweenx(
            advection_p, 0, advection, where=advection < 0,
            color="#2563eb", alpha=0.72, interpolate=True,
        )
        limit = max(0.1, float(np.nanpercentile(np.abs(advection), 95)) * 1.25)
        advection_ax.set_xlim(-limit, limit)
    else:
        advection_ax.text(
            0.5, 0.5, "Unavailable", transform=advection_ax.transAxes,
            ha="center", va="center", fontsize=9, color="#64748b",
        )
    advection_ax.set_ylim(1050, 150)
    advection_ax.tick_params(axis="y", labelleft=False, left=False)
    advection_ax.tick_params(axis="x", labelsize=8)
    advection_ax.grid(axis="y", alpha=0.2)
    advection_ax.set_title("Implied Temp\\nAdvection", fontsize=11)
    advection_ax.set_xlabel("°C/hr", fontsize=9)

    out = io.BytesIO()
    fig.savefig(out, format="png", bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)
    diagnostics.pop("dgz_p_bottom", None)
    diagnostics.pop("dgz_p_top", None)
    return json.dumps({
        "image": "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii"),
        "diagnostics": diagnostics,
        "interactive": interactive,
    })
`);
        state.pyodide = pyodide;
        return pyodide;
    })();
    return state.pyReady;
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
        wet_bulb_zero: aglText(values.wet_bulb_zero_m),
        melting_distance: values.total_melting_distance_m == null
            ? 'Unavailable' : formatHeightValue(values.total_melting_distance_m, units),
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

async function renderCycle(stationId, cycle, profile) {
    const requestId = state.activeRequest;
    els.cycleLabel.textContent = `Cycle: ${cycle.label}`;
    els.dataSource.href = `${IEM_RAOB_BASE}?ts=${cycle.timestamp}&station=${stationId}`;
    const meta = getStationMeta(stationId);
    if (meta.country === 'US') {
        els.spcSource.href = `${cycle.spcUrlStem}/${stationId}.gif`;
        els.spcSource.hidden = false;
    } else {
        els.spcSource.hidden = true;
    }

    const plotKey = `${stationId}|${cycle.timestamp}`;
    if (state.plotCache.has(plotKey)) {
        showPlot(stationId, cycle, state.plotCache.get(plotKey));
        return;
    }

    els.placeholder.textContent = `Rendering ${stationId} from ${cycle.label} with MetPy...`;
    els.placeholder.classList.add('is-visible');
    els.output.classList.remove('is-visible');
    els.plotContainer.classList.remove('is-visible');
    els.detailImage.classList.remove('is-visible');
    els.detailToggle.hidden = true;
    els.diagnostics.hidden = true;
    setStatus('Loading MetPy in the browser (first plot takes longest)...');

    try {
        const pyodide = await loadMetPy();
        if (requestId !== state.activeRequest) return;
        setStatus('Plotting with MetPy...');
        pyodide.globals.set('profile_json', JSON.stringify(profile));
        pyodide.globals.set('station_id', stationId);
        pyodide.globals.set('cycle_label', cycle.label);
        pyodide.globals.set('station_latitude', meta.lat);
        const resultJson = await pyodide.runPythonAsync(
            'make_skewt(profile_json, station_id, cycle_label, station_latitude)'
        );
        if (requestId !== state.activeRequest) return;
        const result = JSON.parse(resultJson);
        state.plotCache.set(plotKey, result);
        showPlot(stationId, cycle, result);
    } catch (error) {
        console.error('Skew-T rendering failed:', error);
        els.placeholder.textContent = `Plot rendering failed for ${stationId}.`;
        setStatus('Something went wrong plotting this sounding -- try another cycle or station.');
    } finally {
        els.older.disabled = false;
        els.newer.disabled = false;
    }
}

// Turns one polyline of pixel coordinates (as produced by _transform_xy /
// _segments_pixel in the Python above) into a low-key background Plotly
// trace -- used for dry/moist adiabats and mixing lines.
function backgroundLineTrace(line, color, opacity) {
    return {
        x: line.x, y: line.y, mode: 'lines',
        line: { color, width: 1 }, opacity,
        hoverinfo: 'skip', showlegend: false,
    };
}

function gridLineTrace(x0, y0, x1, y1) {
    return {
        x: [x0, x1], y: [y0, y1], mode: 'lines',
        line: { color: 'rgba(100,116,139,0.45)', width: 1, dash: 'dot' },
        hoverinfo: 'skip', showlegend: false,
    };
}

function buildSkewTraces(interactive, units) {
    const isImperial = units === 'imperial';
    const tempUnit = isImperial ? '°F' : '°C';
    const heightUnit = isImperial ? 'ft' : 'm';
    const speedUnit = isImperial ? 'mph' : 'kt';
    const convTemp = c => (c == null ? null : (isImperial ? UNITS.cToF(c) : c));
    const convDeltaTemp = c => (c == null ? null : (isImperial ? UNITS.cDeltaToF(c) : c));
    const convHeight = m => (m == null ? null : (isImperial ? UNITS.mToFt(m) : m));
    const convSpeed = kt => (kt == null ? null : (isImperial ? UNITS.ktToMph(kt) : kt));

    const traces = [];
    (interactive.dry_adiabats || []).forEach(line => traces.push(backgroundLineTrace(line, '#f4a261', 0.55)));
    (interactive.moist_adiabats || []).forEach(line => traces.push(backgroundLineTrace(line, '#2a9d8f', 0.55)));
    (interactive.mixing_lines || []).forEach(line => traces.push(backgroundLineTrace(line, '#94a3b8', 0.4)));

    (interactive.isobars || []).forEach(bar => traces.push(gridLineTrace(bar.x0, bar.y, bar.x1, bar.y)));
    (interactive.isotherms || []).forEach(iso => traces.push(gridLineTrace(iso.x0, iso.y0, iso.x1, iso.y1)));

    const temp = interactive.temperature;
    traces.push({
        x: temp.x, y: temp.y, mode: 'lines', name: 'Temperature',
        line: { color: '#d95f02', width: 2.5 },
        customdata: temp.p.map((p, i) => [p, convTemp(temp.t[i]), convHeight(temp.h[i]), temp.wd[i], convSpeed(temp.ws[i])]),
        hovertemplate: `%{customdata[0]:.0f} hPa (%{customdata[2]:.0f} ${heightUnit})<br>` +
            `Temp: %{customdata[1]:.1f}${tempUnit}<br>Wind: %{customdata[3]:.0f}° @ %{customdata[4]:.0f} ${speedUnit}<extra>Temperature</extra>`,
    });

    const dew = interactive.dewpoint;
    traces.push({
        x: dew.x, y: dew.y, mode: 'lines', name: 'Dew point',
        line: { color: '#1b9e77', width: 2.5 },
        customdata: dew.p.map((p, i) => [p, convTemp(dew.td[i])]),
        hovertemplate: `%{customdata[0]:.0f} hPa<br>Dew point: %{customdata[1]:.1f}${tempUnit}<extra>Dew point</extra>`,
    });

    if (interactive.surface_parcel) {
        const sp = interactive.surface_parcel;
        traces.push({
            x: sp.x, y: sp.y, mode: 'lines', name: 'Surface parcel',
            line: { color: '#7570b3', width: 2, dash: 'dash' },
            customdata: sp.p.map((p, i) => [p, convTemp(sp.t[i]), convDeltaTemp(sp.diff[i])]),
            hovertemplate: `%{customdata[0]:.0f} hPa<br>Parcel: %{customdata[1]:.1f}${tempUnit}<br>` +
                `%{customdata[2]:+.1f}${tempUnit} vs. environment<extra>Surface parcel</extra>`,
        });
        if (sp.lcl) {
            traces.push({
                x: [sp.lcl.x], y: [sp.lcl.y], mode: 'markers', name: 'LCL',
                marker: { color: '#7570b3', size: 8, symbol: 'circle' },
                customdata: [[sp.lcl.p, convTemp(sp.lcl.t)]],
                hovertemplate: `LCL: %{customdata[0]:.0f} hPa, %{customdata[1]:.1f}${tempUnit}<extra></extra>`,
            });
        }
    }

    if (interactive.mixed_parcel) {
        const mp = interactive.mixed_parcel;
        traces.push({
            x: mp.x, y: mp.y, mode: 'lines', name: '100-hPa mixed parcel',
            line: { color: '#7570b3', width: 1.5, dash: 'dot' },
            customdata: mp.p.map((p, i) => [p, convTemp(mp.t[i])]),
            hovertemplate: `%{customdata[0]:.0f} hPa<br>Mixed parcel: %{customdata[1]:.1f}${tempUnit}<extra>Mixed parcel</extra>`,
        });
    }

    (interactive.reference_lines || []).forEach(line => {
        const cd = [convHeight(line.height_m), line.p];
        traces.push({
            x: [line.x0, line.x1], y: [line.y, line.y], mode: 'lines', name: line.label,
            line: { color: line.color, width: 2.2, dash: 'dash' },
            customdata: [cd, cd],
            hovertemplate: `${line.label}: %{customdata[0]:.0f} ${heightUnit} AGL (%{customdata[1]:.0f} hPa)<extra></extra>`,
        });
    });

    return traces;
}

function buildSkewLayout(interactive, title) {
    const shapes = [];
    if (interactive.dgz_rect) {
        const rect = interactive.dgz_rect;
        shapes.push({
            type: 'rect', xref: 'x', yref: 'y',
            x0: rect.x0, x1: rect.x1, y0: rect.y0, y1: rect.y1,
            fillcolor: '#56b4e9', opacity: 0.16, line: { width: 0 }, layer: 'below',
        });
    }

    const annotations = (interactive.isobars || []).map(bar => ({
        x: bar.x0, y: bar.y, xanchor: 'right', yanchor: 'middle', xshift: -4,
        text: `${bar.p}`, showarrow: false, font: { size: 10, color: '#64748b' },
    })).concat((interactive.isotherms || []).map(iso => ({
        x: iso.x0, y: iso.y0, xanchor: 'center', yanchor: 'top', yshift: -4,
        text: `${iso.t}°`, showarrow: false, font: { size: 10, color: '#64748b' },
    })));

    return {
        title: { text: title, font: { size: 13 } },
        margin: { l: 45, r: 20, t: 36, b: 30 },
        xaxis: { visible: false, fixedrange: false },
        yaxis: { visible: false, fixedrange: false, scaleanchor: 'x', scaleratio: 1 },
        shapes,
        annotations,
        hovermode: 'closest',
        showlegend: true,
        legend: { orientation: 'h', y: -0.03, font: { size: 10 } },
        plot_bgcolor: '#ffffff',
        paper_bgcolor: '#ffffff',
    };
}

function renderInteractivePlot(stationId, cycle, interactive, units) {
    const traces = buildSkewTraces(interactive, units);
    const layout = buildSkewLayout(interactive, `${stationId} Observed Sounding — ${cycle.label}`);
    const config = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'] };
    Plotly.react(els.plotContainer, traces, layout, config);
}

function showPlot(stationId, cycle, result) {
    state.current = { stationId, cycle, result };
    els.placeholder.classList.remove('is-visible');

    if (result.interactive && window.Plotly) {
        try {
            renderInteractivePlot(stationId, cycle, result.interactive, state.units);
            els.plotContainer.classList.add('is-visible');
            els.output.classList.remove('is-visible');
        } catch (error) {
            console.error('Interactive skew-T rendering failed, falling back to static image:', error);
            els.plotContainer.classList.remove('is-visible');
            els.output.src = result.image;
            els.output.alt = `MetPy skew-T plot for ${stationId} at ${cycle.label}`;
            els.output.classList.add('is-visible');
        }
    } else {
        els.plotContainer.classList.remove('is-visible');
        els.output.src = result.image;
        els.output.alt = `MetPy skew-T plot for ${stationId} at ${cycle.label}`;
        els.output.classList.add('is-visible');
    }

    els.detailImage.src = result.image;
    els.detailImage.classList.remove('is-visible');
    els.detailToggle.hidden = false;
    els.detailToggle.textContent = 'Show full analysis (hodograph, wind barbs, thermal advection)';

    renderDiagnostics(result.diagnostics, state.units);
    setStatus(`Showing ${stationId} from ${cycle.label}.`);
    els.older.disabled = false;
    els.newer.disabled = false;
}

// --- History trend chart (freezing level / wet-bulb zero / snow level) ----
// Fetches the small, bot-updated JSON asset that scripts/collect_radiosonde_history.py
// appends to on a schedule (see .github/workflows/radiosonde_history.yml),
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
        { key: 'wet_bulb_zero_m', name: 'Wet-bulb zero', color: '#0891b2' },
        { key: 'snow_level_m', name: 'Snow level', color: '#db2777' },
        { key: 'snow_level_saturated_m', name: 'Snow level (saturated)', color: '#f9a8d4' },
    ];
    return series.map(series_item => ({
        x, y: entries.map(entry => conv(entry[series_item.key])),
        mode: 'lines+markers', name: series_item.name,
        line: { color: series_item.color, width: 2 }, marker: { size: 5 },
        connectgaps: false,
        hovertemplate: `%{x|%b %d %HZ}<br>${series_item.name}: %{y:.0f} ${heightUnit} AGL<extra></extra>`,
    }));
}

function renderHistoryChart(stationId) {
    if (!els.historyPlot || !window.Plotly) return;
    loadHistory().then(data => {
        const entries = data && data.stations && data.stations[stationId];
        if (!entries || !entries.length) {
            els.historyPlot.classList.remove('is-visible');
            if (els.historyEmpty) els.historyEmpty.hidden = false;
            return;
        }
        if (els.historyEmpty) els.historyEmpty.hidden = true;

        const traces = buildHistoryTraces(entries, state.units);
        const now = new Date();
        const twoDaysAgo = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);
        const layout = {
            margin: { l: 55, r: 15, t: 10, b: 40 },
            xaxis: { type: 'date', range: [twoDaysAgo.toISOString(), now.toISOString()] },
            yaxis: { title: state.units === 'imperial' ? 'Feet AGL' : 'Meters AGL' },
            legend: { orientation: 'h', y: -0.2 },
            hovermode: 'closest',
        };
        Plotly.react(els.historyPlot, traces, layout, { responsive: true, displaylogo: false });
        els.historyPlot.classList.add('is-visible');
    });
}
