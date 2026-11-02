"""Pre-render the radiosonde skew-T composites (MetPy) so the page does not have to run Python in the browser.

    python scripts/radiosonde_skewt.py                  # all stations, newest cycles
    python scripts/radiosonde_skewt.py --station UIL    # one station
    python scripts/radiosonde_skewt.py --force          # re-render cycles already on disk

Data: Iowa State's IEM RAOB JSON API. For each station this walks back through 6-hourly cycles and renders the newest
KEEP cycles that have data (the 00Z/12Z launches; Port Hardy lags by days), writing
    assets/data/radiosonde/<STATION>/<YYYYMMDDHH00>.png
    assets/data/radiosonde/manifest.json   (cycles and diagnostics per station, newest first, read by assets/radiosonde.js)
Cycles that fall out of the KEEP window are deleted. A cycle already rendered is skipped, so this is cheap to run often.

The plotting code was moved here from the Pyodide string that used to live in assets/radiosonde.js.
"""
import argparse
import io
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from PIL import Image

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
_MELT_GRID_STEP_M = 5.0         # m, vertical resolution of the integration grid
_MELT_ENSEMBLE_DIAMETERS_MM = (1.5, 3.0, 5.0)  # small / medium / large snowflakes, mm
_AIR_KINEMATIC_VISCOSITY = 1.4e-5  # m^2/s, air near 0 C -- for the Reynolds number below

# A flat ventilation factor (C_vent=1.2) tuned to a flat 1 m/s fall speed
# for every size badly under-melts for maritime PNW snow: larger, more
# aggregated/rimed flakes both fall faster AND get more ventilation-
# enhanced heat transfer than small pristine crystals, and the model's own
# original spec offered exactly this as the more physical alternative
# (C_vent = 1.0 + 0.23*Re^0.5) to the flat baseline. So each ensemble
# member gets its own fall speed (increasing with size, representative of
# aggregated/moderately rimed snow rather than a literature-precise fit)
# and its own Reynolds-number-based ventilation coefficient. Tested
# against a synthetic sounding shaped like a reported real case: this
# takes the medium flake's melting distance from 925 m down to 540 m, and
# turns a "never fully melts by the surface" dry-column result into a
# snow level 465 m above the surface -- a meaningfully faster, more
# PNW-appropriate melt than the flat-1.2 baseline, without melting
# implausibly fast either.
_MELT_FALL_SPEEDS_MS = (1.0, 1.5, 2.2)  # small / medium / large, m/s


def _saturation_vapor_pressure_hpa(t_c):
    # Magnus-Tetens approximation.
    return 6.112 * np.exp(17.62 * t_c / (243.12 + t_c))


def _relative_humidity_pct(t_c, td_c):
    return 100.0 * _saturation_vapor_pressure_hpa(td_c) / _saturation_vapor_pressure_hpa(t_c)


def _wet_bulb_stull(t_c, rh_pct):
    # Stull, R., 2011: "Wet-Bulb Temperature from Relative Humidity and Air
    # Temperature," J. Appl. Meteor. Climatol., 50, 2267-2269. An empirical
    # fit (found via gene-expression programming, not a physical
    # derivation) valid for 5-99% RH and -20 to 50 C, accurate to within
    # about +-1 C (mean absolute error ~0.3 C) without needing to solve the
    # psychrometric equation iteratively. We replaced a flat "Tw = T -
    # (T-Td)/3" proxy with this: that fixed 1/3 fraction understates the
    # true wet-bulb depression across the whole 0-20 C range relevant to a
    # melting layer (checked against the linearized psychrometric equation
    # -- the true (T-Tw)/(T-Td) ratio runs ~0.4-0.7 there, not 0.33), which
    # would bias the wet-bulb-zero height too high. RH is clamped to
    # Stull's validated range since this is an empirical fit, not a
    # physical law -- extrapolating outside it isn't reliable. Note the
    # arctangents are in radians (verified against Stull's own published
    # T=20C/RH=50%->Tw=13.699C reference case), not degrees. Widened
    # slightly past the documented 5-99% range at the saturated end
    # (RH=100 is common and physically important for a cloudy/precipitating
    # layer, and the formula stays smooth right up to it -- checked against
    # a T=0/RH=100 case, which should give exactly Tw=0 and gives -0.13 C)
    # so a fully saturated column's wet-bulb-zero comes out exactly equal
    # to its freezing level, as it should by construction, rather than a
    # clipping artifact leaving a small gap between them.
    rh_pct = np.clip(rh_pct, 1.0, 100.0)
    return (
        t_c * np.arctan(0.151977 * (rh_pct + 8.313659) ** 0.5)
        + np.arctan(t_c + rh_pct)
        - np.arctan(rh_pct - 1.676331)
        + 0.00391838 * rh_pct ** 1.5 * np.arctan(0.023101 * rh_pct)
        - 4.686035
    )


