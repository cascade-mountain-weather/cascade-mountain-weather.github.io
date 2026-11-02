"""Merge the newest satellite frames into the rolling set that is published on the `satellite-data` branch.

Run by .github/workflows/update_satellite_loop.yml every hour, after scripts/build_cod_satellite_loop.py has built
the newest ~8 hours of frames (20 minutes apart) into a scratch folder:

    python scripts/publish_satellite_frames.py --built BUILT_DIR --site SITE_DIR --keep-hours 24

SITE_DIR starts as the previous contents of the branch (or empty). New frames are copied in under a name that carries
their time (so a frame that was already there is not rewritten), frames older than --keep-hours are dropped, and the
manifest is rewritten, oldest frame first, with paths relative to the branch root:

    manifest.json, latest_frame.webp, frames/sat_YYYYMMDDTHHMMZ.webp

The workflow then force-pushes SITE_DIR as a single commit, so the branch never accumulates history.
"""
import argparse
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--built", required=True, help="folder from build_cod_satellite_loop.py (satellite_manifest.json + frames/)")
    ap.add_argument("--site", required=True, help="working copy of the satellite-data branch")
    ap.add_argument("--keep-hours", type=float, default=24)
    ap.add_argument("--built-manifest", default="satellite_manifest.json")
    args = ap.parse_args()
    built, site = Path(args.built), Path(args.site)
    (site / "frames").mkdir(parents=True, exist_ok=True)

    new = json.loads((built / args.built_manifest).read_text(encoding="utf-8"))
    old_path = site / "manifest.json"
    old = json.loads(old_path.read_text(encoding="utf-8")) if old_path.exists() else {}

    frames = {f["file"]: f for f in old.get("frames", [])}
    for f in new.get("frames", []):
        ts = parse(f["timestamp_utc"])
        name = f"frames/sat_{ts:%Y%m%dT%H%MZ}.webp"
        dest = site / name
        if not dest.exists():
            shutil.copyfile(built / "frames" / f["file"], dest)
        frames[name] = {"file": name, "timestamp_utc": ts.strftime("%Y-%m-%dT%H:%M:%S+00:00"), "duration_ms": f.get("duration_ms", 300)}
    if not frames:
        raise SystemExit("no frames to publish")

    newest = max(parse(f["timestamp_utc"]) for f in frames.values())
    cutoff = newest - timedelta(hours=args.keep_hours)
    kept = sorted((f for f in frames.values() if parse(f["timestamp_utc"]) >= cutoff), key=lambda f: f["timestamp_utc"])
    keep_files = {f["file"] for f in kept}
    for p in (site / "frames").glob("*"):
        if f"frames/{p.name}" not in keep_files:
            p.unlink()

    shutil.copyfile(site / kept[-1]["file"], site / "latest_frame.webp")
    manifest = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": new.get("source_url"),
        "latest_frame_file": "latest_frame.webp",
        "frame_count": len(kept),
        "frames": kept,
    }
    old_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"Published {len(kept)} frames, {kept[0]['timestamp_utc']} to {kept[-1]['timestamp_utc']}")


if __name__ == "__main__":
    main()
