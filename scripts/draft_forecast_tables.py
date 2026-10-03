"""Draft the snowfall table and snow-level list for a forecast post from an NBM snapshot.

    python scripts/draft_forecast_tables.py                      # newest snapshot
    python scripts/draft_forecast_tables.py data/forecasts/nbm_snapshot_2026-10-03.json

Prints HTML in the same structure the posts use now (`snow-totals-grid` table, then a list), and also
writes it to data/forecasts/draft_tables_<first-day>.html. It is a DRAFT: paste it into the post and
change whatever your own judgment says to change. It does not touch any post.

Snowfall cells show the median, with the 25th to 75th percentile range beside it:
    1"  (0-3")
Rounded to whole inches; anything under half an inch shows as 0". The exact values are in the cell's
title attribute (hover). Snow level is the median of the 3-hourly median snow levels in each day,
rounded to 100 ft, with the lowest 25th and highest 75th percentile in parentheses.

Only temperature is corrected for elevation in the snapshot. Snowfall and snow level here are the NBM
grid-cell values. No Python dependencies beyond the standard library.
"""
import json
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORECASTS = ROOT / "data" / "forecasts"


def is_pdt(d):
    """US daylight time: second Sunday of March through the first Sunday of November."""
    def nth_sunday(year, month, n):
        first = date(year, month, 1)
        return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))
    return nth_sunday(d.year, 3, 2) <= d < nth_sunday(d.year, 11, 1)


def day_label(start_utc):
    start = datetime.strptime(start_utc, "%Y-%m-%dT%H:%MZ")
    local_hour = 12 - (7 if is_pdt(start.date()) else 8)
    ampm = f"{local_hour}am"
    return start, start.strftime("%A"), f"{start:%a} {ampm} to {(start + timedelta(days=1)):%a} {ampm}"


def inches(x):
    return "0" if x is None or x < 0.5 else f"{int(x + 0.5)}"  # round half up (round() goes to even)


def snow_cell(v):
    if not v or v.get("p50") is None:
        return "<td>n/a</td>"
    lo, mid, hi = inches(v["p25"]), inches(v["p50"]), inches(v["p75"])
    exact = f'p25 {v["p25"]} / median {v["p50"]} / p75 {v["p75"]} in'
    if v.get("method") != "percentile":
        exact += " (interpolated from exceedance probabilities)"
    if lo == mid == hi == "0":
        return f'<td title="{exact}">0"</td>'
    rng = f" <small>({lo}–{hi}\")</small>" if (lo, hi) != (mid, mid) else ""
    return f'<td title="{exact}">{mid}"{rng}</td>'


def snow_level_text(site, times, start_utc):
    start = datetime.strptime(start_utc, "%Y-%m-%dT%H:%MZ")
    end = start + timedelta(days=1)
    idx = [i for i, t in enumerate(times)
           if start <= datetime.strptime(t, "%Y-%m-%dT%H:%MZ") < end]
    sl = site["snow_level_ft"]
    p50 = [sl["p50"][i] for i in idx if sl["p50"][i] is not None]
    p25 = [sl["p25"][i] for i in idx if sl["p25"][i] is not None]
    p75 = [sl["p75"][i] for i in idx if sl["p75"][i] is not None]
    if not p50:
        return None
    rd = lambda v: int(round(v / 100.0) * 100)  # noqa: E731
    return rd(statistics.median(p50)), rd(min(p25)), rd(max(p75))


def build(snap):
    windows = snap["windows"]
    day_ids = [w for w in windows if w.startswith("day")]
    cols = [(w, *day_label(windows[w]["start_utc"])[1:]) for w in day_ids]
    if "total" in windows:
        first, last = day_label(windows[day_ids[0]]["start_utc"]), day_label(windows[day_ids[-1]]["start_utc"])
        cols.append(("total", "Weekend total", f"cumulative, {first[2].split(' to ')[0]} to {last[2].split(' to ')[1]}"))
    cycle = snap["source"]["cycle_utc"]

    out = ['<section class="forecast-section">', "    <h2>❄️ Snowfall</h2>",
           '    <div class="forecast-details">',
           f"        <h3><strong>Snow Accumulation Forecast</strong></h3>",
           '        <table class="snow-totals-grid">', "            <thead>", "                <tr>",
           "                    <th>Site</th>"]
    for _, name, sub in cols:
        out.append(f"                    <th>{name}<br><small>{sub}</small></th>")
    out += ["                </tr>", "            </thead>", "            <tbody>"]
    for name, site in snap["sites"].items():
        cells = "".join(snow_cell(site["snowfall_in"].get(w)) for w, _, _ in cols)
        out.append(f"                <tr><td><strong>{name}</strong></td>{cells}</tr>")
    out += ["            </tbody>", "        </table>",
            f"        <p><small>Median with the 25th–75th percentile range, from the NBM run of {cycle}. "
            "Grid-cell values; hover a cell for the exact numbers.</small></p>",
            "    </div>", "</section>", "",
            '<section class="forecast-section">', "    <h2>\U0001f9ca Snow Level</h2>",
            '    <div class="forecast-details">']
    for name, site in snap["sites"].items():
        parts = []
        for w, day, _ in cols:
            if w == "total":
                continue
            r = snow_level_text(site, snap["series_times_utc"], windows[w]["start_utc"])
            parts.append(f"{day} {r[0]:,} ft <small>({r[1]:,}–{r[2]:,})</small>" if r else f"{day} n/a")
        out.append(f"        <p><strong>{name}:</strong> " + "; ".join(parts) + "</p>")
    out += ["    </div>", "</section>"]
    return "\n".join(out)


def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        found = sorted(FORECASTS.glob("nbm_snapshot_*.json"))
        if not found:
            sys.exit("no nbm_snapshot_*.json in data/forecasts")
        path = found[-1]
    snap = json.loads(path.read_text(encoding="utf-8"))
    html = build(snap)
    out = FORECASTS / f"draft_tables_{snap['source']['first_day_local']}.html"
    out.write_text(html + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(html)
    print(f"\n<!-- wrote {out.relative_to(ROOT)} -->", file=sys.stderr)


if __name__ == "__main__":
    main()
