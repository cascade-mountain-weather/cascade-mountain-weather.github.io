"""Run the corn energy balance on Danny's logged good and bad days and plot the 30 cm snow temperature as a heat map.

    python scripts/corn_validate.py --day 2026-02-28            # one day (a date from DAYS)
    python scripts/corn_validate.py --all                       # every day Synoptic can supply

For each day: hourly air temperature, humidity and wind from nearby stations (Synoptic; token in .synoptic-token or the
environment), lapse-adjusted between a low and a high station where both exist; cloud from the measured-to-clear-sky shortwave
ratio at a nearby radiometer; snow age from the nearest SNOTEL daily record (AWDB); terrain from data/corn/class_terrain_cascades.csv
(the class nearest the site: elevation band, slope, aspect). The column is spun up from the start of the last snow-free stretch
(at most SPINUP_DAYS before the day) from an isothermal start at the mean air temperature capped at 0 C, then the target day is
run. Output: docs/corn/<date>_<id>.png (heat map of snow temperature, depth against time, with the liquid-water and 0 C lines,
and air / surface temperature and absorbed shortwave beneath), plus a summary table printed at the end.

ASSUMPTIONS (placeholders to review): site elevation and slope are stated, not measured; the snow age resets at a SNOTEL daily gain
of at least SNOW_DAY_IN of water equivalent; cloud fraction = clip(1 - kt / KT_CLEAR, 0, 1) with kt the measured / clear-sky ratio
(KT_CLEAR 0.95 from the Stevens Tye Mill clear days) and held through the night by interpolating between daytime values; wind is the
station value used as 10 m wind; no precipitation or snowfall enters the column (snow that falls during the spin-up is not added).
Days before about Oct 2025 are outside the Synoptic token's history and are not run here.
"""
import argparse
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corn_clearsky as cs  # noqa: E402
import corn_energy as ce  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "corn" / "validation"
FIG = ROOT / "docs" / "corn"
SPINUP_DAYS = 4
SNOW_DAY_IN = 0.2
KT_CLEAR = 0.95
FT = 0.3048

