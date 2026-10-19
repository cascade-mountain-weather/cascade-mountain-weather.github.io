"""Thin-layer surface energy balance for the corn model (PLAN.md, "Corn model: design", build step 4).

    python scripts/corn_energy.py --synthetic        # two-day run on made-up forcing, to check behavior (not a forecast)

The top 30 cm of snow in 1 cm layers: temperature and liquid water per layer (enthalpy bookkeeping), a bulk surface balance
solved for the surface temperature every minute, conduction between layers, melt and refreeze at 0 C. The surface balance
follows SNOWPACK (github.com/snowpack-model/snowpack, Source/snowpack/snowpack: Snowpack.cc updateBoundHeatFluxes,
Laws_sn.cc compSensibleHeatCoefficient / compLatentHeat, Meteo.cc RichardsonStability, MeteoIO Atmosphere.cc
Konzelmann_emissivity); only the surface balance is borrowed, not the full profile solver.

Parameters given by Danny (Oct 14 2026): albedo from 0.95 (fresh snow) down to a floor of 0.55 (raised Oct 15), decaying 2% a day and up to 3% a day as melt-freeze cycles accumulate; roughness length 0.25 mm (fresh) rising to 25 mm (old snow, sun cups), also a power law; conductivity of ice 2.2 W/m/K;
diffusion coefficient in air 22e-6 and in snow/ice 85e-6 (m2/s) (these two enter SNOWPACK's snow conductivity, which needs
grain data we do not have; recorded here, not used yet).
PLACEHOLDERS, NOT SOURCED (marked **(source)** in PLAN.md): the decay time scales and exponents (ALBEDO_TAU_DAYS, ROUGH_TAU_DAYS), the snow conductivity
(density formula below), irreducible water fraction, thaw threshold, snow density, deep-snow temperature, reference heights, the stability cap ZETA_MAX.
Shortwave penetrates the snow (multi-band Beer-Lambert absorption as in SNOWPACK's SnLaws::compShortWaveAbsorption, MULTI_BAND, with its band
extinction values, spectral shares and grain-size scaling; the grain radius RG_MM is a placeholder). Not modelled: terrain longwave from surrounding slopes, wind
redistribution, vapor transport inside the snow, percolation beyond a one-way drain, and snowfall during the run.
"""
import argparse
import math

import numpy as np
import pandas as pd
from scipy.optimize import brentq

# SNOWPACK Constants.h
SIGMA = 5.67051e-8
KARMAN = 0.4
EMISS_SNOW = 0.98
CP_AIR, C_ICE, L_SUB, L_FUS, R_AIR, G = 1004.67, 2100.0, 2.838e6, 3.34e5, 287.0, 9.80665
# Danny
ALBEDO_MAX, ALBEDO_MIN = 0.95, 0.55            # minimum raised from 0.3 to 0.55 (Danny, Oct 15); very dirty snow could go lower
Z0_MIN, Z0_MAX = 0.25e-3, 25e-3
K_ICE, D_AIR, D_SNOW = 2.2, 22e-6, 85e-6     # the last two are recorded, not used
# placeholders (see docstring)
ALBEDO_RATE0, ALBEDO_RATE_MAX, ALBEDO_CYCLES_FULL = 0.030, 0.040, 3.0   # fractional loss per day: 3% fresh, rising to 4% as melt-freeze cycles accumulate (Danny, Oct 17: 2-3% was a little too slow; the new values are placeholders)
ALBEDO_MIN_SPRING, SPRING_START_DOY, SPRING_END_DOY = 0.45, 60, 152   # from Mar 1 the floor falls linearly to 0.45 by Jun 1 (dirtier spring snow; Danny: 'say, March'); the 0.45 and the end date are placeholders
MF_MELT_C, MF_FREEZE_C = -0.05, -1.0           # a melt-freeze cycle: surface at 0 C, then back below -1 C
ROUGH_TAU_DAYS, ROUGH_POWER = 14.0, 1.0       # power-law approach to old-snow roughness; Danny: depends on conditions
RHO_SNOW = 400.0
W_IRR = 0.07
W_THAW = 0.005
Z_WIND, Z_TEMP = 10.0, 2.0
ZETA_MAX = 1.0
DZ, NL, DT = 0.01, 30, 60.0
# SNOWPACK Laws_sn.cc (values in use since r140): mean ice extinction coefficient, share of the solar spectrum (%), and 'fudge Bohren' per band
SWA_K = (0.059, 0.180, 0.525, 4.75, 85.23)
SWA_PC = (16.3, 16.8, 15.4, 31.0, 20.5)
SWA_FB = (29.0, 15.0, 5.0, 9.0, 35.0)
RG_MIN_MM, RG_MAX_MM = 1.0, 2.0   # optical grain radius (mm) grows from 1 to 2 with the albedo decay (Danny, Oct 17); SNOWPACK takes it from its grain model
RG_MM = RG_MIN_MM
PENETRATE = True
T_DEEP = 273.15              # lower boundary of the 30 cm column: 0 C (Danny, Oct 17)


