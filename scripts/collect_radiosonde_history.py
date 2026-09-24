#!/usr/bin/env python3
"""Collect a rolling history of freezing-level / wet-bulb-zero / snow-level
diagnostics from observed radiosonde soundings, for the trend chart on the
Skew-T tool page (tools/radiosonde.html).

Run on a schedule (see .github/workflows/radiosonde_history.yml). Every run
re-checks a recent window of launch cycles per station (idempotent -- a
cycle that lands late in IEM's feed still gets picked up on the next pass)
and merges any newly-available cycles into the stored history, then trims
everything to a retention window so the file doesn't grow forever.

This uses the same simplified Matsuo & Sasyo (1981) melting model as
assets/radiosonde.js's compute_melting_layer (see that file for the full
derivation and the reasoning behind the 1/R term in the melting-rate
equation). It's reimplemented here in plain numpy, rather than shared with
the Pyodide version, so this script has no heavy dependency (no
matplotlib/metpy/scipy) and the GitHub Actions job stays fast.

Never fabricates data: every recorded point comes from an actual IEM RAOB
API response for that station and cycle. A cycle with no data (including
the well-documented KOTX/Spokane gap and Port Hardy's multi-day feed lag --
see assets/radiosonde.js STATIONS notes) is simply skipped, not backfilled
or guessed at.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests

IEM_RAOB_BASE = "https://mesonet.agron.iastate.edu/json/raob.py"
HISTORY_PATH = Path("assets/data/radiosonde_history.json")
RETENTION_DAYS = 6  # kept server-side; the page defaults its chart view to the last 2

# Mirrors the STATIONS list in assets/radiosonde.js, but expressed in
# 12-hourly launch cycles (00Z/12Z) rather than the client tool's 6-hourly
# walk-back steps, since actual radiosonde launches only happen twice a day.
STATION_LOOKBACK_CYCLES = {
    "UIL": 8,    # 4 days of 00Z/12Z launches
    "SLE": 8,
    "OTX": 8,
    "CYZT": 28,  # ~14 days, to comfortably clear the observed 4-5 day feed lag
}

# --- Melting-layer model (see assets/radiosonde.js for the full writeup,
# including why each ensemble member gets its own fall speed and a
# Reynolds-number-based ventilation coefficient rather than one flat
# C_vent tuned to a flat 1 m/s -- that under-melts for maritime PNW snow).
_MELT_RHO_SNOW = 100.0
_MELT_LATENT_FUSION = 3.34e5
_MELT_K_EFF = 2.6e-2
_MELT_GRID_STEP_M = 5.0
_MELT_ENSEMBLE_DIAMETERS_MM = (1.5, 3.0, 5.0)
_MELT_FALL_SPEEDS_MS = (1.0, 1.5, 2.2)
_AIR_KINEMATIC_VISCOSITY = 1.4e-5


def compute_melting_layer(heights_m: np.ndarray, temps_c: np.ndarray, dewpoints_c: np.ndarray) -> dict:
    """Same model as assets/radiosonde.js's compute_melting_layer, operating
    on plain height/temperature/dewpoint arrays instead of the Pyodide
    tool's IEM row-array format. Returns freezing_level_m, wet_bulb_zero_m,
    snow_level_m, and total_melting_distance_m (all meters AGL), or Nones
    if the profile doesn't support the calculation.
    """
    result = {
        "freezing_level_m": None,
        "wet_bulb_zero_m": None,
        "snow_level_m": None,
        "total_melting_distance_m": None,
    }

    mask = np.isfinite(heights_m) & np.isfinite(temps_c) & np.isfinite(dewpoints_c)
    if np.count_nonzero(mask) < 6:
        return result

    heights, temps, dewpoints = heights_m[mask], temps_c[mask], dewpoints_c[mask]
    order = np.argsort(heights)
    heights, temps, dewpoints = heights[order], temps[order], dewpoints[order]
    _, unique_idx = np.unique(heights, return_index=True)
    heights, temps, dewpoints = heights[unique_idx], temps[unique_idx], dewpoints[unique_idx]

    heights_agl = heights - heights[0]
    if heights_agl.size < 6 or heights_agl[-1] < 50:
        return result

    grid = np.arange(0.0, heights_agl[-1] + _MELT_GRID_STEP_M, _MELT_GRID_STEP_M)
    t_grid = np.interp(grid, heights_agl, temps)
    td_grid = np.interp(grid, heights_agl, dewpoints)
    tw_grid = t_grid - (t_grid - td_grid) / 3.0  # simplified wet-bulb proxy

    if not np.any(t_grid <= 0.0):
        return result
    freezing_idx = int(np.argmax(t_grid <= 0.0))
    result["freezing_level_m"] = float(grid[freezing_idx])

    if not np.any(tw_grid <= 0.0):
        return result
    wbz_idx = int(np.argmax(tw_grid <= 0.0))
    result["wet_bulb_zero_m"] = float(grid[wbz_idx])

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
            safe_radii = np.maximum(radii, 1e-9)
            rate = (c_vent * _MELT_K_EFF * tw) / (_MELT_RHO_SNOW * _MELT_LATENT_FUSION * safe_radii)
            radii = np.maximum(0.0, radii - rate * dt)
        newly_melted = np.isnan(melted_height) & (radii <= 1e-9)
        melted_height[newly_melted] = grid[i]
        melted_fraction = 1.0 - (np.sum(radii ** 3) / total_volume0)
        if snow_level is None and melted_fraction >= 0.95:
            snow_level = float(grid[i])
        if np.all(radii <= 1e-9):
            break

    if snow_level is None:
        snow_level = float(grid[0])
    result["snow_level_m"] = snow_level

    medium_melted_height = melted_height[1]  # index 1 = medium (3.0 mm) flake
    if np.isfinite(medium_melted_height):
        result["total_melting_distance_m"] = float(result["wet_bulb_zero_m"] - medium_melted_height)
    else:
        result["total_melting_distance_m"] = float(result["wet_bulb_zero_m"] - grid[0])

    return result


def latest_completed_cycle(now: datetime) -> datetime:
    """Most recent synoptic launch hour (00Z or 12Z) that has already
    happened."""
    hour = 12 if now.hour >= 12 else 0
    return now.replace(hour=hour, minute=0, second=0, microsecond=0)


def fetch_profile(station: str, cycle_dt: datetime):
    ts = cycle_dt.strftime("%Y%m%d%H%M")
    try:
        resp = requests.get(IEM_RAOB_BASE, params={"ts": ts, "station": station}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 -- one bad cycle shouldn't kill the whole run
        print(f"  {station} {ts}: fetch failed ({exc})")
        return None

    profiles = data.get("profiles") or []
    if not profiles or not profiles[0].get("profile"):
        return None

    heights, temps, dewpoints = [], [], []
    for row in profiles[0]["profile"]:
        if row.get("hght") is None or row.get("tmpc") is None or row.get("dwpc") is None:
            continue
        heights.append(row["hght"])
        temps.append(row["tmpc"])
        dewpoints.append(row["dwpc"])

    if len(heights) < 6:
        return None
    return (
        np.array(heights, dtype=float),
        np.array(temps, dtype=float),
        np.array(dewpoints, dtype=float),
    )


def load_history() -> dict:
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Existing history file unreadable ({exc}), starting fresh.")
    return {"updated": None, "stations": {}}


def main() -> None:
    history = load_history()
    history.setdefault("stations", {})
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RETENTION_DAYS)

    for station, lookback_cycles in STATION_LOOKBACK_CYCLES.items():
        existing = {entry["cycle"]: entry for entry in history["stations"].get(station, [])}
        cycle = latest_completed_cycle(now)

        for _ in range(lookback_cycles):
            ts = cycle.strftime("%Y%m%d%H%M")
            profile = fetch_profile(station, cycle)
            if profile is not None:
                heights, temps, dewpoints = profile
                diagnostics = compute_melting_layer(heights, temps, dewpoints)
                # Sensitivity check: rerun assuming a fully saturated column
                # (dewpoint = temperature), approximating what the profile
                # would look like once sustained precipitation has
                # evaporatively cooled/moistened the sub-cloud air. See the
                # matching comment in assets/radiosonde.js's make_skewt.
                saturated = compute_melting_layer(heights, temps, temps)
                diagnostics["snow_level_saturated_m"] = saturated["snow_level_m"]
                existing[ts] = {
                    "cycle": ts,
                    "label": cycle.strftime("%Y-%m-%d %HZ"),
                    "valid": cycle.isoformat(),
                    **diagnostics,
                }
                print(
                    f"  {station} {ts}: ok (freezing={diagnostics['freezing_level_m']}, "
                    f"snow={diagnostics['snow_level_m']})"
                )
            cycle = cycle - timedelta(hours=12)

        kept = [
            entry for entry in existing.values()
            if datetime.fromisoformat(entry["valid"]) >= cutoff
        ]
        kept.sort(key=lambda entry: entry["cycle"])
        history["stations"][station] = kept

    history["updated"] = now.isoformat()
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")
    total = sum(len(v) for v in history["stations"].values())
    print(f"Wrote {HISTORY_PATH} ({total} total entries across {len(history['stations'])} stations)")


if __name__ == "__main__":
    main()
