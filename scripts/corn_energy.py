"""Thin-layer surface energy balance for the corn model (PLAN.md, "Corn model: design", build step 4).

    python scripts/corn_energy.py --synthetic        # two-day run on made-up forcing, to check behavior (not a forecast)

The top 30 cm of snow in 1 cm layers: temperature and liquid water per layer (enthalpy bookkeeping), a bulk surface balance
solved for the surface temperature every minute, conduction between layers, melt and refreeze at 0 C. The surface balance
follows SNOWPACK (github.com/snowpack-model/snowpack, Source/snowpack/snowpack: Snowpack.cc updateBoundHeatFluxes,
Laws_sn.cc compSensibleHeatCoefficient / compLatentHeat, Meteo.cc RichardsonStability, MeteoIO Atmosphere.cc
Konzelmann_emissivity); only the surface balance is borrowed, not the full profile solver.

Parameters given by Danny (Oct 14 2026): albedo from 0.95 (fresh snow) down to a floor of 0.3 as a power-law decay, most of the
drop in about a week (realistic floor 0.45-0.6); roughness length 0.25 mm (fresh) rising to 25 mm (old snow, sun cups), also a power law; conductivity of ice 2.2 W/m/K;
diffusion coefficient in air 22e-6 and in snow/ice 85e-6 (m2/s) (these two enter SNOWPACK's snow conductivity, which needs
grain data we do not have; recorded here, not used yet).
PLACEHOLDERS, NOT SOURCED (marked **(source)** in PLAN.md): the decay time scales and exponents (ALBEDO_TAU_DAYS, ROUGH_TAU_DAYS), the snow conductivity
(density formula below), irreducible water fraction, thaw threshold, snow density, deep-snow temperature, reference heights, the stability cap ZETA_MAX.
Not modelled: shortwave penetration into snow (all absorbed at the surface), terrain longwave from surrounding slopes, wind
redistribution, vapor transport inside the snow, percolation beyond a one-way drain, and snowfall during the run.
"""
import argparse
import math

import numpy as np
import pandas as pd

# SNOWPACK Constants.h
SIGMA = 5.67051e-8
KARMAN = 0.4
EMISS_SNOW = 0.98
CP_AIR, C_ICE, L_SUB, L_FUS, R_AIR, G = 1004.67, 2100.0, 2.838e6, 3.34e5, 287.0, 9.80665
# Danny
ALBEDO_MAX, ALBEDO_MIN = 0.95, 0.3
Z0_MIN, Z0_MAX = 0.25e-3, 25e-3
K_ICE, D_AIR, D_SNOW = 2.2, 22e-6, 85e-6     # the last two are recorded, not used
# placeholders (see docstring)
ALBEDO_TAU_DAYS, ALBEDO_POWER = 2.0, 1.0      # power-law decay, most of the drop in about a week (Danny: roughly a week)
ROUGH_TAU_DAYS, ROUGH_POWER = 14.0, 1.0       # power-law approach to old-snow roughness; Danny: depends on conditions
RHO_SNOW = 400.0
W_IRR = 0.07
W_THAW = 0.005
T_DEEP = 273.15
Z_WIND, Z_TEMP = 10.0, 2.0
ZETA_MAX = 1.0
DZ, NL, DT = 0.01, 30, 60.0


def albedo(age_days):
    """Power-law decay with age since the last snowfall: ALBEDO_MIN + (MAX - MIN) (1 + age/tau)^-p."""
    return ALBEDO_MIN + (ALBEDO_MAX - ALBEDO_MIN) * (1 + max(age_days, 0.0) / ALBEDO_TAU_DAYS) ** -ALBEDO_POWER


def z0(age_days):
    """Roughness from 0.25 mm (fresh) toward 25 mm (old, sun cups), approaching it as a power law of age."""
    return Z0_MAX - (Z0_MAX - Z0_MIN) * (1 + max(age_days, 0.0) / ROUGH_TAU_DAYS) ** -ROUGH_POWER


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