def albedo_rate(cycles):
    """Fractional albedo loss per day: ALBEDO_RATE0 with no melt-freeze cycles, rising linearly to ALBEDO_RATE_MAX at ALBEDO_CYCLES_FULL cycles."""
    return ALBEDO_RATE0 + (ALBEDO_RATE_MAX - ALBEDO_RATE0) * min(max(cycles, 0.0) / ALBEDO_CYCLES_FULL, 1.0)


def albedo_floor(doy):
    """Minimum albedo for the day of year: ALBEDO_MIN through February, then falling to ALBEDO_MIN_SPRING by the end of May."""
    f = min(max((doy - SPRING_START_DOY) / (SPRING_END_DOY - SPRING_START_DOY), 0.0), 1.0)
    return ALBEDO_MIN + (ALBEDO_MIN_SPRING - ALBEDO_MIN) * f


def albedo_step(alpha, cycles, dt_days, doy=1):
    """One time step of the albedo decay, floored at albedo_floor(doy)."""
    return max(albedo_floor(doy), alpha * (1.0 - albedo_rate(cycles) * dt_days))


def albedo(age_days, cycles=0.0, doy=1):
    """Albedo after `age_days` of constant-rate decay from ALBEDO_MAX (use albedo_step when the cycle count or the date changes)."""
    return max(albedo_floor(doy), ALBEDO_MAX * (1.0 - albedo_rate(cycles)) ** max(age_days, 0.0))


def z0(age_days):
    """Roughness from 0.25 mm (fresh) toward 25 mm (old, sun cups), approaching it as a power law of age."""
    return Z0_MAX - (Z0_MAX - Z0_MIN) * (1 + max(age_days, 0.0) / ROUGH_TAU_DAYS) ** -ROUGH_POWER


def grain_radius_mm(alpha, floor):
    """Grain radius grown from RG_MIN_MM to RG_MAX_MM as the albedo falls from ALBEDO_MAX to its floor."""
    f = (ALBEDO_MAX - alpha) / max(ALBEDO_MAX - floor, 1e-6)
    return RG_MIN_MM + (RG_MAX_MM - RG_MIN_MM) * min(max(f, 0.0), 1.0)


def k_snow(rho):
    """Effective conductivity from density: a quadratic fit (Calonne et al. 2011, from memory, **(source)** to verify)."""
    return 2.5e-6 * rho ** 2 - 1.23e-4 * rho + 0.024


def e_sat(T):
    """Pa; SNOWPACK Atmosphere::vaporSaturationPressure (ice below the triple point, water above)."""
    a, b = (21.88, 7.66) if T < 273.16 else (17.27, 35.86)
    return 611.73 * math.exp(a * (T - 273.16) / (T - b))


def lw_in(rh, ta, cloud):
    """Incoming longwave (W/m2), Konzelmann et al. 1994 as in MeteoIO: emissivity from vapor pressure and cloudiness."""
    ea = rh * e_sat(ta)
    eps_cs = 0.23 + 0.484 * (ea / ta) ** 0.125
    w = cloud ** 4
    return ((1 - w) * eps_cs + w * 0.952) * SIGMA * ta ** 4


