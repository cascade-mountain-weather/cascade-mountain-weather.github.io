"""Fetch WSDOT's historic seasonal opening and closing dates for the high passes and save them as a table.

    python scripts/pass_seasonal_dates.py            # writes data/passes/seasonal_closures.csv

Source: https://wsdot.wa.gov/travel/roads-bridges/mountain-pass-closure-and-opening-dates (Chinook Pass SR 410, Cayuse Pass SR 123,
North Cascades Highway SR 20; records for many decades). These are the dates the road closed for the winter and reopened in spring.
The cell text is kept as published (some years have temporary closures or a reopening in the Closed column); `closed` is the
last winter-closing date that is not marked temporary, as a real date, `opened` the spring opening. Nothing is guessed: a cell
that cannot be read is left empty.
"""
import csv
import html
import re
from datetime import date
from pathlib import Path

import requests

URL = "https://wsdot.wa.gov/travel/roads-bridges/mountain-pass-closure-and-opening-dates"
OUT = Path(__file__).resolve().parent.parent / "data" / "passes" / "seasonal_closures.csv"
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def cells(row):
    return [html.unescape(re.sub(r"<[^>]+>", " ", c)).replace("\xa0", " ").strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.S)]


def parse_date(text, year, last=True):
    """A 'Mon. D' date in `year`: the last one that is not part of a 'temporary' closure (closing), or the first one (opening)."""
    text = re.sub(r"[A-Za-z]+\.?\s+\d{1,2}\s*-+\s*temporary", " ", text, flags=re.I)
    found = []
    for mon, day in re.findall(r"([A-Za-z]+)\.?\s+(\d{1,2})(?!\d)", text):
        m = MONTHS.get(mon[:3].lower())
        if m:
            try:
                found.append(date(year, m, int(day)))
            except ValueError:
                pass
    if not found:
        return None
    return found[-1] if last else found[0]


PASSES = ["Chinook Pass SR 410", "Cayuse Pass SR 123", "North Cascades SR 20"]


def main():
    h = requests.get(URL, headers={"User-Agent": "Mozilla/5.0 (cascade-mountain-weather.github.io; dlhogan@uw.edu)"}, timeout=60).text
    rows_out = []
    for tbl in re.findall(r"<table.*?</table>", h, flags=re.S):
        rows = [cells(r) for r in re.findall(r"<tr.*?</tr>", tbl, flags=re.S)]
        before = h[:h.index(tbl)]
        # the pass is the last pass name that appears before the table
        pos = {n: before.rfind(n) for n in PASSES}
        name = max(pos, key=pos.get) if max(pos.values()) >= 0 else ""
        for r in rows:
            if len(r) >= 3 and re.fullmatch(r"(19|20)\d\d", r[0]):
                y = int(r[0])
                rows_out.append({"pass": re.sub(r"\s+", " ", name), "year": y, "opened_text": r[1], "closed_text": r[2],
                                 "opened": parse_date(r[1], y, last=False), "closed": parse_date(r[2], y)})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["pass", "year", "opened_text", "closed_text", "opened", "closed"])
        w.writeheader()
        w.writerows(rows_out)
    by = {}
    for r in rows_out:
        by.setdefault(r["pass"], []).append(r["year"])
    for k, v in by.items():
        print(f"{k}: {len(v)} years, {min(v)} to {max(v)}")
    print("wrote", OUT, len(rows_out), "rows")


if __name__ == "__main__":
    main()
