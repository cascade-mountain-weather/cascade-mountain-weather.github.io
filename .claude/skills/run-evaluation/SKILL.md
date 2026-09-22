---
name: run-evaluation
description: Run the weekly forecast evaluation (SNOTEL observations vs saved forecast) and refresh evaluation.html. Use after a forecast period ends.
---

# Weekly forecast evaluation

Scripts live in `scripts/` and expect to run from that directory.

## Pipeline

1. `get_nbm_forecast.py` renames downloaded NBM CSVs into `data/forecasts/<site>.csv` (only if the user has fresh downloads).
2. `build_fx_evaluation.py <snow_level_min> <snow_level_max>` (snow levels in feet) loads the saved forecast, pulls SNOTEL observations via metloom, and writes `data/evaluation_reports/evaluation_YYYY-MM-DD.txt` plus `season_evaluation_summary.txt`.
3. `populate_evaluation_html.py` writes results into `evaluation.html`.

`evaluate_fx.sh` wraps steps 2 and 3 but is interactive (prompts for a conda env, default `DGZefficiency`). From an agent shell, prefer activating the env yourself and running the two Python scripts directly. If the env or dependencies (`metloom`, `selenium`, `pandas`, `bs4`) are missing, tell the user instead of installing into the wrong environment.

## Before running

- Ask the user for the two snow-level arguments if not given. Do not guess.
- Confirm which forecast week is being evaluated and that its `eval_forecast_*.json` exists.
- Selenium and network access are used, so failures can be transient. Report the actual error output.

## After running

- Show the new report's headline results and the `git status` diff summary (expect `evaluation.html`, a new report `.txt`, and the season summary to change).
- `evaluation.html` is a Jekyll page (front matter + body); `populate_evaluation_html.py` does regex-based in-place edits on the file's raw text keyed to specific classes (`stat-number`, `seasonal-card[data-region=...]`, etc.), so it works the same as before the Jekyll migration — no changes needed to the script. Run `jekyll build` afterward and check `_site/evaluation.html` to confirm the new numbers render.
- Do not commit or push unless asked.