def lw_in_dilley(rh, ta, cloud):
    """Incoming longwave (W/m2): Dilley and O'Brien (1998) clear sky, 59.38 + 113.7 (T/273.16)^6 + 96.96 sqrt(w/25) with precipitable water
    w = 4650 e0 / T (e0 in kPa, Prata 1996), as in MeteoIO Atmosphere::Dilley_ilwr, then the Unsworth and Monteith (1975) cloud blend
    eps = (1 - 0.84 c) eps_clear + 0.84 c (MeteoIO Unsworth_ilwr)."""
    e0 = rh * e_sat(ta) * 0.001
    w = 4650.0 * e0 / ta
    clear = 59.38 + 113.7 * (ta / 273.16) ** 6 + 96.96 * math.sqrt(w / 25.0)
    eps_clear = min(clear / (SIGMA * ta ** 4), 1.0)
    return ((1 - 0.84 * cloud) * eps_clear + 0.84 * cloud) * SIGMA * ta ** 4


def exchange(ta, ts, vw, pressure, z0m):
    """Sensible (W/m2/K) and latent (W/m2/Pa) exchange coefficients, SNOWPACK's scheme: Monin-Obukhov iteration for u* and the
    scalar stability correction (Meteo.cc MicroMet and MOStability), then C_h (Laws_sn.cc compSensibleHeatCoefficient).
    Stable side: the log-linear form psi = -5 zeta (SNOWPACK's MO_LOG_LINEAR option) with zeta capped at ZETA_MAX; SNOWPACK's
    default stable form is not used because it does not return to zero in neutral conditions as I read it. Unstable side: the
    Paulson (momentum) and Stearns-Weidner (scalar) forms from the same file."""
    vw = max(vw, 0.3)
    z_ratio = math.log(Z_WIND / z0m)
    ta_v, ts_v = ta, ts            # virtual-temperature correction is below 0.5 K here and is ignored
    psi_m = psi_s = 0.0
    ustar = KARMAN * vw / z_ratio
    for _ in range(100):
        old = ustar
        ustar = KARMAN * vw / (z_ratio - psi_m)
        tstar = KARMAN * (ts_v - ta_v) / (z_ratio - psi_s)
        zeta = -KARMAN * Z_WIND * tstar * G / (ts * ustar ** 2)
        if zeta > 0:
            zeta = min(zeta, ZETA_MAX)
            psi_m = psi_s = -5 * zeta
        else:
            d1 = (1 - 15 * zeta) ** 0.25
            psi_m = 2 * math.log(0.5 * (1 + d1)) + math.log(0.5 * (1 + d1 * d1)) - 2 * math.atan(d1) + 0.5 * math.pi
            d2 = (1 - 22.5 * zeta) ** (1 / 3)
            psi_s = math.log((1 + d2 + d2 * d2) ** 1.5) - 1.732 * math.atan(0.577 * (1 + 2 * d2)) + 0.1659
        if abs(ustar - old) < 1e-3:
            break
    ustar = KARMAN * vw / (z_ratio - psi_m)
    ch = KARMAN * ustar / max(0.7, math.log(Z_TEMP / z0m) - psi_s)     # m/s
    rho_a = pressure / (R_AIR * ta)
    return ch * rho_a * CP_AIR, ch * 0.622 * L_SUB / (R_AIR * ta)