# station roles: T = air temperature (list of (stid, elev ft), interpolated in elevation), W = wind, RH = humidity (same stations as T if
# available), SW = radiometer for cloud, SNOTEL = (triplet) for snow age.
DAYS = [
    dict(id="muir", date="2026-02-28", hhmm="12:00", good=True, place="Muir Snowfield, Mt. Rainier, S-facing", lat=46.82, lon=-121.73,
         elev_ft=6500, slope=17.5, aspect=180, T=["PVC54", "MU101"], W="PVW54", SW=["PVW54", "MU101"], SNOTEL="679:WA:SNTL", region="paradise"),
    dict(id="lundin", date="2026-01-24", hhmm="13:00", good=True, place="Lundin Peak, S-facing, near Snoqualmie Pass", lat=47.43, lon=-121.45,
         elev_ft=5800, slope=30, aspect=180, T=["ALP55"], W="ALP55", SW=["ALP55", "STS54"], SNOTEL="672:WA:SNTL", region="snoqualmie"),
    dict(id="paradise_jan31", date="2026-01-31", hhmm="12:00", good=False, place="Paradise area (too much recent snow)", lat=46.80, lon=-121.74,
         elev_ft=5500, slope=17.5, aspect=180, T=["PVC54", "MU101"], W="PVW54", SW=["PVW54", "MU101"], SNOTEL="679:WA:SNTL", region="paradise"),
    dict(id="paradise_jan17", date="2026-01-17", hhmm="12:00", good=False, place="Paradise area (way too warm)", lat=46.80, lon=-121.74,
         elev_ft=5500, slope=17.5, aspect=180, T=["PVC54", "MU101"], W="PVW54", SW=["PVW54", "MU101"], SNOTEL="679:WA:SNTL", region="paradise"),
    # older days: forcing from HRRR (scripts/corn_hrrr.py), snow age from the nearest SNOTEL; slope and aspect are guesses from the route name
    dict(id="helens_2022", date="2022-01-17", hhmm="12:30", good=True, place="Mt. St. Helens, Worm Flows", lat=46.20, lon=-122.18, elev_ft=5500,
         slope=30, aspect=180, source="hrrr", SNOTEL="1012:WA:SNTL"),
    dict(id="helens_2023", date="2023-03-22", hhmm="11:30", good=True, place="Mt. St. Helens, Worm Flows", lat=46.20, lon=-122.18, elev_ft=5500,
         slope=30, aspect=180, source="hrrr", SNOTEL="1012:WA:SNTL"),
    dict(id="adams_2023", date="2023-06-10", hhmm="11:30", good=True, place="Mt. Adams, Southwest Chutes", lat=46.17, lon=-121.52, elev_ft=6500,
         slope=30, aspect=225, source="hrrr", SNOTEL="702:WA:SNTL"),
    dict(id="crystal_2024", date="2024-04-14", hhmm="13:00", good=True, place="Crystal Mountain, northwest routes", lat=46.935, lon=-121.475, elev_ft=6200,
         slope=30, aspect=315, source="hrrr", SNOTEL="642:WA:SNTL"),
    dict(id="baker_2024", date="2024-06-29", hhmm="13:00", good=True, place="Mt. Baker, Coleman-Deming", lat=48.77, lon=-121.84, elev_ft=6000,
         slope=17.5, aspect=225, source="hrrr", SNOTEL="1011:WA:SNTL"),
    dict(id="baker_2025", date="2025-06-15", hhmm="12:00", good=True, place="Mt. Baker, Coleman-Deming, W/SW", lat=48.77, lon=-121.84, elev_ft=6000,
         slope=17.5, aspect=247.5, source="hrrr", SNOTEL="1011:WA:SNTL"),
    dict(id="baker_ski", date="2026-02-05", hhmm="12:00", good=False, place="Mt. Baker ski area (thick ice crust after rain)", lat=48.86, lon=-121.67,
         elev_ft=4800, slope=17.5, aspect=180, T=["MTB42", "MTB50"], W="MTB50", SW=["MTB50", "KCFW1"], SNOTEL="909:WA:SNTL", region="baker"),
]
def _nws_cold():
    from matplotlib.colors import LinearSegmentedColormap
    # cold-to-freezing ramp in the style of NWS temperature maps: purple, blue, cyan, then green at the melting point
    stops = [(0.0, "#4a1a7a"), (0.25, "#2b4fb3"), (0.5, "#2f8fd8"), (0.75, "#7fd1e8"), (0.93, "#b9efd8"), (1.0, "#34b36a")]
    return LinearSegmentedColormap.from_list("nws_cold", stops)


NWS_COLD = _nws_cold()
TERRAIN = ROOT / "data" / "corn" / "class_terrain_cascades.csv"


def token():
    t = (os.environ.get("SYNOPTIC_TOKEN") or "").strip()
    if not t and (ROOT / ".synoptic-token").exists():
        t = (ROOT / ".synoptic-token").read_text(encoding="utf-8").strip()
    if not t:
        raise SystemExit("no Synoptic token")
    return t


