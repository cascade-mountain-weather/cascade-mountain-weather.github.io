"""Current state of the PNA and the MJO for the "Reading the Tea Leaves" page: assets/data/tele_now.json (daily bot).

    python scripts/tele_now.py [--out FILE]

PNA   CPC daily PNA index (observed, to about yesterday) and the GEFS ensemble forecast of the same index (31 members,
      15 days from the latest run): https://ftp.cpc.ncep.noaa.gov/cwlinks/ (norm.daily.pna.index..., norm.daily.pna.gefs...)
MJO   NOAA PSL ROMI, the real-time OLR-based MJO index computed from CPC OLR, which runs to within a few days of today
      (https://psl.noaa.gov/mjo/mjoindex/romi.cpcolr.1x.txt). The relationships on the site were built with the OMI, whose public
      file is not kept current, so ROMI is turned into the same phase numbering by finding the rotation that best agrees with the
      OMI over their common years. No machine-readable MJO *forecast* is published that we could find, so none is included;
      the page asks the reader to read the ECMWF and GEFS figures for that.
ONI and PDO come from assets/data/climate_indices.json (collect_climate_indices.py).
Nothing is invented: a value the sources do not have is left out.
"""
import argparse
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "tele_now.json"
H = {"User-Agent": "Mozilla/5.0 (cascade-mountain-weather.github.io teleconnection page; dlhogan@uw.edu)"}
CPC = "https://ftp.cpc.ncep.noaa.gov/cwlinks/"
OMI_URL = "https://psl.noaa.gov/mjo/mjoindex/omi.1x.txt"
ROMI_URL = "https://psl.noaa.gov/mjo/mjoindex/romi.cpcolr.1x.txt"
OMI_PHASE_SHIFT = 6        # OMI phases rotated to match the BoM RMM numbering (scripts/tele_analysis.py phase_check; 91% within one phase)


def get(url):
    r = requests.get(url, headers=H, timeout=90)
    r.raise_for_status()
    return r.text


def phases(c1, c2, amp, shift):
    ang = (np.degrees(np.arctan2(c2, c1)) + 360) % 360
    ph = ((((ang - 180) % 360) // 45).astype(int) + shift) % 8 + 1
    return np.where(amp >= 1, ph, 0)


def mjo():
    omi = pd.read_csv(io.StringIO(get(OMI_URL)), sep=r"\s+", header=None, names=["y", "m", "d", "pc1", "pc2", "amp"])
    omi = omi[omi["amp"] < 900]
    omi.index = pd.to_datetime(dict(year=omi.y, month=omi.m, day=omi.d))
    rows = []
    for ln in get(ROMI_URL).splitlines():
        p = ln.split()
        if len(p) >= 7 and p[0].isdigit() and abs(float(p[4])) < 900:
            rows.append((pd.Timestamp(int(p[0]), int(p[1]), int(p[2])), float(p[4]), float(p[5]), float(p[6])))
    romi = pd.DataFrame(rows, columns=["date", "r1", "r2", "amp"]).set_index("date")
    omi_ph = pd.Series(phases(omi["pc1"].values, omi["pc2"].values, omi["amp"].values, OMI_PHASE_SHIFT), index=omi.index)
    j = romi.join(omi_ph.rename("omi"), how="inner")
    j = j[(j["omi"] > 0) & (j["amp"] >= 1)]
    best, ok = max(((s, float((phases(j["r1"].values, j["r2"].values, j["amp"].values, s) == j["omi"].values).mean())) for s in range(8)), key=lambda x: x[1])
    near = float((np.abs(((phases(j["r1"].values, j["r2"].values, j["amp"].values, best) - j["omi"].values + 4) % 8) - 4) <= 1).mean())
    both = romi.join(omi[["amp"]].rename(columns={"amp": "omi_amp"}), how="inner")
    amp_corr = float(np.corrcoef(both["amp"], both["omi_amp"])[0, 1])
    last = romi.tail(40)
    return {"source": ROMI_URL, "romi_shift": best, "agree_exact": round(ok, 3), "agree_within_one": round(near, 3), "overlap_days": int(len(j)), "amp_corr": round(amp_corr, 3),
            "last_omi": str(omi.index[-1].date()),
            "series": [{"date": str(d.date()), "r1": round(r.r1, 3), "r2": round(r.r2, 3), "amp": round(r.amp, 3),
                        "phase": int(phases(np.array([r.r1]), np.array([r.r2]), np.array([r.amp]), best)[0])} for d, r in last.iterrows()]}


def pna():
    obs = []
    for ln in get(CPC + "norm.daily.pna.index.b500101.current.ascii").splitlines():
        import re
        m = re.match(r"\s*(\d{4})\s+(\d+)\s+(\d+)\s*(-?\d+\.\d+)", ln)
        if m and float(m.group(4)) > -90:
            obs.append((f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", float(m.group(4))))
    g = pd.read_csv(io.StringIO(get(CPC + "norm.daily.pna.gefs.z500.120days.csv")))
    init = g["time"].max()
    # the observed index lags a few days; each GEFS run's day-0 value (its analysis) fills the gap up to the forecast
    last_obs = obs[-1][0]
    a0 = g[g["lead"] == 0].groupby("valid_time")["pna_index"].mean()
    for d, v in a0.items():
        if d > last_obs and d < init:
            obs.append((d, float(v)))
    g = g[g["time"] == init]
    by = g.groupby("valid_time")["pna_index"]
    fc = pd.DataFrame({"mean": by.mean(), "p10": by.quantile(0.1), "p90": by.quantile(0.9), "n": by.count()}).reset_index()
    obs = obs[-40:]
    return {"source": CPC, "obs": [{"date": d, "v": round(v, 3)} for d, v in obs], "gefs_init": str(init),
            "gefs": [{"date": r.valid_time, "mean": round(r["mean"], 3), "p10": round(r.p10, 3), "p90": round(r.p90, 3), "n": int(r.n)} for _, r in fc.iterrows()]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    out_path = Path(a.out)
    old = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    res = {}
    for name, fn in [("pna", pna), ("mjo", mjo)]:
        try:
            res[name] = fn()
        except Exception as e:                       # keep the last good value for a source that is down
            print(f"{name}: failed ({e}); keeping the previous value")
            if old.get(name):
                res[name] = old[name]
    if not res:
        sys.exit("nothing fetched; keeping the existing file")
    if {k: v for k, v in old.items() if k != "generated_utc"} == res:
        print("no change")
        return
    res["generated_utc"] = f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
    m, p = res.get("mjo"), res.get("pna")
    print(f"wrote {out_path} ({out_path.stat().st_size // 1024} KB)")
    if m:
        print(f"  MJO: ROMI to {m['series'][-1]['date']} (phase {m['series'][-1]['phase']}, amp {m['series'][-1]['amp']}); rotation {m['romi_shift']}, "
              f"agreement with OMI {m['agree_exact']:.0%} exact, {m['agree_within_one']:.0%} within one phase, amplitude correlation {m['amp_corr']}")
    if p:
        print(f"  PNA: observed to {p['obs'][-1]['date']}, GEFS run {p['gefs_init']} to {p['gefs'][-1]['date']}")


if __name__ == "__main__":
    main()
