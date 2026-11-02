"""Download the weekly sub-seasonal weather-regime figures for outlooks/subseasonal.html.

Run on Wednesdays (workflow s2s_update.yml). The figures come from CW3E (UC San Diego) and the IRI
(Columbia University); saving our own copy means the page does not depend on their servers being
up, and one file per figure keeps the repo small. Output: assets/data/subseasonal/*.png and
manifest.json (what each figure is, when it was saved, and whether it changed since last week).

Nothing is rewritten when a figure is byte-for-byte the same as the saved one.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "assets" / "data" / "subseasonal"
CW3E = "https://cw3e-sites.ucsd.edu/images/S&S/WeatherRegime"
IRI = "https://iri.columbia.edu/~bohar/WR"
CFS = ("https://iri.columbia.edu/~jingyuan/WRs_figure/"
       "CFSv2_WRs_daily_lagged_forecast_GPH500_mean48_AssignonsmoothedMERRA_4class_movingavg_leads_latest_US_vs_mean0.png")

FIGURES = [
    {"id": "cfs_regimes", "file": "cfs_regimes.png", "url": CFS,
     "title": "CFSv2 North American weather-regime forecast",
     "source": "IRI, Columbia University", "page": "https://iri.columbia.edu/"},
    {"id": "wr_precip", "file": "wr_precip_composite.png", "url": f"{IRI}/WR_CPC_precip_anom_composite.png",
     "title": "Precipitation anomaly for each weather regime",
     "source": "IRI, Columbia University", "page": "https://iri.columbia.edu/"},
    {"id": "wr_temp", "file": "wr_temp_composite.png", "url": f"{IRI}/WR_CPC_temp_anom_composite.png",
     "title": "Temperature anomaly for each weather regime",
     "source": "IRI, Columbia University", "page": "https://iri.columbia.edu/"},
    {"id": "wc_precip", "file": "wc_regime_precip.png", "url": f"{CW3E}/NCEP_WRprobPRC.png",
     "title": "West Coast weather patterns: precipitation outlook",
     "source": "CW3E, UC San Diego", "page": "https://cw3e.ucsd.edu/"},
    {"id": "wc_temp", "file": "wc_regime_temp.png", "url": f"{CW3E}/NCEP_WRprobTMP.png",
     "title": "West Coast weather patterns: temperature outlook",
     "source": "CW3E, UC San Diego", "page": "https://cw3e.ucsd.edu/"},
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mpath = OUT / "manifest.json"
    old = {}
    if mpath.exists():
        old = {f["id"]: f for f in json.loads(mpath.read_text(encoding="utf-8")).get("figures", [])}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    figures, failed = [], 0
    for fig in FIGURES:
        prev = old.get(fig["id"], {})
        entry = {k: fig[k] for k in ("id", "file", "title", "source", "page")}
        entry.update({k: prev[k] for k in ("sha256", "fetched", "changed") if k in prev})
        try:
            r = requests.get(fig["url"], timeout=60, headers={"User-Agent": "cascade-mountain-weather (weekly figure copy)"})
            r.raise_for_status()
            if "image" not in r.headers.get("content-type", "") or len(r.content) < 5000:
                raise ValueError(f"not an image ({r.headers.get('content-type')}, {len(r.content)} bytes)")
            digest = sha(r.content)
            if digest != prev.get("sha256") or not (OUT / fig["file"]).exists():
                (OUT / fig["file"]).write_bytes(r.content)
                entry.update({"sha256": digest, "fetched": now, "changed": now})
                print(f"{fig['id']}: new figure saved")
            else:
                entry.update({"fetched": now})
                print(f"{fig['id']}: unchanged")
        except Exception as e:  # keep last week's copy if a source is down
            failed += 1
            print(f"{fig['id']}: FAILED ({e}); keeping the saved copy", file=sys.stderr)
        figures.append(entry)
    manifest = {"updated": now, "figures": figures}
    # only touch the manifest when something changed (the fetch time alone is not worth a commit)
    prev_doc = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    strip = lambda d: [{k: v for k, v in f.items() if k != "fetched"} for f in d.get("figures", [])]
    if strip(prev_doc) != strip(manifest):
        mpath.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        print("manifest written")
    if failed == len(FIGURES):
        sys.exit(1)


if __name__ == "__main__":
    main()
