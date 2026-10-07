# Forecast cycles, six periods, lead-time and bias evaluation: design

Status: draft from the Oct 2026 planning session. Nothing here is built. Items marked **(verify)** are checked in the first build step.

## Goal

Show how each product (NBM, HRRR, HRDPS, and the author's forecast) performs for the same weekend as the lead time shrinks, and whether it has a consistent bias. The author writes the forecast on Thursday evening from the Friday 0Z cycle. Readers get newer cycles on the site every 12 hours.

## Periods

Local-time periods, in UTC:

| Period | UTC window | Local (PST / PDT) |
|---|---|---|
| Friday day | Fri 12Z to Sat 0Z | 4 am to 4 pm / 5 am to 5 pm |
| Friday night | Sat 0Z to Sat 12Z | 4 pm to 4 am / 5 pm to 5 am |
| Saturday day | Sat 12Z to Sun 0Z | |
| Saturday night | Sun 0Z to Sun 12Z | |
| Sunday day | Sun 12Z to Mon 0Z | |
| Sunday night | Mon 0Z to Mon 12Z | |

Day is 12Z to 0Z and night is 0Z to 12Z. Daylight saving ends Nov 1, 2026 and starts Mar 14, 2027, so the local clock shifts by an hour while the UTC windows stay fixed. Page labels must say "(UTC windows)" and show both local times.

A weekend total (Fri 12Z to Mon 12Z) stays as a seventh, derived entry.

## Cycles and lead-time coverage

Cycles every 12 h (0Z and 12Z) from Thursday 12Z through Saturday 12Z (decided Oct 2026). Thursday 12Z is the earliest cycle captured; the writing cycle is Friday 0Z.

- NBM reaches every period from every cycle in that range.
- HRRR and HRDPS reach 48 h only. The Friday 0Z cycle (the writing cycle) covers Friday day, Friday night and Saturday day. Saturday night needs a cycle from Friday 12Z or later, Sunday day from Saturday 0Z or later, and Sunday night from Saturday 12Z only.

The forecast-evolution plot must show the gaps (no value) and not interpolate across them.

NBM long cycles run at 01, 07, 13, 19Z. The nearest to 0Z and 12Z are 01Z and 13Z, so label cycles by the actual initialization time and record it.

## Snowfall for a 12 h period (NBM)

The NBM offers 6, 24, 48 and 72 h snowfall windows ending on 6 h boundaries.

- 12 h period = sum of two consecutive 6 h windows. Medians and percentiles do not add.
- Candidate methods: (a) sum the deterministic or median values and mark the band as approximate; (b) take the exceedance-probability curves of each 6 h window and combine them, assuming a stated dependence; (c) use 12 h differences of 24/48 h totals where windows align.
- Step 0 result (Oct 2026, `scripts/test_nbm_percentiles.py`, `docs/nbm_percentile_test.json`; 82 site-weekends from 23 weekends of 2025-26, 24 h windows ending Monday 12Z, built from four 6 h windows): none of the simple combinations is right. Summing the 6 h medians is about 0.7 in low against the real 24 h median (ratio 0.64 for 1-3 in, 0.96 for storms over 8 in), summing the 6 h p25 is far too low (ratio 0.15 to 0.74), and summing the 6 h p75 is 4-12% high. The real 24 h interquartile range is 0.73 of the fully-correlated sum. Per-percentile scale factors (p25 x1.42, p50 x1.11, p75 x0.93) cut leave-one-weekend-out error from 0.95/0.70/0.61 in to 0.71/0.63/0.47 in, but the factors depend on amount. Decision (Oct 2026): adopted. Use scaled sums and label 12 h NBM percentiles approximate (`method: scaled-sum`), with p25 shown as the weakest. Caveat: the test is at 24 h; 12 h sums two windows, so errors should be smaller but are not verified.
- Original plan for the test **(done, see result above)**: for 24 h windows, where real percentiles exist, compare each method's p25/p50/p75 against the real ones, over the saved snapshots. Pick the method with the smallest error and record the choice and its error in the file.
- Every stored value carries `method` (`direct`, `sum-of-medians`, `exceedance-interp`, and so on), as the snapshot already does.

## Archive format

One file per model and cycle, small, only for the weekend it is relevant to:

`data/cycles/<model>/<YYYYMMDDHH>.json` (inside the excluded `data/` folder)

```
{
  "model": "nbm" | "hrrr" | "hrdps",
  "cycle": "2026-11-27T00:00Z",          // actual initialization time
  "captured": "2026-11-27T04:55Z",       // when the bot got it
  "weekend": "2026-11-28",               // first Friday-based weekend this cycle feeds (Friday date)
  "sites": {
    "<site id>": {
      "elevation_ft": ..., 
      "periods": {
        "fri_day": {"snow_in": {"p25":, "p50":, "p75":, "method":}, "snow_level_ft": {...}, "temp_f": ..., "gust_mph": ...},
        ...
      }
    }
  }
}
```

Deterministic models store a single value in place of the percentiles. HRDPS assumes 10:1 snow ratio, as today, and says so. A missing period is stored as null with a reason, never omitted.

Size check **(verify)**: 3 models x 8 cycles x about 10 sites per weekend is small. If it grows, compress by season.

## Capture

- The two plume workflows already run every 6 h and keep only the newest cycle. They gain a step that also writes the cycle file when the cycle falls on 0Z or 12Z within the capture window. This reuses the files they already download.
- Each capture looks for the latest available cycle and records which one it got. A missed 12-hourly capture is permanent for HRDPS (not archived); NBM and HRRR can be rebuilt from AWS.
- GitHub throttles scheduled workflows, so run times are best effort. The workflows keep their `git pull --rebase` and `[skip ci]` pattern.
- The Thursday snapshot (`nbm_snapshot.py`) stays the author's saved forecast-time record and is also written in the new six-period format. It is the cycle used to score "as written".

## Site display

- Plume pages show the newest cycle every 12 h.
- Decided: the first release shows only the newest cycle. It adds a **trend metric** per site and period: the change from the previous cycle (12 h earlier) in forecast snowfall, shown as an arrow and amount, with "steady" inside a small tolerance. It reads from the cycle archive, so earlier cycles are never shown, only the difference. Stepping through earlier cycles stays a later option.

## Observations (SNOTEL)

`scripts/snotel_obs.py` already uses AWDB hourly data in UTC, so periods align exactly. Needed changes, tested on the 2025-26 backfill and known storms before any scoring change:

- 12 h windows have two 6 h steps, so one noisy sample matters much more. Try 3 h steps and re-derive the noise thresholds. Count how many station-periods change.
- Add a maximum-step filter (for example, a SWE or depth change implausible within a step is flagged, not scored).
- Add a depth sanity check (depth above zero with near-zero SWE, negative values, and resets that recover).
- Keep and re-check: noise floor, SWE cap against accumulated precipitation, trace rule, warm-step rule, depth agreement with SWE.
- Keep saving every filter input and the `gate` that fired, so any estimate can be audited. Flag stations as questionable instead of silently dropping them.

## Scoring and bias tracking

Per cycle, per model, per site, per period: forecast value, observed value, error, and the lead time in hours (cycle to period start).

Metrics, all by lead-time bin and by period, and kept season by season:

- **Hit rate:** observed midpoint inside the forecast range (as the current page defines it).
- **Bias:** mean signed error, with a weekend-clustered 90% interval, so a handful of big storms cannot dominate. Also bias of the ratio (forecast / observed) for snow, since errors scale with amount.
- **Error size:** MAE and RMSE, plus a skill score against a reference (persistence of the earlier cycle, and the NBM median).
- **Categorical skill:** snowfall at or above thresholds (for example 1, 3, 6, 12 in per period) with hit rate, false alarm rate and frequency bias, since "is there fresh snow Friday night?" is a yes/no decision.
- **Snow level:** signed error against the observed level (radiosonde, and station temperature where it constrains it), by lead time. Known caveat: the NBM has only snow level, not freezing level.
- **Systemic bias breakdowns:** by area, by elevation band, by period (day or night), by storm type or snow level regime (cold, marginal, warm), and by amount bin. Show them as a small table and a heatmap with the sample size in each cell. Cells under a minimum count (for example 5) are greyed, not scored.
- **Calibration:** for NBM, how often the observed value falls inside p25-p75 (should be about 50%) and p10-p90 if available.

The author's forecast is scored on the same periods as an extra "product", from the posts, as today (`scripts/ours_from_posts.py`). It exists for the Friday 0Z cycle only.

The evaluation JSON gains: `periods`, `cycles` (per product, by lead time) and `bias` (the breakdown tables). The page gets the six-period filter, a lead-time error plot per model, and a bias section. Season boundaries stay September to August.

## Forecast-evolution plot

For a chosen weekend, site and period: x is cycle (or lead time), y is forecast snowfall, with p25-p75 as a band for NBM and a point for the deterministic models, and the observed value as a horizontal band. Gaps are shown as gaps. This is a lagged comparison of successive runs, not an ensemble: the spread shows how much the forecast changed, not the true uncertainty. Label it that way.

## Build order

1. **Step 0 (tests, no UI):** the NBM 12 h percentile method test, the SNOTEL 3 h versus 6 h step test on 12 h windows, and the filter checks, all on 2025-26 and saved snapshots. Output: a short result table added to `docs/nbm_fields.md` or a new `docs/evaluation_filters.md`.
2. **Schema and archive writer:** `scripts/cycle_archive.py`, used by the plume bots and the Thursday snapshot.
3. **Backfill:** NBM and HRRR cycles for 2025-26 from AWS (HRDPS cannot be backfilled).
4. **Scoring:** period and lead-time scoring, bias tables, `build_evaluation_json.py` changes.
5. **Page:** period filter, lead-time plot, bias section, forecast-evolution plot.
6. **Automation:** Monday scoring as a scheduled Action once the Herbie extraction is proven in Actions.

## Decisions (Oct 2026)

1. First release shows only the newest cycle, plus a trend metric (change from the previous cycle).
2. Capture starts Thursday 12Z.
3. Bias cells need at least 5 samples; categorical thresholds are 1, 3, 6 and 12 in per period.

4. Snowfall hit slack (Oct 2026): a forecast range counts as a hit when the observed amount is within the range plus the larger of 1 in or 10% of the observed amount (`slack_in` in `score_forecast.py`). Small errors on dry weekends are not misses, and big storms are still held to a range.
5. SNOTEL observations (Oct 2026): `snotel_obs.station_window` is now step-based (cleaned 3 h steps, summed into windows), so periods add up to the 24 h and weekend totals. Windows with a SWE gain under 0.2 in carry `near_sensor_resolution` and a low end of 0. The old estimator stays as `station_window_v1` until the 2025-26 results are accepted.

## Open questions

1. How the Thursday snapshot relates to the Friday 0Z cycle file: the same cycle may be captured twice, once by the author and once by the bot. Keep both, flagged, and score from the author's.
2. Trend tolerance for "steady" (placeholder: within 1 in or 20%, whichever is larger).
