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

const IEM_RAOB_BASE = 'https://mesonet.agron.iastate.edu/json/raob.py';
const PYODIDE_VERSION = 'v0.26.4';
const SPC_BASE = 'https://www.spc.noaa.gov/exper/archive/events';

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
    plotCache: new Map(),  // `${station}|${timestamp}` -> { image, diagnostics }
    station: STATIONS[0].id,
    displayedCycle: null,  // the cycle object currently shown
    activeRequest: 0,
};

const els = {};

document.addEventListener('DOMContentLoaded', () => {
    Object.assign(els, {
        stationButtons: document.getElementById('station-buttons'),
        older: document.getElementById('cycle-older'),
        newer: document.getElementById('cycle-newer'),
        cycleLabel: document.getElementById('selected-cycle'),
        status: document.getElementById('sounding-status'),
        stationNote: document.getElementById('station-note'),
        output: document.getElementById('skewt-output'),
        placeholder: document.getElementById('plot-placeholder'),
        diagnostics: document.getElementById('sounding-diagnostics'),
        dataSource: document.getElementById('data-source-link'),
        spcSource: document.getElementById('spc-source-link'),
    });

    if (!els.stationButtons || !els.output) return;

    renderStationButtons();
    els.older.addEventListener('click', () => stepCycle(-1));
    els.newer.addEventListener('click', () => stepCycle(1));

    selectStation(getStationRequestedInUrl() || state.station);
});

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
    els.older.disabled = true;
    els.newer.disabled = true;
    setStatus(`Looking for the most recent ${stationId} sounding...`);
    els.placeholder.classList.add('is-visible');
    els.placeholder.textContent = `Looking for the most recent ${stationId} sounding...`;
    els.output.classList.remove('is-visible');
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
    downdraft_cape,
    lcl,
    mixed_layer_cape_cin,
    mixed_parcel,
    most_unstable_cape_cin,
    most_unstable_parcel,
    parcel_profile,
    precipitable_water,
    surface_based_cape_cin,
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
        "sbcape": None,
        "dcape": None,
        "pw_mm": None,
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

    diagnostics["mucape"] = cape_value(lambda: most_unstable_cape_cin(p, t, td))
    diagnostics["mlcape"] = cape_value(lambda: mixed_layer_cape_cin(p, t, td))
    diagnostics["sbcape"] = cape_value(lambda: surface_based_cape_cin(p, t, td))
    diagnostics["dcape"] = cape_value(lambda: downdraft_cape(p, t, td))

    try:
        pw = precipitable_water(p, td)
        diagnostics["pw_mm"] = round(float(pw.to("mm").magnitude), 1)
    except Exception:
        pass

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


def make_skewt(profile_json, station, cycle_label, station_latitude):
    arr = parse_iem_profile(profile_json)
    p = arr[:, 0] * units.hPa
    t = arr[:, 2] * units.degC
    td = arr[:, 3] * units.degC
    diagnostics = calculate_diagnostics(arr, p, t, td)
    advection_p, advection, grid_u, grid_v = temperature_advection_profile(
        arr,
        station_latitude,
    )

    fig = plt.figure(figsize=(10.5, 9), dpi=150)
    skew = SkewT(fig, rotation=45, rect=(0.065, 0.055, 0.68, 0.91))
    skew.plot(p, t, color="#d95f02", linewidth=2.0, label="Temperature")
    skew.plot(p, td, color="#1b9e77", linewidth=2.0, label="Dew point")

    try:
        lcl_p, lcl_t = lcl(p[0], t[0], td[0])
        prof = parcel_profile(p, t[0], td[0]).to("degC")
        skew.plot(p, prof, color="#7570b3", linewidth=1.5, linestyle="--", label="Surface parcel")
        skew.ax.plot(lcl_t, lcl_p, marker="o", color="#7570b3", markersize=5)
    except Exception:
        pass

    try:
        _, mixed_t, mixed_td = mixed_parcel(p, t, td, depth=100 * units.hPa)
        mixed_prof = parcel_profile(p, mixed_t, mixed_td).to("degC")
        skew.plot(
            p, mixed_prof, color="#7570b3", linewidth=1.5, linestyle=":",
            label="100-hPa mixed parcel",
        )
    except Exception:
        pass

    skew.ax.set_ylim(1050, 100)
    skew.ax.set_xlim(-40, 45)
    skew.plot_dry_adiabats(alpha=0.35, linewidth=0.7)
    skew.plot_moist_adiabats(alpha=0.35, linewidth=0.7)
    skew.plot_mixing_lines(alpha=0.25, linewidth=0.7)
    if diagnostics["dgz_p_bottom"] is not None:
        skew.ax.axhspan(
            diagnostics["dgz_p_top"], diagnostics["dgz_p_bottom"],
            color="#56b4e9", alpha=0.14, label="DGZ (-12 to -18 C)",
        )
    skew.ax.axvline(0, color="#444444", linewidth=1.0)
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
    skew_position = skew.ax.get_position()
    barb_left = skew_position.x1 + 0.012
    barb_width = 0.07
    advection_left = barb_left + barb_width + 0.012
    advection_width = max(0.11, 0.98 - advection_left)

    barb_ax = fig.add_axes([barb_left, skew_position.y0, barb_width, skew_position.height], sharey=skew.ax)
    barb_ax.set_xlim(0, 1)
    barb_ax.set_ylim(1050, 100)
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
    advection_ax.set_ylim(1050, 100)
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
    })
`);
        state.pyodide = pyodide;
        return pyodide;
    })();
    return state.pyReady;
}

function renderDiagnostics(values) {
    const formatCape = value => (value == null ? 'Unavailable' : `${value} J/kg`);
    const diagnostics = {
        mucape: values.mucape == null ? 'Unavailable' : `${formatCape(values.mucape)} · ${values.mu_height ?? '—'} m AGL`,
        mlcape: formatCape(values.mlcape),
        sbcape: formatCape(values.sbcape),
        dcape: formatCape(values.dcape),
        pw: values.pw_mm == null ? 'Unavailable' : `${values.pw_mm} mm`,
        advection: values.advection,
        dgz: values.dgz,
    };
    els.diagnostics.querySelectorAll('[data-diagnostic]').forEach(element => {
        element.textContent = diagnostics[element.dataset.diagnostic] || 'Unavailable';
    });
    els.diagnostics.hidden = false;
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

function showPlot(stationId, cycle, result) {
    els.output.src = result.image;
    els.output.alt = `MetPy skew-T plot for ${stationId} at ${cycle.label}`;
    els.output.classList.add('is-visible');
    els.placeholder.classList.remove('is-visible');
    renderDiagnostics(result.diagnostics);
    setStatus(`Showing ${stationId} from ${cycle.label}.`);
    els.older.disabled = false;
    els.newer.disabled = false;
}
