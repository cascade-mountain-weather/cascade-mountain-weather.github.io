"""Fill the snow forecast table for a post from the frozen plume data.

    python scripts/post_snow_table.py --data assets/images/20261105_fx            # prints the table HTML
    python scripts/post_snow_table.py --data assets/images/20261105_fx --out snow_table.html

Run scripts/post_plume.py first: it writes <dir>/plume_data.json, the frozen numbers for the window you chose
(--start, --days). This script reads that file, so the table and the plumes always agree and neither changes
after you post. Paste the output over the <table class="snow-table"> in your post (inside .snow-table-wrap).

Layout: five areas, and for each one a row per source (HRRR, RRFS, HRDPS, NBM) plus an "Our call" row that you
fill in. Columns are 12-hour periods of each forecast day (4 am to 4 am Pacific = 12Z to 12Z; 4a-4p and 4p-4a),
then the total. A 12-hour period is two 6-hour model windows added together.

  value   inches of new snow, as the model itself reports it (HRRR/RRFS ASNOW; HRDPS water equivalent x 10;
          NBM median of its snowfall blend). NOT yet split by dew point, see below.
  --      the model has no data for that period (its run does not reach it)
  1.2*    only one of the period's two 6-hour windows exists, so the value is partial
  total   sum of the periods that have data; marked * when the model does not cover the whole window

Holiday or long weekends: use a longer window. For Thanksgiving, run post_plume.py with --start on the
Wednesday and --days 5 (4 am Wed to 4 am Mon), then run this script on the same folder; the table grows by
two columns per extra day. HRRR/HRDPS (48 h) and RRFS (84 h) will show "--" for the later days, NBM reaches
further.

Dew point rain/snow split: not done here. The plume files hold each model's own snowfall, not temperature or
dew point, so the split would need dew point added to scripts/hires_plume.py and scripts/nbm_plume.py (and a
threshold and snow-to-liquid ratio from you). Until then every column is the model's own snow estimate.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

AREAS = ["Mt. Baker", "Stevens Pass", "Snoqualmie Pass", "Crystal", "White Pass"]
DISPLAY = {"Crystal": "Crystal Mountain"}
SOURCES = [("hrrr", "HRRR"), ("rrfs", "RRFS"), ("hrdps", "HRDPS"), ("nbm", "NBM")]
TZ = "America/Los_Angeles"


def windows_for(site, key):
    """Snowfall per 6-hour window for one source, aligned to data['ends_utc'] (None = no data)."""
    if key == "nbm":
        return site["nbm"]["p50"]
    return site[key]["snow"] if key in site else None


def period_value(vals, k):
    """(sum, complete) for the two 6-hour windows of 12-hour period k, or None if neither exists."""
    got = [v for v in vals[2 * k:2 * k + 2] if v is not None]
    if not got:
        return None
    return sum(got), len(got) == 2


def fmt(x):
    return "0" if round(x, 1) == 0 else f"{x:.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="folder holding plume_data.json (from post_plume.py)")
    ap.add_argument("--areas", nargs="+", default=AREAS)
    ap.add_argument("--out", help="write the HTML here instead of printing it")
    args = ap.parse_args()

    data = json.loads((Path(args.data) / "plume_data.json").read_text(encoding="utf-8"))
    t0 = pd.Timestamp(data["window_start_local"])
    t1 = pd.Timestamp(data["window_end_local"])
    days = int(round((t1 - t0) / pd.Timedelta(days=1)))
    nper = days * 2
    # the window list from the file must start at the window's own start (12Z) for the 12-hour pairing to line up
    first_end = pd.Timestamp(data["ends_utc"][0])
    assert first_end == (t0.tz_convert("UTC") + pd.Timedelta(hours=6)), "plume_data.json does not start at the window start"

    out = []
    w = out.append
    w('<table class="snow-table">')
    w("    <caption>Forecast snowfall in inches per 12 hours (forecast days run 4 am to 4 am Pacific), plus total</caption>")
    w("    <thead>")
    w("        <tr>")
    w('            <th rowspan="2" scope="col">Area</th>')
    w('            <th rowspan="2" scope="col">Source</th>')
    for d in range(days):
        day = t0 + pd.Timedelta(days=d)
        w(f'            <th colspan="2" scope="colgroup">{day:%a} {day.month}/{day.day}</th>')
    w('            <th rowspan="2" scope="col">Total</th>')
    w("        </tr>")
    w("        <tr>" + "".join('<th scope="col">4a–4p</th><th scope="col">4p–4a</th>' for _ in range(days)) + "</tr>")
    w("    </thead>")
    missing = []
    for area in args.areas:
        site = data["sites"].get(area)
        if site is None:
            missing.append(area)
            continue
        w("    <tbody>")
        for i, (key, label) in enumerate(SOURCES):
            vals = windows_for(site, key)
            cells, tot, complete = [], 0.0, True
            for k in range(nper):
                r = period_value(vals, k) if vals is not None else None
                if r is None:
                    cells.append("—")
                    complete = False
                else:
                    cells.append(fmt(r[0]) + ("" if r[1] else "*"))
                    tot += r[0]
                    complete = complete and r[1]
            any_data = any(c != "—" for c in cells)
            total = (fmt(tot) + ("" if complete else "*")) if any_data else "—"
            head = f'<th rowspan="5" scope="rowgroup">{DISPLAY.get(area, area)}</th>' if i == 0 else ""
            cls = ' class="area-start"' if i == 0 else ""
            w(f'        <tr{cls}>{head}<th scope="row">{label}</th>' + "".join(f"<td>{c}</td>" for c in cells) + f'<td class="total">{total}</td></tr>')
        w('        <tr class="mine"><th scope="row">Our call</th>' + "<td>—</td>" * nper + '<td class="total">—</td></tr>')
        w("    </tbody>")
    w("</table>")
    c = data["cycles"]
    w("<!-- sources: " + ", ".join(f"{k} {v}" for k, v in c.items()) + " | * = model covers only part of the period or window -->")

    html = "\n".join(out) + "\n"
    if args.out:
        Path(args.out).write_text(html, encoding="utf-8")
        print("wrote", args.out)
    else:
        print(html)
    if missing:
        print("no data for:", ", ".join(missing))


if __name__ == "__main__":
    main()
