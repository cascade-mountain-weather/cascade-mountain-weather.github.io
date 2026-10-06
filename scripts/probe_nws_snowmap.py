"""Discovery probe for the NWS snowfall observation map (weather.gov/source/crh/snowmap.html).

The page is a JavaScript map, so the snowfall reports it draws come from some other file or API that
we have not identified yet. This script fetches the page and the scripts it loads, lists every URL,
JSON/GeoJSON/CSV path and API-looking string in them, and saves the lot so the data source can be
identified (and, if it is open, used to check forecasts against observed snowfall).

    python scripts/probe_nws_snowmap.py

Output (data/ is excluded from the Jekyll build): data/nws_snowmap/
    page.html            the page as served
    scripts/*.js         every same-site script the page references
    probe_report.json    script URLs, candidate data URLs, response status and content type of each
Nothing here is parsed into snowfall numbers yet; that comes once the data endpoint is known.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

PAGE = "https://www.weather.gov/source/crh/snowmap.html?zoom=9&lat=47.38&lon=-122.06&hr=24"
OUT = Path(__file__).resolve().parent.parent / "data" / "nws_snowmap"
HEADERS = {"User-Agent": "cascade-mountain-weather-probe (+https://github.com/cascade-mountain-weather)"}
DATA_HINT = re.compile(r"""["'`]([^"'`\s]+?\.(?:json|geojson|csv|txt|xml|kml)(?:\?[^"'`\s]*)?)["'`]""", re.I)
URL_HINT = re.compile(r"""["'`](https?://[^"'`\s]+|/[A-Za-z0-9_\-./]+/[A-Za-z0-9_\-./?=&%{}$]+)["'`]""")
API_HINT = re.compile(r"(api\.weather\.gov|mapservices|arcgis|rest/services|FeatureServer|MapServer|geoserver|wms|wfs|lsr|pns|snowfall|snowmap)", re.I)


def get(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    return r


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scripts").mkdir(exist_ok=True)
    report = {"probed_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}", "page": PAGE}
    try:
        page = get(PAGE)
    except requests.RequestException as exc:
        report["error"] = str(exc)[:300]
        (OUT / "probe_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        print("could not fetch the page:", exc)
        return
    report["page_status"] = page.status_code
    report["page_content_type"] = page.headers.get("content-type")
    (OUT / "page.html").write_text(page.text, encoding="utf-8")

    sources = sorted({urljoin(PAGE, m) for m in re.findall(r"""<script[^>]+src=["']([^"']+)["']""", page.text, re.I)})
    texts = {PAGE: page.text}
    report["scripts"] = []
    for src in sources:
        entry = {"url": src}
        if urlparse(src).netloc.endswith(("weather.gov", "noaa.gov")):
            try:
                r = get(src)
                entry.update(status=r.status_code, bytes=len(r.content))
                if r.ok:
                    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", urlparse(src).path.strip("/"))[-100:] or "script.js"
                    (OUT / "scripts" / name).write_text(r.text, encoding="utf-8")
                    texts[src] = r.text
            except requests.RequestException as exc:
                entry["error"] = str(exc)[:200]
        else:
            entry["note"] = "third-party library, not saved"
        report["scripts"].append(entry)

    candidates = {}
    for where, text in texts.items():
        for m in DATA_HINT.findall(text) + [u for u in URL_HINT.findall(text) if API_HINT.search(u)]:
            candidates.setdefault(urljoin(where, m) if not m.startswith("http") else m, where)
    report["candidate_data_urls"] = []
    for url, where in sorted(candidates.items())[:60]:
        entry = {"url": url, "found_in": where}
        if "{" not in url and "$" not in url:
            try:
                r = requests.get(url, headers=HEADERS, timeout=20, stream=True)
                entry.update(status=r.status_code, content_type=r.headers.get("content-type"),
                             length=r.headers.get("content-length"))
                r.close()
            except requests.RequestException as exc:
                entry["error"] = str(exc)[:150]
        report["candidate_data_urls"].append(entry)
    (OUT / "probe_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"page {report['page_status']}, {len(report['scripts'])} scripts, "
          f"{len(report['candidate_data_urls'])} candidate data URLs -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
