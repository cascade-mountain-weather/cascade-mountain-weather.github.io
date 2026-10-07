# Ski tool beta test: week of Oct 9-11, 2026

What is real: the National Blend of Models run of Wed Oct 7 19Z, extracted by `scripts/ski_nbm.py` at each zone's forecast point for Fri, Sat and Sun
(24 h snow median with 25th and 75th percentile, snow-to-liquid ratio, snow level, gusts, cloud, visibility, temperature over 7 am to 4 pm), checked against the plume
data the precipitation page already uses (24 h liquid and snow match exactly for Stevens, Snoqualmie, Crystal and Baker). Snow on the ground comes from the live conditions file.
Pass delay chances use the I-90 curve (`docs/pass-closures.md`). Avalanche danger is "no forecast" until NWAC resumes (late November). Drive times are hand estimates.

Run it: `python scripts/ski_nbm.py` (needs Herbie: the cmw-herbie conda env with its Library\bin on PATH), then `python scripts/ski_features.py --real`.

## What this week shows

Early October: a wet Friday (0.0 to 0.5 in of liquid, snow levels 5,000 to 6,700 ft), dry Saturday and Sunday, no snowfall forecast anywhere (Icicle Creek 0.4 in on Saturday).
Resorts are closed and no area has the base the tool asks for (resort 20 in, backcountry 24 in, nordic 12 in; rough starting values), so every mode returns "nothing fits" with the reasons.
That is the right answer, and it tests the null path, the gates and the messages. It cannot test the ranking.

## Known gaps

- Visibility is missing for 13 of 39 zone-days (a Herbie subset-file error on a few forecast hours); the scorer treats it as neutral.
- NBM point values are not corrected for the elevation of the point; the snow ratio is not meaningful when no snow falls.
- No avalanche forecast, no live traffic, no resort open-day schedules; base thresholds and the closed-months rule are my guesses.
- The delay curve is borrowed from I-90.
- Nothing has been checked against what happened. After a storm weekend, compare the tool's picks with the observed snowfall (`scripts/score_forecast.py` machinery).

## Next to test the scoring

Replay a past storm weekend (the 2025-26 snapshots in `data/forecasts/` carry snow, snow level and temperature), or wait for the first November storm and run this each Thursday.
