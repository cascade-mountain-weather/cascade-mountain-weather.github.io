"""Does the temperature aloft say anything about snow-to-liquid ratio (SLR)? First look.

    python scripts/slr_analysis.py                     # everything downloaded so far
    python scripts/slr_analysis.py --shift 1           # pair each SNOTEL day with the sounding day after (timing check)
    python scripts/slr_analysis.py --min-swe 0.6 --max-temp 32

Reads what scripts/slr_pull_snotel.py and scripts/slr_pull_soundings.py saved in data/slr/ and works in four steps.

1. One SNOTEL "storm day" per station and day: the change in SWE and in snow depth between consecutive daily readings.
   A daily value is a midnight Pacific reading (08Z), so the interval from one reading to the next (08Z to 08Z) contains
   the 12Z launch of that date and the 00Z launch of the next. (--shift moves the pairing a day, as a check on that
   assumption: the right alignment should show the stronger relationship.)
2. Screens, each counted in the printout, because daily depth is noisy (whole inches, settling, sensor flicker). Settling and
   compaction only ever lower the measured depth gain, so every SLR here is a LOWER BOUND on the true new-snow SLR:
     swe gain at least --min-swe (default 0.4 in)      a small gain is at the sensor's resolution
     depth gain at least 1 in                          depth must rise too (settling only ever lowers SLR)
     daily mean temperature at most --max-temp (34 F)  rain on snow raises SWE without making snow
     precipitation gain supports the SWE gain          swe <= 1.3 x precip + 0.1 in, and swe >= 0.7 x precip
     depth gain above the SWE gain and the precip gain   an SLR under 1 is impossible for snow
     SLR between --min-slr (3) and --max-slr (30)      outside this is usually a sensor fault, not snow
   SLR = depth gain / SWE gain, so 10 means 10 inches of snow per inch of water.
3. Each kept day is paired with the mean of the two launches' temperatures at 925, 850, 700 and 500 hPa from Quillayute
   (UIL), Spokane (OTX) and Salem (SLE), and with the station's own daily mean temperature as the thing to beat.
4. For every site and level: how many days, Pearson and Spearman correlation with SLR, and the slope (SLR per degree C).
   Then the same split by region (west or east of about 121.0 W, a rough crest line) and elevation band, and the median
   SLR by 700 hPa temperature bin for the site with the strongest relationship.

Writes data/slr/slr_pairs.csv (every kept day with its temperatures) so the analysis can be redone or plotted without
rerunning the pulls. A first look: the screens and thresholds above are the first thing to question.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SLR = ROOT / "data" / "slr"
SITES = ("UIL", "OTX", "SLE")
LEVELS = (925, 850, 700, 500)
CREST_LON = -121.0   # west of this is the west slope, east of it the east side (rough)


def load_snotel():
    frames = []
    for path in sorted((SLR / "snotel_daily").glob("*.csv")):
        df = pd.read_csv(path, parse_dates=["date"])
        df["station"] = path.stem.replace("_", ":", 2)   # 791_WA_SNTL -> 791:WA:SNTL
        frames.append(df)
    if not frames:
        sys.exit("no files in data/slr/snotel_daily; run scripts/slr_pull_snotel.py first")
    return pd.concat(frames, ignore_index=True)


def load_soundings():
    frames = [pd.read_csv(p) for p in sorted((SLR / "soundings").glob("*.csv"))]
    if not frames:
        sys.exit("no files in data/slr/soundings; run scripts/slr_pull_soundings.py first")
    s = pd.concat(frames, ignore_index=True)
    s = s[s["status"] == "ok"].copy()
    s["valid"] = pd.to_datetime(s["valid_utc"].str.rstrip("Z"))
    return s


def station_meta(stations):
    """lat, lon and elevation per station: from the saved summary if the pull finished, else from AWDB."""
    path = SLR / "snotel_stations.csv"
    if path.exists():
        m = pd.read_csv(path).rename(columns={"triplet": "station"})
        return m.set_index("station")[["name", "elevation_ft", "lat", "lon"]]
    import requests
    r = requests.get("https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/stations",
                     params={"stationTriplets": ",".join(stations)}, timeout=120)
    r.raise_for_status()
    return pd.DataFrame([{"station": s["stationTriplet"], "name": s["name"], "elevation_ft": s.get("elevation"),
                          "lat": s.get("latitude"), "lon": s.get("longitude")} for s in r.json()]).set_index("station")


def storm_days(sn, a):
    """One row per station and date d: the change from the reading on d to the reading on d+1."""
    nxt = sn.copy()
    nxt["date"] = nxt["date"] - pd.Timedelta(days=1)      # so a join on date brings in the next day's reading
    m = sn.merge(nxt, on=["station", "date"], suffixes=("", "_next"))
    out = pd.DataFrame({"station": m["station"], "date": m["date"],
                        "d_swe": m["wteq_in_next"] - m["wteq_in"], "d_depth": m["snwd_in_next"] - m["snwd_in"],
                        "d_prec": m["prec_in_next"] - m["prec_in"], "tavg_f": m["tavg_f"]})
    return out.dropna()


def screen(df, a):
    """Apply the screens in order, printing how many days survive each."""
    steps = [
        (f"SWE gain >= {a.min_swe} in", df["d_swe"] >= a.min_swe),
        ("depth gain >= 1 in", df["d_depth"] >= 1),
        (f"daily mean temperature <= {a.max_temp} F", df["tavg_f"] <= a.max_temp),
        ("precipitation supports the SWE gain", (df["d_swe"] <= 1.3 * df["d_prec"] + 0.1) & (df["d_swe"] >= 0.7 * df["d_prec"])),
        ("depth gain exceeds the SWE gain and the precipitation gain (SLR above 1)", (df["d_depth"] > df["d_swe"]) & (df["d_depth"] > df["d_prec"])),
    ]
    df = df.copy()
    df["slr"] = df["d_depth"] / df["d_swe"]
    steps.append((f"SLR between {a.min_slr:g} and {a.max_slr:g}", df["slr"].between(a.min_slr, a.max_slr)))
    print(f"{len(df):>8,} station-days with both readings and a temperature")
    for label, ok in steps:
        df = df[ok.loc[df.index]]
        print(f"{len(df):>8,}   after {label}")
    return df


def attach_soundings(df, snd, shift):
    """Mean of the 12Z launch on the pairing day and the 00Z launch the next day, per site and level."""
    for site in SITES:
        s = snd[snd["station"] == site].set_index("valid")
        for lev in LEVELS:
            col = f"t{lev}_c"
            if s.empty or col not in s:
                df[f"{site}_{lev}"] = np.nan
                continue
            t12 = s[col].reindex(df["date"] + pd.Timedelta(days=shift, hours=12)).to_numpy()
            t00 = s[col].reindex(df["date"] + pd.Timedelta(days=shift + 1)).to_numpy()
            df[f"{site}_{lev}"] = np.where(np.isnan(t12) | np.isnan(t00), np.nan, (t12 + t00) / 2)
    return df


def relationship(df, col):
    d = df[["slr", col]].dropna()
    if len(d) < 30:
        return None
    slope, intercept = np.polyfit(d[col], d["slr"], 1)
    r = d[col].corr(d["slr"])
    return {"n": len(d), "pearson": r, "spearman": d[col].corr(d["slr"], method="spearman"), "slope": slope, "r2": r * r}


def table(df, cols, title):
    rows = []
    for label, col in cols:
        rel = relationship(df, col)
        if rel:
            rows.append({"predictor": label, **rel})
    print(f"\n{title}")
    if not rows:
        print("  (fewer than 30 days with data)")
        return None
    t = pd.DataFrame(rows).set_index("predictor")
    print(t.to_string(float_format=lambda v: f"{v:.2f}"))
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-swe", type=float, default=0.4, help="smallest SWE gain kept, inches")
    ap.add_argument("--max-temp", type=float, default=34.0, help="warmest daily mean temperature kept, F")
    ap.add_argument("--min-slr", type=float, default=3.0, help="lowest SLR kept; settling makes daily SLR a lower bound, so low values are real, but below this is usually a fault")
    ap.add_argument("--max-slr", type=float, default=30.0, help="highest SLR kept")
    ap.add_argument("--shift", type=int, default=0, help="pair each SNOTEL day with the sounding day this many days later")
    a = ap.parse_args()

    sn = load_snotel()
    snd = load_soundings()
    print(f"SNOTEL: {sn['station'].nunique()} stations, {len(sn):,} Nov-Apr days; "
          f"soundings: " + ", ".join(f"{k} {v:,}" for k, v in snd.groupby('station').size().items()) + " launches with 700 hPa")
    days = storm_days(sn, a)
    kept = screen(days, a)
    kept = attach_soundings(kept, snd, a.shift)
    meta = station_meta(sorted(kept["station"].unique()))
    kept = kept.join(meta, on="station")
    kept["region"] = np.where(kept["lon"] < CREST_LON, "west", "east")
    kept["band"] = pd.cut(kept["elevation_ft"], [0, 3500, 5000, 20000], labels=["under 3,500 ft", "3,500-5,000 ft", "over 5,000 ft"])

    print(f"\nSLR of the kept days: median {kept['slr'].median():.1f}, 25th-75th percentile "
          f"{kept['slr'].quantile(.25):.1f}-{kept['slr'].quantile(.75):.1f}, n = {len(kept):,} (shift {a.shift})")
    cols = [("station temperature", "tavg_f")] + [(f"{s} {lev} hPa", f"{s}_{lev}") for s in SITES for lev in LEVELS]
    overall = table(kept, cols, "All stations: SLR against temperature (slope is SLR change per degree; station temperature is in F, the rest C)")
    if overall is None:
        return
    sound = overall.drop(index="station temperature", errors="ignore")
    if sound.empty:
        print("No sounding predictor has 30 or more paired days yet (the soundings are still downloading, or do not overlap the kept days).")
        out = SLR / "slr_pairs.csv"
        kept.drop(columns=["band"]).to_csv(out, index=False)
        print(f"wrote {out.relative_to(ROOT)} ({len(kept):,} rows)")
        return
    best = sound["spearman"].abs().idxmax()
    bcol = dict(cols)[best]
    print(f"\nStrongest sounding predictor overall: {best}")

    for field, vals in (("region", ["west", "east"]), ("band", list(kept["band"].cat.categories))):
        for v in vals:
            sub = kept[kept[field] == v]
            table(sub, [("station temperature", "tavg_f")] + [(f"{s} 700 hPa", f"{s}_700") for s in SITES], f"{field}: {v} ({len(sub):,} days)")

    d = kept[["slr", bcol]].dropna()
    d["bin"] = pd.cut(d[bcol], np.arange(-24, 4, 2))
    b = d.groupby("bin", observed=True)["slr"].agg(n="size", median="median", p25=lambda x: x.quantile(.25), p75=lambda x: x.quantile(.75))
    print(f"\nSLR by {best} temperature bin (C)")
    print(b[b["n"] >= 5].to_string(float_format=lambda v: f"{v:.1f}"))

    out = SLR / "slr_pairs.csv"
    kept.drop(columns=["band"]).to_csv(out, index=False)
    print(f"\nwrote {out.relative_to(ROOT)} ({len(kept):,} rows)")


if __name__ == "__main__":
    main()
