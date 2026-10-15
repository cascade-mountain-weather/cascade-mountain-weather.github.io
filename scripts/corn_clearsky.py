"""Clear-sky shortwave engine for the corn model (PLAN.md, "Corn model: design", build step 3).

    python scripts/corn_clearsky.py --check          # self-test and sanity numbers, nothing written

For a forcing region and an elevation it returns clear-sky global, direct and diffuse irradiance on the horizontal for every
day of the corn season (Jan 1 to Jun 30) and every 30-minute window of the day, then transposes it to a tilted surface (slope
and aspect of a terrain class). Pure clear sky: clouds come later, as a scaling of this, so the two bounds in the plan (clear
and NBM-cloud-adjusted) share one engine.

Model choices (PLAN.md marks the clear-sky model as "verify"; this is the first pick, and --check prints how far the other
pvlib model is from it so the spread is visible):
  * solar position: pvlib NREL SPA, at the middle of each 30-minute window (UTC clock; the caller converts to local time);
  * clear sky: Ineichen-Perez with the pvlib Linke turbidity climatology and the site elevation (pressure from altitude);
    Simplified Solis (aod700 0.03 and 0.5 cm precipitable water placeholders, no sourced values) is the cross-check;
  * tilt: Hay-Davies sky diffuse plus a ground-reflected term. The ground albedo seen by a slope (nearby snow) is a
    PLACEHOLDER (ALBEDO_SURROUND); it is not the snow albedo of the energy balance, which comes from the snow model.
NOT included yet: horizon shading by surrounding terrain and the sky-view factor (they need the DEM and are a separate
step), the Sun's disk reaching a slope below the local horizon, and snow-covered-terrain multiple reflections.
Day indexing: a fixed non-leap reference year (REF_YEAR), so day-of-year arrays are year-independent. Solar position differs
by under a few hundredths of a degree between years.
"""
import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
import yaml

ROOT = Path(__file__).resolve().parent.parent
REF_YEAR = 2027
SEASON_DAYS = pd.date_range(f"{REF_YEAR}-01-01", f"{REF_YEAR}-06-30", freq="D")
STEP_MIN = 30
ALBEDO_SURROUND = 0.6      # placeholder for the reflected term on a tilted surface
SOLIS = dict(aod700=0.03, precipitable_water=0.5)   # placeholders for the cross-check model only


def window_times():
    """UTC window midpoints (:15 and :45 past each hour) for every day of the season."""
    step = pd.Timedelta(minutes=STEP_MIN)
    t0 = SEASON_DAYS[0].tz_localize("UTC") + step / 2
    return pd.date_range(t0, periods=len(SEASON_DAYS) * 48, freq=f"{STEP_MIN}min")


def horizontal(lat, lon, elev_m, model="ineichen", times=None):
    """Clear-sky GHI/DNI/DHI (W/m2) on the horizontal plus solar position, one row per window midpoint."""
    times = window_times() if times is None else times
    sp = pvlib.solarposition.get_solarposition(times, lat, lon, altitude=elev_m)
    pressure = pvlib.atmosphere.alt2pres(elev_m)
    if model == "ineichen":
        lt = pvlib.clearsky.lookup_linke_turbidity(times, lat, lon)
        am = pvlib.atmosphere.get_absolute_airmass(pvlib.atmosphere.get_relative_airmass(sp["apparent_zenith"]), pressure)
        cs = pvlib.clearsky.ineichen(sp["apparent_zenith"], am, lt, elev_m, pvlib.irradiance.get_extra_radiation(times))
    elif model == "solis":
        cs = pvlib.clearsky.simplified_solis(sp["apparent_elevation"], pressure=pressure, dni_extra=pvlib.irradiance.get_extra_radiation(times), **SOLIS)
    else:
        raise ValueError(model)
    out = cs[["ghi", "dni", "dhi"]].fillna(0.0).clip(lower=0.0)
    out["zenith"], out["azimuth"] = sp["zenith"], sp["azimuth"]
    out["dni_extra"] = pvlib.irradiance.get_extra_radiation(times)
    return out


def tilted(h, slope_deg, aspect_deg):
    """Clear-sky irradiance (W/m2) on a surface facing aspect_deg (compass direction it faces) at slope_deg. Columns: total, direct,
    diffuse, reflected. Flat (slope 0) returns the horizontal values."""
    poa = pvlib.irradiance.get_total_irradiance(
        slope_deg, aspect_deg, h["zenith"], h["azimuth"], h["dni"], h["ghi"], h["dhi"], dni_extra=h["dni_extra"],
        albedo=ALBEDO_SURROUND, model="haydavies")
    return poa.rename(columns={"poa_global": "total", "poa_direct": "direct", "poa_sky_diffuse": "diffuse", "poa_ground_diffuse": "reflected"})[
        ["total", "direct", "diffuse", "reflected"]].fillna(0.0)


