"""Read your own weekend-total snowfall forecasts straight out of the posts.

    python scripts/ours_from_posts.py            # writes data/forecasts/ours_from_posts.json and prints differences

The posts are the source of truth for what was forecast. Two layouts exist:
  - a table (class `snow-totals-grid`): the last column is the weekend total (most posts);
  - a list under a heading containing "Weekend Snow Accumulation" (the 2025-12-04 post).
The older saved evaluation files (data/forecasts/eval_forecast_*.json) turned out to hold wrong ranges for
2025-12-04 (they carry the 2025-12-11 values), so the evaluation reads this file instead.

A value that is not a plain range ("Multiple", a dash, an empty cell) is skipped, never guessed.

Two posts are skipped on purpose: 2025-11-20 and 2025-11-27 wrote their forecast as prose (the only list in the
2025-11-27 post is a teaching example about the dendritic growth zone), so there is no weekend total to read.
Area names are matched to the nine forecast areas; anything else (a stray "1", a dash) is dropped.
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "_posts"
OUT = ROOT / "data" / "forecasts" / "ours_from_posts.json"
NUM = r"(\d+(?:\.\d+)?)"
SKIP = {"2025-11-20", "2025-11-27"}
AREAS = {"mt. baker": "Mt. Baker", "baker": "Mt. Baker", "washington pass": "Washington Pass", "stevens pass": "Stevens Pass",
         "stevens": "Stevens Pass", "hurricane ridge": "Hurricane Ridge", "blewett pass": "Blewett Pass", "blewett": "Blewett Pass",
         "snoqualmie pass": "Snoqualmie Pass", "snoqualmie": "Snoqualmie Pass", "crystal": "Crystal", "crystal mountain": "Crystal",
         "paradise": "Paradise", "white pass": "White Pass"}


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def area_name(s):
    return re.sub(r"\s*\(.*?\)", "", clean(s)).rstrip(":").strip()


def parse_range(text):
    t = clean(text).replace("–", "-").replace("—", "-").replace('"', "").replace("in", "").strip()
    m = re.fullmatch(NUM + r"\s*-\s*" + NUM, t)
    if m:
        return [float(m.group(1)), float(m.group(2))]
    m = re.fullmatch(NUM, t)
    if m:
        return [float(m.group(1)), float(m.group(1))]
    return None


def canon(name):
    return AREAS.get(area_name(name).lower())


def parse_post(path):
    areas, kind = parse_raw(path)
    return {canon(k): v for k, v in areas.items() if canon(k)}, kind


def parse_raw(path):
    t = path.read_text(encoding="utf-8")
    areas = {}
    # Some posts reuse the class `snow-totals-grid` for other tables (the 2026-01-29 post has a precipitation
    # record table first), so take the table whose first column names the forecast areas.
    for table in re.findall(r'<table class="snow-totals-grid">(.*?)</table>', t, re.S):
        found = {}
        for row in re.findall(r"<tr>(.*?)</tr>", table, re.S):
            cells = re.findall(r"<td>(.*?)</td>", row, re.S)
            if len(cells) >= 2 and canon(cells[0]):
                rng = parse_range(cells[-1])
                if rng:
                    found[area_name(cells[0])] = rng
        if len(found) >= 3:
            return found, "table"
    head = re.search(r"(?is)<h3>.{0,40}Weekend Snow Accumulation.*?</h3>\s*<ul>(.*?)</ul>", t)
    if head:
        for li in re.findall(r"<li>(.*?)</li>", head.group(1), re.S):
            m = re.match(r"\s*<strong>(.*?)</strong>(.*)", li, re.S)
            if m:
                rng = parse_range(m.group(2))
                if rng:
                    areas[area_name(m.group(1))] = rng
        return areas, "list"
    # 2025-12-11 and similar: weekend-total list without that heading wording
    items = re.findall(r"<li><strong>([^<]{3,40}):</strong>\s*(\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?)\s*\"", t)
    for name, val in items:
        rng = parse_range(val + '"')
        if rng and area_name(name) not in areas:
            areas[area_name(name)] = rng
    return areas, "loose list" if areas else "none"


def main():
    out, notes = {}, {}
    for post in sorted(POSTS.glob("*.html")):
        date = post.name[:10]
        if date in SKIP:
            out[date], notes[date] = {}, "skipped (prose forecast)"
            continue
        areas, kind = parse_post(post)
        out[date] = areas
        notes[date] = kind
    OUT.write_text(json.dumps({"source": "parsed from _posts/*.html", "forecast_date": out, "layout": notes}, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")

    # compare with the saved evaluation files
    diffs = []
    for date, areas in out.items():
        saved = ROOT / "data" / "forecasts" / f"eval_forecast_{date}.json"
        if not saved.exists():
            continue
        sd = json.loads(saved.read_text(encoding="utf-8")).get("areas", {})
        for name, rng in areas.items():
            key = next((k for k in sd if isinstance(sd[k], dict) and k.lower() == name.lower()), None)
            j = ((sd.get(key) or {}).get("accumulated_snowfall") or {}).get("our_forecast", {}).get("range") if key else None
            if j is None or j[0] is None or [round(x, 1) for x in j] != rng:
                diffs.append((date, name, rng, j))
    print(f"\nparsed {sum(1 for a in out.values() if a)} posts with ranges; {len(diffs)} area ranges differ from the saved evaluation files:")
    for d in diffs:
        print("  ", d)
    print("\nposts with no weekend-total ranges found:", [d for d, a in out.items() if not a])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