TAU_WET_H = 24.0             # wet-snow densification time scale (h) toward the density target: PLACEHOLDER (see _densify)
RHO_WET, RHO_PER_CYCLE = 550.0, 100.0   # target density of continuously wet snow, and the extra per completed melt-freeze cycle of that layer: PLACEHOLDERS
RHO_CRUST_MAX = 800.0        # refreezing meltwater can fill the pores of a layer up to this density (kg/m3); Danny: refrozen crust 700-800
RHO_SATURATED = 950.0        # bulk density (ice plus liquid) a layer cannot exceed; further water passes down (kg/m3)
RHO_FLOOR = 300.0            # when a layer melts and drains its matrix collapses rather than going lighter than this (kg/m3): PLACEHOLDER
SKIN_DZ, BODY_DZ, DEPTH = 0.005, 0.010, 0.30      # top 'skin' layer 0.5 cm (Danny: a thin skin), 1 cm layers below, a 30 cm column
DZ_MIN = 0.004               # a layer thinner than this (melted away) is merged into its neighbor
DT_MAX, STAB = 60.0, 0.4     # largest substep (s) and the fraction of the explicit conduction stability limit used


def residual_water_vol(theta_i):
    """SNOWPACK ElementData::snowResidualWaterContent (Coleou and Lesaffre 1998): residual water content by volume from the ice volume fraction,
    limited to 0.08 and to the pore space."""
    if theta_i > 0.23:
        r = 0.0264 + 0.0099 * (1.0 - theta_i) / theta_i
    else:
        r = 0.08 - 0.1023 * (theta_i - 0.03)
    return min(r, 0.08, (1.0 - theta_i) * 917.0 / 1000.0)