def _build_tw_profile(arr):
    """Shared prep for both the melting-layer and precip-type diagnostics:
    dedupes/sorts by height, converts to AGL, interpolates onto a uniform
    5-m grid, and computes Tw via Stull's formula. Returns None if the
    profile doesn't support it, otherwise (grid_m, t_grid, tw_grid)."""
    height_mask = np.isfinite(arr[:, 1])
    if np.count_nonzero(height_mask) < 6:
        return None

    heights = arr[height_mask, 1]
    temps = arr[height_mask, 2]
    dewpoints = arr[height_mask, 3]
    order = np.argsort(heights)
    heights, temps, dewpoints = heights[order], temps[order], dewpoints[order]
    _, unique_idx = np.unique(heights, return_index=True)
    heights, temps, dewpoints = heights[unique_idx], temps[unique_idx], dewpoints[unique_idx]

    heights_agl = heights - heights[0]
    if heights_agl.size < 6 or heights_agl[-1] < 50:
        return None

    # Interpolate to a high-resolution grid for numerical stability, then
    # compute wet-bulb temperature via Stull's (2011) empirical formula
    # (see _wet_bulb_stull) rather than solving the psychrometric equation
    # iteratively.
    grid = np.arange(0.0, heights_agl[-1] + _MELT_GRID_STEP_M, _MELT_GRID_STEP_M)
    t_grid = np.interp(grid, heights_agl, temps)
    td_grid = np.interp(grid, heights_agl, dewpoints)
    rh_grid = _relative_humidity_pct(t_grid, td_grid)
    tw_grid = _wet_bulb_stull(t_grid, rh_grid)
    return grid, t_grid, tw_grid


