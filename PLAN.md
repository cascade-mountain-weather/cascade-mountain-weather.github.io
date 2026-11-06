# Outstanding tasks (updated Nov 6 2026)

Finished work lives in `docs/PLAN-archive.md`. The longer notes further down (ski tool, corn model, storm-type analysis) are design records and were not changed.

## Do next
- [ ] Push the local commits and the post-title (SEO) change. `git pull --rebase` first; bots push to `main`.
- [ ] Oct 30 post: its `forecast_period` is text ("Season opener coming November 5"), so its search title reads oddly. Give it a `seo_title`.
- [ ] Nov 5 post: `tagline` was set to the search title. Check what the home page "Latest Forecast" card shows.
- [ ] Read the "where it is" sentence for each area in `_data/area_pages.yml`.
- [ ] Add "| Cascade Mountain Weather" to the ten area page titles (offered, not done).

## Search and indexing
- [ ] About Nov 10-13: Search Console, Pages report, for the 12 requested URLs (areas, the nine area pages, mt-hood, teleconnections, precipitation tools, home). On `tools/stevens-pass`, compare the declared and Google-selected canonical. If they differ, make internal links, canonicals and the sitemap use one URL form (menu links use `.html`, canonicals do not).
- [ ] Late November: Performance report, once there are two to four weeks of data.
- [ ] Every week: request indexing for the new post and the home page once live; write each post's `description` with the area names (it is the Google snippet).
- [ ] Optional: add `jekyll-feed`.

## Area pages
- [ ] Use `area_notes:` in a post's front matter when it covers a specific zone.
- [ ] Live-conditions map popups still link to the precipitation tools (`page:` in `_data/areas.yml`); point them at the new area pages.
- [ ] Mt. Adams and Mt. St. Helens still redirect to the conditions map; decide whether they get pages.

## Scheduling (cron-job.org)
- [ ] About Nov 7-8: check the `main` log. "Update observations" should be about hourly; also UW soundings and the `satellite-data` branch.
- [ ] Put the GitHub token's expiry date on a calendar.
- [ ] Powder Stash (`update_forecast_data.yml`, twice a day, pushes to `forecast-data`): look at its run history; move it to cron-job.org if runs are missing. Only move `model_data`, `ski_features` and the daily ones if gaps show up.
- [ ] If duplicate runs waste minutes, remove the `schedule:` block from the three moved workflows. Never run both schedulers on `model_data.yml` or `daily_data.yml` (no concurrency group).
- [ ] Leave `weekly_evaluation.yml` on GitHub (a dispatch skips its 10 am Pacific check and would score twice).

## Site polish
- [ ] Posts still feel busy (Danny to simplify): boxes per section, related-tools chips, back-to-contents links.
- [ ] Evaluation page overflows by about 8 px at 320 px wide; two older posts' snow-totals table by 3 px.
- [ ] The teleconnection bar chart is drawn to the box width at render and not redrawn on resize.
- [ ] Tool-page headers (`.hero`) keep tight padding on purpose; revisit if everything should match.

## Paused (done for now, picked up when needed)
- [ ] Storm-type analysis (became the Powder Stash Predictor) and the ski recommendation tool are parked; their notes are in `docs/PLAN-archive.md`. Still open there: NWAC avalanche feed (late November), lowland fallback, drive-time pulls, threshold tuning, checking the picks, rotating the Synoptic token and adding a WSDOT secret.
- [ ] Corn model: still in development (design and notes below).

## Live conditions
- [ ] After the next hourly run, confirm `live_conditions.json` has `swe_hourly_in` and `precip_hourly_in` for NWAC stations too (their precipitation comes from Synoptic `precip_accum_one_hour`; I could only test the SNOTEL side without the token) and that the popup chart shows for NWAC stations (precipitation line only, since NWAC has no SWE).
- [ ] Easy Pass (SNOTEL 998) reports no precipitation total, so it has no precipitation row; Stevens Pass (791) SWE stopped on Nov 5.

## In progress and ideas (existing notes)

Goals: 

7. I want to make a some flags for dendritic growth zone height, east flow/strong inversions, atmospheric river signal. This will update with model conditions

Development goals: tools to be constructed in the background before posting

2. I eventually want to build a simple "corn" model. That is estimate the time, aspects, and elevations where corn will be good. This will essentially be an energy balance model. We could either build it ourselves or try and use an open source snowpack energy balance model. The thing is we only really have to worry about the top 6 inches or so of the snowpack for this to work effectively. Corn is best to ski when it is like 2-10 centimeters. This will essentially require inputs of short and longwave radiation, windspeed, temperature, humidity (an use bulk aerodynamic methods to estimate latent and sensible heat fluxes), a terrain dem, and a solar angle model. The vision is a map of the region with a toggle for the day (upcoming from Thursday-Sunday), a time of day slider, and shading for optimal corn timing. For example, most north facing slopes would not have good corn during this period, but a southwesterly slope at lets say 11am would be pretty good on a May day after a freeze. The model would require a freeze. We could test out the model using observations from nearby SNOTEL sites and days that I found the corn skiing to be pretty good. We can then compare those obs based model results to forcing data from model output. Mayb e achived HRRR if we can get it? It would be nice to also use something like RRFS, HRDPS, or data from the NBM. This would also require a warning for days since the last snowfall. A few days are required before the snow metamorphoses into melt forms that are good for skiing. We could use SNOWPACK, or a simple snow metamorphosis model to estimate when snow starts to become melt forms, or just do a simple number of melt freezecycles greater than 2.
- okay, so one of the final steps will now be to develop the corn model. i want to begin with the "simplest" side of things. The first thing we need is a terrain map/dem/aspect map where we can get an accurate picture of solar clearsky irradiance over terrain throughout each day of the year and each 30-minute window in a day. We don't need actual data yet (that will include cloud cover) but we do need 
          highly detailed high rez maps if we can get them for the region above 4000 feet. We will skip other areas because people wont be skiing them. Is that going to be too difficult to host? From there we are going to deal with several assumptions. We don't really care about exactly how much snow is on the ground, we only care that there is some snow, there isnt really recent fresh snow or rain, that there was or will be a refreeze, and the timing of temperatures and winds over the day. Then we can develop a simple energy balance model to estimate when snow would melt and at what depth to estimate the depth of corn snow over a given location. The clouds again will be uncertain. The corn model will turn off/reset/won't recommend anything if there is precip in the forecast or there is no freeze within the snow model predicted or its super windy, or its cloudy for the entire time. lets start crafting how we will do this.  