class Column:
    """A snow column 30 cm deep with variable layer thickness: a 0.5 cm skin on top and 1 cm layers below. Each layer has a thickness dz, a
    total mass m (ice plus liquid, kg/m2; density is m / dz), a temperature T and a liquid mass w. Water that drains from a layer lowers its
    mass (its density falls, down to RHO_FLOOR, below which the matrix collapses and the layer thins); water that refreezes in a colder layer
    fills pores and raises that layer's density (up to RHO_CRUST_MAX): so density rises as pores freeze and falls as they melt and drain,
    like frozen ground. Wet layers also compact toward RHO_WET plus RHO_PER_CYCLE per completed melt-freeze cycle. The column keeps its 30 cm
    depth: layers that melt away are merged and new layers are added at the bottom, at the starting density and the lower-boundary temperature."""

    def __init__(self, T0=273.15, w0=0.0, rho=RHO_SNOW):
        self.dz = np.array([SKIN_DZ, SKIN_DZ] + [BODY_DZ] * int(round((DEPTH - 2 * SKIN_DZ) / BODY_DZ)))
        n = len(self.dz)
        self.m = rho * self.dz
        self.T = np.full(n, float(T0))
        self.w = w0 * self.m
        self.cyc = np.zeros(n)                  # melt-freeze cycles each layer has been through (wet, then frozen)
        self.wet = np.zeros(n, dtype=bool)
        self.cycles = 0                         # completed surface melt-freeze cycles (surface reached 0 C, then fell below MF_FREEZE_C)
        self._melted = False
        self.t_deep = T_DEEP                    # temperature at the bottom of the column (K)
        self.ts = float(T0)

    @property
    def rho(self):
        return self.m / self.dz

    def centers(self):
        return np.cumsum(self.dz) - self.dz / 2

    def set_linear_profile(self, t_top):
        """Temperature from t_top at the surface to the lower-boundary temperature at the bottom."""
        f = self.centers() / self.dz.sum()
        self.T = t_top + (self.t_deep - t_top) * f

    def on_grid(self, depths):
        """(temperature K, liquid fraction of mass, density) at the given depths (m), as piecewise-constant layer values."""
        idx = np.minimum(np.searchsorted(np.cumsum(self.dz), depths, side="right"), len(self.dz) - 1)
        return self.T[idx], (self.w / self.m)[idx], self.rho[idx]

    def k_layers(self):
        return k_snow(self.rho)

    def water_cap(self):
        theta_i = np.clip((self.m - self.w) / (917.0 * self.dz), 0.02, 0.99)
        return np.array([residual_water_vol(t) for t in theta_i]) * 1000.0 * self.dz

    def _receive(self, j, mass):
        """Liquid arriving in layer j: it refreezes first in a layer below 0 C (filling pores, up to RHO_CRUST_MAX, and warming the layer); the
        rest stays as liquid while the layer has pore space (bulk density below RHO_SATURATED), and any excess passes on to the next layer.
        Water that leaves the bottom is lost."""
        n = len(self.dz)
        while mass > 1e-12 and j < n:
            if self.T[j] < 273.15:
                room = max(RHO_CRUST_MAX * self.dz[j] - self.m[j], 0.0)
                frz = min(mass, C_ICE * self.m[j] * (273.15 - self.T[j]) / L_FUS, room)
                self.T[j] += frz * L_FUS / (C_ICE * self.m[j])
                self.m[j] += frz
                mass -= frz
            hold = min(mass, max(RHO_SATURATED * self.dz[j] - self.m[j], 0.0))
            self.w[j] += hold
            self.m[j] += hold
            mass -= hold
            j += 1

    def add_rain(self, mass):
        """Rain (kg/m2) onto the surface."""
        self._receive(0, mass)

    def _apply_heat(self, E):
        """E (J/m2 per layer): warm to 0 C then melt (E > 0); refreeze liquid then cool (E < 0)."""
        cm = C_ICE * self.m
        T, w = self.T, self.w
        pos = E > 0
        need = np.where(T < 273.15, cm * (273.15 - T), 0.0)
        warm = np.where(pos, np.minimum(E, need), 0.0)
        T = T + warm / cm
        w = np.minimum(w + np.where(pos, E - warm, 0.0) / L_FUS, self.m)
        neg = E < 0
        frz = np.where(neg, np.minimum(w, -E / L_FUS), 0.0)
        w = w - frz
        T = T + np.where(neg, E + frz * L_FUS, 0.0) / cm
        self.T, self.w = T, w

    def _drain(self):
        """Liquid above the residual amount leaves a layer (its mass and density fall) and goes to the layer below, where it refreezes or is held.
        Water leaving the bottom is lost."""
        cap = self.water_cap()
        for i in range(len(self.dz)):
            ex = self.w[i] - cap[i]
            if ex <= 0:
                continue
            self.w[i] -= ex
            self.m[i] -= ex
            if i + 1 < len(self.dz):
                self._receive(i + 1, ex)

    def _densify(self, dt):
        wet = self.w / self.m >= W_THAW
        done = self.wet & ~wet & (self.T < 273.15 - 0.2)          # was wet, now frozen: one more cycle for the layer
        self.cyc[done] += 1
        self.wet = np.where(wet, True, np.where(done, False, self.wet))
        rho = self.rho
        target = np.minimum(RHO_CRUST_MAX, RHO_WET + RHO_PER_CYCLE * self.cyc)
        rho = np.where(wet & (rho < target), rho + (target - rho) * (1.0 - math.exp(-dt / (TAU_WET_H * 3600.0))), rho)
        rho = np.maximum(rho, RHO_FLOOR)                           # a melted, drained matrix collapses rather than going lighter
        self.dz = self.m / rho

    def _merge(self, i):
        """Merge layer i into the thinner of its neighbors, conserving mass, liquid and heat."""
        n = len(self.dz)
        j = i + 1 if (i == 0 or (i + 1 < n and self.dz[i + 1] <= self.dz[i - 1])) else i - 1
        a, b = min(i, j), max(i, j)
        m = self.m[a] + self.m[b]
        self.T[a] = (self.T[a] * self.m[a] + self.T[b] * self.m[b]) / m
        self.cyc[a] = (self.cyc[a] * self.m[a] + self.cyc[b] * self.m[b]) / m
        self.wet[a] = self.wet[a] or self.wet[b]
        self.w[a] += self.w[b]
        self.dz[a] += self.dz[b]
        self.m[a] = m
        for name in ("dz", "m", "w", "T", "cyc", "wet"):
            setattr(self, name, np.delete(getattr(self, name), b))

    def _regrid(self):
        while len(self.dz) > 2 and self.dz.min() < DZ_MIN:
            self._merge(int(np.argmin(self.dz)))
        while self.dz[0] > 1.5 * SKIN_DZ:                           # keep a thin skin on top: split the top layer
            f = SKIN_DZ / self.dz[0]
            for name in ("dz", "m", "w"):
                a = getattr(self, name)
                setattr(self, name, np.concatenate([[a[0] * f], [a[0] * (1 - f)], a[1:]]))
            for name in ("T", "cyc", "wet"):
                a = getattr(self, name)
                setattr(self, name, np.concatenate([a[:1], a[:1], a[1:]]))
        while self.dz.sum() < DEPTH - 0.5 * BODY_DZ:                 # the column keeps its depth: new snow comes up from below
            self.dz = np.append(self.dz, BODY_DZ)
            self.m = np.append(self.m, RHO_SNOW * BODY_DZ)
            self.w = np.append(self.w, 0.0)
            self.T = np.append(self.T, self.t_deep)
            self.cyc = np.append(self.cyc, 0.0)
            self.wet = np.append(self.wet, False)

    def stable_dt(self):
        kk = self.k_layers()
        return STAB * float(np.min(self.dz ** 2 * self.rho * C_ICE / (2.0 * kk)))

    def step(self, f, dt):
        """One substep of length dt (s). f: dict sw_abs (W/m2 net of albedo), lw_in, ta, rh, vw, pressure, z0, rg. Returns the surface
        temperature and the net flux into the top layer."""
        ta = f["ta"]
        kk = self.k_layers()
        a, b = exchange(ta, self.ts, f["vw"], f["pressure"], f["z0"])      # exchange coefficients from the surface temperature one substep ago
        sw_surface = 0.0 if PENETRATE else f["sw_abs"]
        ea = f["rh"] * e_sat(ta)

        def terms(ts):
            return sw_surface + EMISS_SNOW * f["lw_in"] - EMISS_SNOW * SIGMA * ts ** 4 + a * (ta - ts) + b * (ea - e_sat(ts))

        ts = self.T[0]                           # the 0.5 cm skin layer is the surface: its temperature is the surface temperature
        into_top = terms(ts)                     # net surface flux (longwave, sensible, latent, and shortwave if not penetrating) into the skin layer
        dz = self.dz
        kint = (dz[:-1] + dz[1:]) / (dz[:-1] / kk[:-1] + dz[1:] / kk[1:])
        between = kint * (self.T[:-1] - self.T[1:]) / (0.5 * (dz[:-1] + dz[1:]))
        bottom = kk[-1] * (self.T[-1] - self.t_deep) / (dz[-1] / 2)
        fin = np.concatenate([[into_top], between])
        fout = np.concatenate([between, [bottom]])
        swl = sw_absorption(f["sw_abs"], self.rho, f.get("rg", RG_MM), dz) if PENETRATE else np.zeros(len(dz))
        self._apply_heat((fin - fout + swl) * dt)
        self._drain()
        self._densify(dt)
        self._regrid()
        if ts >= 273.15 + MF_MELT_C and into_top > 0:
            self._melted = True
        elif self._melted and ts < 273.15 + MF_FREEZE_C:
            self.cycles += 1
            self._melted = False
        self.ts = ts
        return ts, into_top

    def advance(self, f, duration):
        """Run for `duration` seconds in substeps no longer than the explicit conduction stability limit."""
        t = 0.0
        ts = into_top = 0.0
        while t < duration - 1e-9:
            dt = min(DT_MAX, self.stable_dt(), duration - t)
            ts, into_top = self.step(f, dt)
            t += dt
        return ts, into_top

    def thawed_cm(self):
        return 100 * float(np.sum(self.dz[self.w / self.m >= W_THAW]))

    def crust_cm(self):
        """Depth of the frozen (below 0 C and no liquid) top layers, counted from the surface."""
        d = 0.0
        for i in range(len(self.dz)):
            if self.T[i] < 273.15 - 1e-6 and self.w[i] == 0:
                d += self.dz[i]
            else:
                break
        return 100 * d