def synoptic(stids, start, end):
    """Hourly obs for several stations, one DataFrame per station (columns T, RH, W, SW), cached on disk."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / f"syn_{'-'.join(sorted(stids))}_{start:%Y%m%d}_{end:%Y%m%d}.pkl"
    if key.exists():
        return pd.read_pickle(key)
    r = requests.get("https://api.synopticdata.com/v2/stations/timeseries", params=dict(
        token=token(), stid=",".join(stids), start=start.strftime("%Y%m%d%H%M"), end=end.strftime("%Y%m%d%H%M"),
        vars="air_temp,relative_humidity,wind_speed,solar_radiation", obtimezone="utc", units="metric"), timeout=120).json()
    if r["SUMMARY"].get("RESPONSE_CODE") not in (1, 2):
        raise RuntimeError(r["SUMMARY"].get("RESPONSE_MESSAGE"))
    out = {}
    for st in r["STATION"]:
        o = st["OBSERVATIONS"]
        df = pd.DataFrame(index=pd.to_datetime(o["date_time"], utc=True))
        for col, name in (("air_temp", "T"), ("relative_humidity", "RH"), ("wind_speed", "W"), ("solar_radiation", "SW")):
            k = next((k for k in o if k.startswith(col + "_set_1")), None)
            df[name] = pd.to_numeric(pd.Series(o[k], index=df.index), errors="coerce") if k else np.nan
        out[st["STID"]] = (dict(elev_m=float(st["ELEVATION"]) * FT, lat=float(st["LATITUDE"]), lon=float(st["LONGITUDE"])), df[~df.index.duplicated()])
    pd.to_pickle(out, key)
    return out


def snotel(triplet, start, end):
    r = requests.get("https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data", params=dict(
        stationTriplets=triplet, elements="WTEQ,PREC,TAVG,SNWD", duration="DAILY", beginDate=str(start.date()), endDate=str(end.date())), timeout=60).json()
    cols = {}
    for e in r[0]["data"]:
        cols[e["stationElement"]["elementCode"]] = pd.Series({pd.Timestamp(v["date"]): v.get("value") for v in e["values"]})
    return pd.DataFrame(cols)


def dewpoint(T, RH):
    a, b = 17.625, 243.04
    g = np.log(np.clip(RH, 1, 100) / 100.0) + a * T / (b + T)
    return b * g / (a - g)


def forcing_hrrr(day, idx):
    """HRRR version of forcing(): returns the same tuple plus the model's downward longwave (W/m2) on idx."""
    f = CACHE / f"hrrr_{day['id']}_{day['date']}.pkl"
    df = pd.read_pickle(f)
    df.index = pd.DatetimeIndex(df.index).tz_localize("UTC")
    hr = lambda s: s.reindex(idx.union(s.index)).interpolate(limit=7, limit_area="inside").reindex(idx).ffill().bfill()
    elev = day["elev_ft"] * FT
    orog = float(df["orog"].median())
    dz = elev - orog
    T = hr(df["t2m"]) - 273.15 - 0.0065 * dz          # standard lapse to the site elevation (placeholder; HRRR terrain is smoothed)
    Td = hr(df["d2m"]) - 273.15 - 0.002 * dz
    es = lambda t: 6.112 * np.exp(17.62 * t / (243.12 + t))
    RH = np.clip(es(Td) / es(T), 0.05, 1.0)
    W = np.hypot(hr(df["u10"]), hr(df["v10"])).clip(lower=0.3)
    h = cs.horizontal(day["lat"], day["lon"], orog, times=idx)
    kt = (hr(df["sdswrf"]) / h["ghi"].where(h["ghi"] > 80)).where(lambda x: (x >= 0) & (x <= 1.05))
    kt = kt.where((90 - h["zenith"]) > 15).interpolate(limit_area=None).ffill().bfill()
    print(f"   HRRR point terrain {orog / FT:.0f} ft (site {day['elev_ft']} ft): median midday kt {float(kt[(90 - h['zenith']) > 25].median()):.2f}")
    cloud = (1 - kt / KT_CLEAR).clip(0, 1)
    return (T + 273.15), RH, W, cloud, kt, T, hr(df["sdlwrf"])


