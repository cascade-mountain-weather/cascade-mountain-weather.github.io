---
name: run-evaluation
description: Score the latest forecast weekend against SNOTEL and soundings and refresh the evaluation page data. Use on Monday after a forecast weekend ends.
---

# Weekly forecast evaluation

Run from the repo root in the `cmw-herbie` conda env (Herbie, cfgrib, eccodes; see `docs/nbm_fields.md`).

## Each weekend

1. **Thursday, when the forecast is written:** `python scripts/nbm_snapshot.py` (newest long NBM cycle, Friday to Sunday). It writes `data/forecasts/nbm_snapshot_<first-day>.json`. The NBM cannot be rebuilt later for the exact run you saw, so capture it then.
   `python scripts/draft_forecast_tables.py` drafts the post's snowfall and snow-level tables from it.
2. **Monday, after the weekend:** `python scripts/score_forecast.py data/forecasts/nbm_snapshot_<first-day>.json` scores it against SNOTEL snowfall (`scripts/snotel_obs.py`) and radiosonde snow level, and reads your ranges from the published post (`scripts/ours_from_posts.py`). Output: `data/evaluation/score_<first-day>.json`.
3. `python scripts/build_evaluation_json.py` rebuilds `assets/data/evaluation.json`, which `evaluation.html` reads in the browser. The weekend's season comes from its date.

## Notes

- Your forecast ranges come from the post's weekend-total table. The saved `eval_forecast_*.json` files are retired: several held wrong ranges.
- The observed snowfall is an estimate and a wide range; see the docstring in `scripts/snotel_obs.py` for the checks (trace precipitation, rain on snow, depth spikes).
- To redo a whole past season after changing the method: `python scripts/backfill_evaluation.py --rescore`.
- A new season needs an entry in `SEASONS` in `scripts/build_evaluation_json.py`. Test weekends before a season's first real forecast go in `PRESEASON`.
- Run `jekyll build` and open `/evaluation.html` to check it. Do not commit or push unless asked.