def compute_melting_layer(arr):
    """Estimate the freezing level, wet-bulb-zero height, and true snow
    level from one sounding, using the melting model described above.

    Heights are reported in meters AGL (above the sounding's lowest
    reported level). Returns a dict of Nones (with an explanatory "note")
    if the profile doesn't support the calculation -- e.g. an entirely
    sub-freezing column, one with no sub-cloud melting layer at all, or a
    "warm nose" profile (see below) that this surface-based model isn't
    designed for.
    """
    result = {
        "freezing_level_m": None,
        "wet_bulb_zero_m": None,
        "snow_level_m": None,
        "total_melting_distance_m": None,
        "note": None,
    }

    profile = _build_tw_profile(arr)
    if profile is None:
        result["note"] = "Not enough height data in this sounding to estimate a melting layer."
        return result
    grid, t_grid, tw_grid = profile

    # This model assumes exactly one melting transition as you descend --
    # snow up top, and it either fully melts by the surface or it doesn't.
    # A "warm nose" profile (sub-freezing surface with a melting layer
    # aloft, e.g. sleet or freezing rain setups) breaks that assumption:
    # searching bottom-up for the first freezing crossing would just hit
    # the already-sub-freezing surface and report a meaningless 0 m for
    # everything. Detect that case explicitly rather than guess.
    if t_grid[0] <= 0.0 and np.any(t_grid > 0.0):
        result["note"] = (
            "This sounding has a warm layer aloft over sub-freezing surface air (a 'warm nose') -- "
            "sleet or freezing rain territory. This model assumes melting happens near the surface and "
            "doesn't apply well here; see the Surface Precipitation Type diagnostic instead."
        )
        return result

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
    # equation above. Each ensemble member has its own fall speed, so it
    # also has its own dt (= dz / that member's fall speed) and its own
    # Reynolds-number-based ventilation coefficient.
    diameters_m = np.array([d / 1000.0 for d in _MELT_ENSEMBLE_DIAMETERS_MM])
    radii0 = diameters_m / 2.0
    radii = radii0.copy()
    total_volume0 = float(np.sum(radii0 ** 3))
    fall_speed = np.array(_MELT_FALL_SPEEDS_MS)
    dt = _MELT_GRID_STEP_M / fall_speed
    reynolds = fall_speed * diameters_m / _AIR_KINEMATIC_VISCOSITY
    c_vent = 1.0 + 0.23 * np.sqrt(reynolds)
    melted_height = np.full(radii.shape, np.nan)
    snow_level = None

    for i in range(wbz_idx, -1, -1):
        tw = max(0.0, float(tw_grid[i]))
        if tw > 0.0:
            safe_radii = np.maximum(radii, 1e-9)  # avoid divide-by-zero for already-melted flakes
            rate = (c_vent * _MELT_K_EFF * tw) / (_MELT_RHO_SNOW * _MELT_LATENT_FUSION * safe_radii)
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
        snow_level = float(grid[0])
        if wbz_idx > 0:
            # There was a real melting layer above the surface (surface Tw
            # > 0), and the ensemble still didn't finish melting by the
            # time it reached the ground -- worth flagging explicitly.
            result["note"] = (
                "The snowflake ensemble was not fully melted by the surface in this model -- "
                "snow may be reaching the ground despite above-freezing surface air."
            )
        # else: wbz_idx == 0 means the wet-bulb-zero is already at the
        # surface (Tw <= 0 at ground level) -- melting never had any room
        # to occur at all, which is just the normal, unremarkable outcome
        # for a straightforward all-below-freezing snow profile. No note
        # needed (and claiming "above-freezing surface air" here would be
        # false, since the surface is at or below freezing by definition
        # of reaching this branch with wbz_idx == 0).
    result["snow_level_m"] = snow_level

    medium_melted_height = melted_height[1]  # index 1 = medium (3.0 mm) flake
    if np.isfinite(medium_melted_height):
        result["total_melting_distance_m"] = float(result["wet_bulb_zero_m"] - medium_melted_height)
    elif wbz_idx == 0:
        # Same trivial case as above -- no melting layer existed at all, so
        # of course the medium flake didn't melt either. Not worth a note.
        result["total_melting_distance_m"] = 0.0
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
    """Render one sounding. Returns (png_bytes, diagnostics)."""
    arr = parse_iem_profile(profile_json)
    p = arr[:, 0] * units.hPa
    t = arr[:, 2] * units.degC
    td = arr[:, 3] * units.degC
    diagnostics = calculate_diagnostics(arr, p, t, td)
    melting = compute_melting_layer(arr)
    diagnostics["freezing_level_m"] = melting["freezing_level_m"]
    diagnostics["wet_bulb_zero_m"] = melting["wet_bulb_zero_m"]
    diagnostics["snow_level_m"] = melting["snow_level_m"]
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
            f"The air below the clouds looks quite dry here, which is why the Modeled snow level "
            f"({int(round(saturation_gap))} m lower than the Saturated Column estimate) looks so low: "
            "a falling snowflake in dry air loses moisture to its surroundings (sublimates) instead of "
            "warming up and melting, so it survives much closer to the ground. Once it's actually been "
            "snowing or raining for a while, that dry layer moistens up and the real snow level should "
            "sit closer to the Saturated Column number instead."
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
        ("Snow level (saturated column)", "#f9a8d4", melting_saturated["snow_level_m"]),
        ("Snow level (modeled)", "#db2777", melting["snow_level_m"]),
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
    advection_ax.set_title("Implied Temp\nAdvection", fontsize=11)
    advection_ax.set_xlabel("°C/hr", fontsize=9)

    out = io.BytesIO()
    fig.savefig(out, format="png", bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)
    out.seek(0)
    small = io.BytesIO()   # palette-quantize: ~3x smaller files, no visible change on line art
    Image.open(out).convert("RGB").quantize(128, dither=Image.Dither.NONE).save(small, "PNG", optimize=True)
    out = small
    diagnostics.pop("dgz_p_bottom", None)
    diagnostics.pop("dgz_p_top", None)
    return out.getvalue(), diagnostics


