"""Build assets/data/basins.geojson: the HUC8 watershed polygons the live
conditions map highlights (the basin codes come from _data/areas.yml).

Source: USGS Watershed Boundary Dataset (hydro.nationalmap.gov). Polygons are
simplified (~400 m) to keep the file small. Static: only re-run when a basin
code in areas.yml changes.

Run from the repo root:  python scripts/build_basins.py
"""
import json
from pathlib import Path

import requests
import yaml

REPO = Path(__file__).resolve().parent.parent
AREAS_FILE = REPO / '_data' / 'areas.yml'
OUT_FILE = REPO / 'assets' / 'data' / 'basins.geojson'
WBD_URL = 'https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/4/query'


def main():
    areas = yaml.safe_load(AREAS_FILE.read_text(encoding='utf-8'))['areas']
    codes = sorted({c for a in areas for c in (a.get('basins') or [a.get('basin')]) if c})
    where = 'huc8 IN (' + ','.join(f"'{c}'" for c in codes) + ')'
    resp = requests.get(WBD_URL, params={
        'where': where,
        'outFields': 'huc8,name',
        'outSR': 4326,
        'maxAllowableOffset': 0.004,
        'geometryPrecision': 3,
        'f': 'geojson',
    }, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    found = {f['properties']['huc8'] for f in data.get('features', [])}
    missing = set(codes) - found
    if missing:
        raise SystemExit(f'No polygon returned for basin code(s): {sorted(missing)}')
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(data, separators=(',', ':')), encoding='utf-8')
    print(f'Wrote {OUT_FILE.relative_to(REPO)}: {len(found)} basins, {OUT_FILE.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