3. **Forecast Floater** (idea, Oct 2026): a "floater" forecast tool set for any region I care about or a friend might be going to: a hut trip in the Sawtooths, friends skiing in BC or Japan. By request: give a location (lat/lon or a named place) and a date range, and get a bundle of useful forecast data fast, instead of hunting for it when the time comes. Could start as an "in development" page in the tools section ("Forecast Floater"), and later become a form that builds the bundle on demand. Open questions: which sources cover which places (the NBM covers CONUS and southwest BC, not Japan; HRDPS covers western Canada; global models such as GFS, ECMWF and ICON for anywhere; Open-Meteo would be the easy global source but its non-commercial terms need a check, see the ski tool's open questions); what a bundle contains (point forecast of snow, snow level, wind and temperature; forecast sounding; nearby observations such as SNOTEL, which exists in Idaho; the regional avalanche forecast link); whether the static-site constraint means a page that builds links and client-side plots, or a scheduled Action for a short list of saved places. The plumbing (Herbie extraction at a point, the sounding derivations, the plume plots) is shared with the ski tool and the corn model.
---
## New tools

| Tool | Data source | Page | Update cadence |
|---|---|---|---|
| Radiosonde / Skew-T viewer | IEM RAOB JSON API (`mesonet.agron.iastate.edu/json/raob.py?ts=...&station=...`), rendered client-side with MetPy running in-browser via Pyodide — same technique as `clinton-alden.github.io/radiosonde.html` | new `tools/radiosonde.html` | Twice daily (00Z/12Z soundings), client fetches on page load — no server/cron needed |
| Newsletter signup | Mailchimp embedded form | homepage (button already stubbed via `newsletter_button` front matter flag) | N/A — static form |
| Merch page | Print-on-demand provider (TBD — research Printful/Bonfire/Threadless) | new `merch.html` | N/A — static |
| SNOTEL evaluation dashboard | SNOTEL obs via `metloom` (already used in `scripts/build_fx_evaluation.py`) + saved forecast JSON | `evaluation.html` rework | Monday mornings (new scheduled GitHub Action) |
| Homepage normals widgets | Same SNOTEL pipeline as above, plus climatological normals | `index.html` | Daily |
| DGZ / east-flow / inversion / AR flags | Derived from existing CW3E/UW/NBM model data already scraped by `synoptic.yml` | model-tools pages, referenced in forecast posts | Updates with model runs |
| Climate outlook + teleconnections page | NOAA CPC products: [PNA ensemble](https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna_index_ensm.shtml), [MJO](https://www.cpc.ncep.noaa.gov/products/precip/CWlink/MJO/mjo.shtml), [ENSO](https://www.cpc.ncep.noaa.gov/products/precip/CWlink/MJO/enso.shtml), plus CPC ensemble outlook toggles | new `tools/climate-outlook.html` | Start with CPC's own charts embedded/linked (Thursdays alongside the forecast); Danny's own MJO-phase/local-snow correlation analysis layers in later once he's built it |
| UW WRF ensemble viewer | `a.atmos.washington.edu/wrfrt/ensembles/plumes.html` — feasibility TBD (see Open questions) | model-tools pages | With each UW WRF run (~every 6 hrs) |
| Ski-area recommendation tool | NWAC avalanche danger (Avalanche.org API), WSDOT pass conditions, NBM forecasts pulled with Herbie, precomputed drive times; see "Ski-area recommendation tool: design" below | new `tools/find-your-ski-day.html` (name TBD) | Scheduled Action every ~3 h writes `assets/data/ski_features.json`; scoring runs in the browser |
| Corn model | Energy-balance model (shortwave/longwave, wind, temp, humidity, terrain DEM, solar angle) validated against SNOTEL obs and Danny's own field observations of good corn days; forcing from HRRR/RRFS/HRDPS/NBM if accessible | new `tools/corn-model.html` (see `.claude/skills/corn-forecast-model/SKILL.md`) | Thu-Sun outlook, spring season only |

## Corn model: design

Status: draft from the Oct 7 2026 planning session. Nothing is built. Items marked **(verify)** or **(source)** need a real reference or measurement before use; do not fill in physics numbers from memory.

### Decisions so far

- **Season:** January through June (corn cycles can show up as early as January).
- **Hosting:** do not host irradiance maps. Host static terrain only and compute the sun (position from date/time/lat/lon; slope and aspect; horizon blocking; elevation).
- **Class-based, not per pixel.** Classes are elevation band x aspect octant x slope bin, per region. A scheduled Action runs the energy balance per class and writes a small JSON (corn depth by class, day and half-hour). A static categorical class-ID raster (compressed PNG or tiles) says which class each cell is in; the browser colors it from the JSON, so the time slider is instant. Optional later: a shaded/unshaded flag per half-hour as a class dimension if horizon shading turns out to matter.
- **Elevation cutoffs:** three nested layers, 4000+, 5000+ and 6000+ ft, user-selectable. Measure the cell count and file size per cutoff before choosing the resolution (30 m vs 10 m).
- **Own thin-layer energy balance**, top ~10 cm only, rather than SNOWPACK. Corn target is 2-10 cm thawed depth.
- **Cloud uncertainty:** run two bounds, clear sky and NBM-cloud-adjusted, and show a window with a range.

### Terrain area measured (Oct 7 2026)

`scripts/corn_terrain_area.py`: USGS 3DEP 1/3 arc-second tiles read from the public S3 bucket through their overviews (about 30 m). Boxes: WA Cascades 45.6-49N, 122.7-119.8W (includes St. Helens and Adams, and some low east-side ridges); Olympics 47.4-48.3N, 124.8-122.9W. Cell counts at 10 m are area divided by 100 m2, not a separate read.

| Cutoff | Cascades km2 | Cascades cells at 30 m | Cascades cells at 10 m | Olympics km2 |
|---|---|---|---|---|
| 4000+ ft | 19,646 | 30.8 M | 196 M | 1,336 |
| 5000+ ft | 10,480 | 16.5 M | 105 M | 535 |
| 6000+ ft | 4,302 | 6.8 M | 43 M | 109 |

Reading: 10 m is out for the hosted raster at every cutoff (even 6000+ is 43 M cells). 30 m is workable if the class raster compresses well, but the compressed size is not measured yet; that comes from building the class raster for one cutoff. The classes can also be built at 10 m and then block-reduced to 30 m for hosting.

**Class raster size test (Oct 7 2026):** `scripts/corn_class_raster.py --min-ft 5000` builds a 16-bit PNG of class ids over the WA Cascades at about 30 m: 16.5 M cells above 5000 ft, classes used: see rebuild below; first run **8.2 MB** with 3 slope bins, rebuilt with 4 slope bins (10-25, 25-35, 35-45, 45+): **8.5 MB** (500 ft bands x flat or slope bins x 8 aspect octants; the bands, slope edges and flat limit are placeholders, not sourced). The file is not committed. 4000+ ft has about 1.9x the cells, so roughly 15 MB if it scales (not measured); 6000+ would be smaller. Still to decide: serve the three cutoffs as one 4000+ raster (the cutoff is just a filter on the elevation band) rather than three files.

**Slope bins (decided Oct 14 2026, replaces the Oct 8 reading):** flat = under 10 degrees (no aspect), shallow = 10-25, then 25-35 and 35-45, so four slope classes; 45 degrees and steeper is not forecast (class 0). 8 aspect octants for every class except flat, 500 ft elevation bands (placeholder). **One raster** serves all three cutoffs (4000+, 5000+, 6000+ ft are a filter on the elevation band). Measured with this scheme: the 4000+ ft raster is **14.8 MB** (29.2 M cells forecastable, 523 classes), as estimated. Not committed; still to check that it loads quickly on mobile, or consider tiling.

### Regional model and the click-to-rose view

- Two separate things vary in space. **Terrain** (elevation band, aspect, slope) is the class raster above. **Weather forcing** (air temperature, wind, humidity, cloud) comes from forecast grid points and varies by region. So the Action runs the energy balance for every (forcing region x terrain class) pair, and writes region x class x day x half-hour values. Forcing regions (decided Oct 8 2026): the ski tool's 13 zones plus one new region around Glacier Peak (14 total). The corn regions live in their own file (**to create**, for example `data/corn/regions.yml`, referencing the ski zones) so adding Glacier Peak does not add a destination to the ski tool; its forecast point needs coordinates **(verify)**. Each region's forcing is lapse-rate adjusted to the class elevation.
- A second small raster (or polygons) assigns each cell its forcing region. The map colors a cell by looking up (region, class) in the JSON for the chosen day and time.
- Click a point: read the cell's region and elevation band. The **rose** is a polar plot with aspect around the circle and elevation outward; each wedge is that region's result for that (aspect octant, elevation band) at the selected day and time (slope bin fixed or selectable). The point's own cell is outlined. No new data is needed; it is a different view of the same JSON.
- Limits: the rose shows open-terrain behavior for the region. Per-cell horizon shading and local microclimate are not in it unless we add the shaded flag.

### Static layers (one-time script, shares DEM code with `scripts/ski_dem.py`)

USGS 3DEP DEM (WA). Derived: elevation, slope, aspect, sky-view factor, horizon angle in about 16-36 azimuths **(verify the count against horizon-shading accuracy)**. Clear-sky shortwave via `pvlib` solar position and a clear-sky model **(verify choice of model)**. Commit only the derived class raster and class table, not source rasters.

### Model structure

1. Gates, in order: snow exists; no recent new snow or rain; wind under threshold; not overcast all day. Any failure gives "no recommendation". All thresholds are placeholders to tune **(source)**. There is no air-temperature freeze gate: the refreeze test is the surface energy balance (step 2).
2. Run the full energy balance through the night, every night, including nights with air temperature above 0 C. The surface can refreeze with air above freezing if net longwave loss (clear, dry sky) outweighs the turbulent and ground heat gains. The result is a frozen-crust depth, possibly very thin, which is the cold content the sun must spend before melt. A thin crust gives a short corn window; show it anyway, flagged as marginal, so people who want to chase it can. "No refreeze" is the outcome of the balance (crust depth effectively zero), not a pre-filter. The nighttime sky longwave term depends on cloud and humidity, so it gets the same clear-sky / NBM-cloud bounds as the day.
3. Daytime melt: absorbed shortwave (slope-corrected) + longwave in - longwave out + sensible and latent heat (bulk aerodynamic) + ground and rain terms. Melt depth is the cumulative surplus after cold content. Albedo, roughness length, transfer coefficients and the stability correction need literature values **(source)**.
4. Melt-freeze cycle count since the last snowfall, at least 2, shown as a warning label.

### Forcing

NBM through Herbie (shared with the ski tool). Needs temperature, wind, dewpoint or RH, cloud cover; NBM likely has no radiation, so compute it **(verify in `docs/nbm_fields.md` and the GRIB inventory)**. Later: HRRR/HRDPS for the first 48 h. Some SNOTEL and NWAC stations report shortwave radiation, but rarely and noisily (Danny, Oct 2026). Use them as a sanity check on the clear-sky engine and cloud scaling, with quality filtering, not as a calibration target; list which stations have it **(verify)**. Start archiving forcing and SNOTEL observations this winter so a replay set exists by spring.

### Validation log (Danny's good-corn days)

| Date | Time | Place / aspect |
|---|---|---|
| 2022-01-17 | 12:30 | Mt. St. Helens, Worm Flows |
| 2023-03-22 | ~11:30 | Mt. St. Helens, Worm Flows |
| 2023-06-10 | ~11:30 | Mt. Adams, Southwest Chutes |
| 2024-04-14 | ~13:00 | Crystal Mountain, northwest routes |
| 2024-06-29 | ~13:00 | Mt. Baker, Coleman-Deming |
| 2025-06-15 | 12:00 | Mt. Baker, Coleman-Deming, W/SW aspect |
| 2026-01-24 | ~13:00 | Lundin Peak, S-facing, near Snoqualmie Pass |
| 2026-02-28 | ~12:00 | Muir Snowfield, Mt. Rainier, S-facing |

Elevations: Danny says all of the good days were between 5,000 and 7,000 ft (no per-day value recorded).

Bad days (negatives; Danny avoids skiing when he expects bad corn, so there are few):

| Date | Place | Why it was bad |
|---|---|---|
| 2026-01-31 | Paradise area | too much recent snow (fails the recent-snow gate) |
| 2026-01-17 | Paradise area | way too warm |
| 2026-02-05 | Mt. Baker ski resort | thick ice crust, very warm after big rain (rain gate / rain-on-snow crust) |

The negatives test different parts of the model: Jan 31 the recent-snow gate, Feb 5 the rain gate and the hard-crust case (a very warm night should not read as corn), Jan 17 the energy balance itself, since warm air plus a weak refreeze should give no or negligible corn. The negatives were bad all day, so score them as no corn at any time of day, on any aspect there. Gaps to fill with Danny: elevation and aspect where missing. Pair each entry with the nearest SNOTEL station **(source)**. Note the eight positives are fewer than the model has parameters worth tuning, so use them mainly to check qualitative behavior (timing, aspect order, gates), not to fit.

### Build order

1. Measure area and size above 4000/5000/6000 ft; pick resolution.
2. Static terrain layers and class table.
3. Clear-sky engine; check against `pvlib` on flat ground and any radiation station.
4. Energy balance on synthetic forcing, then observed forcing on the validation days.
5. NBM forcing, scheduled Action writing the class JSON.
6. Class raster and `tools/corn-model.html`.

## Constraints

- Stays static and hosted on GitHub Pages — any new "backend" work has to be either (a) a scheduled GitHub Action that writes data/HTML the static site reads, or (b) client-side compute (like the Pyodide/MetPy Skew-T approach).
- Existing URLs must not break (SEO, sitemap) — this held throughout the Jekyll migration via `permalink` config; new tools get new URLs, nothing existing gets renamed without a redirect plan.
- Never fabricate forecast numbers, model output, or observations — always cite the data source.
- Large binary assets (looper frames, DEM data for the corn model, etc.) need to stay reasonable for a GitHub-hosted static site; watch repo size as new tools land.

## Non-goals

- Not building a server/database-backed app — everything stays static + client-side or scheduled-Action-generated.
- Not converting old forecast posts to Markdown (decided during the Jekyll migration — HTML content stays as-is).
- Not attempting real-time/sub-hourly data for anything — cadences above (daily, twice-daily, per-model-run) are the ceiling.
- Not building the full PNA/MJO/ENSO correlation analysis up front — ships first as a straightforward display of NOAA CPC's existing products; the custom "which MJO phases mean good local snow" analysis is Danny's own work, layered in once it exists.
- Not committing to the UW WRF tool or the merch provider until the open questions below are resolved.

## Phases

1. **Quick wins** — newsletter signup (Mailchimp embed wiring), merch page, mobile image click-through/lightbox.
2. **Radiosonde / Skew-T tool** — Pyodide+MetPy client-side approach, 4 stations (Quillayute, Salem, Spokane, Port Hardy).
3. **SNOTEL data pipeline** — shared infrastructure feeding both the evaluation-page rework (Monday mornings) and the homepage normals bar plots (daily); new scheduled GitHub Action, same pattern as the existing bots (`synoptic.yml` etc.).
4. **CW3E/UW presentation revamp + flags** — play/pause carousel, timezone fix, station map, DGZ/east-flow/inversion/AR flags.
5. **Climate outlook + teleconnections page** — CPC PNA/MJO/ENSO + ensemble outlook toggles, starting with NOAA's own charts.
6. **UW WRF feasibility spike** — short, timeboxed investigation into whether the ensemble plumes page is scrapeable before committing to building against it.
7. **Ski-area recommendation tool** — capstone; composes the avalanche flag, closure risk, drive time, and its own NBM/Herbie forecast pipeline (it does not depend on the CW3E/UW work in phases 4-6). Start with its Phase 0 NBM spike early, since the DEM and NBM extraction code is shared with the corn model. See "Ski-area recommendation tool: design".
8. **Corn model** — physics/validation work can happen through winter, but real-world testing needs actual corn conditions, so target a March launch rather than racing it now.

## Open questions

- UW WRF ensemble page: is `plumes.html` actually scrapeable, or does it need a different access path? (Phase 6 spike will answer this.)
- Merch provider: which print-on-demand service — Printful, Bonfire, Threadless, something else? Needs a quick comparison of cost/quality/ease of logo upload.
- Corn model: build the energy-balance model from scratch, or adapt an existing open-source snow-metamorphosis model (e.g. a simplified SNOWPACK)? Depends on what forcing data (HRRR/RRFS/HRDPS/NBM) turns out to be accessible.
- Ski-recommendation tool: criterion thresholds (powder, corn, "Cascade concrete", visibility, wind) are placeholders to tune with Danny; the structure and open questions are in "Ski-area recommendation tool: design" above.
- Radiosonde PW (precipitable water) estimate: worth scoping once the base Skew-T tool is working — may just be a derived MetPy calculation from the same sounding data.

## Reference links

Sounding page example (Skew-T rendering approach to reuse):
- https://github.com/clinton-alden/clinton-alden.github.io/blob/main/radiosonde.html
- Confirmed technique: MetPy running client-side via Pyodide, sounding data from IEM's RAOB JSON API (`mesonet.agron.iastate.edu/json/raob.py?ts=...&station=...`). Only need soundings for Quillayute, Salem, Spokane, Port Hardy for now; may add more later.

UW WRF ensemble output:
- https://a.atmos.washington.edu/wrfrt/ensembles/plumes.html

Scripts for HRRR data acquisition and sounding data (reference implementation):
- https://github.com/clinton-alden/clinton-alden.github.io/tree/main/scripts

NBM viewer and data downloader:
- https://apps.gsl.noaa.gov/nbmviewer/?col=2&hgt=1&obs=false&fontsize=1&location=Downtown+Seattle&selectedgroup=Default&darkmode=on&graph=fa-chart-bar&probfield=Tmax&proboperator=%3E%3D&probvalue=40&colorfriendly=false&whiskers=false&boxes=true&median=false&det=true&tz=local
- See `docs/plan-images/NBM-viewer.png` for a screenshot.

Ski-recommendation tool data sources:
- Avalanche.org public API (NWAC zones): https://api.avalanche.org/v2/public/products/map-layer/NWAC and https://github.com/NationalAvalancheCenter/Avalanche.org-Public-API-Docs
- Avalanche Canada products API: https://docs.avalanche.ca/
- WSDOT Traveler Information API (mountain passes): https://wsdot.wa.gov/traffic/api/
- NBM on AWS: https://registry.opendata.aws/noaa-nbm/ and Herbie NBM docs: https://herbie.readthedocs.io/en/stable/gallery/noaa_models/nbm.html
- Nordic grooming: https://www.kongsbergers.org/GroomingReport, https://parks.wa.gov/find-sno-parks/hyak-sno-park, https://parks.wa.gov/find-sno-parks/crystal-springs-sno-park, https://methowtrails.org/conditions

West WRF figures from CW3E:
- https://cw3e.ucsd.edu/west-wrf_ensemble_meteograms?station=US2

CW3E freezing level and precipitation maps:
- https://cw3e.ucsd.edu/DSMaps/DS_freezing.html

NOAA CPC teleconnection/outlook products (for the climate outlook + teleconnections page):
- PNA ensemble: https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna_index_ensm.shtml
- MJO: https://www.cpc.ncep.noaa.gov/products/precip/CWlink/MJO/mjo.shtml
- ENSO: https://www.cpc.ncep.noaa.gov/products/precip/CWlink/MJO/enso.shtml

### Corn regions status (Oct 14 2026)

`data/corn/regions.yml` has 13 forcing regions: 12 ski zones (North Bend dropped as lowland, Whistler left out for now) plus Glacier Peak (48.077 N, -121.10 W). `scripts/corn_region_raster.py` assigns each cell of the Cascades raster to the nearest region point (first rule, to revisit): 0.24 MB PNG, regions claim 2.5% (Stevens) to 17.4% (White Pass, which also covers Mt. Adams) of the box. Hurricane Ridge is in the Olympics, outside the Cascades box, so it only claims eastern Puget Sound cells; the Olympics need their own class raster.

### Surface energy balance: what we take from SNOWPACK (Oct 14 2026)

Source: `Source/snowpack/snowpack/` in github.com/snowpack-model/snowpack (master), read Oct 14 2026: `Snowpack.cc` (`updateBoundHeatFluxes`, `neumannBoundaryConditions`, `getParameterizedAlbedo`), `Laws_sn.cc` (`compSensibleHeatCoefficient`, `compLatentHeat_Rh`, `compLWRadCoefficient`, `parameterizedSnowAlbedo`), `Meteo.cc` (`MicroMet`, `MOStability`, `RichardsonStability`), `Constants.h`, and MeteoIO `Atmosphere.cc` (`Brutsaert_emissivity`, `Konzelmann_emissivity`, `vaporSaturationPressure`). The tree is C++ with config-file defaults, so roughness length and the albedo choice are not in the code and must come from the SNOWPACK docs or ini defaults **(source, not yet read)**.

Structure to copy (the surface boundary condition for the top snow element):
- Sensible: `qs = rho_air * cp_air * C_h * (Tair - Tsurf)`, with `C_h = karman * u* / max(0.7, ln(z / z0) - psi_s)`; u* and psi from an iterated Monin-Obukhov loop (stable-side options include Holtslag-De Bruin, Stearns-Weidner; Paulson on the unstable side; a log-linear Richardson-number option is the simplest).
- Latent: `ql = beta * (e_air - e_surface)`, `beta = C_h * 0.622 * Ls / (R_air * Tair)`, surface saturated (ice below 0 C, water at melt), `e_air = RH * e_sat(Tair)`, `e_sat` a Magnus-type form over ice or water.
- Longwave: `lw_net = eps_snow * ea * sigma * Tair^4 - eps_snow * sigma * Tsurf^4`; the incoming term is treated as a convective-like term that linearizes in Tsurf so the solve is implicit. Clear-sky `ea`: Brutsaert (1.24 (e_mb/T)^(1/7)); cloud adjusted: Konzelmann (clear 0.23 + 0.484 (e/T)^(1/8), overcast 0.952, weight cloudiness^4).
- Rain: `qr = rain_rate * c_water * (max(Tair, 0 C) - Tsurf)`.
- Shortwave: absorbed = (1 - albedo) * iswr (our clear-sky engine, scaled for cloud); SNOWPACK's albedo is a regression on snow properties and weather, which we cannot supply, so albedo needs a simpler rule **(source)**.
- Constants (`Constants.h`): sigma 5.67051e-8, emissivity of snow 0.98, karman 0.4, rho_air 1.1 (we should compute from pressure), cp_air 1004.67, Ls 2.838e6, Lv 2.504e6, Lf 3.34e5, c_water 4190, c_ice 2100, k_ice 2.2, rho_ice 917.
- Iteration: SNOWPACK solves the temperature profile implicitly (finite elements) with a semi-explicit branch once liquid water and ice coexist at the surface (fluxes clamped at +-350 and +-250 W/m2 sensible/latent there). We do not need the whole profile: the top ~10 cm in a few layers, solving the surface balance for Tsurf each half hour, with melt when Tsurf would exceed 0 C.

### Parameters from Danny and first energy-balance run (Oct 14 2026)

- **Albedo:** constant decay with age since the last snowfall, from 0.95 (fresh) to a floor of 0.3 (very dirty snow; realistic floor 0.45-0.6). The decay rate is **not given**; `ALBEDO_DECAY_PER_DAY = 0.02` in `scripts/corn_energy.py` is a placeholder **(source)**.
- **Roughness length:** 0.25 mm (fresh) rising to 25 mm (old snow, sun cups), log-interpolated over `ROUGH_FULL_DAYS` (placeholder 30 days) **(source)**.
- **Constants:** conductivity of ice 2.2 W/m/K; diffusion coefficient in air 22e-6 and in snow (called "ice" in the message) 85e-6 m2/s, as in SNOWPACK's Constants.h. They enter SNOWPACK's microstructure-based snow conductivity (grain and bond radii we do not have), so they are recorded but not used yet. The engine uses a density-based conductivity from memory (Calonne et al. 2011 fit, **verify**).
- **Radiation stations (Synoptic):** Alpental summit ALP55, Mt. Baker Pan Dome MTB50, Stevens Pass Tye Mill STS54 have shortwave. Danny: it breaks often in the mountains (rime, snow on the sensor, tilt), so filter hard: only compare to the clear-sky engine on clear days, reject anything above the clear-sky value or at night, check against a plausible clearness index, and prefer midday medians. Not yet pulled.
- **First run** (`python scripts/corn_energy.py --synthetic`, made-up forcing, 30 deg south slope near Paradise latitude, Mar 21-22, clear, RH 40%, 2 m/s wind): with air at +2 C overnight the top 10 cm refroze to about -8 C at the surface and the whole 10 cm layer was frozen by 05:00; by 11:00 the next day 9 cm was thawed. The overnight result is driven by longwave loss (-47 to -50 W/m2) against sensible gain (+15-18 W/m2) and is sensitive to the stable-boundary-layer coupling (`ZETA_MAX = 1`, a placeholder). SNOWPACK's own Richardson option shuts turbulent exchange off completely in this case, and its default stable function does not return to zero in neutral conditions as I read it, so I used its log-linear option. The 10 cm column is fully frozen by morning, so a deeper column (about 30 cm) is needed to measure crust depth.

**Update, same day (Danny):** albedo and roughness both follow a power-law form with age since the last snowfall, albedo dropping most of the way in about a week; roughness depends on conditions (so its time scale is the weakest placeholder). In `scripts/corn_energy.py`: albedo = 0.3 + 0.65 (1 + age/2 d)^-1 (0.41 at 10 days; the 2-day scale and exponent 1 are placeholders chosen to drop most of the way in a week), z0 = 25 mm - 24.75 mm (1 + age/14 d)^-1 (placeholder). Column is now 30 cm. Stability cap (`ZETA_MAX = 1`) accepted. Synthetic re-run (10-day-old snow, albedo 0.41): the air +2 C night freezes 11 cm by 05:00 and the crust is gone by 11:00; at -10 to 0 C the crust is 15-18 cm and is still there at 08:00. Next: tighten the corn-depth metric to the contiguous wet depth from the surface once the crust is gone (the current thawed count includes wet snow under a crust), then pull ALP55, MTB50, STS54 shortwave and run the eight good and three bad days.

### Radiation station check (Oct 15 2026)

Pulled Jan-Jun 2026 hourly shortwave for ALP55, MTB50, STS54 (`scripts/corn_radiation_obs.py fetch|check|bias`; data in `data/corn/radiation/`, git-ignored). Against the clear-sky engine (Ineichen, station elevation, flat surface):
- **Stevens Tye Mill (STS54)** is the usable one. On clear steady days the clearness index (measured over clear-sky) is 0.89-0.97 (median 0.96 in Mar-Jun, 0.89 in January; 1-5 clear days a month), so the engine reads about 4-6% high there in spring, more in January (low sun, small sample).
- **Alpental (ALP55) and Baker Pan Dome (MTB50)** often read well above the clear-sky value: the daily-maximum hourly index has a median of 1.04-1.20 in Apr-Jun, a 75th percentile of 1.3 and maxima of 1.4-1.8. Cloud-edge enhancement and bright surrounding snow explain a few percent, not 30-80%, so a sensor tilt, calibration or placement problem is likely. Do not use them to tune the engine; they pass the 1.05 screen only a minority of the time.
- Feb 28 2026 (Muir day): ALP55 0.90 and STS54 0.89, consistent with clear skies; MTB50 0.28 (cloud or a covered sensor).

### Terrain-reflected shortwave (raised by Danny, Oct 15 2026)

What the engine has now: a single ground-reflected term that treats everything below a slope as an infinite, flat, fully sunlit plane of albedo 0.6 (placeholder), and sky diffuse that sees the whole sky. Sizes from `corn_clearsky.py` (Paradise latitude, 1900 m, clear): on a 30 deg south slope the reflected term is 2-4% of the daily total (Feb 28, Apr 14); on a 30 deg north slope 19-24% in late February (0.6-0.8 MJ/m2 of a 3 MJ/m2 total) and 7-9% in mid-April; on a 40 deg north slope 57-64% in late February (but a very small total) and 15-20% in mid-April. So it matters most on shaded aspects in late winter, which is exactly where corn is marginal.

What it is missing: in real terrain the surfaces a slope sees are other slopes. A north face in a bowl sees a sunlit south face across the valley, which can deliver more than the infinite-plane term, and a sheltered site also loses sky diffuse (sky-view factor) and direct sun to horizon blocking. Plan, in order: (1) from the DEM compute per class the sky-view factor, the terrain configuration factor (share of the hemisphere filled by terrain) and the horizon profile (16-36 azimuths) over the 30 m grid; (2) reduce sky diffuse by the sky-view factor and block direct sun below the horizon; (3) reflected = terrain factor x surrounding albedo x the shortwave the surrounding terrain receives, first as the flat-ground value as a bound, then iterating once or twice with the neighbors' own class irradiance (a radiosity pass) to see how much it changes; (4) test the sign and size against STS54, which reads about 4-6% under the flat engine on clear days, and against the Alpental and Baker readings that exceed clear-sky (their sensors may be seeing exactly this, but a sensor 30-80% over clear-sky is still more than terrain reflection should add on a horizontal surface). The surrounding albedo should follow the same age-decay as the snow (0.8-0.9 fresh, about 0.4-0.5 after a week), not a constant 0.6.

**Terrain step built (Oct 15 2026).** `scripts/corn_terrain_shading.py` (numba; 20 km rays, 16 azimuths, every 4th 30 m cell above 4000 ft) writes `data/corn/class_terrain_<box>.csv`: per class the sky-view factor, the share of the sky the tilted surface sees (vd), the terrain configuration factor (ct) and the mean horizon in 16 directions. `scripts/corn_class_raster.py` now takes `--box cascades|olympics` and caches each DEM in `data/corn/cache/` (git-ignored). Boxes: Cascades as before; **Olympics -123.8 to -122.9 W, 47.3 to 48.1 N**, centered on The Brothers (47.654 N, 123.141 W) and including Hurricane Ridge (adjustable; 1.85 M forecastable cells). Results over the Cascades above 4000 ft (1.8 M sampled cells, 509 classes): mean sky-view 0.90, ct 0.045. By slope bin, sky-view falls from 0.97 (flat) to 0.83 (35-45 deg) and ct rises from 0.023 to 0.062; north-facing classes see about 0.060 terrain, south-facing 0.040. `corn_clearsky.tilted_terrain()` applies it: horizon-blocked direct sun, sky diffuse scaled by vd, reflected = ct x surrounding albedo x flat-ground global (an upper bound). Effect on a typical class at Paradise latitude: on north faces the horizon and sky-view losses outweigh the reflected gain (30 deg N, Feb 28: 3.1 -> 1.5 MJ/m2; 40 deg N, Apr 14: 11.5 -> 8.6); on south faces the change is 1-5%. Class-mean horizons blur bowls and ridges together, so the deep-bowl case is understated. Also fixed: `tilted()` previously reported ground-reflected light inside its `diffuse` column; `diffuse` is now sky diffuse only, with `reflected` separate (totals unchanged).

### First good/bad day test (Oct 15 2026)

`scripts/corn_validate.py` runs the energy balance on a day with observed forcing (Synoptic stations, SNOTEL snow age, terrain-aware clear-sky shortwave scaled by the measured clearness index) and draws the 30 cm snow temperature as a heat map (`docs/corn/<date>_<id>.png`, git-ignored). **Only the five 2026 days could be run: the Synoptic token has no history before about late 2025** (the other six good days, 2022-2025, need a different forcing source such as HRRR archives through Herbie, or ERA5, with the terrain lapse-adjusted). Site elevation, slope and aspect are my assumptions (5,500-6,500 ft, 17.5 or 30 deg, S) since the logs only give a place. Also fixed during this: meltwater draining into cold layers now refreezes (it releases latent heat, warming the layer) and the bottom boundary follows a smoothed air temperature instead of being fixed at 0 C.

| Day | Result | Overnight min air | Overnight min surface | Crust at 06:00 | Surface at 0 C |
|---|---|---|---|---|---|
| 2026-02-28 Muir (good) | thawed 26 cm by 12:00 | -3.4 C | -11.7 C | 15 cm | 09:15 |
| 2026-01-24 Lundin (good) | thawed 9 cm at 13:00, 18 cm by 15:00 | -6.1 C | -14.0 C | 30 cm (all) | 11:15 |
| 2026-01-31 Paradise (bad, new snow) | thawed 9 cm | +2.6 C | -0.9 C | 2 cm | 09:45 |
| 2026-01-17 Paradise (bad, too warm) | 30 cm wet | +4.3 C | -6.0 C | 12 cm | 09:15 |
| 2026-02-05 Baker (bad, rain crust) | 30 cm wet | +10.1 C | -3.6 C | 5 cm | 08:45 |

Reading: the two good days refreeze hard (overnight air -3 to -6 C, crust 15 cm to the whole column) and thaw from late morning; the three bad days have warm nights (air +2.6 to +10 C) and a thin crust (2-5 cm) except Jan 17, where a clear night gives a 12 cm crust at +4.3 C air: the model refreezes where the day was "way too warm" (cloud at night is unknown: it is interpolated from daytime clearness, so a cloudy night would remove the crust; check Jan 17 night cloud against the MU101 and PVW54 radiation and the Paradise webcam/observations). The wet-depth metric does not separate good from bad, because every day thaws the full 30 cm; corn needs a better target (thaw rate, thaw depth timing, or the wet depth at the reported hour against a threshold) and the albedo at 4-6 days (0.49 with the placeholder decay) is probably too low for Muir in February.

**Albedo revision (Danny, Oct 15 2026):** minimum raised to 0.55; the fractional loss per day is 2% with no melt-freeze cycles, rising linearly to 3% at 3 cycles (`ALBEDO_RATE0`, `ALBEDO_RATE_MAX`, `ALBEDO_CYCLES_FULL`; the cycle scale is a placeholder). A cycle is counted when the surface reaches 0 C and then falls below -1 C (`Column.cycles`). The albedo is integrated forward step by step in `corn_validate.py`. Heat-map colors changed to an NWS-style cold ramp (purple, blue, cyan, green at 0 C). First 2026 re-run with the higher albedo: Muir (good) now has a 30 cm crust at 06:00 and thaws only 1 cm by 12:00 and 4 cm by 15:00 (the 2-10 cm target), Paradise Jan 31 (new snow) 0 cm at noon, Baker Feb 5 (warm, rain crust) 30 cm wet, but Lundin Jan 24 (good) never reaches 0 C (dry air, RH about 20%, wind 3-8 m/s from the ridge station Alpental summit, so the latent and sensible losses balance the shortwave; a sheltered south slope probably sees much less wind) and Paradise Jan 17 (too warm) now has a 30 cm crust on a +4.3 C night, which the model gets wrong. HRRR forcing (`scripts/corn_hrrr.py`) is being fetched for the six 2022-2025 good days.

### Shortwave penetration, 0 C lower boundary and all 11 days (Oct 17 2026)

Danny: shortwave penetrates and should be extinct by about 10 cm (check against SNOWPACK); lower boundary 0 C. SNOWPACK (`Laws_sn.cc` `compShortWaveAbsorption`) has a multi-band scheme (five bands, extinction k = 0.059, 0.180, 0.525, 4.75, 85.23, spectral shares 16.3, 16.8, 15.4, 31.0, 20.5 %, fudge factors 29, 15, 5, 9, 35; per band Ks = fb x 0.84 x sqrt(1000 k / (2 rg)) x rho / rho_ice, rg the grain radius in mm) and a single-band one (extinction = rho/10 + 30 per m, about 70/m at 400 kg/m3, e-folding 1.4 cm; 99.9% absorbed by 10 cm). `scripts/corn_energy.py` now uses the multi-band scheme: with rg = 1 mm (placeholder, SNOWPACK reads it from its grain model) the bands e-fold at about 0.6 to 3.4 cm and the top band by 0.04 cm, so essentially nothing is left by 10 cm, consistent with Danny's value. The lower boundary is fixed at 0 C and the starting profile is linear from the mean air temperature (capped at 0 C) to 0 C.

Results on all 11 days (HRRR forcing for 2022-2025, stations for 2026; site slope, aspect and elevation assumed; surface at 0 C is "never" when it stays below):

| Day | Label | Snow age | Overnight min air | Crust 06:00 | Wet depth at report / 15:00 | Verdict |
|---|---|---|---|---|---|---|
| 2022-01-17 St. Helens | good | 4.8 d | +3.6 | 30 | 7 / 12 cm | fits |
| 2023-03-22 St. Helens | good | 2.8 | -4.0 | 30 | 0 / 0 | misses (never thaws) |
| 2023-06-10 Adams | good | 30.8 | +6.0 | 0 | 30 / 30 | too wet (slush, thaw from 06:15) |
| 2024-04-14 Crystal | good | 1.9 | -0.0 | 30 | 0 / 2 | misses |
| 2024-06-29 Baker | good | 14.9 | +5.2 | 1 | 30 / 30 | too wet |
| 2025-06-15 Baker | good | 22.8 | +3.3 | 12 | 30 / 30 | too wet |
| 2026-01-24 Lundin | good | 3.9 | -6.1 | 30 | 0 / 0 | misses |
| 2026-02-28 Muir | good | 4.8 | -3.4 | 30 | 1 / 5 | fits |
| 2026-01-31 Paradise | bad (new snow) | 2.8 | +2.6 | 2 | 0 / 0 | no corn, right answer |
| 2026-01-17 Paradise | bad (warm) | 6.8 | +4.3 | 30 | 2 / 10 | wrong (gives corn on a +4 C night) |
| 2026-02-05 Baker | bad (rain crust) | 8.8 | +10.1 | 5 | 30 / 30 | no corn, but for the wrong reason (no crust physics) |

Pattern: winter and early-spring days are too cold (no thaw: albedo 0.86-0.92 at 2-5 days, net longwave about -50 to -90 W/m2 against about 50-110 W/m2 absorbed), June days are too warm (30 cm wet at the report hour, albedo down to 0.55-0.7, 300-400 W/m2 absorbed). A single fixed albedo-decay rule cannot serve both. Candidate causes, not yet tested: the albedo rule (an older, dirtier or coarse-grained snow surface in spring), the 30 deg slope and aspect guesses, cloud and longwave from HRRR, wind at 10 m versus a sheltered slope, rg = 1 mm, and the missing rain and new-snow processes. The wet-depth metric (liquid at least 0.5% of mass) saturates in June because the 30 cm column sits on a 0 C lower boundary; a thaw-rate or crust-erosion-time measure would be better.

**Lapse rate and spring albedo floor (Danny, Oct 17 2026):** forcing air temperature is now moved to the site elevation with the dry adiabatic rate (9.8 K/km, dew point 1.8 K/km placeholder) instead of 6.5 K/km, and the HRRR longwave is scaled by (T_site/T_model)^4 for the same change. The albedo floor is 0.55 through February, then falls linearly from Mar 1 to 0.45 on Jun 1 (`albedo_floor`; 0.45 and the end date are placeholders). Re-run of the 11 days: the winter misses stay misses (St. Helens 2023-03-22, Crystal 2024-04-14, Lundin: still no 0 C surface), changes were a few tenths of a degree in the overnight minimum; the June days stay too wet. Longwave sources: Synoptic days use the Konzelmann emissivity from air temperature, humidity and a cloud fraction from the radiometer; HRRR days use the model's downward longwave at the nearest 3 km grid point. Wind: Synoptic days use the station anemometer (Paradise Wind PVW54, Alpental summit ALP55, Pan Dome MTB50), HRRR days the model 10 m wind; neither is adjusted for slope sheltering.

**Round 3 changes (Danny, Oct 17 2026):** albedo loss rate raised to 3% a day (fresh) rising to 4% with melt-freeze cycles (placeholders); snow age resets only on a daily snow-depth gain of at least 10 cm (SNOTEL SNWD; where the sensor is missing, a SWE gain of 0.4 in); Baker site moved to 2,400 m (7,874 ft) for both days; optical grain radius grows from 1 to 2 mm as albedo falls from 0.95 to its floor and feeds the shortwave penetration; heat-map shading marks a thawed layer of 2-10 cm from the surface (corn window, ////) and a thawed layer deeper than 10 cm (slush, ....), black line is liquid water of at least 0.5% of mass. Results (wet depth at the reported hour): Muir 4 cm, Lundin 16, St. Helens 2022 15, St. Helens 2023 30, Adams 30, Crystal 30, Baker 2024 30, Baker 2025 30; bad days Paradise Jan 31 0, Paradise Jan 17 4, Baker ski 30. With the 10 cm reset most snow ages are now 12-31 days, albedo sits at its floor on most days, and the model over-thaws instead of under-thawing; a thawed layer forms below a frozen skin because penetrating shortwave warms the subsurface first (surface stays about -1 C). Next: a better corn criterion than the wet-depth threshold, longwave checks (Danny's suspicion), and the albedo rule.

**Correction (Danny, Oct 17 2026):** the snow-age reset uses only SWE gain, or precipitation that fell as snow (daily mean air temperature at or below 33 F), at least 0.4 in of water (about 10 cm of snow at 10:1, a placeholder); never snow depth. Rain does not reset it. The heat map now marks the corn window (surface layer thawed to 2-10 cm) with gold corn-kernel markers only. Re-run (wet depth at report / 15:00): Muir 3 / 11 cm, Lundin 15 / 27, St. Helens 2022 10 / 17, St. Helens 2023 0 / 0, Crystal 9 / 26, Adams, Baker x2 30 / 30; bad days Paradise Jan 31 0 / 9, Paradise Jan 17 3 / 15, Baker ski 30 / 30.

### Longwave comparison and corn-window score (Oct 17 2026)

Scoring (Danny): a good corn day lasts several hours and the window should surround the reported ski time. `corn_validate.py` now reports the corn window (surface layer thawed to 2-10 cm, 06:00-20:00 local) that overlaps the reported time +/- 1 h, its span and duration, and the longest window of the day. Longwave options (`--lw`, `--compare-lw`): Konzelmann (before), Dilley and O'Brien 1998 clear sky with the Unsworth-Monteith cloud blend (MeteoIO `Dilley_ilwr` / `Unsworth_ilwr`; now the default), and HRRR's downward longwave on the HRRR days. Mean incoming longwave night / midday (W/m2) differs by 10-30 between models; for the corn window it changes the span by 0.5 h at most, except Paradise Jan 31 (bad, new snow), where Konzelmann gives a false 3.5 h window and Dilley gives none.

| Day | Label | Konzelmann: window at report | Dilley | HRRR |
|---|---|---|---|---|
| 2026-02-28 Muir | good | 3.5 h (11:15-14:15) | 4.0 h (11:15-14:45) | n/a |
| 2022-01-17 St. Helens | good | 2.5 h | 3.0 h | 2.5 h |
| 2024-04-14 Crystal | good | 2.5 h | 2.5 h | 2.0 h |
| 2026-01-24 Lundin | good | none | none | n/a |
| 2023-03-22 St. Helens | good | none | none | none |
| 2023-06-10 Adams | good | none (slush) | none | none |
| 2024-06-29, 2025-06-15 Baker | good | none (slush) | none | none |
| 2026-01-31 Paradise | bad | 3.5 h (false) | none | n/a |
| 2026-01-17 Paradise | bad | 2.5 h (false) | 3.0 h (false) | n/a |
| 2026-02-05 Baker ski | bad | none | none | n/a |

So the longwave choice is not the main lever. Three good days hit, five do not (two never thaw to 2 cm in a usable window, three saturate the 30 cm column in June), one bad day is a false positive on any model.

**Frozen-skin tolerance and the Baker 2026 and Lundin days (Danny, Oct 17 2026):** a surface layer below 0 C over a thawed layer is not counted as frozen: the corn depth starts at the first wet layer if it is layer 0 or 1 (`wet_run`). Re-run with Dilley longwave: corn window at the report hour, Muir 4.0 h (11:15-14:45), St. Helens 2022 3.0 h, St. Helens 2023 4.0 h (12:15-15:45, now a hit; the reported time is 11:30, so it is a late start), Crystal 2.5 h, Lundin none (longest 1.5 h, not at the report time), Adams and both Baker June days none (slush or too brief); bad days Paradise Jan 31 none (right), Paradise Jan 17 3.0 h (false), Baker ski none (right). Baker ski area Feb 5 2026 (Pan Dome 5,020 ft): air 10-12 C overnight and 15-16 C by midday, RH 5-10% at midday, wind 1-6 m/s (3.5-4.4 m/s from 10:00 to 14:00), shortwave 290-460 W/m2; SNOTEL Wells Creek and MF Nooksack show no precipitation on Feb 4-5 and settling snow depth, so the rain came earlier and the crust is a refrozen rain layer the column cannot represent (it has no ice layer, a uniform 400 kg/m3). Lundin Jan 24: very strong valley inversion on the clear morning (Alpental summit 5,470 ft at -0.7 C at 06:00 and +0.2 C at 09:00 against -8.1 and -9.5 C at Alpental base 3,100 ft, 8-10 C); the Lundin run uses the Alpental summit station directly, not HRRR, so it is not affected by an HRRR inversion error.

**Refrozen-crust mechanism and relabeling (Danny, Oct 17 2026):** each layer now has its own mass, so its density follows from it (`Column.rho`), conductivity and shortwave extinction are per layer, and water that drains into a colder layer refreezes there and adds ice mass up to 800 kg/m3 (`RHO_CRUST_MAX`; Danny: refrozen rain crust 700-800). Rain comes from SNOTEL daily precipitation gains of at least 0.2 in on days with mean air temperature above 33 F, spread over the local day and put into the top layer as liquid (`RAIN_MIN_IN`); the Baker ski run starts 10 days back to include the Jan 28 to Feb 2 rain (56 kg/m2 at Wells Creek). Source layers keep their mass when they drain (the surface does not lower); a mass-conserving version was tried and abandoned because melted layers lost ice and became unphysically light (100 kg/m3) and warmed too fast. Result: no crust forms in the Baker 2026 run, because the pack is already isothermal at 0 C when the rain falls and the surface barely goes below 0 C afterwards, so the modeled column stays wet and cold-free from Jan 30 and the corn window on Feb 5 is none (right answer, still not the observed hard crust). The 2026-01-17 Paradise day is relabeled unlabeled: Danny did not ski it and fresh snow may have given proto-corn (corn feel from newer snow that turns to sticky mush quickly), which the model does not represent, so it is excluded from false-positive counts (the model gives a 3.0 h window there). Lundin (strong clear sun on a south slope, Danny): slope 30, 35 or 40 degrees makes little difference (absorbed shortwave 340-380 W/m2 at midday); the corn window is still absent.

**Ice-crust representation (Oct 19 2026):** the heat map hatches (brown) every layer with density of at least 600 kg/m3, and a top layer that dense is never counted as corn (`CRUST_RHO`), even at 0 C with liquid. A run can also take an observed crust put in by hand (`day["crust"] = dict(when, depth_cm, rho)`), which is a way to test a crust the weather forcing cannot make. Test on Baker Feb 5 2026 (assumed 3 or 6 cm at 750 kg/m3 from Feb 3 06:00, not a measured value): the dense layer persists all day but warms to 0 C by 09:00 under 15-16 C air and strong sun, so thermally it behaves like wet snow; the corn window is none either way. Danny's view: the Baker period is probably a forcing and longwave problem the energy balance cannot get right; HRRR for Feb 5 2026 has not been pulled to compare. SNOTEL requests now retry and are cached.

**Wet-snow compaction and crust building (Oct 19 2026):** SNOWPACK's settling is viscous creep under overburden plus a sintering term (`Snowpack::compSnowCreep`); its Kojima option is eta = 8.64e6 exp(0.021 rho) Pa s (3.8e10 at 400 kg/m3), which compacts the top 30 cm by only about 4e-5 per day, and its default viscosity needs grain neck and sphericity data we do not carry. In SNOWPACK melt-freeze crusts come from percolating water, not creep. The column therefore uses an empirical wet-snow densification (`Column.densify`, all placeholders for Danny to tune against observed crusts): a layer that holds liquid water (at least 0.5% of mass) densifies with a 24 h time scale toward 550 kg/m3 plus 100 per completed melt-freeze cycle of that layer, capped at 800. A dense top layer (600 kg/m3 or more) that is not thawed counts as an ice crust, not corn. Result: crusts now build on days with several cycles; maximum density by day: Muir 475, St. Helens 2022/2023 515/462, Lundin 679, Crystal 626, Adams 646, Baker 2024/2025 750/765, Baker ski 800. Corn window at the report hour: Muir 4.5 h (11:15-15:15), Lundin 2.5 h (11:15-13:15, now a hit), St. Helens 2022 3.0 h, St. Helens 2023 4.5 h, Crystal 3.0 h; misses: Adams, Baker 2024, Baker 2025 (2.0 h longest, not at the report time); bad days: Paradise Jan 31 none, Baker ski none at the report; Paradise Jan 17 (unlabeled) 5.0 h.

### Variable-thickness column with a skin, oscillating density (Oct 19-20 2026)

Danny: the column needs a thin skin layer; crusts should freeze and melt with the cycle; treat it like frozen ground (pores fill with ice at night, melt and drain by day, density oscillating and building); melt looks instant while freezing takes all night; cap the colorbar at 0 to -5 C. Changes in `scripts/corn_energy.py` (`Column` rewritten) and `corn_validate.py`: (1) a 0.5 cm skin layer, a second 0.5 cm layer, then 1 cm layers to 30 cm, with variable thickness and mass conserved; thin layers are merged, a thick top layer is split to keep the skin, and new snow comes in at the bottom to keep 30 cm. (2) Water that drains from a layer lowers its mass and density (down to a 300 kg/m3 floor, below which the matrix collapses); water that refreezes in a colder layer fills pores and raises density (to 800); a layer cannot exceed 950 kg/m3 bulk density with liquid. Wet layers also compact toward 550 kg/m3 plus 100 per completed layer cycle (24 h time scale, placeholders). (3) The residual water content is SNOWPACK's (Coleou and Lesaffre 1998, `snowResidualWaterContent`: about 0.039 by volume at 400 kg/m3, limited to 0.08) instead of a flat 7% by mass. (4) Explicit conduction uses adaptive substeps (stability limit, 5-12 s with the skin); the surface balance uses the exchange coefficients from the previous substep and a root solve. (5) The heat map reads the column on a 0.5 cm grid and the colorbar is 0 to -5 C.

Why melt looks sudden and freezing slow (checked, it is the energy balance): shortwave penetrates and heats the top layers volumetrically while the cold escapes only at the surface; a 1 cm layer at 450 kg/m3 holds about 4.5 kg/m2 and needs only about 28 kJ/m2 to warm from -3 C to 0 C, then about 130 kJ/m2 to hold its residual water (0.39 kg/m2) which has to refreeze before it can cool again; at a net surface loss of 50 W/m2 each cm takes about 40 minutes to refreeze, 10 cm about 7 hours. So thaw is fast when the sun is on and refreezing is slow overnight, as the plot shows. Results (corn window at the report hour): Muir 5.0 h (11:45-16:15), St. Helens 2022 5.0 h (10:45-15:15), Crystal 2.5 h, Lundin 1.0 h (12:15-12:45, marginal), St. Helens 2023 none (a hit before the new column), Adams and Baker 2024/2025 none; bad days Paradise Jan 31 none and Baker ski none (right); unlabeled Paradise Jan 17 4.0 h. Crusts of 600 kg/m3 or more exist on the rain days (Baker ski, Paradise Jan 31).

**Surface = skin layer (Danny, Oct 20 2026):** the separate surface-temperature solve (balance against conduction from the skin center) left the surface 0.3-1 C below a 0 C pack, because shortwave is absorbed inside the snow and the skin loses longwave and turbulent heat. Now the 0.5 cm skin layer is the surface: its temperature is the surface temperature and the net surface flux goes into it (removes the root solve). Corn window at the report hour: Muir 4.5 h (11:45-15:45), St. Helens 2022 4.0 h, Crystal 3.0 h, Lundin none (1.0 h before), St. Helens 2023 none, Adams and both Baker June days none; bad days none; unlabeled Paradise Jan 17 4.5 h. Candidate simplifications Danny may want: drop the per-layer cycle densification (target 550 + 100 per cycle) and rely on the mass-conserving melt and refreeze; use a fixed grid with a skin instead of merging and splitting layers.