class Column:
    def __init__(self, T0=273.15, w0=0.0, rho=RHO_SNOW):
        self.m = rho * DZ                       # kg/m2 per layer (ice plus liquid)
        self.T = np.full(NL, T0)
        self.w = np.full(NL, w0 * self.m)       # liquid water, kg/m2
        self.k = k_snow(rho)
        self.t_deep = T_DEEP                    # temperature just below the column (K); the caller may update it

    def add_heat(self, i, E):
        """E in J/m2 into layer i: warm, then melt (E>0); or refreeze liquid first, then cool (E<0)."""
        cm = C_ICE * self.m
        if E > 0:
            if self.T[i] < 273.15:
                need = cm * (273.15 - self.T[i])
                if E <= need:
                    self.T[i] += E / cm
                    return
                self.T[i], E = 273.15, E - need
            self.w[i] = min(self.w[i] + E / L_FUS, self.m)
        else:
            if self.w[i] > 0:
                frz = min(self.w[i], -E / L_FUS)
                self.w[i] -= frz
                E += frz * L_FUS
            if E < 0:
                self.T[i] += E / cm

    def drain(self):
        """Liquid above the irreducible fraction moves down one layer per call; entering a layer below 0 C it refreezes first, warming that
        layer (the cold content meltwater has to satisfy before the wet front can advance). Water leaving the bottom is lost."""
        cap = W_IRR * self.m
        for i in range(NL):
            ex = self.w[i] - cap
            if ex <= 0:
                continue
            self.w[i] = cap
            if i + 1 < NL:
                j = i + 1
                if self.T[j] < 273.15:
                    frz = min(ex, C_ICE * self.m * (273.15 - self.T[j]) / L_FUS)
                    self.T[j] += frz * L_FUS / (C_ICE * self.m)
                    ex -= frz
                self.w[j] += ex

    def step(self, f, dt=DT):
        """One substep. f: dict sw_abs (W/m2 already net of albedo), lw_in, ta, rh, vw, pressure, z0. Returns surface temperature and the
        melt energy flux into the top layer."""
        ta = f["ta"]
        h_coef_cache = {}

        def terms(ts):
            a, b = exchange(ta, ts, f["vw"], f["pressure"], f["z0"])
            qs = a * (ta - ts)
            ql = b * (f["rh"] * e_sat(ta) - e_sat(ts))
            return f["sw_abs"] + EMISS_SNOW * f["lw_in"] - EMISS_SNOW * SIGMA * ts ** 4 + qs + ql

        T1 = self.T[0]
        g_cond = lambda ts: self.k * (ts - T1) / (DZ / 2)
        Q = lambda ts: terms(ts) - g_cond(ts)
        if Q(273.15) >= 0:                       # surface would exceed 0 C: hold at 0 C, all the net flux goes into the top layer
            ts, into_top = 273.15, terms(273.15)
        else:
            lo, hi = 200.0, 273.15
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                if Q(mid) > 0:
                    lo = mid
                else:
                    hi = mid
            ts = 0.5 * (lo + hi)
            into_top = g_cond(ts)
        flux = np.zeros(NL + 1)                  # flux[i] = heat into layer i from above (W/m2); flux[NL] = out of the bottom
        flux[0] = into_top
        for i in range(1, NL):
            flux[i] = self.k * (self.T[i - 1] - self.T[i]) / DZ
        flux[NL] = self.k * (self.T[NL - 1] - self.t_deep) / DZ
        for i in range(NL):
            self.add_heat(i, (flux[i] - flux[i + 1]) * dt)
        self.drain()
        return ts, into_top

    def thawed_cm(self):
        return 100 * DZ * float(np.sum(self.w / self.m >= W_THAW))

    def crust_cm(self):
        """Depth of the frozen (below 0 C and no liquid) top layers, counted from the surface."""
        n = 0
        for i in range(NL):
            if self.T[i] < 273.15 - 1e-6 and self.w[i] == 0:
                n += 1
            else:
                break
        return 100 * DZ * n


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
