# Plan archive

Finished work moved out of `PLAN.md` so the plan only lists what is still open. Nothing here is current guidance; for how things work now read `CLAUDE.md`.

## Completed Nov 6 2026

- **Scheduling:** GitHub was dropping or delaying the hourly crons (observations landed every 5 to 9 hours). `observations.yml`, `update_satellite_loop.yml` and `uw_soundings.yml` are now also triggered from cron-job.org through `workflow_dispatch`; the GitHub schedules stay as a backup.
- **Area pages:** a page for each of the nine areas plus Mt. Hood (`tools/<slug>.html`, layout `_layouts/area.html`, data in `_data/area_pages.yml`), an "Areas We Cover" menu and the `areas.html` hub. Each shows the snowfall and precipitation plumes, NBM cloud cover and the point-forecast meteogram for that site. The old redirect stubs were replaced.
- **Live plume data:** `scripts/plume_live.py` writes `assets/data/plume_live.json` in `model_data.yml`; the same chart code serves the posts and the pages (`CMWPlume.chartSvg`, `CMWCloud.chartSvg`).
- **Precipitation tools page:** "Model plume (snow)" and "Model plume (precip)" products replaced the old NBM snow (6 h) product.
- **Home meteogram:** a Total column in the precipitation rows (sum over the window shown, `*` where a model covers only part of it).
- **Page structure:** one set of width, padding, gap, radius and shadow values in `style.css` `:root`; posts, outlook cards, the meteogram card and the area pages use them. Titles scale with the screen; the tagline is hidden on phones outside the home page; the post header no longer overflows.
- **Teleconnections:** intro text, "(El Nino, ENSO, PNA, MJO)" under the title and the menu item, jump links as questions, MJO origin text, stacked tool layout with question headings.
- **Search:** post `<title>` is the post's `seo_title` or "Washington Cascades Weekend Ski Forecast: <period>"; indexing requested for the new URLs; the Nov 5 post requested.
- **Live conditions:** the map popup now charts the last 48 hours of SWE change and precipitation accumulation on one axis, to see how the two signals interact (SNOTEL was already fetched hourly; the history was not kept). Snow depth change was dropped: SNOTEL depth is whole inches, so hourly steps are mostly rounding.
- **Small:** CMW logo beside Evaluation in the menu; `.git_token` added to `.gitignore`.

## Old "Done" list (moved from PLAN.md, Nov 6 2026)

