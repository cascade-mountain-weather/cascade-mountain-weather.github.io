"""Cropped North Pacific charts from ECMWF Open Charts, for the synoptic tools page.

    python scripts/fetch_ecmwf_charts.py --out DIR                  # every product and model, newest complete run
    python scripts/fetch_ecmwf_charts.py --out DIR --only jet200    # one product
    python scripts/fetch_ecmwf_charts.py --out DIR --workers 2      # be gentler (default 4)

ECMWF Open Charts (https://charts.ecmwf.int, CC-BY-4.0) renders a chart on request: the API answers with JSON whose
data.link.href is a PNG. Each PNG is the whole Pacific basin (2000x1800, ~2 MB, 6 s to render), too slow and heavy to call from a
browser. This script calls the API, downloads the PNG, crops the map to the North Pacific (100E to 100W, 10N to the top of the
chart at 69N), keeps the legend, adds a header and the ECMWF credit, and writes one small WebP per frame:

    {product}_{model}_{base}_{hour:03d}.webp      base is the run, YYYYMMDDHH
    manifest.json                                 {"charts": {product: {model: {"base": ..., "hours": [...]}}}, "file": pattern, ...}

assets/model-tools-synoptic.js reads manifest.json. Frames of an older run are deleted once the newer run is complete; a run that
is already published is not fetched again. The workflow (ecmwf_charts.yml) force-pushes the folder as one commit on the
`ecmwf-charts` branch, so the repository does not grow.

Geometry (measured from the gridlines of the Pacific projection, which is plain latitude/longitude): 7.17 px per degree, 80E at
x=122, the equator at y=728, the map box x 11-1989, y 234-1222. If ECMWF changes the layout the image size check below fails and
nothing is written for that frame.

Deps: requests pillow.
"""
import argparse
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

API = "https://charts.ecmwf.int/opencharts-api/v1/products"
HEADERS = {"User-Agent": "cascade-mountain-weather.github.io chart cache (dlhogan@uw.edu)"}
PROJECTION = "opencharts_pacific"
FILE = "{product}_{model}_{base}_{hour}.webp"

# model key: (API name prefix, last forecast hour, label)
MODELS = {
    "hres": ("", 240, "ECMWF HRES"),
    "aifs": ("aifs_single_", 360, "ECMWF AIFS"),
    "aifs_ens": ("aifs_ens_cf_", 360, "ECMWF AIFS ensemble control"),
}
# product key: (Open Charts name, extra query)
PRODUCTS = {
    "jet200": ("medium-mslp-wind200", ""),
    "z500": ("medium-uv-z", "&level=500"),
    "wind850": ("medium-mslp-wind850", ""),
    "z500t850": ("medium-z500-t850", ""),
}

# the crop, in pixels of the 2000x1800 chart
PX_PER_DEG = 7.17
X_80E, Y_EQ = 122.0, 728.0
MAP_TOP = 234
LON_W, LON_E = 100.0, 260.0       # 100E to 100W (degrees east)
LAT_S = 10.0
CROP = (round(X_80E + (LON_W - 80) * PX_PER_DEG), MAP_TOP, round(X_80E + (LON_E - 80) * PX_PER_DEG), round(Y_EQ - LAT_S * PX_PER_DEG))
WIDTH = CROP[2] - CROP[0]
LEGEND_SCALE = 0.62                # the legend (colour bar, numbers, line and arrow keys) is drawn this fraction of ECMWF's size
STAR = (47.0, 236.0)               # central Washington coast: 47N, 124W (236E)


def hours_for(model):
    """Every 6 h to 144 h (day 6), every 12 h to 240 h, then daily out to the model's last hour."""
    last = MODELS[model][1]
    return list(range(0, 145, 6)) + list(range(156, 241, 12)) + list(range(264, last + 1, 24))


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def get_json(session, name, extra, base, valid, tries=3):
    url = f"{API}/{name}/?base_time={iso(base)}&valid_time={iso(valid)}&projection={PROJECTION}{extra}"
    for k in range(tries):
        try:
            r = session.get(url, headers=HEADERS, timeout=90)
            if r.status_code == 200:
                return r.json()
            if r.status_code < 500 and r.status_code != 429:
                return None                       # the run or time does not exist
        except (requests.RequestException, ValueError):
            pass
        time.sleep(3 * (k + 1))
    return None


