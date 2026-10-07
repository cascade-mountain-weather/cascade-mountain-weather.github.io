"""UW WRF forecast soundings: fetch the raw profile for each forecast hour and derive snow diagnostics.

    python scripts/uw_soundings.py                       # Stampede Pass, newest available run
    python scripts/uw_soundings.py --init 2026100612 --hours 0 24 48
    python scripts/uw_soundings.py --out data/uw_soundings_ksmp.json

Source: the PacNW WRF-GFS 4/3 km forecast soundings page at a.atmos.washington.edu/mm5rt/rt/showsounding_d4.cgi.
Each frame (one per 3 forecast hours) embeds a plain-text table of the model profile at the station:
    PRES TMPC DWPC TMPF DWPF DRCT SPED SKNT HGTM HGTFT      (hPa, C, C, F, F, deg, m/s, kt, m, ft)
from the model's surface level up. A header line gives the station id, lat/lon, elevation and valid time.

Derived per frame (numpy only; the melting model is shared with scripts/collect_radiosonde_history.py):
  freezing level, wet-bulb-zero level and melting-model snow level (all MSL, ft),
  dendritic growth zone: thickness of the layer between -12 and -18 C, and the part of it that is near
  saturation (T - Td <= 2 C, a humidity proxy: the DGZ only makes snow where it is moist),
  strongest low-level inversion (lowest 3 km above the station): base height and temperature rise,
  precipitable water above the station (mm), and integrated vapor transport (kg/m/s) from the profile.

Be polite: it makes about 25 requests per site per run, one pause between each. Nothing is invented: a frame
that cannot be fetched or parsed is recorded as missing.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_radiosonde_history import compute_melting_layer  # noqa: E402

BASE = "https://a.atmos.washington.edu/mm5rt/rt/showsounding_d4.cgi"
HEADERS = {"User-Agent": "cascade-mountain-weather.github.io forecast-sounding research (dlhogan@uw.edu)"}
SITES = {   # id: (name, lat/lon string as the page expects)
    "ksmp": ("Stampede Pass,WA", "47.28N,121.34W"),
    "pvc55": ("Paradise-Mt Rainier,WA", "46.79N,121.74W"),
    "rimrk": ("Rimrock Retreat,WA", "46.67N,121W"),            # White Pass
    "kosmo": ("Kosmos,WA", "46.53N,122.2W"),                   # Mt. St. Helens side
    "dowlx": ("Olympex DOW,WA", "47.49N,123.87W"),             # Olympics
    "discl": ("Diablo Powerhouse,WA", "48.72N,121.14W"),       # North Cascades
    "lvwth": ("Leavenworth,WA", "47.6N,120.67W"),
    "mtwpm": ("Methow Valley,WA", "48.42N,120.16W"),
}
M_TO_FT = 3.28084
G = 9.80665


def page_url(init, hr, loc):
    name, latlon = SITES[loc]
    return (f"{BASE}?initmodel=GFS&yyyymmddhh={init}&reqhr={hr}&loc={loc}"
            f"&locname={requests.utils.quote(name)}&latlon={latlon}")


def fetch_frame(init, hr, loc, tries=3):
    """Raw text of one frame, or None if the run or hour is not there."""
    for attempt in range(tries):
        try:
            r = requests.get(page_url(init, hr, loc), headers=HEADERS, timeout=60)
            if r.status_code == 200 and "PRES" in r.text and "TMPC" in r.text:
                return r.text
            if r.status_code == 200:
                return None
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def parse_frame(html):
    """(meta, columns) from a frame page: meta has station, lat, lon, elev_m, valid (UTC datetime)."""
    text = re.sub(r"<[^>]*>", " ", html)
    meta = {}
    m = re.search(r"STID\s*=\s*(\w+).*?TIME\s*=\s*(\d{6})/(\d{4})", text, re.S)
    if not m:
        return None, None
    meta["station"] = m.group(1)
    meta["valid"] = datetime.strptime(m.group(2) + m.group(3), "%y%m%d%H%M").replace(tzinfo=timezone.utc)
    m = re.search(r"SLAT\s*=\s*([-\d.]+)\s+SLON\s*=\s*([-\d.]+)\s+SELV\s*=\s*([-\d.]+)", text)
    if m:
        meta["lat"], meta["lon"], meta["elev_m"] = float(m.group(1)), float(m.group(2)), float(m.group(3))
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.split()[:3] == ["PRES", "TMPC", "DWPC"]), None)
    if start is None:
        return meta, None
    names = lines[start].split()
    rows = []
    for ln in lines[start + 1:]:
        parts = ln.split()
        if len(parts) != len(names):
            if rows:
                break
            continue
        try:
            rows.append([float(x) for x in parts])
        except ValueError:
            break
    if len(rows) < 6:
        return meta, None
    arr = np.array(rows)
    return meta, {n: arr[:, i] for i, n in enumerate(names)}


def _es(t_c):
    return 6.112 * np.exp(17.62 * t_c / (243.12 + t_c))


def derive(meta, c):
    """Snow-relevant diagnostics from one profile (heights are MSL in the data; levels reported in feet MSL)."""
    p, t, td, z = c["PRES"], c["TMPC"], c["DWPC"], c["HGTM"]
    elev = z[0]
    out = {"surface_ft": round(elev * M_TO_FT), "surface_t_c": round(float(t[0]), 1), "surface_p_hpa": round(float(p[0]), 1)}
    melt = compute_melting_layer(z, t, td)   # heights above the lowest level (AGL)
    for key, name in (("freezing_level_m", "freezing_level_ft"), ("wet_bulb_zero_m", "wet_bulb_zero_ft"), ("snow_level_m", "snow_level_ft")):
        out[name] = None if melt[key] is None else round((melt[key] + elev) * M_TO_FT)
    if not np.any(t <= 0.0):
        out["freezing_level_ft"] = None   # whole profile above freezing
    elif t[0] <= 0.0:
        out["freezing_level_ft"] = round(elev * M_TO_FT)   # at or below freezing at the surface (station is above it)

    # dendritic growth zone: -12 to -18 C
    zi = np.linspace(z[0], z[-1], 2000)
    ti, tdi = np.interp(zi, z, t), np.interp(zi, z, td)
    in_dgz = (ti <= -12.0) & (ti >= -18.0)
    sat = in_dgz & ((ti - tdi) <= 2.0)
    dz = float(zi[1] - zi[0])
    out["dgz_thickness_m"] = round(float(in_dgz.sum() * dz))
    out["dgz_saturated_m"] = round(float(sat.sum() * dz))
    if in_dgz.any():
        out["dgz_base_ft"], out["dgz_top_ft"] = round(float(zi[in_dgz][0]) * M_TO_FT), round(float(zi[in_dgz][-1]) * M_TO_FT)

    # strongest inversion in the lowest 3 km: largest temperature rise from a local minimum to a later maximum
    low = zi <= z[0] + 3000.0
    zl, tl = zi[low], ti[low]
    run_min_i = np.minimum.accumulate(tl)
    rise = tl - run_min_i
    k = int(np.argmax(rise))
    if rise[k] >= 1.0:
        base_i = int(np.argmax(tl[:k + 1] == run_min_i[k]))
        out["inversion_rise_c"], out["inversion_base_ft"], out["inversion_top_ft"] = round(float(rise[k]), 1), round(float(zl[base_i]) * M_TO_FT), round(float(zl[k]) * M_TO_FT)
    else:
        out["inversion_rise_c"] = 0.0

    # precipitable water above the station and integrated vapor transport
    e = np.minimum(_es(td), 0.99 * p)
    w = 0.622 * e / (p - e)
    q = w / (1 + w)
    dp = -np.diff(p) * 100.0   # Pa, positive going up
    qm = 0.5 * (q[1:] + q[:-1])
    out["pw_mm"] = round(float((qm * dp).sum() / G), 1)
    spd, drc = c["SPED"], np.radians(c["DRCT"])
    u, v = -spd * np.sin(drc), -spd * np.cos(drc)
    um, vm = 0.5 * (u[1:] + u[:-1]), 0.5 * (v[1:] + v[:-1])
    qu, qv = (qm * um * dp).sum() / G, (qm * vm * dp).sum() / G
    out["ivt_kgms"] = round(float(np.hypot(qu, qv)))
    # 850 hPa and 700 hPa for context
    for lev in (850, 700):
        if p[-1] <= lev <= p[0]:
            out[f"t{lev}_c"] = round(float(np.interp(-lev, -p, t)), 1)
            out[f"wind{lev}_kt"] = round(float(np.interp(-lev, -p, c["SKNT"])))
    return out


def newest_init(loc, last_hr, now=None):
    """Newest 00Z/12Z run whose last requested frame already exists (so a half-published run is skipped)."""
    now = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    t = now - timedelta(hours=now.hour % 12)
    for _ in range(6):
        init = t.strftime("%Y%m%d%H")
        if fetch_frame(init, last_hr, loc, tries=1):
            return init
        t -= timedelta(hours=12)
    return None


PROFILE_TOP_HPA = 300.0   # the page's skew-T stops here, so higher levels are not stored


def compact_profile(c):
    """The part of a profile the skew-T draws: pressure, temperature, dew point (C, 0.1) and height (m), up to 300 hPa."""
    keep = c["PRES"] >= PROFILE_TOP_HPA
    r = lambda k, nd: [round(float(v), nd) for v in c[k][keep]]  # noqa: E731
    return {"p": r("PRES", 1), "t": r("TMPC", 1), "td": r("DWPC", 1), "z": [int(round(float(v))) for v in c["HGTM"][keep]]}


def run_site(loc, init, hours, pause):
    frames, missing, profiles = [], [], []
    for hr in hours:
        html = fetch_frame(init, hr, loc)
        meta, cols = parse_frame(html) if html else (None, None)
        if cols is None:
            missing.append(hr)
        else:
            head = {"hour": hr, "valid_utc": f"{meta['valid']:%Y-%m-%dT%H:%MZ}"}
            frames.append({**head, **derive(meta, cols)})
            profiles.append({**head, **compact_profile(cols)})
        time.sleep(pause)
    return frames, missing, profiles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loc", nargs="+", default=["ksmp"], help="site ids, or 'all'")
    ap.add_argument("--init", help="run time YYYYMMDDHH (UTC); default: newest available")
    ap.add_argument("--hours", type=int, nargs="+", default=list(range(0, 73, 3)))
    ap.add_argument("--pause", type=float, default=0.7, help="seconds between requests")
    ap.add_argument("--out", help="JSON file for all sites (written compact)")
    ap.add_argument("--profile-dir", help="also write <dir>/<site>.json with the full profiles and diagnostics (the page reads these)")
    ap.add_argument("--archive-dir", help="also save the run as <dir>/<init>.json.gz; a run already there is skipped (nothing is fetched)")
    ap.add_argument("--quiet", action="store_true", help="skip the per-frame table")
    args = ap.parse_args()

    locs = list(SITES) if args.loc == ["all"] else args.loc
    t0 = time.time()
    init = args.init or newest_init(locs[0], max(args.hours))
    if init is None:
        print("no complete run found yet; nothing to do")
        return
    archive = Path(args.archive_dir) / f"{init}.json.gz" if args.archive_dir else None
    if archive and archive.exists():
        print(f"run {init}Z is already archived; nothing to do")
        return
    out = {"source": "UW PacNW WRF-GFS 4/3 km forecast soundings", "init_utc": init,
           "first_seen_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}",   # lag after the run time = publication delay
           "fetched_utc": None, "sites": {}}
    site_files = {}
    for loc in locs:
        frames, missing, profiles = run_site(loc, init, args.hours, args.pause)
        out["sites"][loc] = {"name": SITES[loc][0], "missing_hours": missing, "frames": frames}
        site_files[loc] = {"init_utc": init, "name": SITES[loc][0], "elevation_ft": frames[0]["surface_ft"] if frames else None,
                           "frames": [{**f, **pr} for f, pr in zip(frames, profiles)]}
        print(f"{loc} run {init}Z: {len(frames)} frames, missing {missing}, {time.time() - t0:.0f} s elapsed", flush=True)
        if args.quiet:
            continue
        print("hr  valid          sfc_T  frz_ft wbz_ft snow_ft  DGZ m (sat)  inv C @ft      PW mm  IVT  T850")
        for f in frames:
            print(f"{f['hour']:>3} {f['valid_utc'][5:]} {f['surface_t_c']:>6} {str(f['freezing_level_ft']):>7} {str(f['wet_bulb_zero_ft']):>6} {str(f['snow_level_ft']):>7}  "
                  f"{f['dgz_thickness_m']:>5} ({f['dgz_saturated_m']:>4})  {f['inversion_rise_c']:>4} @{str(f.get('inversion_base_ft', '-')):>6}  {f['pw_mm']:>6} {f['ivt_kgms']:>4}  {f.get('t850_c', '-')}")
    out["fetched_utc"] = f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}"
    if any(v["missing_hours"] for v in out["sites"].values()) and archive:
        print("some frames are missing; not archiving this run (the next attempt retries)")
        return
    text = json.dumps(out, separators=(",", ":"))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote", args.out)
    if args.profile_dir:
        Path(args.profile_dir).mkdir(parents=True, exist_ok=True)
        for loc, body in site_files.items():
            (Path(args.profile_dir) / f"{loc}.json").write_text(json.dumps(body, separators=(",", ":")), encoding="utf-8")
        print("wrote profiles for", ", ".join(site_files), "to", args.profile_dir)
    if archive:
        import gzip
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(gzip.compress(text.encode("utf-8")))
        print("archived", archive, f"({archive.stat().st_size // 1024} KB)")

if __name__ == "__main__":
    main()
