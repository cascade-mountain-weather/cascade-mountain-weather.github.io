# UW WRF forecast soundings

Findings from the Oct 2026 spike. Scripts: `scripts/uw_soundings.py` (fetch and derive), `scripts/test_uw_vs_radiosonde.py` (spot check).

## Source

PacNW WRF-GFS 4/3 km forecast soundings, `a.atmos.washington.edu/mm5rt/rt/showsounding_d4.cgi`. One page per site, run and forecast hour. Each page embeds a plain text table (`PRES TMPC DWPC TMPF DWPF DRCT SPED SKNT HGTM HGTFT`) from the model surface level up, plus a header with station id, lat/lon, elevation and valid time.

- Runs: **00Z and 12Z only** (06Z and 18Z do not exist). At least 3.5 days of runs stay available. The Oct 7 00Z run was not there 35 minutes after its time.
- Frames: every 3 h from 0 to at least 72 (25 frames).
- Cost: about 25 requests per site per run, one every 0.7 s, so 8 sites take about 5 minutes. Run it twice a day, after each run lands. The site's terms of use have not been read; `robots.txt` on this host only redirects to atmos.uw.edu.

Sites (id: name): `ksmp` Stampede Pass, `pvc55` Paradise-Mt Rainier, `rimrk` Rimrock Retreat (White Pass), `kosmo` Kosmos (Mt. St. Helens), `dowlx` Olympex DOW (Olympics), `discl` Diablo Powerhouse (North Cascades), `lvwth` Leavenworth, `mtwpm` Methow Valley.

## Derived per frame

Freezing level, wet-bulb-zero level and melting-model snow level (feet MSL), growth-zone (-12 to -18 C) thickness and its near-saturated part, strongest low-level inversion, precipitable water above the station, integrated vapor transport (IVT), and 850 and 700 hPa temperature and wind. The melting model is the one in `scripts/collect_radiosonde_history.py`.

## Spot check against Quillayute radiosondes (Oct 3-6, 2026)

Olympex DOW forecast minus Quillayute observed, 4 to 8 pairs per lead, warm dry early-October pattern (freezing level about 13,200 to 14,400 ft):

| Lead | Freezing level (ft) | 850 hPa T (C) | 700 hPa T (C) | Precipitable water (mm) | IVT (kg/m/s) |
|---|---|---|---|---|---|
| 0 h | +410 | +1.1 | +0.8 | -2.4 | -29 |
| 12 h | +54 (MAE 159) | -0.1 | +0.3 | -1.6 | -26 |
| 24 h | -34 (MAE 190) | -0.1 | +0.1 | -1.6 | -26 |
| 48 h | -221 (MAE 258) | -0.8 | -0.1 | -2.1 | -38 |

- Temperatures and the freezing level agree within about 1 C and a few hundred feet.
- Precipitable water is about 10% dry and IVT is low in every lead. Model top, sonde humidity noise and a 60 km offset are possible causes; not resolved.
- Wet-bulb-zero and snow level have a mean absolute error of 500 to 800 ft. In dry air they are not meaningful (the radiosonde tool only trusts them near saturation), so this period says nothing about snow level in storms.
- Limits: tiny sample, one pair of sites, no storm, so no verdict on snow level, growth zone or IVT in wet weather. Score every 00Z and 12Z launch through the season, once the runs are archived (see `docs/forecast-cycles-design.md`).