def forcing(day, idx):
    """Forcing on the half-hour index `idx` (UTC): air T (K), RH (0-1), wind (m/s) at the site; cloud fraction and kt."""
    d0 = pd.Timestamp(day["date"], tz="UTC") - pd.Timedelta(days=SPINUP_DAYS + 1)
    d1 = pd.Timestamp(day["date"], tz="UTC") + pd.Timedelta(days=2)
    stids = sorted(set(day["T"] + [day["W"]] + day["SW"]))
    obs = synoptic(stids, d0, d1)
    elev = day["elev_ft"] * FT
    hr = lambda s: s.reindex(idx.union(s.index)).interpolate(limit=6, limit_area="inside").reindex(idx)
    Ts, Ds = [], []
    for sid in day["T"]:
        meta, df = obs[sid]
        T, RH = hr(df["T"]), hr(df["RH"])
        Ts.append((meta["elev_m"], T))
        Ds.append((meta["elev_m"], dewpoint(T, RH)))
    if len(Ts) == 1:
        T, Td = Ts[0][1], Ds[0][1]
        lapse = 0.0065 * (elev - Ts[0][0])             # no second station: standard lapse rate to the site (placeholder)
        T, Td = T - lapse, Td - 0.002 * (elev - Ts[0][0])
    else:
        (e0, T0), (e1, T1) = sorted(Ts, key=lambda x: x[0])
        (_, D0), (_, D1) = sorted(Ds, key=lambda x: x[0])
        f = (elev - e0) / (e1 - e0)
        T, Td = T0 + f * (T1 - T0), D0 + f * (D1 - D0)
    es = lambda t: 6.112 * np.exp(17.62 * t / (243.12 + t))
    RH = np.clip(es(Td) / es(T), 0.05, 1.0)
    wmeta, wdf = obs[day["W"]]
    W = hr(wdf["W"]).clip(lower=0.3)
    kt_f, used = None, None
    for sid in day["SW"]:                          # first radiometer with a usable clearness index in this window
        smeta, sdf = obs[sid]
        sw = hr(sdf["SW"])
        h = cs.horizontal(smeta["lat"], smeta["lon"], smeta["elev_m"], times=idx)
        kt = (sw / h["ghi"].where(h["ghi"] > 80)).where(lambda x: (x >= 0) & (x <= 1.05))
        kt_day = kt.where((90 - h["zenith"]) > 15)
        if kt_day.notna().sum() >= 8:
            kt_f, used = kt_day.interpolate(limit_area=None).ffill().bfill(), sid
            break
    if kt_f is None:
        print("   WARNING: no usable radiometer, assuming clear sky (kt = KT_CLEAR)")
        kt_f, used = pd.Series(KT_CLEAR, index=idx), "none"
    print(f"   radiometer {used}: median midday kt {float(kt_f[(90 - cs.horizontal(smeta['lat'], smeta['lon'], smeta['elev_m'], times=idx)['zenith']) > 25].median()):.2f}")
    cloud = (1 - kt_f / KT_CLEAR).clip(0, 1)
    T, RH, W = (x.ffill().bfill() for x in (T, RH, W))
    return (T + 273.15), RH, W, cloud, kt_f, T, None


def snow_age(day, idx):
    sn = snotel(day["SNOTEL"], pd.Timestamp(day["date"]) - pd.Timedelta(days=30), pd.Timestamp(day["date"]) + pd.Timedelta(days=1))
    gain = sn["WTEQ"].diff()
    snowy = gain[gain >= SNOW_DAY_IN]
    target = pd.Timestamp(day["date"])
    prior = snowy[snowy.index <= target]
    last = prior.index.max() if len(prior) else target - pd.Timedelta(days=30)
    return last, sn


