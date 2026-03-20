#!/usr/bin/env python3
"""Download Meteoblue time-series JSON for all forecast points.

Usage:
  1) Set environment variable METEOBLUE_API_KEY.
  2) Run: python data/forecasts/meteoblue/pull_meteoblue_timeseries.py

This writes one JSON file per point into data/forecasts/meteoblue/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

API_BASE_URL = "https://my.meteoblue.com/packages/basic-3h_clouds-3h"
API_KEY_ENV = "METEOBLUE_API_KEY"
DEFAULT_KEY_FILE = ".meteoblue_api_key"


@dataclass(frozen=True)
class ForecastPoint:
    name: str
    lat: float
    lon: float
    asl_ft: int


# Forecast points used across site products.
# Snoqualmie Pass and Blewett Pass are intentionally +500 ft per request.
POINTS: List[ForecastPoint] = [
    ForecastPoint("Mt. Baker Ski Area", 48.8629, -121.6826, 4200/3.28),
    ForecastPoint("Stevens Pass", 47.7447, -121.0890, 4061/3.28),
    ForecastPoint("Blewett Pass", 47.3350, -120.5780, 4602/3.28),
    ForecastPoint("Snoqualmie Pass", 47.4240, -121.4130, 3522/3.28),
    ForecastPoint("Crystal Mountain", 46.9391, -121.4740, 4400/3.28),
    ForecastPoint("Paradise", 46.7868, -121.7353, 5400/3.28),
    ForecastPoint("White Pass", 46.6375, -121.3910, 4500/3.28),
    ForecastPoint("Hurricane Ridge", 47.9698, -123.4980, 5242/3.28),
    ForecastPoint("Washington Pass", 48.5164, -120.6545, 5477/3.28),
]


def make_slug(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return slug


def build_url(api_key: str, point: ForecastPoint) -> str:
    params = {
        "apikey": api_key,
        "lat": f"{point.lat:.4f}",
        "lon": f"{point.lon:.4f}",
        "asl": str(point.asl_ft),
        "format": "json",
    }
    return f"{API_BASE_URL}?{urlencode(params)}"


def fetch_json(url: str, timeout: int) -> Dict:
    with urlopen(url, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset)
        return json.loads(body)


def resolve_output_dir(user_output_dir: str | None) -> Path:
    if user_output_dir:
        out_dir = Path(user_output_dir).expanduser().resolve()
    else:
        out_dir = Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def read_api_key_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None

    # Support either plain key file or KEY=value format.
    first_line = text.splitlines()[0].strip()
    if not first_line or first_line.startswith("#"):
        return None

    if "=" in first_line:
        _, value = first_line.split("=", 1)
        key = value.strip().strip('"').strip("'")
    else:
        key = first_line

    return key or None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pull Meteoblue basic-3h_clouds-3h JSON for all forecast points."
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help=f"Meteoblue API key (overrides key file and {API_KEY_ENV} env var).",
    )
    parser.add_argument(
        "--api-key-file",
        default=None,
        help=f"Path to hidden API key file (default: this folder/{DEFAULT_KEY_FILE}).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write point JSON files (defaults to this script's folder).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds (default: 30).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    key_file = Path(args.api_key_file).expanduser().resolve() if args.api_key_file else (script_dir / DEFAULT_KEY_FILE)
    file_api_key = read_api_key_file(key_file)
    env_api_key = os.getenv(API_KEY_ENV)
    api_key = args.api_key or file_api_key or env_api_key

    if not api_key:
        print(
            (
                "Missing API key. Provide one of: --api-key, "
                f"{key_file}, or {API_KEY_ENV}."
            ),
            file=sys.stderr,
        )
        return 2

    output_dir = resolve_output_dir(args.output_dir)
    fetched_at = datetime.now(timezone.utc).isoformat()

    manifest = {
        "fetched_at_utc": fetched_at,
        "api_package": "basic-3h_clouds-3h",
        "points": {},
    }

    failures: List[str] = []

    for point in POINTS:
        slug = make_slug(point.name)
        output_path = output_dir / f"{slug}.json"
        url = build_url(api_key, point)

        try:
            payload = fetch_json(url, timeout=args.timeout)
        except HTTPError as exc:
            failures.append(f"{point.name}: HTTP {exc.code}")
            print(f"ERROR {point.name}: HTTP {exc.code}", file=sys.stderr)
            continue
        except URLError as exc:
            failures.append(f"{point.name}: URL error ({exc.reason})")
            print(f"ERROR {point.name}: URL error ({exc.reason})", file=sys.stderr)
            continue
        except json.JSONDecodeError as exc:
            failures.append(f"{point.name}: invalid JSON ({exc})")
            print(f"ERROR {point.name}: invalid JSON ({exc})", file=sys.stderr)
            continue

        wrapped_payload = {
            "point": {
                "name": point.name,
                "lat": point.lat,
                "lon": point.lon,
                "asl_ft": point.asl_ft,
            },
            "fetched_at_utc": fetched_at,
            "source": "meteoblue",
            "package": "basic-3h_clouds-3h",
            "data": payload,
        }

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(wrapped_payload, f, indent=2)

        manifest["points"][point.name] = str(output_path.name)
        print(f"Saved {point.name} -> {output_path}")

    manifest_path = output_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Wrote manifest: {manifest_path}")

    if failures:
        print("\nCompleted with failures:", file=sys.stderr)
        for msg in failures:
            print(f"  - {msg}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
