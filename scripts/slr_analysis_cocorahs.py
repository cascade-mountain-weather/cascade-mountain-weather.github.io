"""SLR against temperature aloft, from CoCoRaHS volunteer measurements (the cleaner test than SNOTEL daily depth).

    python scripts/slr_analysis_cocorahs.py
    python scripts/slr_analysis_cocorahs.py --min-swe 0.15 --max-slr 40 --need-both

Each report (scripts/slr_pull_cocorahs.py) gives new-snow depth and its melted water content, measured by one observer
around 7 am for the previous 24 hours, so SLR = depth / water content is a direct measurement of the snow that fell.
Each report is paired with the mean temperature of the 00Z and 12Z launches inside its 24 h window (Quillayute UIL,
Spokane OTX, Salem SLE; 925, 850, 700, 500 hPa), the same soundings as scripts/slr_analysis.py. A storm that fell for only part of the
window is blended with the rest of the window, so some noise remains.

Screens (counted in the printout): water content at least --min-swe (default 0.10 in, since 0.01 in resolution makes small
amounts meaningless), depth at least 0.5 in, SLR between --min-slr (2) and --max-slr (40). Writes data/slr/slr_pairs_cocorahs.csv.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slr_analysis import LEVELS, SITES, SLR, ROOT, load_soundings, relationship, table  # noqa: E402


def load_reports():
    frames = [pd.read_csv(p, dtype={"station": str}) for p in sorted((SLR / "cocorahs").glob("*.csv"))]
    if not frames:
        sys.exit("no files in data/slr/cocorahs; run scripts/slr_pull_cocorahs.py first")
    df = pd.concat(frames, ignore_index=True).drop_duplicates(["obs_date", "station"])
    local = pd.to_datetime(df["obs_date"] + " " + df["obs_time"].fillna("07:00 AM"), format="%Y-%m-%d %I:%M %p", errors="coerce")
    df = df[local.notna()].copy()
    local = local[local.notna()]
    # Pacific local to UTC (daylight time from March)
    df["end_utc"] = local.dt.tz_localize("America/Los_Angeles", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC").dt.tz_localize(None)
    return df[df["end_utc"].notna()]


def attach(df, snd, need_both):
    ends = df["end_utc"].to_numpy()
    for site in SITES:
        s = snd[snd["station"] == site].sort_values("valid")
        times = s["valid"].to_numpy()
        for lev in LEVELS:
            vals = s[f"t{lev}_c"].to_numpy(dtype=float)
            out, count = np.full(len(df), np.nan), np.zeros(len(df), int)
            lo = np.searchsorted(times, ends - np.timedelta64(24, "h"), side="right")
            hi = np.searchsorted(times, ends, side="right")
            for i, (a, b) in enumerate(zip(lo, hi)):
                v = vals[a:b]
                v = v[~np.isnan(v)]
                if len(v) and (len(v) >= 2 or not need_both):
                    out[i], count[i] = v.mean(), len(v)
            df[f"{site}_{lev}"] = out
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-swe", type=float, default=0.10)
    ap.add_argument("--min-slr", type=float, default=2.0)
    ap.add_argument("--max-slr", type=float, default=40.0)
    ap.add_argument("--need-both", action="store_true", help="require both the 00Z and 12Z launch in the window")
    a = ap.parse_args()

    df = load_reports()
    snd = load_soundings()
    print(f"{len(df):,} CoCoRaHS snow reports with a water content, {df['station'].nunique()} stations, "
          f"{df['obs_date'].min()} to {df['obs_date'].max()}")
    df["slr"] = df["new_snow_in"] / df["new_snow_swe_in"]
    for label, ok in ((f"water content >= {a.min_swe} in", df["new_snow_swe_in"] >= a.min_swe),
                      ("depth >= 0.5 in", df["new_snow_in"] >= 0.5),
                      (f"SLR between {a.min_slr:g} and {a.max_slr:g}", df["slr"].between(a.min_slr, a.max_slr))):
        df = df[ok.loc[df.index]]
        print(f"{len(df):>8,}   after {label}")

    df = attach(df, snd, a.need_both)
    try:
        from cocorahs_obs import stations
        elev = {s["id"]: s["elev_ft"] for s in stations()}
        df["elevation_ft"] = df["station"].map(elev)
    except Exception as exc:   # noqa: BLE001 -- elevation is only for the split
        print("no elevations:", str(exc)[:80])
        df["elevation_ft"] = np.nan
    df["region"] = np.where(df["lon"] < -121.0, "west", "east")
    df["band"] = pd.cut(df["elevation_ft"], [-1, 500, 1500, 20000], labels=["under 500 ft", "500-1,500 ft", "over 1,500 ft"])

    print(f"\nSLR: median {df['slr'].median():.1f}, 25th-75th percentile {df['slr'].quantile(.25):.1f}-{df['slr'].quantile(.75):.1f}, n = {len(df):,}")
    cols = [(f"{s} {lev} hPa", f"{s}_{lev}") for s in SITES for lev in LEVELS]
    overall = table(df, cols, "All reports: SLR against sounding temperature (C)")
    if overall is None:
        return
    best = overall["spearman"].abs().idxmax()
    bcol = dict(cols)[best]
    print(f"\nStrongest predictor: {best}")
    for field, vals in (("region", ["west", "east"]), ("band", list(df["band"].cat.categories))):
        for v in vals:
            sub = df[df[field] == v]
            table(sub, [(f"{s} {lev}", f"{s}_{lev}") for s in SITES for lev in (850, 700)], f"{field}: {v} ({len(sub):,} reports)")

    for label, col in (("700 hPa, best site", max((f"{s}_700" for s in SITES), key=lambda c: abs(df[c].corr(df['slr'], method='spearman') or 0))), (best, bcol)):
        d = df[["slr", col]].dropna()
        d["bin"] = pd.cut(d[col], np.arange(-26, 6, 2))
        b = d.groupby("bin", observed=True)["slr"].agg(n="size", median="median", p25=lambda x: x.quantile(.25), p75=lambda x: x.quantile(.75))
        print(f"\nSLR by {label} ({col}) temperature bin (C)")
        print(b[b["n"] >= 10].to_string(float_format=lambda v: f"{v:.1f}"))

    out = SLR / "slr_pairs_cocorahs.csv"
    df.drop(columns=["band"]).to_csv(out, index=False)
    print(f"\nwrote {out.relative_to(ROOT)} ({len(df):,} rows)")


if __name__ == "__main__":
    main()