def run(day):
    terr = pd.read_csv(TERRAIN)
    hc = [c for c in terr.columns if c.startswith("h") and c[1:].isdigit()]
    sb = 1 if day["slope"] < 25 else (2 if day["slope"] < 35 else 3)
    oc = int(round(day["aspect"] / 45)) % 8
    band_lo = int((day["elev_ft"] - 4000) // 500) * 500 + 4000
    g = terr[(terr.slope_bin == sb) & (terr.octant == oc)]
    g = g.iloc[(g.elev_ft_mid - (band_lo + 250)).abs().argsort()[:1]]
    row = g.iloc[0]
    last_snow, sn = snow_age(day, None)
    target = pd.Timestamp(day["date"], tz="UTC")
    local = pd.Timedelta(hours=-8)                               # PST for all the winter days run here
    start = max(target - pd.Timedelta(days=SPINUP_DAYS), (last_snow + pd.Timedelta(days=1)).tz_localize("UTC")) + pd.Timedelta(hours=8)
    end = target + pd.Timedelta(days=1) + pd.Timedelta(hours=8)
    idx = pd.date_range(start + pd.Timedelta(minutes=15), end, freq="30min")
    T, RH, W, cloud, kt, Tc, lw_override = (forcing_hrrr if day.get("source") == "hrrr" else forcing)(day, idx)
    hh = cs.horizontal(day["lat"], day["lon"], day["elev_ft"] * FT, times=idx)
    sw_cl = cs.tilted_terrain(hh, day["slope"], day["aspect"], row.vd, row.ct, row[hc].values)["total"]
    pressure = 101325 * (1 - 2.25577e-5 * day["elev_ft"] * FT) ** 5.25588
    age0 = (idx[0].tz_localize(None) - last_snow).total_seconds() / 86400
    alpha = ce.albedo(age0)                                  # decayed from fresh snow at the last snowfall, then stepped with the melt-freeze count
    col = ce.Column(T0=min(float(np.nanmean(T.values[:48])), 273.15), w0=0.0)
    top0 = min(float(np.nanmean(T.values[:48])), 273.15)
    col.T = np.linspace(top0, 273.15, ce.NL)               # starts linear from the mean air temperature (capped at 0 C) to the 0 C lower boundary
    col.t_deep = ce.T_DEEP
    rec = dict(t=[], T=[], w=[], ts=[], sw=[], ta=[], alb=[], lw=[], qs=[], ql=[], wind=[], rh=[])
    for n, t in enumerate(idx):
        age = age0 + (t - idx[0]).total_seconds() / 86400
        sw_abs = (1 - alpha) * sw_cl.values[n] * (kt.values[n] if np.isfinite(kt.values[n]) else 1.0)
        f = dict(sw_abs=sw_abs, lw_in=(float(lw_override.values[n]) if lw_override is not None else ce.lw_in(RH.values[n], T.values[n], cloud.values[n])), ta=T.values[n], rh=RH.values[n], vw=W.values[n],
                 pressure=pressure, z0=ce.z0(age))
        for _ in range(int(30 * 60 / ce.DT)):
            ts, _q = col.step(f)
        alpha = ce.albedo_step(alpha, col.cycles, 0.5 / 24)
        a_, b_ = ce.exchange(f["ta"], ts, f["vw"], pressure, f["z0"])
        rec["lw"].append(ce.EMISS_SNOW * f["lw_in"] - ce.EMISS_SNOW * ce.SIGMA * ts ** 4)
        rec["qs"].append(a_ * (f["ta"] - ts)); rec["ql"].append(b_ * (f["rh"] * ce.e_sat(f["ta"]) - ce.e_sat(ts))); rec["wind"].append(f["vw"]); rec["rh"].append(f["rh"])
        rec["t"].append(t); rec["T"].append(col.T - 273.15); rec["w"].append(col.w / col.m); rec["ts"].append(ts - 273.15)
        rec["sw"].append(sw_abs); rec["alb"].append(alpha); rec["ta"].append(T.values[n] - 273.15)
    res = {k: np.array(v) for k, v in rec.items() if k != "t"}
    res["t"] = pd.DatetimeIndex(rec["t"]).tz_localize(None) + local
    res["age0"], res["last_snow"], res["row"], res["sn"] = age0, last_snow, row, sn
    return res


def contiguous_wet_cm(w_frac):
    n = 0
    for x in w_frac:
        if x >= ce.W_THAW:
            n += 1
        else:
            break
    return n * ce.DZ * 100


def plot(day, res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIG.mkdir(parents=True, exist_ok=True)
    t, Tm, w = res["t"], res["T"], res["w"]
    depth = (np.arange(ce.NL) + 0.5) * ce.DZ * 100
    fig = plt.figure(figsize=(13, 7.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[3, 1.3], width_ratios=[60, 1], hspace=0.08, wspace=0.12)
    a1 = fig.add_subplot(gs[0, 0])
    a2 = fig.add_subplot(gs[1, 0], sharex=a1)
    cax = fig.add_subplot(gs[0, 1])
    plt.setp(a1.get_xticklabels(), visible=False)
    x = mdates_num(t)
    pm = a1.pcolormesh(x, depth, Tm.T, cmap=NWS_COLD, vmin=-15, vmax=0, shading="nearest")
    a1.contour(x, depth, w.T, levels=[ce.W_THAW], colors="k", linewidths=1.3)
    a1.set_ylim(depth[-1] + 0.5, 0)
    a1.set_ylabel("depth below the surface (cm)")
    cb = fig.colorbar(pm, cax=cax)
    cb.set_label("snow temperature (C); green = at 0 C")
    a1.set_title(f"{day['place']}  {day['date']}  ({'good corn' if day['good'] else 'bad day'}; reported {day['hhmm']})   {day['elev_ft']} ft, {day['slope']} deg, aspect {day['aspect']}\n"
                 f"black line: liquid water begins (>= {100 * ce.W_THAW:.1f}% of mass).  Snow age at start {res['age0']:.1f} d.  Forcing: observed stations; shortwave scaled by measured cloud.", fontsize=10)
    hh, mm = (int(v) for v in day["hhmm"].split(":"))
    mark = pd.Timestamp(day["date"]) + pd.Timedelta(hours=hh, minutes=mm)
    for a in (a1, a2):
        a.axvline(mdates_num([mark])[0], color="k", ls="--", lw=1)
        a.grid(alpha=0.2)
    a2.plot(x, res["ta"], color="#475569", label="air (lapse-adjusted)")
    a2.plot(x, res["ts"], color="#1d4ed8", label="snow surface")
    a2.axhline(0, color="k", lw=0.6)
    a2.set_ylabel("temperature (C)")
    a3 = a2.twinx()
    a3.fill_between(x, 0, res["sw"], color="#f59e0b", alpha=0.3)
    a3.set_ylabel("absorbed shortwave (W/m2)")
    a2.legend(loc="upper left", fontsize=8)
    import matplotlib.dates as md
    a2.xaxis.set_major_formatter(md.DateFormatter("%m-%d %H:%M"))
    plt.setp(a2.get_xticklabels(), rotation=25, ha="right")
    out = FIG / f"{day['date']}_{day['id']}.png"
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out


def mdates_num(t):
    import matplotlib.dates as md
    return md.date2num(pd.DatetimeIndex(t).to_pydatetime())


def summarize(day, res):
    t = res["t"]
    d0 = pd.Timestamp(day["date"])
    at = lambda h: int(np.argmin(np.abs((t - (d0 + pd.Timedelta(hours=h))).total_seconds())))
    hh, mm = (int(v) for v in day["hhmm"].split(":"))
    i = at(hh + mm / 60)
    m6 = at(6)
    night = (t >= d0 - pd.Timedelta(hours=6)) & (t <= d0 + pd.Timedelta(hours=7))
    crust = 0
    for k in range(ce.NL):
        if res["T"][m6, k] < -1e-6 and res["w"][m6, k] == 0:
            crust += 1
        else:
            break
    day_idx = np.where((t >= d0 + pd.Timedelta(hours=6)) & (t <= d0 + pd.Timedelta(hours=18)))[0]
    reach = [j for j in day_idx if res["ts"][j] > -0.05]
    return dict(day=day["date"], id=day["id"], good=day["good"], age_d=round(res["age0"] + (i * 0.5 / 24), 1), night_min_air=round(float(res["ta"][night].min()), 1),
                night_min_surf=round(float(res["ts"][night].min()), 1), crust_6am_cm=crust, surf_0C_at=(t[reach[0]].strftime("%H:%M") if reach else "never"),
                air_at_report=round(float(res["ta"][i]), 1), wet_cm_at_report=contiguous_wet_cm(res["w"][i]), wet_cm_15h=contiguous_wet_cm(res["w"][at(15)]))


def midday_budget(day, res):
    t = res["t"]
    d0 = pd.Timestamp(day["date"])
    m = (t >= d0 + pd.Timedelta(hours=10.5)) & (t <= d0 + pd.Timedelta(hours=13.5))
    g = lambda k: float(np.mean(np.asarray(res[k])[m]))
    return (f"   10:30-13:30 mean: SW absorbed {g('sw'):4.0f}  LW net {g('lw'):4.0f}  sensible {g('qs'):4.0f}  latent {g('ql'):4.0f} W/m2   "
            f"albedo {g('alb'):.2f}  wind {g('wind'):.1f} m/s  RH {100 * g('rh'):.0f}%  air {g('ta'):.1f} C  surface {g('ts'):.1f} C")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    todo = [d for d in DAYS if a.all or d["date"] == a.day]
    rows = []
    for d in todo:
        try:
            res = run(d)
        except Exception as ex:
            print(d["id"], "failed:", repr(ex)[:200])
            continue
        print(d["id"], "->", plot(d, res), "last snow day", res["last_snow"].date())
        print(midday_budget(d, res))
        rows.append(summarize(d, res))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
