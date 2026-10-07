"""Extract the I-90 Snoqualmie Pass delay table from WSDOT's study PDF (exact text, not a transcription).

    python scripts/pass_i90_parse.py

Source: WSDOT Snoqualmie Winter Operations Study, December 2024, Figure 4 "Closure Map" (page 7 of the PDF):
https://wsdot.wa.gov/sites/default/files/2024-12/Snoqualmie-Winter-Operations-Study-December2024.pdf
Needs `pdftotext` (poppler). Writes data/passes/i90_snoqualmie_closures_2017_2024.csv with the date, mileposts, weather, cause and delay
as printed. The figure lists delays above some length with a date but no clock time, so the unit used elsewhere is the day.
"""
import csv
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import requests

URL = "https://wsdot.wa.gov/sites/default/files/2024-12/Snoqualmie-Winter-Operations-Study-December2024.pdf"
OUT = Path(__file__).resolve().parent.parent / "data" / "passes" / "i90_snoqualmie_closures_2017_2024.csv"
DATE = re.compile(r"^([A-Z][a-z]+ \d{1,2}, \d{4})\s+(.+)$")


def minutes(text):
    h = re.search(r"(\d+)\s*hrs?", text)
    m = re.search(r"(\d+)\s*mins?", text)
    return (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)


def parse(raw):
    rows, mp, cur = [], None, None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.fullmatch(r"MP \d+(/\d+)*", line) or re.fullmatch(r"MP \d+(, \d+)+", line):
            mp = line[3:].replace("/", ", ")
            continue
        d = DATE.match(line)
        if d:
            cur = {"mileposts": mp, "date_as_published": d.group(1), "weather": d.group(2), "cause": []}
            continue
        if cur is None:
            continue
        dm = re.search(r"delay:\s*(.*)$", line, flags=re.I)
        if dm:
            before = line[:dm.start()].strip()
            if before:
                cur["cause"].append(before)
            cur["delay_min"] = minutes(dm.group(1))
            rows.append(cur)
            cur = None
        elif re.fullmatch(r"(POOR VISIBILITY|FREEZING RAIN)", line) and not cur["cause"]:
            cur["weather"] += " " + line
        else:
            cur["cause"].append(line)
    return rows


def main():
    with tempfile.TemporaryDirectory() as t:
        pdf = Path(t) / "s.pdf"
        pdf.write_bytes(requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=120).content)
        raw = subprocess.run(["pdftotext", "-raw", "-f", "7", "-l", "7", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    rows = parse(raw)
    for r in rows:
        r["cause"] = " ".join(r["cause"])
        try:
            r["date"] = datetime.strptime(r["date_as_published"], "%B %d, %Y").date().isoformat()
            r["date_note"] = ""
        except ValueError:
            m = re.match(r"([A-Z][a-z]+) (\d+), (\d{4})", r["date_as_published"])
            r["date"] = f"{m.group(3)}-{datetime.strptime(m.group(1), '%B').month:02d}-{int(m.group(2)) - 1:02d}"      # an impossible day: use the day before
            r["date_note"] = "published as an impossible date (November 31); treated as November 30"
    rows.sort(key=lambda r: (r["date"], r["mileposts"] or ""))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "mileposts", "weather", "cause", "delay_min", "date_as_published", "date_note"])
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in w.fieldnames} for r in rows)
    tot = sum(r["delay_min"] for r in rows)
    print(f"{len(rows)} delays; sum {tot // 60} h {tot % 60} min (the study reports 458 h 7 min of closure after merging overlaps)")
    print("wrote", OUT)


if __name__ == "__main__":
    sys.exit(main())
