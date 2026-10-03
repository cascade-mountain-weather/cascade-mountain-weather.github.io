# NBM via Herbie: Phase 0 findings

Spike run 2026-10-02 with `scripts/spike_nbm_herbie.py` in the `cmw-herbie` conda env
(Herbie 2026.9.2, cfgrib 0.9.15.1, ecCodes 2.49.0). Everything below was measured, not assumed.

## Verdict

Herbie can pull the NBM fields the forecast and evaluation tools need, only the fields wanted,
in about 20 seconds for seven fields at one forecast hour. It reproduces the NBM viewer exactly.

## Validation against the viewer CSVs

`data/forecasts/Stevens Pass.csv` came from the **2026-04-17 01Z cycle**. At the Stevens Pass
grid point, Herbie's values for that cycle match the CSV to the digit:

| valid (UTC) | Herbie snow level | CSV | Herbie 2 m temp | CSV |
|---|---|---|---|---|
| 2026-04-17 02Z | 816 m | 816 | 271.84 K | 271.84 |
| 2026-04-17 08Z | 784 m | 784 | 270.38 K | 270.38 |

Neighboring cycles differ by 8 to 64 m, so the match is not a coincidence. This means the existing
eval JSON files and the Herbie pipeline use the same data, and the Selenium step can be retired once
this is automated.

## What the cycles contain (13Z cycle, checked file by file)

- **Hourly full files F001-F048.** Each is ~150 MB with 150+ messages.
- **Every 3 hours F050-F191** (50, 53, 56, ...), **every 6 hours F197-F263**. The files in between
  (F049, F051, F052, ...) exist but are ~1 MB single-message placeholders. Check the `.idx` size
  before trusting a file: a 51-byte `.idx` is a placeholder.
- **Long cycles only:** 01Z, 07Z, 13Z and 19Z reach F263. The one other cycle I tested (22Z) stops near F048,
  so a Thursday forecast for Fri-Mon (about F100) must use one of these four.
- Whistler is inside the CONUS grid (0.3 km to the nearest point), so Herbie covers southwest BC at least
  to there. This resolves the BC open question for the Whistler point.

## Fields confirmed (names as the GRIB `.idx` writes them)

| need | message | notes |
|---|---|---|
| snow level (deterministic) | `SNOWLVL:0 m above mean sea level` | meters MSL. Opens as an `unknown` variable. |
| snow level (distribution) | `SNOWLVL:surface:...:N% level` | 16 percentile levels, 1% to 99% |
| snow-to-liquid ratio | `SNOWLR:surface:...:N% level` | percentile levels only, no deterministic field. 11.7 to 14.4 in the April spot check. |
| temperature | `TMP:2 m above ground` (+ `ens std dev`) | Kelvin |
| gust | `GUST:10 m above ground` (+ `ens std dev`) | m/s, opens as `i10fg` |
| cloud | `TCDC:surface` | percent, opens as `tcc` |
| visibility, ceiling | `VIS:surface`, `CEIL:cloud ceiling` | with exceedance probabilities |
| precip type | `PTYPE:surface:prob >=N <M` | probabilities only |
| snow depth | `SNOD:surface` | with exceedance probabilities |

`CSNOW` and `CRAIN` (categorical snow and rain) do not exist.

## The snowfall catch (important for evaluation)

Weekend snowfall is **not** one field. What each file holds:

- **F001-F048 (hourly files):** `ASNOW` and `APCP` are **1-hour** accumulations (window label
  `23-24 hour acc` in the F024 file). `ASNOW` has 24 messages: percentile levels, 1% to 99%.
- **F050-F098 (3-hourly files):** most files carry `APCP` (1 hour, deterministic) and **no `ASNOW`**.
  `ASNOW` only appears in files whose forecast hour ends 5 mod 6 (F053, F059, F065, F071, ...). Those hold
  **6-, 24-, 48- and 72-hour accumulation windows**, each with percentile levels (for example F053 has
  `47-53`, `29-53`, `5-53` and `5-29`). The viewer's `ASNOW6hr/24hr/48hr/72hr` columns come from these.
- Hours that end in those windows land on 18Z, 00Z, 06Z and 12Z for the 13Z cycle (cycle hour + 5).
- A few 3-hourly F131-F188 files returned errors in my parallel scan; I believe they were transient
  (6 simultaneous requests) but I did not re-check them individually.

Consequences:

1. A weekend total with a **proper probability range** comes from the long-window `ASNOW` percentiles
   (a 72-hour window ending at the right hour), not from adding hourly values: percentiles do not add.
2. The right window ending exactly at Monday 4am is not always available. Where it is not, combine
   a 72-hour window with a 6- or 24-hour one and say so; or accept a deterministic sum of the 50% level.
3. `ASNOW` is missing for days 3-4 in most files. For those hours snowfall has to be inferred from
   `APCP`, `SNOWLVL` and `SNOWLR`, or taken from the long-window files only.

This is the first thing to design carefully before the evaluation compares "your range" with "NBM".

## Operational findings

- **Source.** NOMADS keeps about 2 days; the AWS bucket `noaa-nbm-grib2-pds` keeps the archive (April 2026
  is present, and the bucket goes back to 2020). Locating a cycle takes 0.6 to 1.7 s.
- **Do not pass `source="aws"`.** With `verbose=False` Herbie still resolved old cycles to NOMADS and
  failed. Use `priority=["aws"]` for cycles older than 2 days (the script does this).
- **Cost.** One field at one forecast hour is 0.8 to 1.7 MB (byte range). The snow-level percentile set
  (16 messages) is about 20 MB and took 34 s: ask for the one percentile you need, not the whole set.
- **First-run work:** a full 24-hour window of hourly files for 10 sites is on the order of 100 range requests.
  Within an Action this should be minutes, but time it before choosing a cron frequency.
- **Windows:** the env must be on `PATH` (`Library\bin`) or ecCodes is not found. Not an issue on `ubuntu-latest`.
- **Environment:** `mamba` solved the env in about a minute; classic `conda` was far slower.

## Open items

- ASNOW file coverage for F131-F188: recheck without parallelism.
- Elevation correction: values above are the nearest 2.5 km grid point. The ski tool still needs the
  DEM step in its plan.
- Pick the exact snapshot cycle and time for the Thursday forecast (a 13Z or 19Z cycle is available by
  mid-morning Pacific).
- Check that ecCodes installs on `ubuntu-latest` through `conda-incubator/setup-miniconda` or `apt`.