def exists(session, name, extra, base, hour):
    j = get_json(session, name, extra, base, base + timedelta(hours=hour), tries=3)
    return bool(j and j.get("data"))


def newest_run(session, name, extra, last_hour, now):
    """The newest 00Z/12Z run whose last frame exists (a run still being posted does not have it yet), or None."""
    top = now.replace(minute=0, second=0, microsecond=0)
    top -= timedelta(hours=top.hour % 12)
    for back in range(0, 5):
        base = top - timedelta(hours=12 * back)
        if exists(session, name, extra, base, last_hour):
            return base
    return None


def font(size, bold=False):
    for f in (("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), "arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def compose(png, title, line2):
    im = Image.open(BytesIO(png)).convert("RGB")
    if im.size != (2000, 1800):
        raise ValueError(f"unexpected chart size {im.size}")
    mp = im.crop(CROP)
    # a star on the central Washington coast (the chart is plain latitude/longitude, so this is a straight conversion)
    sx = X_80E + (STAR[1] - 80) * PX_PER_DEG - CROP[0]
    sy = Y_EQ - STAR[0] * PX_PER_DEG - CROP[1]
    star = [(sx + (r_ * math.sin(k * math.pi / 5)), sy - (r_ * math.cos(k * math.pi / 5))) for k, r_ in ((k, 12 if k % 2 == 0 else 5) for k in range(10))]
    ImageDraw.Draw(mp).polygon(star, fill="#f59e0b", outline="#111827")
    # legend: the non-white blocks between the map and the footer, each trimmed to its own bounding box and stacked tightly
    # (ECMWF leaves large white gaps between the colour bar, its numbers, and the line key)
    # the map's bottom edge differs a little between products (about 1198 to 1222). Grid lines run the whole height of the map, so
    # no row of the map is blank: the first blank row below y=1100 is just under the map
    gray = im.convert("L")
    gpx = gray.load()
    top = 1225
    for yy in range(1100, 1400):
        if not any(gpx[x, yy] < 245 for x in range(20, 1980, 4)):
            top = yy
            break
    band = im.crop((0, top, 2000, 1640)).convert("L")
    dark = Image.eval(band, lambda v: 255 if v < 245 else 0)
    w, hb = dark.size
    px = dark.load()
    rows = [any(px[x, y] for x in range(0, w, 2)) for y in range(hb)]
    blocks, y = [], 0
    while y < hb:
        if rows[y]:
            y0 = y
            gap = 0
            while y < hb and (rows[y] or gap <= 14):
                gap = 0 if rows[y] else gap + 1
                y += 1
            y1 = y - gap
            blocks.append((y0, y1))
        else:
            y += 1
    parts = []
    for y0, y1 in blocks:
        sub = dark.crop((0, y0, w, y1)).getbbox()
        if sub:
            parts.append(im.crop((max(0, sub[0] - 8), top + y0, min(2000, sub[2] + 8), top + y1)))
    leg = None
    if parts:
        parts = [p.resize((max(1, round(p.width * LEGEND_SCALE)), max(1, round(p.height * LEGEND_SCALE))), Image.LANCZOS) for p in parts]
        lw = min(WIDTH, max(p.width for p in parts))
        parts = [p if p.width <= WIDTH else p.resize((WIDTH, round(p.height * WIDTH / p.width)), Image.LANCZOS) for p in parts]
        leg = Image.new("RGB", (lw, sum(p.height for p in parts) + 6 * (len(parts) - 1)), "white")
        yy = 0
        for p in parts:
            leg.paste(p, ((lw - p.width) // 2, yy))
            yy += p.height + 6
    head, foot = 74, 30
    h = head + mp.height + 8 + (leg.height + 8 if leg else 0) + foot
    out = Image.new("RGB", (WIDTH, h), "white")
    d = ImageDraw.Draw(out)
    d.text((8, 8), title, fill="#1e3c72", font=font(27, True))
    d.text((8, 44), line2, fill="#334155", font=font(20))
    out.paste(mp, (0, head))
    y = head + mp.height + 8
    if leg:
        out.paste(leg, ((WIDTH - leg.width) // 2, y))
        y += leg.height + 8
    d.text((8, y + 6), "© ECMWF, CC BY 4.0, from charts.ecmwf.int. Cropped to the North Pacific by Cascade Mountain Weather.", fill="#64748b", font=font(15))
    return out


def fetch_frame(session, product, model, base, hour, out_dir):
    name, extra = PRODUCTS[product]
    prefix, _, label = MODELS[model]
    valid = base + timedelta(hours=hour)
    if (out_dir / FILE.format(product=product, model=model, base=f"{base:%Y%m%d%H}", hour=f"{hour:03d}")).exists():
        return True                       # fetched by an earlier (interrupted or differently spaced) run
    j = get_json(session, prefix + name, extra, base, valid)
    if not j or not j.get("data"):
        return False
    href = j["data"]["link"]["href"]
    for k in range(3):
        try:
            r = session.get(href, headers=HEADERS, timeout=120)
            if r.status_code == 200:
                title = j["data"]["attributes"].get("title", product).replace("\xa0", " ")
                line2 = f"{label}   run {base:%d %b %H}Z   valid {valid:%a %d %b %H}Z (+{hour} h)"
                img = compose(r.content, title, line2)
                img.save(out_dir / FILE.format(product=product, model=model, base=f"{base:%Y%m%d%H}", hour=f"{hour:03d}"), "WEBP", quality=88, method=6)
                return True
        except (requests.RequestException, ValueError, OSError) as exc:
            print(f"    {product}/{model} +{hour}: {str(exc)[:80]}", flush=True)
        time.sleep(3 * (k + 1))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="folder to write the frames and manifest.json to (existing contents are reused)")
    ap.add_argument("--only", nargs="*", choices=list(PRODUCTS), help="only these products")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--hours", type=int, default=None, help="stop at this forecast hour (for a quick test)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    mpath = out / "manifest.json"
    old = {}
    if mpath.exists():
        try:
            old = json.loads(mpath.read_text(encoding="utf-8")).get("charts", {})
        except ValueError:
            old = {}
    now = datetime.now(timezone.utc)
    session = requests.Session()
    charts = {p: dict(m) for p, m in old.items()}
    for product in (a.only or list(PRODUCTS)):
        name, extra = PRODUCTS[product]
        for model, (prefix, last, _label) in MODELS.items():
            hours = [h for h in hours_for(model) if a.hours is None or h <= a.hours]
            base = newest_run(session, prefix + name, extra, hours[-1], now)
            if base is None:
                print(f"{product}/{model}: no complete run found, keeping what is published", flush=True)
                continue
            tag = f"{base:%Y%m%d%H}"
            have = old.get(product, {}).get(model, {})
            if have.get("base") == tag and all((out / FILE.format(product=product, model=model, base=tag, hour=f"{h:03d}")).exists() for h in have.get("hours", [])) and have.get("hours") == hours:
                print(f"{product}/{model}: run {tag} already published", flush=True)
                continue
            print(f"{product}/{model}: run {tag}, {len(hours)} frames", flush=True)
            with ThreadPoolExecutor(a.workers) as pool:
                ok = list(pool.map(lambda h: fetch_frame(session, product, model, base, h, out), hours))
            got = [h for h, k in zip(hours, ok) if k]
            if not got or got[0] != 0 or len(got) < 0.75 * len(hours):
                print(f"  only {len(got)} of {len(hours)} frames: keeping the previous run", flush=True)
                for h in got:
                    (out / FILE.format(product=product, model=model, base=tag, hour=f"{h:03d}")).unlink(missing_ok=True)
                continue
            charts.setdefault(product, {})[model] = {"base": tag, "hours": got}
            for f in out.glob(f"{product}_{model}_*.webp"):      # older runs of this chart
                if f"_{tag}_" not in f.name:
                    f.unlink()
    if not charts:
        sys.exit("nothing published")
    mpath.write_text(json.dumps({"updated": f"{now:%Y-%m-%dT%H:%MZ}", "file": "{product}_{model}_{base}_{hour}.webp",
                                 "source": "ECMWF Open Charts (CC-BY-4.0)", "charts": charts}), encoding="utf-8")
    print("manifest written:", {p: {m: v["base"] for m, v in d.items()} for p, d in charts.items()})


if __name__ == "__main__":
    main()
