"""Render frozen weekend plume figures (snowfall and precipitation) for a forecast post.

    python scripts/post_plume.py --start 2026-11-06 --days 3 --out assets/images/20261105_fx
    python scripts/post_plume.py --start 2026-11-06 --days 3 --out DIR --areas "Mt. Baker" "Crystal"

Reads assets/data/nbm_plumes.json and assets/data/hires_plumes.json (the same files the precipitation
tools page draws live) and writes two PNGs into --out:
    plume_snow.png     snowfall: NBM median bars with 25th-75th whiskers, HRRR, RRFS and HRDPS dots joined by
                       light dashed lines, and
                       accumulation lines for the window
    plume_precip.png   liquid precipitation: NBM bars, HRRR, RRFS and HRDPS dots, accumulation lines
    plume_data.json    the same numbers for every site, frozen, for the interactive map
    ours.json          skeleton for the map table's "Our call" row (written once, never overwritten)
                       (assets/post-plume-map.js; see the plume-map block in posts/TEMPLATE-post.html)
Every area in a PNG shares the same y axes (the largest any area needs), so sites compare directly.

Run it when you write the post, after the data files are fresh (git pull first; the model_data.yml
workflow keeps them current). The PNGs do not change afterward, which is the point: the post shows the
numbers it was written against. Windows are 6 hours; a forecast "day" runs 4 am to 4 am Pacific
(12Z to 12Z, which is 5 am in daylight time), starting at 4 am on --start. 12Z is a model window edge,
so days line up exactly with the data. A model that does not reach the whole window stops where its data ends.

HRDPS snowfall assumes a 10:1 ratio, and values are at the nearest grid point, not corrected for elevation.
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NBM = ROOT / "assets" / "data" / "nbm_plumes.json"
HIRES = ROOT / "assets" / "data" / "hires_plumes.json"
TZ = "America/Los_Angeles"
DEFAULT_AREAS = ["Mt. Baker", "Stevens Pass", "Snoqualmie Pass", "Crystal", "White Pass"]
STYLE = {"hrrr": dict(color="#dc2626", marker="D", label="HRRR", dx=-0.45),
         "rrfs": dict(color="#16a34a", marker="s", label="RRFS", dx=0.45),
         "hrdps": dict(color="#7c3aed", marker="^", label="HRDPS", dx=1.35)}
NBM_DX = -1.35  # hours: offsets keep the models from sitting on top of each other
BLUE, NAVY, TEAL, ORANGE = "#3b82f6", "#1e3c72", "#0f766e", "#f59e0b"


def arr(v):
    return np.array([np.nan if x is None else x for x in v], dtype=float)


def pac(ts):
    return pd.DatetimeIndex(pd.to_datetime(ts, utc=True)).tz_convert(TZ)


def cumulate(vals):
    """Running total that stops at the first missing value (a model's data ends there)."""
    out, tot = [], 0.0
    for v in vals:
        if np.isnan(v):
            break
        tot += v
        out.append(tot)
    return np.array(out)


def series(model_ends, values, t0, t1):
    """(window midpoints, values) for the 6-hour windows that fall inside [t0, t1]."""
    ends = pac(model_ends)
    keep = (ends - pd.Timedelta(hours=6) >= t0) & (ends <= t1)
    mid = ends[keep] - pd.Timedelta(hours=3)
    return mid, arr(values)[keep]


def build(kind, areas, t0, t1, nbm, hires, out_path):
    snow = kind == "snow"
    unit = "snow (in)" if snow else "liquid (in)"
    fig, axes = plt.subplots(len(areas), 1, figsize=(10, 2.55 * len(areas) + 0.9), sharex=True)
    axes = np.atleast_1d(axes)
    pairs = []
    used = set()
    for ax, area in zip(axes, areas):
        site = nbm["sites"].get(area)
        if site is None:
            ax.text(0.5, 0.5, f"{area}: no data", transform=ax.transAxes, ha="center")
            continue
        ax2 = ax.twinx()
        # NBM rates: dots with a light dashed line
        if snow:
            mid, p50 = series(nbm["window_end_utc"], site["p50"], t0, t1)
            _, p25 = series(nbm["window_end_utc"], site["p25"], t0, t1)
            _, p75 = series(nbm["window_end_utc"], site["p75"], t0, t1)
            nb_off = pd.Timedelta(hours=NBM_DX)
            ax.plot(mid + nb_off, p50, color=NAVY, lw=1.0, ls=(0, (3, 2)), alpha=0.5, zorder=3)
            ax.scatter(mid + nb_off, p50, marker="o", s=34, color=NAVY, edgecolor="white", lw=0.8, zorder=4)
            ok = ~np.isnan(p25) & ~np.isnan(p75)
            ax.vlines((mid + nb_off)[ok], p25[ok], p75[ok], color=NAVY, lw=1.4, alpha=0.7, zorder=3)
            cum_mid = cumulate(p50)
            cum_lo = cumulate(np.where(np.isnan(p25), p50, p25))
            cum_hi = cumulate(np.where(np.isnan(p75), p50, p75))
            n = len(cum_mid)
            if n:
                xs = [mid[0] - pd.Timedelta(hours=3)] + list(mid[:n] + pd.Timedelta(hours=3))
                f = lambda c: np.concatenate([[0], c])  # noqa: E731
                ax2.fill_between(xs, f(cum_lo[:n]), f(cum_hi[:n]), color=BLUE, alpha=0.18, lw=0)
                ax2.plot(xs, f(cum_mid), color=NAVY, lw=2.2)
                ax2.annotate(f'{cum_mid[-1]:.1f}" ({cum_lo[-1]:.1f}-{cum_hi[-1]:.1f}")', (xs[-1], cum_mid[-1]),
                             xytext=(-4, 6), textcoords="offset points", ha="right", fontsize=8.5,
                             color=NAVY, fontweight="bold")
        else:
            mid, q = series(nbm["window_end_utc"], site["precip"], t0, t1)
            nb_off = pd.Timedelta(hours=NBM_DX)
            ax.plot(mid + nb_off, q, color=NAVY, lw=1.0, ls=(0, (3, 2)), alpha=0.5, zorder=3)
            ax.scatter(mid + nb_off, q, marker="o", s=34, color=NAVY, edgecolor="white", lw=0.8, zorder=4)
            c = cumulate(q)
            if len(c):
                xs = [mid[0] - pd.Timedelta(hours=3)] + list(mid[:len(c)] + pd.Timedelta(hours=3))
                ax2.plot(xs, np.concatenate([[0], c]), color=NAVY, lw=2.2)
                ax2.annotate(f'{c[-1]:.2f}"', (xs[-1], c[-1]), xytext=(-4, 6), textcoords="offset points",
                             ha="right", fontsize=8.5, color=NAVY, fontweight="bold")
        # HRRR / HRDPS
        for key, md in hires["models"].items():
            st = md["sites"].get(area)
            if key not in STYLE or st is None:
                continue
            s = STYLE[key]
            m, v = series(md["window_end_utc"], st["snow" if snow else "precip"], t0, t1)
            if not len(m):
                continue
            used.add(key)
            off = pd.Timedelta(hours=s["dx"])
            # rates per 6 h: dots joined by a light dashed line (gaps where the model has no data)
            ax.plot(m + off, v, color=s["color"], lw=1.0, ls=(0, (3, 2)), alpha=0.5, zorder=3)
            ax.scatter(m + off, v, marker=s["marker"], s=34, color=s["color"], edgecolor="white", lw=0.8, zorder=4)
            c = cumulate(v)
            if len(c):
                xs = [m[0] - pd.Timedelta(hours=3)] + list(m[:len(c)] + pd.Timedelta(hours=3))
                ax2.plot(xs, np.concatenate([[0], c]), color=s["color"], lw=1.8, ls=(0, (5, 2)))
                ax2.annotate(f'{c[-1]:.1f}"' if snow else f'{c[-1]:.2f}"', (xs[-1], c[-1]), xytext=(4, -10),
                             textcoords="offset points", fontsize=8, color=s["color"], fontweight="bold")
        ax.set_ylabel("per 6 h", fontsize=8.5, color="#334155")
        ax2.set_ylabel("accumulated", fontsize=8.5, color="#334155")
        pairs.append((ax, ax2))
        ax.set_title(area, loc="left", fontsize=11, fontweight="bold", color=NAVY, pad=3)
        ax.grid(axis="y", color="#e2e8f0", zorder=0)
        for a in (ax, ax2):
            a.tick_params(labelsize=8.5)
            for sp in ("top",):
                a.spines[sp].set_visible(False)
        ax.set_xlim(t0, t1)
    # One scale for every area so differences between sites read directly. Each axis takes the largest
    # range any area needed (with a floor so an all-dry forecast is not blown up to full scale).
    floor6, floorc = (1.0, 2.0) if snow else (0.25, 0.5)
    top6 = max([floor6] + [a.get_ylim()[1] for a, _ in pairs])
    topc = max([floorc] + [b.get_ylim()[1] for _, b in pairs])
    for a, b in pairs:
        a.set_ylim(0, top6)
        b.set_ylim(0, topc)
    # forecast-day edges (4 am Pacific) and day labels; a tick every 6 hours (the model window edges)
    clock = lambda h: "12a" if h == 0 else f"{h}a" if h < 12 else "12p" if h == 12 else f"{h - 12}p"  # noqa: E731
    ticks = [t0 + pd.Timedelta(hours=6 * k) for k in range(int((t1 - t0) / pd.Timedelta(hours=6)) + 1)]
    for ax in axes:
        for t in ticks:
            if (t - t0) % pd.Timedelta(days=1):
                ax.axvline(t, color="#e2e8f0", lw=0.8, zorder=0)
    day = t0
    while day < t1:
        for ax in axes:
            ax.axvline(day, color="#94a3b8", ls=(0, (3, 3)), lw=1)
        axes[-1].text(day + pd.Timedelta(hours=12), -0.2, f"{day:%a} {day.month}/{day.day}",
                      transform=axes[-1].get_xaxis_transform(), ha="center", va="top", fontsize=9.5,
                      fontweight="bold", color="#334155")
        day += pd.Timedelta(days=1)
    axes[-1].set_xticks(ticks)
    axes[-1].set_xticklabels([clock(t.hour) for t in ticks], fontsize=8)
    axes[-1].set_xlabel("Pacific time, every 6 hours (days run 4 am to 4 am)", fontsize=8.5, color="#64748b", labelpad=40)
    for ax in axes[:-1]:
        ax.tick_params(axis="x", length=0)
    # legend + title
    name = "Snowfall" if snow else "Liquid precipitation"
    fig.suptitle(f"{name} plume, {t0:%a} {t0.month}/{t0.day} 4 am to {t1:%a} {t1.month}/{t1.day} 4 am (Pacific time)",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=NAVY)
    handles = [plt.Line2D([], [], marker="o", color=NAVY, ls=(0, (3, 2)), lw=1.0, markeredgecolor="white", alpha=0.9),
               plt.Line2D([], [], color=NAVY, lw=2.2)]
    labels = ["NBM median per 6 h" + (" (whiskers 25th-75th)" if snow else ""), "NBM accumulation" + (" (shading = 25th-75th)" if snow else "")]
    for key in hires["models"]:
        if key in STYLE and key in used:
            s = STYLE[key]
            handles.append(plt.Line2D([], [], marker=s["marker"], color=s["color"], ls=(0, (3, 2)), lw=1.0, markeredgecolor="white"))
            labels.append(s["label"] + (" (10:1)" if key == "hrdps" and snow else ""))
    fig.legend(handles, labels, loc="upper left", ncol=len(labels), fontsize=8.5, frameon=False,
               bbox_to_anchor=(0.005, 0.968))
    fig.tight_layout(rect=(0, 0.015, 1, 0.94))
    fig.savefig(out_path, dpi=130, facecolor="white")
    plt.close(fig)
    print("wrote", out_path)


def map_data(t0, t1, nbm, hires):
    """Frozen data for the interactive map (assets/post-plume-map.js): every site the NBM file has, the 6-hour
    windows inside [t0, t1], and the NBM and high-resolution values on that one set of windows."""
    import yaml

    cfg = yaml.safe_load((ROOT / "data" / "nbm" / "sites.yml").read_text(encoding="utf-8"))
    coords = {s["name"]: (s["lat"], s["lon"]) for s in cfg["sites"] + cfg.get("plume_only_sites", [])}
    ends_all = pac(nbm["window_end_utc"])
    keep = (ends_all - pd.Timedelta(hours=6) >= t0) & (ends_all <= t1)
    ends_utc = [e for e, k in zip(nbm["window_end_utc"], keep) if k]

    def pick(model_ends, values):
        by_end = dict(zip(model_ends, values))
        return [by_end.get(e) for e in ends_utc]

    def rnd(v):
        return [None if x is None else round(float(x), 3) for x in v]

    sites = {}
    for name, s in nbm["sites"].items():
        if name not in coords:
            continue
        sel = lambda key: [v for v, k in zip(s[key], keep) if k]  # noqa: E731
        site = {"lat": coords[name][0], "lon": coords[name][1],
                "nbm": {"p25": rnd(sel("p25")), "p50": rnd(sel("p50")), "p75": rnd(sel("p75")),
                        "det": rnd(sel("det")), "precip": rnd(sel("precip"))}}
        for key, md in hires["models"].items():
            st = md["sites"].get(name)
            if key in STYLE and st:
                site[key] = {"snow": rnd(pick(md["window_end_utc"], st["snow"])),
                             "precip": rnd(pick(md["window_end_utc"], st["precip"]))}
        sites[name] = site
    return {"schema": 1, "tz": TZ, "window_start_local": str(t0), "window_end_local": str(t1),
            "generated_utc": nbm["generated_utc"],
            "cycles": {"nbm": nbm["cycle_utc"], **{k: v["cycle_utc"] for k, v in hires["models"].items()}},
            "ends_utc": ends_utc, "sites": sites}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="first Pacific day, YYYY-MM-DD (usually the Friday)")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--out", required=True, help="folder for the PNGs, e.g. assets/images/20261105_fx")
    ap.add_argument("--areas", nargs="+", default=DEFAULT_AREAS)
    ap.add_argument("--nbm", default=str(NBM), help="NBM plume JSON (default assets/data/nbm_plumes.json)")
    ap.add_argument("--hires", default=str(HIRES), help="HRRR/RRFS/HRDPS plume JSON (default assets/data/hires_plumes.json)")
    args = ap.parse_args()

    nbm = json.loads(Path(args.nbm).read_text(encoding="utf-8"))
    hires = json.loads(Path(args.hires).read_text(encoding="utf-8"))
    # forecast days run 12Z to 12Z (4 am PST), the same edges as the NBM and HRRR 6-hour windows
    t0u = pd.Timestamp(args.start, tz="UTC") + pd.Timedelta(hours=12)
    t0 = t0u.tz_convert(TZ)
    t1 = (t0u + pd.Timedelta(days=args.days)).tz_convert(TZ)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"NBM cycle {nbm['cycle_utc']}; " + ", ".join(f"{k} {v['cycle_utc']}" for k, v in hires["models"].items()))
    build("snow", args.areas, t0, t1, nbm, hires, out / "plume_snow.png")
    build("precip", args.areas, t0, t1, nbm, hires, out / "plume_precip.png")
    data = map_data(t0, t1, nbm, hires)
    (out / "plume_data.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print("wrote", out / "plume_data.json", f"({len(data['sites'])} sites)")
    # "Our call" row of the map's table: a skeleton you fill in. Never overwritten, so your numbers are safe on a re-run.
    ours = out / "ours.json"
    if not ours.exists():
        nper = (len(data["ends_utc"]) + 1) // 2
        skeleton = {n: {"periods": ["—"] * nper, "total": "—"} for n in data["sites"]}
        ours.write_text(json.dumps(skeleton, indent=1, ensure_ascii=False), encoding="utf-8")
        print("wrote", ours, "(fill in your forecast: one entry per 12-hour period, plus the total)")


if __name__ == "__main__":
    main()