# ---------------------------------------------------------------- driver
IEM_RAOB_BASE = "https://mesonet.agron.iastate.edu/json/raob.py"
HEADERS = {"User-Agent": "cascade-mountain-weather.github.io skew-T render (dlhogan@uw.edu)"}
OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "data" / "radiosonde"
KEEP = 8   # cycles kept per station: four days of 00Z/12Z launches
STATIONS = {   # id: (name, latitude, max 6-hourly steps to look back for KEEP cycles)
    "UIL": ("Quillayute, WA", 47.95, 28),
    "SLE": ("Salem, OR", 44.91, 28),
    "OTX": ("Spokane, WA", 47.70, 28),
    "CYZT": ("Port Hardy, BC", 50.68, 64),   # the feed lags Canadian sites by 4-5 days
}


def fetch_profile(station, ts, tries=3):
    """IEM profile rows for one cycle, or None if there is no sounding."""
    for attempt in range(tries):
        try:
            r = requests.get(IEM_RAOB_BASE, params={"ts": ts, "station": station}, headers=HEADERS, timeout=30)
            r.raise_for_status()
            profiles = r.json().get("profiles") or []
            if profiles and isinstance(profiles[0].get("profile"), list) and len(profiles[0]["profile"]) >= 6:
                return profiles[0]["profile"]
            return None
        except (requests.RequestException, ValueError):
            time.sleep(2 * (attempt + 1))
    return None


def cycle_list(steps):
    now = datetime.now(timezone.utc)
    latest = now.replace(hour=now.hour // 6 * 6, minute=0, second=0, microsecond=0)
    return [latest - timedelta(hours=6 * i) for i in range(steps + 1)]


def run_station(station, force, previous):
    name, lat, steps = STATIONS[station]
    sdir = OUT_DIR / station
    sdir.mkdir(parents=True, exist_ok=True)
    old = {c["cycle"]: c for c in previous}

    entries = []
    for cyc in cycle_list(steps):
        if len(entries) >= KEEP:
            break
        ts = cyc.strftime("%Y%m%d%H00")
        png = sdir / f"{ts}.png"
        if ts in old and png.exists() and not force:
            entries.append(old[ts])
            continue
        profile = fetch_profile(station, ts)
        time.sleep(0.3)
        if not profile:
            continue
        label = cyc.strftime("%Y-%m-%d %HZ")
        try:
            png_bytes, diagnostics = make_skewt(json.dumps(profile), station, label, lat)
        except Exception as exc:   # one bad sounding must not block the rest
            print(f"{station} {label}: render failed ({exc})", file=sys.stderr)
            continue
        png.write_bytes(png_bytes)
        print(f"{station} {label}: rendered ({len(png_bytes) // 1024} kB)")
        entries.append({"cycle": ts, "label": label, "image": f"{station}/{ts}.png", "diagnostics": diagnostics})

    keep = {e["image"].split("/")[1] for e in entries}
    for stale in sdir.glob("*.png"):
        if stale.name not in keep:
            stale.unlink()
    return entries


def main():
    ap = argparse.ArgumentParser(description="Pre-render radiosonde skew-T composites.")
    ap.add_argument("--station", choices=sorted(STATIONS), help="only this station")
    ap.add_argument("--force", action="store_true", help="re-render cycles already on disk")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT_DIR / "manifest.json"
    before = {}
    if manifest_path.exists():
        before = json.loads(manifest_path.read_text("utf-8")).get("stations", {})
    stations = dict(before)
    for station in ([args.station] if args.station else STATIONS):
        stations[station] = run_station(station, args.force, before.get(station, []))

    # leave the file untouched when nothing changed, so the bot has nothing to commit
    if stations != before:
        manifest = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stations": stations}
        manifest_path.write_text(json.dumps(manifest, separators=(",", ":")), "utf-8")


if __name__ == "__main__":
    main()
