---
name: new-forecast-post
description: Scaffold the weekly weekend forecast post as a new _posts/ file from posts/TEMPLATE-post.html, using Jekyll front matter. Use when starting or publishing a new Thursday forecast.
---

# New weekly forecast post

Ask the user for anything not already provided: the post date (default: the coming Thursday), the tagline, a 1-2 sentence summary, and the figure files. Never invent forecast content, numbers, or model output.

## Steps

1. **Pick the date** `YYYY-MM-DD` and confirm `_posts/YYYY-MM-DD-weekend-forecast.html` does not already exist.
2. **Copy the template**: `posts/TEMPLATE-post.html` to `_posts/YYYY-MM-DD-weekend-forecast.html`. The date in the filename becomes the post's date and its URL segment — Jekyll's permalink config keeps the historical scheme `/posts/YYYY-MM-DD-weekend-forecast.html`. Use the most recent existing file in `_posts/` as a structural reference for section order and markup.
3. **Fill front matter**: `title` (plain text, no " | Cascade Mountain Weather" suffix — the layout adds that automatically), `description`, `keywords`, `tagline` and `summary` (shown in the homepage hero for the latest post — can match `title`/`description` if there's no punchier line), `forecast_period` (just the date range, e.g. `"18-19 April 2026"` — the layout adds the "🎿 Forecast:" label). List any remaining `[UPDATE` markers in the body and report them rather than guessing content.
4. **Figures**: images live in `assets/images/YYYYMMDD_fx/` (folder date = post date, no dashes). Reference them from the post body as `../assets/images/YYYYMMDD_fx/<file>` (posts render one path segment deep, same as before). Add meaningful `alt` text where the user describes the figure. If the folder is missing, ask where the images are; do not fabricate paths.
5. **No manual wiring needed**: the homepage hero, "Recent Forecasts", and `posts/archive.html` all read `site.posts` automatically — adding the file is the only step. Do not touch `index.html` or `posts/archive.html`.
6. **Preview before finishing**: run `jekyll build` (or `jekyll serve`) from the repo root and check the new post renders, plus that it now appears as the homepage hero and at the top of the archive.
7. **Verify**: run the `/site-check` steps for the new post (image files exist, no leftover `[UPDATE`).
8. **Do not commit or push** unless asked. When asked, note that bots push to `main` often, so `git pull --rebase` first. Commit style: short, e.g. `posting this week's forecast`.

Evaluation is a separate step after the forecast period; see `/run-evaluation`. The forecast JSON `data/forecasts/eval_forecast_YYYY-MM-DD.json` for the post date should exist for that step (see `eval_forecast_template.json`). Ask the user for the numbers rather than filling them in.
