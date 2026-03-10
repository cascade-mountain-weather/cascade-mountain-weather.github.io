#!/usr/bin/env python3
"""Build a local GOES + radar loop by parsing frame URLs from COD SatRad HTML."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PRODUCT_TIME_RE = re.compile(r"\.(\d{8})\.(\d{6})\.")
RADAR_TIME_RE = re.compile(r"\.(\d{14})\.")


@dataclass
class ProductFrame:
    url: str
    dt: datetime


@dataclass
class RadarFrame:
    url: str
    dt: datetime


def parse_product_time(url: str) -> Optional[datetime]:
    match = PRODUCT_TIME_RE.search(url)
    if not match:
        return None
    return datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def parse_radar_time(url: str) -> Optional[datetime]:
    match = RADAR_TIME_RE.search(url)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def fetch_image(session: requests.Session, url: str) -> Image.Image:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    img = Image.open(BytesIO(response.content))
    return img.convert("RGBA")


def build_retry_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "CascadeMountainWeatherBot/1.0"})
    return session


def choose_radar(product_dt: datetime, radars: list[RadarFrame]) -> Optional[RadarFrame]:
    if not radars:
        return None

    before = [r for r in radars if r.dt <= product_dt]
    if before:
        return before[-1]
    return radars[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build local COD GOES+radar loop from SatRad HTML")
    parser.add_argument(
        "--url",
        default="https://weather.cod.edu/satrad/?parms=regional-w_northwest-truecolor-24-1-100-4&checked=radar-map&colorbar=undefined",
        help="SatRad page URL",
    )
    parser.add_argument("--output-dir", default="assets/images/satellite", help="Output directory for gif/frames/manifest")
    parser.add_argument("--gif-name", default="cod_nw_truecolor_radar.gif", help="Output GIF filename")
    parser.add_argument("--manifest-name", default="satellite_manifest.json", help="Output manifest filename")
    parser.add_argument("--frames-subdir", default="frames", help="Subdirectory for extracted frame PNGs")
    parser.add_argument("--max-frames", type=int, default=24, help="Maximum number of newest frames to keep")
    parser.add_argument("--delay-ms", type=int, default=250, help="GIF delay in milliseconds")
    parser.add_argument("--max-width", type=int, default=1280, help="Maximum frame width in pixels (no upscale)")
    parser.add_argument("--frame-format", choices=["png", "webp"], default="webp", help="Frame image format")
    parser.add_argument("--frame-quality", type=int, default=78, help="Frame quality (used for webp)")
    parser.add_argument("--latest-frame-name", default="latest_frame.webp", help="Fallback static frame filename")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    frames_dir = output_dir / args.frames_subdir
    gif_path = output_dir / args.gif_name
    manifest_path = output_dir / args.manifest_name
    latest_frame_path = output_dir / args.latest_frame_name

    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old_frame in frames_dir.glob("frame-*.*"):
        try:
            old_frame.unlink()
        except OSError:
            # If a previewer holds a lock, continue and overwrite what we can.
            pass

    session = build_retry_session()

    html_response = session.get(args.url, timeout=60)
    html_response.raise_for_status()

    soup = BeautifulSoup(html_response.text, "html.parser")

    map_overlay_url = None
    map_overlay = soup.find("img", {"class": "overlay", "id": "map"})
    if map_overlay and map_overlay.get("data-url"):
        map_overlay_url = map_overlay["data-url"]

    product_frames: list[ProductFrame] = []
    for img in soup.find_all("img"):
        img_id = img.get("id", "")
        src = img.get("src", "")
        if not str(img_id).isdigit():
            continue
        if "/truecolor/" not in src:
            continue
        dt = parse_product_time(src)
        if not dt:
            continue
        product_frames.append(ProductFrame(url=src, dt=dt))

    radar_frames: list[RadarFrame] = []
    for overlay in soup.find_all("img", {"class": "overlay", "id": "radar"}):
        data_url = overlay.get("data-url", "")
        if "/overlays/radar/" not in data_url:
            continue
        dt = parse_radar_time(data_url)
        if not dt:
            continue
        radar_frames.append(RadarFrame(url=data_url, dt=dt))

    if not product_frames:
        raise RuntimeError("No truecolor frames found in SatRad HTML")

    # The page can contain duplicate <img> tags for current frame and timeline entries.
    product_seen = set()
    deduped_products: list[ProductFrame] = []
    for frame in sorted(product_frames, key=lambda f: (f.dt, f.url)):
        key = (frame.dt, frame.url)
        if key in product_seen:
            continue
        product_seen.add(key)
        deduped_products.append(frame)

    radar_seen = set()
    deduped_radars: list[RadarFrame] = []
    for frame in sorted(radar_frames, key=lambda f: (f.dt, f.url)):
        key = (frame.dt, frame.url)
        if key in radar_seen:
            continue
        radar_seen.add(key)
        deduped_radars.append(frame)

    product_frames = deduped_products
    radar_frames = deduped_radars
    target_frames = max(1, args.max_frames)
    selected_products = product_frames[-target_frames:]

    # If the upstream page has fewer timestamps than requested, pad using the
    # oldest available frame so frontend controls remain stable in size.
    if selected_products and len(selected_products) < target_frames:
        pad_count = target_frames - len(selected_products)
        selected_products = [selected_products[0]] * pad_count + selected_products

    map_img = fetch_image(session, map_overlay_url) if map_overlay_url else None

    gif_images: list[Image.Image] = []
    manifest_frames = []

    for idx, product in enumerate(selected_products):
        base = fetch_image(session, product.url)

        radar = choose_radar(product.dt, radar_frames)
        if radar:
            radar_img = fetch_image(session, radar.url)
            base.alpha_composite(radar_img)

        if map_img:
            base.alpha_composite(map_img)

        if args.max_width and base.width > args.max_width:
            new_height = int(base.height * (args.max_width / base.width))
            base = base.resize((args.max_width, new_height), Image.LANCZOS)

        frame_ext = "webp" if args.frame_format == "webp" else "png"
        frame_name = f"frame-{idx:03d}.{frame_ext}"
        frame_path = frames_dir / frame_name
        if args.frame_format == "webp":
            base.convert("RGB").save(frame_path, format="WEBP", quality=args.frame_quality, method=6)
        else:
            base.save(frame_path, format="PNG", optimize=True)

        gif_images.append(base.convert("P", palette=Image.ADAPTIVE))
        manifest_frames.append(
            {
                "index": idx,
                "file": frame_name,
                "duration_ms": args.delay_ms,
                "timestamp_utc": product.dt.isoformat(),
                "source_truecolor": product.url,
                "source_radar": radar.url if radar else None,
            }
        )

    # Lightweight fallback image used when manifest fetch fails or times out.
    if manifest_frames:
        latest_src = frames_dir / manifest_frames[-1]["file"]
        latest_img = Image.open(latest_src)
        latest_img.save(latest_frame_path, format="WEBP", quality=min(90, max(60, args.frame_quality + 5)), method=6)

    if not gif_images:
        raise RuntimeError("No frames could be built")

    gif_images[0].save(
        gif_path,
        save_all=True,
        append_images=gif_images[1:],
        duration=args.delay_ms,
        loop=0,
        optimize=False,
        disposal=2,
    )

    manifest = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": args.url,
        "gif_file": args.gif_name,
        "latest_frame_file": args.latest_frame_name,
        "frame_count": len(manifest_frames),
        "frames": manifest_frames,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Built loop with {len(manifest_frames)} frames")
    print(f"GIF: {gif_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
