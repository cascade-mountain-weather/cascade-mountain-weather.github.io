"""Moist (saturated) adiabatic temperature adjustment between two elevations.

Used to move an NBM 2 m temperature from the model's smoothed grid-cell elevation to the elevation
of a forecast site. The NBM grid is 2.5 km, so a mountain pass or ski area is usually higher or lower
than the cell average.

    from lapse import adjust_temperature
    adjust_temperature(t_kelvin, from_elev_m, to_elev_m)   # -> temperature at to_elev_m

Assumptions (also stated in the snapshot file):
  - The air is saturated, so the cooling rate is the saturated adiabatic one. In dry or clear air the
    real rate is closer to the dry adiabat (9.8 K/km), so this under-corrects there. Under a nighttime
    inversion the true change can even have the opposite sign. It is an estimate, not a measurement.
  - Pressure comes from the standard atmosphere at the given height.
  - Latent heat of vaporization over water is used at all temperatures (what MetPy's moist_lapse does).
"""
import math

G = 9.80665          # m s-2
CP = 1004.0          # J kg-1 K-1, dry air
RD = 287.04          # J kg-1 K-1
LV = 2.501e6         # J kg-1
EPS = 0.622


def _pressure_pa(z_m):
    """ICAO standard atmosphere, valid through the troposphere."""
    return 101325.0 * (1.0 - 2.25577e-5 * z_m) ** 5.25588


def _es_pa(t_k):
    """Saturation vapor pressure over water (Bolton 1980)."""
    tc = t_k - 273.15
    return 611.2 * math.exp(17.67 * tc / (tc + 243.5))


def moist_lapse_rate(t_k, z_m):
    """Saturated adiabatic lapse rate in K per meter (positive = cooling with height)."""
    p = _pressure_pa(z_m)
    es = _es_pa(t_k)
    rs = EPS * es / (p - es)
    num = G * (1.0 + LV * rs / (RD * t_k))
    den = CP + (LV ** 2) * rs * EPS / (RD * t_k ** 2)
    return num / den


def adjust_temperature(t_k, from_elev_m, to_elev_m, step_m=25.0):
    """Temperature at to_elev_m for a saturated parcel moved from from_elev_m (K in, K out)."""
    dz = to_elev_m - from_elev_m
    if dz == 0:
        return t_k
    n = max(1, int(math.ceil(abs(dz) / step_m)))
    h = dz / n
    t, z = t_k, from_elev_m
    for _ in range(n):  # midpoint rule: lapse rate at the middle of each layer
        t_mid = t - moist_lapse_rate(t, z) * h / 2.0
        t = t - moist_lapse_rate(t_mid, z + h / 2.0) * h
        z += h
    return t


if __name__ == "__main__":
    for t_c, z in ((20, 500), (10, 1000), (0, 1200), (-5, 1500), (-15, 1500)):
        print(f"{t_c:>4} C at {z:>5} m: {moist_lapse_rate(t_c + 273.15, z) * 1000:.2f} K/km")
    print("300 m up from 0 C at 1200 m:", round(adjust_temperature(273.15, 1200, 1500) - 273.15, 2), "C")
