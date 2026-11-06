"""SLR against temperature aloft, from hourly SNOTEL SWE and depth at 28 Cascade and Olympic stations.

    python scripts/slr_analysis_hourly.py
    python scripts/slr_analysis_hourly.py --min-swe 0.3 --max-slr 25 --max-temp 34

Reads what scripts/slr_pull_snotel_hourly.py and scripts/slr_pull_soundings.py saved in data/slr/.

Windows. Each 00Z and 12Z launch gets a 12-hour window centred on it (launch minus 6 h to launch plus 6 h), so the sounding is the
air mass the snow fell from. For each station and window:
    swe, depth     net change over the window (end minus start; hourly gaps of up to 3 h are interpolated)
    swe_pos, dep_pos   the sum of the positive hourly steps of a 3-hour median of each series, which ignores settling (it only ever
                   subtracts) at the price of counting sensor noise upward
    prec, tobs     precipitation gain and mean air temperature (F) in the window
SLR = depth / SWE. The analysis uses the net change; 'positive steps' is a variant printed in the comparison.

Storm runs. Consecutive windows that each gain at least 0.1 in of SWE (and are cold enough) are merged into one run, so a storm
that outlasts 12 hours is judged on its whole length, paired with the mean of the launches in the run.

Screens, counted in the printout: SWE gain at least --min-swe (0.2 in per window, 0.5 in per run), mean air temperature at most --max-temp
(34 F), precipitation supports the SWE gain (swe <= 1.4 x precip + 0.1 in and precip <= 1.6 x swe + 0.1 in), depth gain above 0, SLR from --min-slr (2) to --max-slr
(25). Then correlations (Pearson and Spearman, and the slope per degree C) against the 925, 850, 700 and 500 hPa temperatures
of Quillayute (UIL), Spokane (OTX) and Salem (SLE), and against the station's own temperature. Also splits by elevation and by the east and west
sides of the crest, the median SLR and the depth-on-SWE slope (sum of depth over sum of SWE, the ratio the bulk of the snow had) by temperature bin, and how
the answer changes with the SLR cap and with net versus positive-step gains. Writes data/slr/slr_pairs_hourly.csv.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slr_analysis import LEVELS, SITES, SLR, ROOT, load_soundings, table  # noqa: E402

HALF = pd.Timedelta(hours=6)
PST = pd.Timedelta(hours=8)   # local standard time to UTC
CREST_LON = -121.0


def station_series():
    """{triplet: hourly frame on a UTC grid} with gaps up to 3 h interpolated."""
    groups = {}
    for p in sorted((SLR / "snotel_hourly").glob("*.csv")):
        groups.setdefault(p.stem.rsplit("_", 1)[0], []).append(p)
    if not groups:
        sys.exit("no files in data/slr/snotel_hourly; run scripts/slr_pull_snotel_hourly.py first")
    out = {}
    for key, paths in groups.items():
        df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
        if df.empty:
            continue
        df["time"] = pd.to_datetime(df["time"]) + PST
        df = df.drop_duplicates("time").set_index("time").sort_index()
        grid = pd.date_range(df.index[0], df.index[-1], freq="h")
        df = df.reindex(grid)
        df = df.interpolate(limit=3, limit_area="inside")
        out[key.replace("_", ":", 2)] = df
    return out


def positive_steps(s):
    """Cumulative sum of the positive hourly steps of a 3 h median, so a window sum is a difference of two values."""
    m = s.rolling(3, center=True, min_periods=2).median()
    return m.diff().clip(lower=0).fillna(0).cumsum()


def windows(key, df, snd_idx):
    launches = df.index[(df.index.hour % 12 == 0)]
    launches = launches[(launches >= df.index[0] + HALF) & (launches <= df.index[-1] - HALF)]
    lo, hi = launches - HALF, launches + HALF
    swe, dep, prec = df["wteq_in"], df["snwd_in"], df["prec_in"]
    cswe, cdep = positive_steps(swe), positive_steps(dep)
    tmean = df["tobs_f"].rolling(13, center=True, min_periods=8).mean()
    r = pd.DataFrame({
        "station": key, "launch": launches,
        "swe": swe.reindex(hi).to_numpy() - swe.reindex(lo).to_numpy(),
        "depth": dep.reindex(hi).to_numpy() - dep.reindex(lo).to_numpy(),
        "prec": prec.reindex(hi).to_numpy() - prec.reindex(lo).to_numpy(),
        "swe_pos": cswe.reindex(hi).to_numpy() - cswe.reindex(lo).to_numpy(),
        "dep_pos": cdep.reindex(hi).to_numpy() - cdep.reindex(lo).to_numpy(),
        "tobs_f": tmean.reindex(launches).to_numpy(),
    })
    for (site, lev), s in snd_idx.items():
        r[f"{site}_{lev}"] = s.reindex(launches).to_numpy()
    return r


def storm_runs(w, a):
    """Merge consecutive qualifying windows of one station into runs."""
    rows = []
    for st, g in w.groupby("station"):
        g = g.sort_values("launch")
        ok = (g["swe"] >= 0.1) & (g["tobs_f"] <= a.max_temp) & (g["depth"] > 0)
        brk = (g["launch"].diff() != pd.Timedelta(hours=12)) | ~ok | ~ok.shift(fill_value=False)
        gid = brk.cumsum()
        for _, r in g[ok].groupby(gid[ok]):
            row = {"station": st, "launch": r["launch"].iloc[0], "n_win": len(r)}
            for c in ("swe", "depth", "prec", "swe_pos", "dep_pos"):
                row[c] = r[c].sum()
            row["tobs_f"] = r["tobs_f"].mean()
            for c in w.columns:
                if c[:3] in SITES:
                    row[c] = r[c].mean()
            rows.append(row)
    return pd.DataFrame(rows)


def screen(df, a, swe_col="swe", dep_col="depth", min_swe=None, verbose=True, cap=None):
    min_swe = a.min_swe if min_swe is None else min_swe
    cap = a.max_slr if cap is None else cap
    d = df.copy()
    d["slr"] = d[dep_col] / d[swe_col]
    steps = [(f"SWE gain >= {min_swe} in", d[swe_col] >= min_swe),
             (f"mean air temperature <= {a.max_temp} F", d["tobs_f"] <= a.max_temp),
             ("precipitation supports the SWE gain", (d[swe_col] <= 1.4 * d["prec"] + 0.1) & (d["prec"] <= 1.6 * d[swe_col] + 0.1)),
             ("depth gain above 0", d[dep_col] > 0),
             (f"SLR between {a.min_slr:g} and {cap:g}", d["slr"].between(a.min_slr, cap))]
    if verbose:
        print(f"{len(d):>8,}   windows or runs with both readings")
    for label, ok in steps:
        d = d[ok.loc[d.index]]
        if verbose:
            print(f"{len(d):>8,}   after {label}")
    return d


def spearman(d, col):
    x = d[["slr", col]].dropna()
    return (x[col].corr(x["slr"], method="spearman"), len(x)) if len(x) >= 30 else (np.nan, len(x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-swe", type=float, default=0.2, help="smallest SWE gain per 12 h window, inches (runs use 2.5 times this)")
    ap.add_argument("--max-temp", type=float, default=34.0)
    ap.add_argument("--min-slr", type=float, default=2.0)
    ap.add_argument("--max-slr", type=float, default=25.0)
    a = ap.parse_args()

    series = station_series()
    snd = load_soundings()
    snd_idx = {(site, lev): snd[snd["station"] == site].drop_duplicates("valid").set_index("valid")[f"t{lev}_c"]
               for site in SITES for lev in LEVELS}
    w = pd.concat([windows(k, df, snd_idx) for k, df in series.items()], ignore_index=True)
    meta = pd.read_csv(SLR / "snotel_stations.csv").rename(columns={"triplet": "station"}).set_index("station")[["name", "elevation_ft", "lat", "lon"]]
    print(f"{len(series)} stations, {len(w):,} twelve-hour windows, {w['launch'].min():%Y-%m-%d} to {w['launch'].max():%Y-%m-%d}")

    print("\n--- 12 h windows, net change ---")
    d = screen(w, a)
    d = d.join(meta, on="station")
    d["region"] = np.where(d["lon"] < CREST_LON, "west", "east")
    d["band"] = pd.cut(d["elevation_ft"], [0, 4000, 5000, 20000], labels=["3,000-4,000 ft", "4,000-5,000 ft", "over 5,000 ft"])
    print(f"\nSLR: median {d['slr'].median():.1f}, 25th-75th percentile {d['slr'].quantile(.25):.1f}-{d['slr'].quantile(.75):.1f}, n = {len(d):,}")
    cols = [("station temperature", "tobs_f")] + [(f"{s} {lev} hPa", f"{s}_{lev}") for s in SITES for lev in LEVELS]
    overall = table(d, cols, "All windows: SLR against temperature (station in F, soundings in C)")
    if overall is None:
        return
    sound = overall.drop(index="station temperature", errors="ignore")
    best = sound["spearman"].abs().idxmax()
    bcol = dict(cols)[best]
    print(f"\nStrongest sounding predictor: {best}")
    for field, vals in (("region", ["west", "east"]), ("band", list(d["band"].cat.categories))):
        for v in vals:
            sub = d[d[field] == v]
            table(sub, [("station temperature", "tobs_f")] + [(f"{s} {lev}", f"{s}_{lev}") for s in SITES for lev in (850, 700)], f"{field}: {v} ({len(sub):,} windows)")

    for label, col in (("700 hPa, Spokane", "OTX_700"), (best, bcol)):
        x = d[["slr", "depth", "swe", col]].dropna()
        x["bin"] = pd.cut(x[col], np.arange(-26, 6, 2))
        b = x.groupby("bin", observed=True).agg(n=("slr", "size"), median=("slr", "median"), p25=("slr", lambda s: s.quantile(.25)),
                                               p75=("slr", lambda s: s.quantile(.75)), depth=("depth", "sum"), swe=("swe", "sum"))
        b["depth_per_swe"] = b["depth"] / b["swe"]
        print(f"\nSLR by {label} temperature bin (C); depth_per_swe is total depth over total SWE")
        print(b[b["n"] >= 10].drop(columns=["depth", "swe"]).to_string(float_format=lambda v: f"{v:.1f}"))

    print("\n--- 12 h windows, sum of positive steps (settling ignored) ---")
    dp = screen(w, a, "swe_pos", "dep_pos")
    print("\n--- storm runs (consecutive windows) ---")
    runs = storm_runs(w, a)
    print(f"{len(runs):,} runs from {runs['station'].nunique()} stations")
    dr = screen(runs, a, min_swe=a.min_swe * 2.5)

    print("\nSpearman correlation with SLR (n in brackets) by version")
    keys = [("tobs_f", "station T"), ("UIL_700", "UIL 700"), ("OTX_850", "OTX 850"), ("OTX_700", "OTX 700"), ("SLE_850", "SLE 850"), ("SLE_700", "SLE 700")]
    versions = [(f"windows net, cap {c:g}", screen(w, a, verbose=False, cap=c)) for c in (20, 25, 30)]
    versions += [("windows positive steps", dp), ("storm runs", dr)]
    rows = []
    for name, v in versions:
        row = {"version": name, "n": len(v), "median SLR": v["slr"].median()}
        for col, lab in keys:
            r, n = spearman(v, col)
            row[lab] = r
        rows.append(row)
    print(pd.DataFrame(rows).set_index("version").to_string(float_format=lambda v: f"{v:.2f}"))

    out = SLR / "slr_pairs_hourly.csv"
    d.drop(columns=["band"]).to_csv(out, index=False)
    print(f"\nwrote {out.relative_to(ROOT)} ({len(d):,} rows)")


if __name__ == "__main__":
    main()
