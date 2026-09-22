---
name: site-check
description: Sanity-check the site before pushing - a Jekyll build, leftover template markers, front matter, and missing image files. Use after editing posts, layouts, includes, or the homepage.
---

# Pre-push site check

Read-only unless the user asks for fixes.

1. **Build**: run `jekyll build` (or `bundle exec jekyll build`) from the repo root. Any Liquid syntax error or missing-layout warning shows up here — this is the single most useful check after touching `_layouts/`, `_includes/`, or any front matter, since GitHub Pages' own build is otherwise the first place it would surface.
2. **Changed files**: `git status` and `git diff --stat` against `main`.
3. **Front matter**: for any new/changed file in `_posts/` or a top-level page, confirm required fields are present (posts: `title`, `tagline`, `summary`, `forecast_period`; pages: at least `layout` and `title`).
4. **Leftover markers**: grep `_posts/`, `posts/TEMPLATE-post.html`, and top-level `*.html` for `[UPDATE` and `TODO`.
5. **Image references**: for each changed post, extract `src="..."` values that point at local files and confirm each exists on disk (post images are referenced as `../assets/images/YYYYMMDD_fx/x.png`, relative to the post's rendered depth). Watch for case mismatches, since GitHub Pages is case-sensitive even though Windows is not.
6. **Rendered output**: for a changed post, check `_site/posts/<file>` (after building) actually shows the new content, and that it appears in the rendered `_site/index.html` hero/recent-list and `_site/posts/archive.html`.
7. **Canonical/date consistency**: the post's filename date, its rendered `<title>`, and its forecast_period text should agree.
8. **Large files**: flag any newly added image over roughly 5 MB.
9. Ignore bot-generated files (`tools/model-tools-current-weather.html`, `assets/images/satellite/`, `gfs_dgz_F24.png`) and build output (`_site/`, gitignored) — these are never hand-edited or reviewed as source changes.

Summarize as a short pass/fail list with file paths.