def sw_absorption(i0, rho, rg_mm=RG_MM, dz=None):
    """Shortwave (W/m2) absorbed in each layer from `i0` net at the surface, SNOWPACK MULTI_BAND (Laws_sn.cc compShortWaveAbsorption): per band
    Ks = fb * 0.84 * sqrt(1000 k / (2 rg)) * rho / rho_ice (1/m), absorbed in a layer i0_band * (exp(-tau_top) - exp(-tau_bottom)). Light left at
    the bottom of the column is added to the last layer (as SNOWPACK does for the bottom element)."""
    rho = np.asarray(rho, dtype=float)
    dz = np.full(len(rho), DZ) if dz is None else np.asarray(dz, dtype=float)
    out = np.zeros(len(rho))
    for k, pc, fb in zip(SWA_K, SWA_PC, SWA_FB):
        ks = fb * 0.84 * math.sqrt(1000.0 * k / (2.0 * rg_mm)) * rho / 917.0
        tau = np.cumsum(ks * dz)
        top = np.concatenate([[0.0], tau[:-1]])
        out += (i0 * pc / 100.0) * (np.exp(-top) - np.exp(-tau))
        out[-1] += (i0 * pc / 100.0) * math.exp(-tau[-1])
    return out


def synthetic():
    import corn_clearsky as cs
    lat, lon, elev = 46.786, -121.735, 1900.0
    pressure = 101325 * (1 - 2.25577e-5 * elev) ** 5.25588
    h = cs.horizontal(lat, lon, elev)
    sw = cs.tilted(h, 30, 180)["total"]
    t0 = pd.Timestamp("2027-03-21 00:00", tz="UTC")
    idx = pd.date_range(t0, periods=96, freq="30min")        # 48 h of 30-minute windows
    sw = sw.reindex(idx + pd.Timedelta(minutes=15)).values
    print("Synthetic run: Paradise latitude, 1900 m, 30 deg south slope, Mar 21-22, clear sky. Forcing is made up to test behavior.")
    print("Case A: clear, dry, air +2 C at night / +6 C by day, wind 2 m/s, ripe snow to start (0 C, 2% liquid), old snow (age 10 d).")
    for label, tmin, tmax in (("A  air +2 to +6 C", 2.0, 6.0), ("B  air -4 to +3 C", -4.0, 3.0), ("C  air -10 to 0 C", -10.0, 0.0)):
        col = Column(T0=273.15, w0=0.02)
        age = 10.0
        print(f"\n{label}   albedo {albedo(age):.2f}, z0 {1000 * z0(age):.1f} mm")
        print("  local(PDT)  air C  surf C  thawed cm  crust cm   SWabs  LWnet  sens  latent")
        for n, t in enumerate(idx):
            hour = (t.hour + t.minute / 60 - 7) % 24                       # UTC-7 (PDT)
            ta = 273.15 + tmin + (tmax - tmin) * 0.5 * (1 - math.cos(2 * math.pi * (hour - 5) / 24))   # min near 05:00, max near 17:00
            f = dict(sw_abs=(1 - albedo(age)) * sw[n], lw_in=lw_in(0.4, ta, 0.0), ta=ta, rh=0.4, vw=2.0, pressure=pressure, z0=z0(age))
            for _ in range(int(30 * 60 / DT)):
                ts, _q = col.step(f)
            if t.hour % 3 == 0 and t.minute == 0 and t >= t0 + pd.Timedelta(hours=24):
                a, b = exchange(ta, ts, 2.0, pressure, z0(age))
                print(f"  {hour:5.1f}h   {ta - 273.15:6.1f} {ts - 273.15:7.1f}  {col.thawed_cm():8.1f}  {col.crust_cm():8.1f}  {f['sw_abs']:6.0f} "
                      f"{EMISS_SNOW * f['lw_in'] - EMISS_SNOW * SIGMA * ts ** 4:6.0f} {a * (ta - ts):5.0f} {b * (0.4 * e_sat(ta) - e_sat(ts)):6.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    args = ap.parse_args()
    if args.synthetic:
        synthetic()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
