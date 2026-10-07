"""Resolve the ECMWF sub-seasonal and seasonal outlook charts to image addresses for the outlook pages.

    python scripts/outlook_links.py                       # writes assets/data/outlook_links.json
    python scripts/outlook_links.py --out FILE --pause 3

Source: ECMWF OpenCharts (charts.ecmwf.int/opencharts-api/v1), licence CC BY 4.0: the pages must credit ECMWF.
Each chart request returns a small JSON with the address of a PNG. The API limits request rates (it answers 429
after a burst), so visitors' browsers do not call it; this script does, politely, and the pages read the result.

How it finds what exists (no date arithmetic): a request with a base time that does not exist is answered with the
list of base times that do ("Current available base_time [...]"), and a request with a valid time that does not
exist for a real base time is answered with the valid times that do. So per product it takes one request for the
bases, one for the valid times, then one per chart. A chart already resolved in the existing file (same product,
base time and valid time) is reused, so a steady-state run is only the lookups.

Products (plan item 9 in PLAN.md):
  sub-seasonal  extended-anomaly-spread-tp (precipitation), extended-anomaly-range-ratio-t (temperature),
                extended-anomaly-z500 (500 hPa height); weekly means, projection North America
  seasonal      seasonal_system5_standard_t850, _rain (area NAME), _z500; one month each (SEAS5)
  indices       mofc_multi_mjo_family_index (MJO), seasonal_system5_climagrams_teleconnection (PNA)
Nothing is invented: a product that cannot be resolved is left out and the run says so.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API = "https://charts.ecmwf.int/opencharts-api/v1/products/"
HEADERS = {"User-Agent": "cascade-mountain-weather.github.io outlook page (dlhogan@uw.edu)"}
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "outlook_links.json"
NA = {"projection": "opencharts_north_america"}

EXTENDED = {
    "precip": ("extended-anomaly-spread-tp", "Precipitation", NA),
    "temp": ("extended-anomaly-range-ratio-t", "Temperature", NA),
    "z500": ("extended-anomaly-z500", "500 hPa height", NA),
}
SEASONAL = {
    "t850": ("seasonal_system5_standard_t850", "850 hPa temperature", {}),
    "rain": ("seasonal_system5_standard_rain", "Precipitation", {"area": "NAME"}),
    "z500": ("seasonal_system5_standard_z500", "500 hPa height", {}),
}


class Api:
    def __init__(self, pause):
        self.pause, self.calls = pause, 0

    def get(self, product, params):
        """(status, json) for one request, pausing between requests and backing off when rate limited."""
        for attempt in range(6):
            time.sleep(self.pause)
            self.calls += 1
            r = requests.get(API + product + "/", params=params, headers=HEADERS, timeout=60)
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            try:
                return r.status_code, r.json()
            except ValueError:
                return r.status_code, {}
        return 429, {}

    def available(self, product, key, params):
        """The list of `key` ('base_time' or 'valid_time') values the API says exist, from its error message."""
        probe = dict(params)
        if key == "base_time":
            probe.update(base_time="2000-01-01T00:00:00Z", valid_time="2000-01-15T00:00:00Z")
        else:
            probe["valid_time"] = "2000-01-15T00:00:00Z"
        status, body = self.get(product, probe)
        text = json.dumps(body)
        m = re.search(r"Current available %s \[(.*?)\]" % key, text.replace('\\"', '"').replace("\\'", "'"))
        return re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", m.group(1)) if m else []

    def chart(self, product, params):
        status, body = self.get(product, params)
        data = (body or {}).get("data") or {}
        link = (data.get("link") or {}).get("href")
        return (link, (data.get("attributes") or {}).get("description")) if status == 200 and link else (None, None)


def reuse(old, group, pid, base, valid):
    for f in (((old.get(group) or {}).get("products") or {}).get(pid) or {}).get("frames") or []:
        if f.get("valid") == valid and (old[group].get("base_time") == base):
            return f
    return None


def build_group(api, old, group, specs, need_valid=True):
    out = {"base_time": None, "products": {}}
    for pid, (product, label, extra) in specs.items():
        bases = api.available(product, "base_time", extra)
        if not bases:
            print(f"  {group}/{pid}: no base times listed, skipped")
            continue
        base = bases[0]
        out["base_time"] = out["base_time"] or base
        if base != out["base_time"]:
            print(f"  {group}/{pid}: newest base {base} differs from {out['base_time']}")
        valids = api.available(product, "valid_time", dict(extra, base_time=base))
        frames = []
        for v in valids:
            f = reuse(old, group, pid, base, v)
            if not f:
                url, desc = api.chart(product, dict(extra, base_time=base, valid_time=v))
                if not url:
                    print(f"  {group}/{pid} {v}: could not resolve")
                    continue
                f = {"valid": v, "url": url, "desc": desc}
            frames.append(f)
        if frames:
            out["products"][pid] = {"product": product, "label": label, "base_time": base, "frames": frames}
            print(f"  {group}/{pid}: base {base}, {len(frames)} charts")
    return out


def build_indices(api, old, extended_base, seasonal_base):
    out = {}
    specs = {
        "mjo": ("mofc_multi_mjo_family_index", {}, "MJO forecast (ECMWF ensemble)"),
        "pna": ("seasonal_system5_climagrams_teleconnection", {"index_type": "Pacific N.Amer pattern"}, "PNA seasonal forecast (SEAS5)"),
    }
    for iid, (product, extra, label) in specs.items():
        bases = api.available(product, "base_time", dict(extra))
        base = bases[0] if bases else None
        if not base:
            print(f"  indices/{iid}: no base times listed, skipped")
            continue
        prev = (old.get("indices") or {}).get(iid) or {}
        if prev.get("base_time") == base and prev.get("url"):
            out[iid] = prev
            continue
        url, desc = api.chart(product, dict(extra, base_time=base))
        if url:
            out[iid] = {"label": label, "product": product, "base_time": base, "url": url, "desc": desc}
            print(f"  indices/{iid}: base {base}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--pause", type=float, default=2.5, help="seconds between requests")
    args = ap.parse_args()
    out_path = Path(args.out)
    old = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    api = Api(args.pause)
    t0 = time.time()
    result = {"source": "ECMWF OpenCharts", "licence": "CC BY 4.0", "licence_url": "https://creativecommons.org/licenses/by/4.0/",
              "copyright": "ECMWF"}
    print("sub-seasonal (extended range)")
    result["extended"] = build_group(api, old, "extended", EXTENDED)
    print("seasonal (SEAS5)")
    result["seasonal"] = build_group(api, old, "seasonal", SEASONAL)
    print("indices")
    result["indices"] = build_indices(api, old, result["extended"]["base_time"], result["seasonal"]["base_time"])
    if not result["extended"]["products"] and not result["seasonal"]["products"]:
        sys.exit("nothing resolved; keeping the existing file")
    # leave the file alone (so no commit) when only the timestamp would change
    body = json.dumps(result, indent=1)
    previous = {k: v for k, v in old.items() if k != "generated_utc"}
    if previous == result:
        print(f"no change ({api.calls} requests, {time.time() - t0:.0f} s)")
        return
    result["generated_utc"] = f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"wrote {out_path} ({api.calls} requests, {time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