def tilted_terrain(h, slope_deg, aspect_deg, vd, ct, horizon_deg, albedo=ALBEDO_SURROUND):
    """Like `tilted`, but with terrain: direct sun is blocked when the sun is below the horizon in its direction (horizon_deg is the 16
    horizon angles from data/corn/class_terrain_<box>.csv, 0 = north clockwise, linear in azimuth), sky diffuse is scaled by the share of
    the sky the surface sees (vd over its unobstructed value (1 + cos slope)/2), and the reflected term is the terrain configuration
    factor ct times `albedo` times the horizontal global irradiance (the surrounding terrain is assumed to receive what flat ground
    does: an upper bound, since shaded terrain reflects less). Columns as `tilted`."""
    base = tilted(h, slope_deg, aspect_deg)
    hz = np.asarray(horizon_deg, dtype=float)
    az = h["azimuth"].values
    hs = np.interp(az, np.append(np.arange(16) * 22.5, 360.0), np.append(hz, hz[0]))
    sun_up = (90.0 - h["zenith"].values) > hs
    unobstructed = (1 + math.cos(math.radians(slope_deg))) / 2
    out = pd.DataFrame(index=h.index)
    out["direct"] = np.where(sun_up, base["direct"].values, 0.0)
    out["diffuse"] = base["diffuse"].values * (vd / unobstructed)
    out["reflected"] = ct * albedo * h["ghi"].values
    out["total"] = out["direct"] + out["diffuse"] + out["reflected"]
    return out[["total", "direct", "diffuse", "reflected"]]


def daily_mj(series):
    """Daily total (MJ/m2) from a W/m2 series at STEP_MIN windows."""
    return series.groupby(series.index.date).sum() * STEP_MIN * 60 / 1e6


def check():
    regs = yaml.safe_load((ROOT / "data" / "corn" / "regions.yml").read_text(encoding="utf-8"))["regions"]
    r = next(x for x in regs if x["id"] == "paradise")
    elev = 1900.0  # about 6,200 ft, a typical corn elevation (Muir Snowfield area is higher; this is just a test point)
    print(f"test point: {r['name']} ({r['lat']}, {r['lon']}), {elev:.0f} m")
    hi = horizontal(r["lat"], r["lon"], elev, "ineichen")
    hs = horizontal(r["lat"], r["lon"], elev, "solis")
    # 1. reference: pvlib's own flat-ground call, same inputs
    times = hi.index
    sp = pvlib.solarposition.get_solarposition(times, r["lat"], r["lon"], altitude=elev)
    ref = pvlib.location.Location(r["lat"], r["lon"], altitude=elev).get_clearsky(times, model="ineichen")
    print(f"flat ground vs pvlib Location.get_clearsky, max |difference| in GHI: {np.abs(hi['ghi'] - ref['ghi']).max():.3f} W/m2")
    # 2. spot days: daily flat totals, Ineichen vs Solis
    print("\nDaily clear-sky GHI on flat ground (MJ/m2), and the Ineichen-Solis difference:")
    for d in ["2027-01-17", "2027-02-28", "2027-03-22", "2027-04-14", "2027-06-10", "2027-06-29"]:
        di, ds = daily_mj(hi["ghi"]), daily_mj(hs["ghi"])
        k = pd.Timestamp(d).date()
        print(f"  {d}  Ineichen {di[k]:5.1f}   Solis {ds[k]:5.1f}   difference {100 * (ds[k] - di[k]) / di[k]:+5.1f}%")
    # 3. slope and aspect behavior on a late-winter and a late-spring day
    for d in ["2027-02-28", "2027-06-10"]:
        k = pd.Timestamp(d).date()
        print(f"\nDaily total (MJ/m2) on {d} by slope and aspect (flat: {daily_mj(hi['ghi'])[k]:.1f}):")
        print("  slope  " + "  ".join(f"{a:>5s}" for a in ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]))
        for sl in (17.5, 30, 40):
            vals = [daily_mj(tilted(hi, sl, a)["total"])[k] for a in range(0, 360, 45)]
            print(f"  {sl:5.1f}  " + "  ".join(f"{v:5.1f}" for v in vals))
    # 4. peak-hour behavior
    k = pd.Timestamp("2027-03-22").date()
    day = hi[hi.index.date == k]
    s = tilted(day, 30, 180)["total"]
    print(f"\nMar 22, 30 deg S slope: peak {s.max():.0f} W/m2 at {s.idxmax().strftime('%H:%M')} UTC; flat peak {day['ghi'].max():.0f} W/m2 at {day['ghi'].idxmax().strftime('%H:%M')} UTC")
    print(f"energy check, Mar 22 flat: GHI - (DNI cos z + DHI) max abs = {np.abs(day['ghi'] - (day['dni'] * np.cos(np.radians(day['zenith'])).clip(lower=0) + day['dhi'])).max():.2f} W/m2")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="self-test and sanity numbers")
    args = ap.parse_args()
    if args.check:
        check()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