5. I want to build a radiosonde tool to visualize the radiosonde data from certain sites that is collected each day and be able to incorporate that information into forecast creation and later evaluation (mostly for freezing level and dendritic growth zone stuff). I want to also include precipitatble water in here, if I can estimate that data. This will update twice daily for the morning and afternoon soundings. Can also build upon request as a script.
8. I want to run some additional analyses myself for some "reading the tea leaves" ideas. That is I want pages to look at the states of the Pacific North American climate teleconnection, the Madden-Julian Oscialltion and the status of the ENSO state. I want to run a rudimentary analysis on the phases of the MJO that locally have corresponded to good conditions for snow (e.g. cold and wet). This will update weekly, but I will need to work through the analysis myself to build the background. We will do this later. Under consturction for now.
1. The primary tool I want to develop is one that allows a site visitor to select several options to create a recommendation for where they should ski. This should essentially be a simple ML model, or something like a decision tree, to recommend the ski area of choice. The options I want the user to be able to balance are: Drive time (up to 5 hours), precipitation chances,snow quality (powder/fresh/corn/cascade concrete/I don't care), temperature (do you want it to be warm or are you okay with it being cold?), visibility (are you okay with clouds and fog? Or do you want bluebird?), driving hazard/difficulty (pass closure risk?), windy/not windy (caveat with uncertainty), elevation range, avalanche danger flag (directly taken from NWAC, DO NOT RECOMMEND during a high danger day ANYWHERE, considerable danger is also bad). We can recommend any of the ski resorts in Washington and souther British Columbia. We will use these as jumping off points for backcountry touring. So that means: Snoqualmie, Stevens, Crystal, White Pass, Mission Ridge, Mazama, Mt. Baker, Whistleyr, Vancouver ski hills,. Also, no recommendation/ a null recommendation can be provided if criterion are not met/something like a huge AR is coming or there are a bunch of pass closures. So essentially we would have somehting like a pass closure risk flag/warning. Then we can provide "what we would do" ski type recommendation  (nordic, downhill, backcountry -- nordic would be okay with slightly different conditions and can recommend any sno-park with a nordic ski area that is groomed), could also update with parking restrictions (need sno-park pass, free parking, ski resort reservation needed, etc. -- would have to research this). We can work through questions for this part of the project.
9. I want a page on climate outlooks, taking estimates from ensembles and the CPC from NOAA that can populate with toggles between product types. This will update on Thursday's alongside the forecast for the longer term outlooks.We can also add this to the reading the tea leaves page (longer term outlooks
    - tools: ECMWF sub seasonal outlooks for precip over NA https://charts.ecmwf.int/opencharts-api/v1/products/extended-anomaly-spread-tp/?base_time=2026-10-06T00%3A00%3A00Z&valid_time=2026-10-26T00%3A00%3A00Z&projection=opencharts_north_america
    - surface temperature https://charts.ecmwf.int/opencharts-api/v1/products/extended-anomaly-range-ratio-t/?base_time=2026-10-06T00%3A00%3A00Z&valid_time=2026-10-19T00%3A00%3A00Z&projection=opencharts_north_america
    - 500 mb heights: https://charts.ecmwf.int/opencharts-api/v1/products/extended-anomaly-z500/?base_time=2026-10-06T00%3A00%3A00Z&valid_time=2026-10-19T00%3A00%3A00Z&projection=opencharts_north_america
    - MJO https://charts.ecmwf.int/opencharts-api/v1/products/mofc_multi_mjo_family_index/?base_time=2026-10-06T00%3A00%3A00Z
    - PNA https://charts.ecmwf.int/opencharts-api/v1/products/seasonal_system5_climagrams_teleconnection/?base_time=2026-10-01T00%3A00%3A00Z&index_type=Pacific+N.Amer+pattern
    - 850mb temp exceedance prob: https://charts.ecmwf.int/opencharts-api/v1/products/seasonal_system5_standard_t850/?base_time=2026-10-01T00%3A00%3A00Z&valid_time=2026-11-01T00%3A00%3A00Z
    - precip exceedance prob:
    https://charts.ecmwf.int/opencharts-api/v1/products/seasonal_system5_standard_rain/?base_time=2026-10-01T00%3A00%3A00Z&valid_time=2026-11-01T00%3A00%3A00Z&area=NAME
    - geopotential 500mb:https://charts.ecmwf.int/opencharts-api/v1/products/seasonal_system5_standard_z500/?base_time=2026-10-01T00%3A00%3A00Z&valid_time=2026-11-01T00%3A00%3A00Z
    - ECMWF forecasted ar activity (has not been updated. can use weeks 2, 3, and 4):  https://cw3e.ucsd.edu/images/S&S/AROccurence/ECCC/ECCC_EP_AR_FCST_Week4.png
    - West Coast Weather Regime Forecast and Impacts from CW3E (starts up in cold season, maybe november 1?)
    - European AR actibit and intensity forecast (can be weeks 2-4): https://cw3e.ucsd.edu/images/S&S/AROccurence/ECCC/barplots/ECCC_BarGraph_ARF_Seattle_Week4.png This one also starts up in november.
    - The CW3E tools will need to be rebuilt once november rolls around, so we should create product tags, but wont run it just yet. 

6. We want to build out the newsletter that will send out the forecast to those who sign up each week. We are setting this up with mail chimp, but just want the sign up to work. This will be done for us using mailchimp, but we will need to prep a forecast for it.
1. For this season, I want to give readers and users a broader range of tools, from custom ones I create (will describe what I want below) that are simple to use and provide quick and easy answers for users, to more nitty gritty and raw data that they can do with what they want. 
2. I want to improve the evaluation page and its methodology. I kind of threw it together, but I want a more robust way to estimate these things. This would mean grabbing the SNOTEL data, cleaning it, and presenting the information in plots and tables more interactively/automatically updating.  This will update on Monday mornings.
3. 4. I want to more simply host older, archived posts with greater efficientc 
4. I want better mobile functionality that makes it easier for a user to click through images that show data I am presenting, whether that is a timeseries of modeled output or satellite data images. 
5.  I want to improve how the CW3E/University of Utah data is presented to the user. I want it to be an easier click through/play/pause set up. And i want a better presentation of the time conversion from UTC to Pacific Standard time. this is currently done in a very clunky and ugly manner. I also want a click/map for these locations so we have an easier time navigating. This will update with each posting, which I think is every 6 hours. 
6.  I want to find a way to access and present UW WRF data. Their page is free and open to the public but I would like to see if we can find a way to grab their data for presentation purposes. This might be possible, we will try. 
7.  We want to make a merchendise page that will link to a simple and clean merch provider. I think there are some low cost/free ones we can try to use, I'll look into that later. Provide some options if there are any. I've seen it where you can upload a logo and the site will process and print and ship all your stuff, so you dont actually have to hold onto inventory and deal with shipping. This should be able to run in the background on its own.
8.  On the main page, I also want to show bar plot comparisons of % normal conditions for accumulated precipitation (for day of year), SWE (for day of year), and temperature anomaly (for prior week [was it colder or warmer than normal], and up temperature anomaly up to that day of the water year) for each ski area we reference. This will update daily. 
9.  I want to turn the "Areas We Cover" into an interactive map with the location and names of ski resorts/forecast areas. On hover, the user should see the location name. On click, the user gets a read out of live conditions and info [elevation, temperature, wind speed (if available), 24 hr prcp.], along with a checklist of recent snowfall or SWE increase (within the last 72 hours), recent precip (same thing), temperature, humidity, visibility flag (if dew point temperature and air temperature are super close together). We will set this up for the following locations and add a box around each location with smaller icons for the specific sites we present: Hurricane ridge  (if we can get NWAC data from synoptic -- otherwise use Waterhole Snotel), Mt Baker - Heather Meadows (can gather Easy Pass, too), Washington Pass (SNOTEL), Mazama (NWAC station, there may be a snotel out there, too now?), Stevens Pass (NWAC stations and snotel. Default to Brooks NWAC station if available), Leavenworth/Icicle Creek (use new Icicle Creek (1338) SNOTEL), Blewett Pass (NWAC or Snotel), Salmon La Sac (use Sasse Ridge SNOTEL), Snoqualmie - East (use Stampede Pass), Snoqualmie West (Ollalie meadows), Alpental (alpental base mid-mountain and summit), Crystal Mountain (use Green Valley NWAC or summit NWAC and Base NWAC, or Morse Lake Snotel if not available), Mt. Rainier - Paradise (use SNOTEL), Mt. St. Helens (Swift Creek SNOTEL), White Pass (White Pass SNOTEL or NWAC), Mt. Adams region (caveat with the fact there are no nearby stations, this is approximate conditions using the Surprise Lakes SNOTEL to the mountain's southwest). For locations with multiple sites, show all available as an ordered list from top to bottom. I think the pop up should be a mini table maybe? if thats possible. Then there should be a link to dive in further for more data on that specific site that currently lies under the precipitation tools sector.
     We should caution certain sites as questionable if: one, the snow depth is currently above 0 (as in right now. for instanvce, brooks chair at stevens pass is at 59 right now, definitely not right), two: snowdepth increases or decreases by more than 36 inches in 24 hours (this is a flag remember, just cautioning that the data may not be trustworthy), or negative. 
- Visual redesign of shared chrome (header/nav/footer, color/type system) now that `_layouts`/`_includes` centralize it (jekyll-migration, landed Sept 2026) — one place to change, not ~35 pages.
- Mobile: lightbox/swipe click-through for figure-heavy pages (forecast posts, model-tools pages, satellite looper) instead of plain inline `<img>` tags.
- Homepage: add daily bar-plot widgets (Phase 3) alongside the existing hero/recent-posts/ski-areas grid.
- CW3E/UW model-tools pages: replace the current static image links with a play/pause carousel (reuse the satellite-looper JS pattern already built for the homepage), fix the UTC→Pacific time display, add a clickable station map.
- Screenshots/sketches: see `docs/plan-images/` (windy_sounding.png, NBM-viewer.png, CW3E_frz-level.png, west-WRF.png, tropical-tidbits-example.png) for the interaction style Danny likes — play/pause sliders, hover tooltips, clickable maps rather than static dropdowns.
- for the drop down carrots, get inspriation from https://nwac.us/

## Point-forecast meteograms and RRFS on the home page (built; the RRFS row is live, Nov 6 2026)

**Point-forecast meteograms on the main page (Oct 8 2026):** a simple meteogram for each point forecast we have, from the NBM, HRRR, ECMWF (only if we can get point data; **verify** what ECMWF open data gives at a point), and HRDPS. Variables: temperature, wind speed, humidity, precipitation. Not downscaled, so the page carries a visible warning that values are model grid cells, not the specific terrain point. Purpose: quick access for people who only want a basic forecast. Shares the Herbie extraction with the ski tool and corn model; one scheduled Action would write a compact JSON per point, and the page draws it client-side.
**RRFS on the main-page meteograms: BUILT Nov 4 2026, awaiting first bot run and a look at the live page** (`scripts/rrfs_ops.py` registers the `rrfs_ops` Herbie template; `meteograms.py` has an `rrfs` row; same 6-hourly `model_data.yml` cadence; steps 1-4 below are done, step 5 is still open). Original notes: a fourth row beside NBM, HRRR and HRDPS. Herbie's built-in `rrfs` template points at the retired prototype bucket `noaa-rrfs-pds` (only 2024 retro runs now), so it cannot fetch current data. Live data is in `noaa-rrfs-ops-pds` (us-east-1, public): `rrfs.YYYYMMDD/HH/rrfs.tHHz.2dfld.3km.fFFF.conus.grib2` with `.idx` files; hourly cycles, 00Z and 06Z run to f084, 03Z only to f018 (check 12Z and 18Z). The messages are the same shape as HRRR (TMP, RH, DPT, UGRD/VGRD at 2/10 m, APCP and ASNOW as `0-N hour acc`). NOAA's notice puts the official production cutover at Nov 3 2026 (`rrfs/prod` on NOMADS), so **verify** the ops bucket is still the right source and the files still carry the same names after the cutover. Steps: (1) a small custom Herbie template (or direct idx byte-range read) for the ops bucket; (2) `rrfs_series` in `scripts/meteograms.py` modeled on `hrrr_series`, plus `rrfs` in `LABELS`, `--models` choices and the cycle picker in `scripts/hires_models.py` (use only the long 00/06/12/18Z cycles); (3) update the "three models" description and sources line in `_includes/meteogram.html`; (4) keep the previous-run fallback if a fetch fails; (5) later and optional: RRFS plumes and evaluation snapshots (no backfill, the ops feed starts about Aug 2026).

## Forecast evaluation rework: decisions (Oct 2026). Built since: evaluation.html is JSON-driven, see CLAUDE.md

## Forecast evaluation rework: decisions (Oct 2026)

Agreed in the Oct 2026 session. Findings behind them are in `docs/nbm_fields.md`.

- **NBM only for now.** Add HRRR and HRDPS later if Herbie makes it easy.
- **Snapshot at forecast time.** `scripts/nbm_snapshot.py` saves `data/forecasts/nbm_snapshot_<first-day>.json` (median with 25th/75th percentiles of snowfall and snow level, temperature corrected to a 5000 ft forecast elevation with a moist adiabatic lapse rate). Needs `data/nbm/sites.yml` and `scripts/site_elevations.py` (one-time).
- **Windows are 12Z to 12Z** (4 am PST, 5 am PDT): a Friday, Saturday and Sunday column plus a cumulative weekend total (Fri 12Z to Mon 12Z). The NBM has no 36 h or 84 h window, so the old "Thursday 4 pm through Monday 4 am" total cannot be reproduced.
- **Table drafts come from the snapshot** (`scripts/draft_forecast_tables.py`); the author edits them. The NBM gives snow level, not freezing level, so the post section is labeled snow level.
- **Old method stays archived** on the evaluation page; the new method starts with the 2026-27 season.
- **Monday evaluation should eventually run itself** as a scheduled Action. The NBM snapshot stays a manual Thursday step until the Herbie extraction is proven in Actions (ecCodes install is still unverified there).
- **Tabled:** a per-forecast time series plot of temperature, snow level and freezing level. The snapshot already holds the series. The same NBM data will feed the ski-area recommendation tool.
- **Evaluation page design (Oct 2026):** the primary unit is the **weekend total**, with a per-day time series for a selected weekend; a hit is the observed **midpoint** inside the forecast range; the page has trackers per product, a product x area heatmap with a map, a weekend-by-weekend bar-and-band plot (observed range as a grey band, products side by side, optional error view and square-root axis), a statistics table with weekend-clustered 90% intervals, big-storm hit/miss tables, and snow-level scatter plots. The prototype lives at `/evaluation-preview.html` (unlisted, noindex), fed by `assets/data/evaluation.json` from `scripts/build_evaluation_json.py`. HRRR and HRDPS plug in as extra fields on each record. They reach only ~48 h, so they get scored on the first days of the weekend.
- **Forecast ranges and observations were fixed (Oct 2026).** The saved `eval_forecast_*.json` files held wrong ranges for several weekends (Dec 4, Jan 29, Mar 26 and others); the evaluation now reads your ranges from the posts (`scripts/ours_from_posts.py`). The observation estimate now ignores trace precipitation (< 0.2 in), rain-on-snow gains while the station is above 35 F, and depth spikes SWE does not confirm. Dry-forecast weekends with false snow fell from 59 to 15 area-weekends. Rescore with `python scripts/backfill_evaluation.py --rescore`.
- **Snow level:** the NBM has no freezing-level field (only `SNOWLVL`). Against sounding data its snow level tracks the measured 0C level (bias -424 ft) far better than the radiosonde tool's melting-model snow level (+1675 ft), so the gap is mostly a definition difference. The page shows both comparisons. HRRR, GFS, HRDPS and ECMWF carry a freezing level and can supply one later.
- **Still to build:** the scoring script (SNOTEL snowfall via AWDB, radiosonde snow level), `assets/data/evaluation.json`, the JSON-driven `evaluation.html`, and a 5-10 day GEFS/ECMWF 500 mb / 850 mb snapshot scored against sondes.

## Storm-type analysis (paused Nov 6 2026; became the Powder Stash Predictor, see CLAUDE.md)

2. Interesting storm signals: September 13 storm for crystal 
**Storm-type analysis (SOM or similar, idea Oct 8 2026):** find the storm orientations that have an outsized effect on particular ski zones. Example: Crystal Mountain is hard to forecast in its outsized events; on Sept 13 2026 (warm season) snow fell at Crystal while nearby Paradise only got rain. Method sketch: (1) from SNOTEL SWE increases, build a storm-total series per zone and compare each storm with what a "normal" storm for that zone gives, using a baseline we define (for example the zone's storm total against regional or cross-zone totals; **decide the anomaly definition**); (2) pull ERA5 reanalysis (500 mb height, 850 mb temperature, moisture transport/IVT, wind direction) for each storm time; (3) cluster the synoptic patterns with a self-organizing map (or k-means/similar if the SOM adds nothing) and compare which nodes line up with positive or negative zone anomalies; (4) read off which 500 mb / 850 mb temperature / moisture-source patterns go with more snow than expected. Open: ERA5 access (Copernicus CDS needs an account/API key; a cloud-hosted ERA5 copy may be easier) **(verify)**; SNOTEL record length per zone; how to separate rain from snow in a SWE increase (the evaluation scripts already filter rain-on-snow, see `scripts/snotel_obs.py`). Analysis is offline work by Danny with help; the outcome feeds storm flags on the site, nothing is built yet.
**Storm-type analysis: decisions (Oct 9 2026).** Window Nov-May, 1991-2026 (the existing SNOTEL panel, `data/teleconnections/results/panel.npz`: daily SWE gain, 36 stations). Zones: the nine forecast areas, each mapped to its SNOTEL stations as in `data/nbm/sites.yml` (`obs:`). **Over-performance event:** a zone's daily SWE gain at least 0.5 in above what that zone usually gets for the amount the other zones got (zone SWE minus the zone's usual ratio times the mean of the other zones), where 0.5 in of water is roughly 4-6 in of snow. A first count on the panel gave about 1,300 days with at least one zone over-performing (95 to 360 zone-days per zone, most of them single-day events); Crystal has 128. Under-performance is symmetrical and can be looked at later. **Gap:** Baker (Wells Creek 909, Easy Pass 998) and Hurricane Ridge (Waterhole 974) are not in the 36-station panel; add them to `scripts/tele_fetch.py` and check their record lengths. **ERA5:** `scripts/era5_fetch.py` downloads z500, t850 and the two IVT components (00/06/12/18Z, 1 degree, 20-65N, 180W-100W) to `data/era5/` (git-ignored); the CDS "daily statistics" datasets refuse a whole cold season, so the hourly datasets are used and averaged to a UTC daily mean. The CDS key needed the new format (no `UID:` prefix, URL `https://cds.climate.copernicus.eu/api`). **SOM size: 3x3 (9 regimes), decided Oct 9 2026.** More nodes would leave too few over-performance days per zone per node (Crystal's 128 days over 12 nodes is about 10 per node); check the 3x3 map's stability across seasons (resample whole seasons and refit) before trusting a node.
**Storm-type analysis: status (Oct 14 2026).** Built and run end to end on the 13 seasons downloaded so far (1992-2004; the ERA5 download is 61 of 144 files, rerun `python scripts/era5_fetch.py --workers 4` in a terminal to finish it, it resumes). `scripts/storm_zones.py` makes the zone table (`data/storms/zone_daily.csv`: nine zones, Baker from Wells Creek 909 and Hurricane Ridge from Waterhole 974, both fetched into the teleconnection cache; 1,978 storm days of 7,429 and 1,582 days with at least one zone over-performing). `scripts/storm_som.py` fits the 3x3 SOM to z500 anomalies on storm days (input: 30-60N, 170-115W, 7 principal components for 90% of the variance), then reports per node and zone the over-performance share against the zone's overall share, with season-resampled 90% ranges, plus a stability check. Dataset check: all four ERA5 fields, no missing times, no NaNs, 1 degree grid, 848 six-hourly times per year file. **First look (13 seasons, not for publication):** the nodes are sensible (ridge and trough patterns; the troughs with the strongest IVT, nodes 6 to 8, come in off the Pacific), but the grouping is only moderately stable (adjusted Rand median 0.35 across season resamples), and with 81 node-by-zone cells at a 90% range about eight false positives are expected, so single starred cells mean little until the full 35 seasons are in and a multiple-testing check is added. **Next:** finish the download; add the multiple-testing check and a leave-seasons-out test of whether a node predicts a zone's over-performance; try 850 hPa wind direction or IVT direction as extra SOM input if z500 alone separates the zones poorly; place Sept 13 2026 (ERA5 preliminary data) on the map.

## Ski tool notes (paused Nov 6 2026)

**Ski tool fixes (Oct 8 2026):** (a) mobile: the page title is overstretched; (b) the snow filter is wrong (Baker shows 7 inches of new snow when it should not); apply the same questionable-data checks the live conditions map uses (snow depth above 0 right now, a depth change over 36 in in 24 h, negative values; see `scripts/collect_live_conditions.py`) to every forecast location and to the recent-snow numbers feeding the ski tool. Find where the 7 inches comes from first (**verify** in `scripts/ski_features.py` and the page).
4. Ski recommendation tool remaining tasks: 
the lowland fallback
NWAC avalanche forecasts (late November)
the drive-time pulls (eight daily runs)
tuning my guessed thresholds
checking its picks against what actually happened

## Ski-area recommendation tool: design

Status: draft from the Oct 2026 planning session. Items marked **(verify)** are unconfirmed and get checked in the Phase 0 spike below.

### Approach

A scoring problem, not a trained model: there are no labels to learn from. **Hard gates** remove a destination outright (avalanche danger, pass closure, major storm). **Weighted soft scoring** ranks the rest: each criterion is normalized to 0-1 and multiplied by the user's slider weight, so every ranking can be explained. The user picks a **mode** first (backcountry, resort, nordic); the mode decides which gates apply and which access points are candidates.

### Destinations

A destination is an **access point** grouped into a **zone**. Forecast, avalanche region, and road dependencies attach to the zone; the tool recommends a zone and lists its access points.

| Access point type | Source | Modes |
|---|---|---|
| Trailhead | Clusters of day-scale start points from the CalTopo "Washington Ski Tours" export, reviewed by hand | backcountry |
| Resort lot | Hand-entered; `parking_url` where the resort has a parking page | resort, backcountry |
| Sno-park | Hand-entered from WA State Parks pages; coordinates and permit info come from there | nordic, backcountry |

- The CalTopo tracks are guidebook-derived (Burgdorfer, Volken, Blair). Use them only to decide where zones go; do not publish the geometry, descriptions, or the guidebook difficulty/avalanche tags.
- A guidebook start is often a summer trailhead. Every zone needs a `winter_access` point (the plowed terminus); drive time is measured to it.
- The CalTopo clustering gives about 11 zones: Snoqualmie, Rainier-Paradise, Stevens, Mt. Baker/Hwy 542, Crystal/Chinook, Hurricane Ridge, Washington Pass, Blewett, White Pass, St. Helens, Leavenworth/Icicle. Whistler, the Vancouver hills, Mission Ridge, and Mazama have no useful tracks and are added by hand.
- Source config lives in `data/ski/destinations.yml` (inside `data/`, already excluded from the Jekyll build). A script merges it with the live features into one `assets/data/ski_features.json`, which the page loads.
- Pass info is a typed field, not a boolean: `pass: {type: sno_park | trail_pass | resort_ticket | none}`. Methow Trails uses its own trail pass, as far as I know **(verify)**.

### Elevation (DEM): one-time script, results stored in the config

No live elevation calls. A script run by hand samples a DEM and writes static values:
- USGS 3DEP (about 10 m) for Washington via `py3dep`/`seamless-3dep`; Copernicus GLO-30 (AWS `copernicus-dem-30m`) for BC **(verify BC tile coverage)**.
- Per access point: elevation. Per zone: `winter_access` elevation, elevation percentiles in a ~1.5 km buffer around the track cluster, and `top`/`vert`. Keep a manual override field.
- Per forecast point: mean DEM elevation inside the 2.5 km NBM cell, used to lapse-rate-correct temperature and wind.
- Commit only the derived numbers. Do not commit rasters (see Constraints on repo size). The same DEM and extraction code is reused by the corn model.

### Forecast pipeline (Herbie + NBM)

- New workflow `.github/workflows/ski_features.yml`, modeled on `radiosonde_history.yml`: `permissions: contents: write`, cron about every 3 h, `pip install` inline, commit only `assets/data/ski_features.json`, then `git pull --rebase origin main` and push.
- Herbie finds the latest NBM cycle (fall back up to a few cycles), fetches only the needed variables via GRIB `.idx` byte ranges, and extracts values at each zone's forecast points. It needs ecCodes/cfgrib: use conda-forge or `apt-get install libeccodes-dev` **(verify which works in Actions)**.
- **Fields already confirmed in the NBM viewer exports in `data/forecasts/*.csv`** (the viewer reads the same NBM data): `SNOWLVL`, `ASNOW` (1/6/24/48/72 h, with percentiles and exceedance probabilities), `SNOWLR`, `APCP` (percentiles and probabilities), `WIND` and `GUST` (probabilities), `TMP`/`TMP_Max`/`TMP_Min`, `TCDC`, `CEIL`, `VIS`, and `PTYPE` probabilities. Whether the GRIB files expose the same set under Herbie's search strings is **(verify)** in Phase 0.
- `SNOWLR` (I read it as snow-to-liquid ratio, **verify** in the GRIB inventory) is a direct density proxy, so use it for powder versus "Cascade concrete" instead of inventing temperature thresholds.
- The percentile and probability fields give uncertainty for free: show `ASNOW24` spread and `P(gust > threshold)` as the confidence caveat on snow and wind.
- Snow level (`SNOWLVL`) is absolute (MSL), so it compares directly with the user's minimum elevation.
- Use `zoneinfo` for the 07:00-16:00 local window. Daylight saving ends Nov 1, 2026.
- Recent observed snow (last 24/48 h) comes from the existing Synoptic station mapping in `scripts/collect_weather_data.py` (`RESORTS_TO_STATIONS`), not from reconstructing past forecasts.
- BC: NBM coverage of Whistler and the Vancouver hills is unconfirmed **(verify)**. Fallback is Open-Meteo (HRDPS; ask about donations being non-commercial) or Environment Canada open data.
- Keep the existing Selenium NBM-viewer flow in `scripts/build_fx_evaluation.py` as is. The viewer only serves named locations, so it cannot supply arbitrary trailhead points.

### Min elevation (rain-snow filter plus vert)

The user's minimum elevation does two jobs:
- Feasibility: fraction of window hours with `SNOWLVL` at or below (minimum elevation minus a margin parameter).
- Vert score: `top - max(user_min, access)`, normalized.
- Avalanche: use the worst rating among the elevation bands above the user's minimum.

### Avalanche, roads, drive times

- Avalanche: Avalanche.org public API, `map-layer/NWAC` (10 zones). It is off-season now: `danger_level: -1`, `off_season: true`, through about 11/21/26. Treat -1 as "no forecast", never "low". Expire ratings daily. BC: Avalanche Canada products API (terms unpublished; email it@avalanche.ca).
- Roads: see "Pass conditions and traffic (WSDOT)" below.
- Drive times: precomputed once from Seattle, Tacoma, Bellingham, Portland, and Olympia to each zone's `winter_access`. Free-flow only. The 5-hour cap is applied at filter time.

### Pass conditions and traffic (WSDOT)

- **Source:** the Traveler Information API (documented; access code by email), `GetMountainPassConditionsAsJson`, 15 passes. Fields: pass id, name, lat/lon, `DateUpdated`, `TemperatureInFahrenheit`, `ElevationInFeet`, `WeatherCondition`, `RoadCondition`, `TravelAdvisoryActive`, and `RestrictionOne`/`RestrictionTwo` (each a `TravelDirection` plus free-text `RestrictionText`). The wsdot.com mountain passes page returned only its header to my fetch, so I could not see what extra it shows. Use the documented API, not undocumented calls behind that page **(verify in a browser whether the page shows anything the API lacks)**.
- **Free text, not codes:** map `RestrictionText` and `RoadCondition` to a severity (none / traction advised / chains / closed) with a lookup table, and treat unrecognized strings as "caution, unknown". Collect the real strings in-season before fixing the table.
- **It reports current state, not forecast risk.** Use it two ways: (1) a current-state penalty or gate for near-term days; (2) a **pass history log**, same pattern as `radiosonde_history.json`: the bot appends only state changes per pass to `assets/data/pass_history.json`. After a season, pair that log with the NBM forecast at each pass to calibrate closure-risk thresholds (snow rate, wind, snow level) from data instead of guessing.
- **Closures:** the Highway Alerts API is the likely source for closures and avalanche-control work, but its docs do not say closures are included. Check its event categories **(verify)**.
- **Bot:** a small hourly workflow `pass_conditions.yml` writing `assets/data/pass_conditions.json` plus the history log, with the access code in an Actions secret. The page shows an "as of" time and treats data older than about 2 h as unknown. The browser cannot call the API directly without exposing the access code.
- **Traffic:** current congestion only matters for same-day trips. For future days, add a tunable `peak_penalty` per route (for example I-90 or US 2 on weekend mornings) on top of free-flow drive time. WSDOT's Travel Times and Traffic Flow APIs are in the same family; which routes they cover is **(verify)**.
- **Zone mapping:** each zone's `road_dependencies` lists pass ids. Phase 0 prints the 15 pass names and ids so the mapping is filled in from real data.

### Nordic grooming

| Source | Covers | What the page showed (2026-10-02) |
|---|---|---|
| [Kongsbergers](https://www.kongsbergers.org/GroomingReport) | Cabin Creek, Erling Stordahl | Weekly grooming schedule table (Dec 1-Mar 31); status "season has ended". In-season daily reports not seen yet. |
| WA State Parks: [Hyak](https://parks.wa.gov/find-sno-parks/hyak-sno-park), [Crystal Springs](https://parks.wa.gov/find-sno-parks/crystal-springs-sno-park) | Hyak (7 mi non-motorized, 150 spaces), Crystal Springs (51 mi motorized and non-motorized, 150 spaces) | Dated grooming entries with snow depth; last entry 3/27/26, grooming suspended. Same report text on both pages. Sno-Park Permit required per the pages. |
| [Methow Trails](https://methowtrails.org/conditions) | Methow winter system (200+ km) | Staff note dated 9/14/26; grooming map is an embedded Nordic Pulse widget. |

Tiers:
- **Tier 0 (beta):** link-only. Every nordic access point has `grooming_url`. Nordic ranking uses weather and snow only, and the page says it cannot tell whether a trail is groomed.
- **Tier 1 (after the season starts and the formats are seen):** parse State Parks entries into a coarse dated status (`active`, `suspended`, `unknown`), showing the entry date and verbatim text with the link. Entries older than a set age become `unknown`. Check each site's terms/robots and contact them first **(verify)**.
- **Tier 2:** Methow via Nordic Pulse is link-only unless Methow Trails offers a feed (ask). Kongsbergers' schedule is shown as "scheduled days", not confirmation.
- Use the Wayback Machine only to inspect in-season page formats, not as a data source.

### Gates and null recommendation

- Backcountry mode: avalanche danger High or above removes the zone. Considerable adds a strong penalty and a warning. Missing or off-season ratings block backcountry recommendations.
- Resort and nordic modes: avalanche danger does not remove a result; it is shown as an info banner. High danger does tend to coincide with pass closures and slow travel, so it raises the road-risk term (a tunable heuristic, calibrated later against `pass_history.json`).
- All modes: pass-closure risk or a major storm (for example a strong atmospheric river with high wind) can produce a null result.
- Any source older than its freshness limit: show "data unavailable" and recommend nothing.
- Wording: "fits your criteria", never "safe".

### Validation

What exists today: 23 weekly summaries in `data/forecasts/eval_forecast_*.json` (from 2025-11-27), each holding per-area NBM accumulated snowfall and snow level next to your own forecast, plus weekly reports in `data/evaluation_reports/` with SNOTEL-observed results. That is enough to sanity-check the snow and snow-level criteria at weekend scale for the nine existing areas.

It is **not** a hindcast of the full scorer. Only one hourly NBM CSV per site is kept (all from the same April 2026 run), so precipitation probability, wind, cloud, and visibility cannot be replayed. Fix that going forward: once the bot runs, it also writes a compact daily snapshot of each zone's extracted features to `data/ski/archive/YYYY-MM-DD.json` (inside the excluded `data/` folder), so a real replay set exists by midwinter.

Avalanche gating cannot be replayed until NWAC forecasts resume (about late November). Save real responses once they do.

### Build order

- **Status (Oct 7 2026):** Phase 0 done (`docs/nbm_fields.md`). Phase 1 skeleton drafted: `data/ski/destinations.yml` (13 zones, coordinates approximate, `verify` lists per zone), `scripts/ski_dem.py` -> `data/ski/elevations.json`. Phase 2 first draft: `scripts/ski_features.py --mock` -> `assets/data/ski_features.json` (sample numbers, flagged `mock`), scorer and page in `assets/ski-model.js` / `in-house/ski-model.html` with a sample-data banner. Phase 3 (real NBM, NWAC, WSDOT) not started. Road risk (Oct 7 2026): delay curve fitted to the WSDOT Snoqualmie study applied to the highway passes, NPS Longmire matrix for Paradise, and a pass logger bot (`scripts/pass_log.py`) started; see `docs/pass-closures.md`.
- **Phase 0 (spike, no UI):** one script samples three points (Snoqualmie, Colchuck, Whistler) with Herbie, prints the GRIB inventory, records run time and file size, and compares values with the viewer CSV for the same site. Output: `docs/nbm_fields.md`.
- **Phase 1:** `data/ski/destinations.yml` skeleton plus the DEM script. Start the daily archive snapshot as soon as the bot runs.
- **Phase 2:** scorer and UI on mock data.
- **Phase 3:** wire in NBM, WSDOT, and avalanche data, with staleness rules.
- **Phase 4 (once NWAC resumes):** replay storm days, then public beta.

### Open questions (ski tool)

1. ~~High danger and resort/nordic~~ Resolved: it gates backcountry only; resort/nordic show a banner and a higher road-risk term.
2. ~~Tier 1 grooming parse~~ Resolved: link-only for beta. Parsing State Parks, Kongsbergers and similar text products is a later phase.
3. Open-Meteo: this site is a hobby funded by donations, not a business or a paid service. That is a reasonable reading of "non-commercial", but Open-Meteo's docs do not define it, so a short email would settle it. It only matters for BC if NBM covers Washington.
4. ~~Does `[skip ci]` on a bot commit suppress the Pages build?~~ Resolved (Oct 2026, from the public Actions run list): no. "pages build and deployment" runs after bot commits that carry `[skip ci]`. Separately, GitHub throttles scheduled workflows: the "hourly" weather bot ran roughly every 6 to 8 hours on 2026-10-05, so treat all cron cadences as best effort and do not promise freshness on the site. A bot that must be timely can be triggered from outside (workflow_dispatch via an API call), which needs a token.
5. Housekeeping before launch: the Synoptic token now comes from the `SYNOPTIC_TOKEN` Actions secret (code changed Oct 2026). **Still to do by hand:** add the secret, rotate the token at Synoptic (the old value is in public git history), and store the WSDOT access code as a secret from the start.
