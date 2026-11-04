"""North Pacific sea surface temperature anomaly maps (Japan to the Washington coast), for the synoptic tools page.

Data: NOAA NCEI daily OISST v2.1 (AVHRR), the `anom` field (departure from the 1991-2020 climatology). The newest days are
only "preliminary" files; NCEI replaces them with final ones about two weeks later, so a frame is rendered from whichever
file exists. Each file is the whole globe (a few MB); only the North Pacific is kept.

Writes assets/data/sst/np_sst_anom_YYYYMMDD.png (bot-generated, do not hand-edit) and manifest.json:
  - a frame every STEP days (anchored to the calendar, so a frame is written once and not rewritten every day)
  - plus the latest available day
  - about WINDOW days back, older frames are deleted.
assets/model-tools-synoptic.js reads manifest.json.

Run: python scripts/sst_anomaly_maps.py   (deps: requests numpy xarray netCDF4 matplotlib)
"""
import json
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests

OUT = Path(__file__).resolve().parent.parent / "assets" / "data" / "sst"
BASE = "https://www.ncei.noaa.gov/data/sea-surface-temperature-optimum-interpolation/v2.1/access/avhrr"
HEADERS = {"User-Agent": "cascade-mountain-weather.github.io SST maps (dlhogan@uw.edu)"}
STEP = 5          # days between frames
WINDOW = 60       # days of frames kept
LAT = (15.0, 65.0)
LON = (120.0, 240.0)   # 120E to 120W on the dataset's 0-360 grid
VLIM = 4.0


def fetch(day):
    """Path of a downloaded NetCDF for this date (final file if it exists, else the preliminary one), or None."""
    ym = day.strftime("%Y%m")
    for suffix in ("", "_preliminary"):
        url = f"{BASE}/{ym}/oisst-avhrr-v02r01.{day.strftime('%Y%m%d')}{suffix}.nc"
        try:
            r = requests.get(url, headers=HEADERS, timeout=120)
        except requests.RequestException:
            continue
        if r.status_code == 200 and len(r.content) > 100_000:
            tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
            tmp.write(r.content)
            tmp.close()
            return Path(tmp.name)
    return None


def render(day, nc_path, png_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import xarray as xr

    ds = xr.open_dataset(nc_path)
    a = ds["anom"].isel(time=0, zlev=0)
    a = a.sel(lat=slice(*LAT), lon=slice(*LON))
    lon, lat, z = a["lon"].values, a["lat"].values, a.values
    ds.close()

    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=110)
    ax.set_facecolor("#9aa3ad")   # land and no-data show as grey
    mesh = ax.pcolormesh(lon, lat, np.ma.masked_invalid(z), cmap="RdBu_r", vmin=-VLIM, vmax=VLIM, shading="auto", rasterized=True)
    # coastline: the edge of the land mask (the analysis is missing over land), drawn as a thin black contour
    land = np.isnan(z).astype(float)
    ax.contour(lon, lat, land, levels=[0.5], colors="k", linewidths=0.6)
    ax.set_xticks(range(120, 241, 20))
    ax.set_xticklabels([f"{x}°E" if x < 180 else ("180°" if x == 180 else f"{360 - x}°W") for x in range(120, 241, 20)], fontsize=8)
    ax.set_yticks(range(20, 66, 10))
    ax.set_yticklabels([f"{y}°N" for y in range(20, 66, 10)], fontsize=8)
    ax.grid(color="k", alpha=0.25, lw=0.5, ls=":")
    ax.set_xlim(*LON)
    ax.set_ylim(*LAT)
    ax.set_title(f"North Pacific sea surface temperature anomaly, {day.day} {day.strftime('%b %Y')}",
                 fontsize=11, loc="left", color="#1e3c72", fontweight="bold")
    cb = fig.colorbar(mesh, ax=ax, orientation="horizontal", pad=0.09, fraction=0.045, extend="both")
    cb.set_label("°C above (red) or below (blue) the 1991–2020 average. NOAA OISST v2.1", fontsize=8)
    cb.ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(png_path, dpi=110)
    plt.close(fig)


def wanted_days(latest):
    days = {latest}
    d = latest
    while (latest - d).days <= WINDOW:
        if d.toordinal() % STEP == 0:
            days.add(d)
        d -= timedelta(days=1)
    return sorted(days)


def newest_available():
    """Most recent date with a file, looking back up to a week."""
    today = datetime.now(timezone.utc).date()
    for back in range(1, 9):
        d = today - timedelta(days=back)
        ym = d.strftime("%Y%m")
        for suffix in ("", "_preliminary"):
            url = f"{BASE}/{ym}/oisst-avhrr-v02r01.{d.strftime('%Y%m%d')}{suffix}.nc"
            try:
                if requests.head(url, headers=HEADERS, timeout=30, allow_redirects=True).status_code == 200:
                    return d
            except requests.RequestException:
                pass
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    latest = newest_available()
    if latest is None:
        print("no OISST file found in the last week", file=sys.stderr)
        sys.exit(1)
    days = wanted_days(latest)
    frames = []
    for d in days:
        png = OUT / f"np_sst_anom_{d.strftime('%Y%m%d')}.png"
        if not png.exists():   # a frame is written once (a preliminary day is not redrawn when NCEI finalizes it; the difference is tiny)
            nc = fetch(d)
            if nc is None:
                print(f"{d}: no file", file=sys.stderr)
                continue
            try:
                render(d, nc, png)
                print(f"{d}: rendered")
            finally:
                nc.unlink(missing_ok=True)
        if png.exists():
            frames.append(d)
    keep = {f"np_sst_anom_{d.strftime('%Y%m%d')}.png" for d in frames}
    for stale in OUT.glob("np_sst_anom_*.png"):
        if stale.name not in keep:
            stale.unlink()
    manifest = {"dates": [d.strftime("%Y%m%d") for d in frames], "latest": latest.strftime("%Y%m%d"),
                "file": "np_sst_anom_{date}.png", "source": "NOAA NCEI OISST v2.1"}
    path = OUT / "manifest.json"
    new = json.dumps(manifest, separators=(",", ":"))
    if not path.exists() or path.read_text("utf-8") != new:
        path.write_text(new, "utf-8")


if __name__ == "__main__":
    main()
