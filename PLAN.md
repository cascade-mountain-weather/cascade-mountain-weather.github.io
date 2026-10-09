Goals: 

7. I want to make a some flags for dendritic growth zone height, east flow/strong inversions, atmospheric river signal. This will update with model conditions

Development goals: tools to be constructed in the background before posting

2. I eventually want to build a simple "corn" model. That is estimate the time, aspects, and elevations where corn will be good. This will essentially be an energy balance model. We could either build it ourselves or try and use an open source snowpack energy balance model. The thing is we only really have to worry about the top 6 inches or so of the snowpack for this to work effectively. Corn is best to ski when it is like 2-10 centimeters. This will essentially require inputs of short and longwave radiation, windspeed, temperature, humidity (an use bulk aerodynamic methods to estimate latent and sensible heat fluxes), a terrain dem, and a solar angle model. The vision is a map of the region with a toggle for the day (upcoming from Thursday-Sunday), a time of day slider, and shading for optimal corn timing. For example, most north facing slopes would not have good corn during this period, but a southwesterly slope at lets say 11am would be pretty good on a May day after a freeze. The model would require a freeze. We could test out the model using observations from nearby SNOTEL sites and days that I found the corn skiing to be pretty good. We can then compare those obs based model results to forcing data from model output. Mayb e achived HRRR if we can get it? It would be nice to also use something like RRFS, HRDPS, or data from the NBM. This would also require a warning for days since the last snowfall. A few days are required before the snow metamorphoses into melt forms that are good for skiing. We could use SNOWPACK, or a simple snow metamorphosis model to estimate when snow starts to become melt forms, or just do a simple number of melt freezecycles greater than 2.
- okay, so one of the final steps will now be to develop the corn model. i want to begin with the "simplest" side of things. The first thing we need is a terrain map/dem/aspect map where we can get an accurate picture of solar clearsky irradiance over terrain throughout each day of the year and each 30-minute window in a day. We don't need actual data yet (that will include cloud cover) but we do need 
          highly detailed high rez maps if we can get them for the region above 4000 feet. We will skip other areas because people wont be skiing them. Is that going to be too difficult to host? From there we are going to deal with several assumptions. We don't really care about exactly how much snow is on the ground, we only care that there is some snow, there isnt really recent fresh snow or rain, that there was or will be a refreeze, and the timing of temperatures and winds over the day. Then we can develop a simple energy balance model to estimate when snow would melt and at what depth to estimate the depth of corn snow over a given location. The clouds again will be uncertain. The corn model will turn off/reset/won't recommend anything if there is precip in the forecast or there is no freeze within the snow model predicted or its super windy, or its cloudy for the entire time. lets start crafting how we will do this.  

2. Interesting storm signals: September 13 storm for crystal 
**Storm-type analysis (SOM or similar, idea Oct 8 2026):** find the storm orientations that have an outsized effect on particular ski zones. Example: Crystal Mountain is hard to forecast in its outsized events; on Sept 13 2026 (warm season) snow fell at Crystal while nearby Paradise only got rain. Method sketch: (1) from SNOTEL SWE increases, build a storm-total series per zone and compare each storm with what a "normal" storm for that zone gives, using a baseline we define (for example the zone's storm total against regional or cross-zone totals; **decide the anomaly definition**); (2) pull ERA5 reanalysis (500 mb height, 850 mb temperature, moisture transport/IVT, wind direction) for each storm time; (3) cluster the synoptic patterns with a self-organizing map (or k-means/similar if the SOM adds nothing) and compare which nodes line up with positive or negative zone anomalies; (4) read off which 500 mb / 850 mb temperature / moisture-source patterns go with more snow than expected. Open: ERA5 access (Copernicus CDS needs an account/API key; a cloud-hosted ERA5 copy may be easier) **(verify)**; SNOTEL record length per zone; how to separate rain from snow in a SWE increase (the evaluation scripts already filter rain-on-snow, see `scripts/snotel_obs.py`). Analysis is offline work by Danny with help; the outcome feeds storm flags on the site, nothing is built yet.
**Storm-type analysis: decisions (Oct 9 2026).** Window Nov-May, 1991-2026 (the existing SNOTEL panel, `data/teleconnections/results/panel.npz`: daily SWE gain, 36 stations). Zones: the nine forecast areas, each mapped to its SNOTEL stations as in `data/nbm/sites.yml` (`obs:`). **Over-performance event:** a zone's daily SWE gain at least 0.5 in above what that zone usually gets for the amount the other zones got (zone SWE minus the zone's usual ratio times the mean of the other zones), where 0.5 in of water is roughly 4-6 in of snow. A first count on the panel gave about 1,300 days with at least one zone over-performing (95 to 360 zone-days per zone, most of them single-day events); Crystal has 128. Under-performance is symmetrical and can be looked at later. **Gap:** Baker (Wells Creek 909, Easy Pass 998) and Hurricane Ridge (Waterhole 974) are not in the 36-station panel; add them to `scripts/tele_fetch.py` and check their record lengths. **ERA5:** `scripts/era5_fetch.py` downloads z500, t850 and the two IVT components (00/06/12/18Z, 1 degree, 20-65N, 180W-100W) to `data/era5/` (git-ignored); the CDS "daily statistics" datasets refuse a whole cold season, so the hourly datasets are used and averaged to a UTC daily mean. The CDS key needed the new format (no `UID:` prefix, URL `https://cds.climate.copernicus.eu/api`). **SOM size** (number of nodes, the regimes): compare 3x3 and 3x4 on stability across seasons; more nodes than that leaves too few over-performance days per zone per node (Crystal's 128 days over 12 nodes is about 10 per node).
**Point-forecast meteograms on the main page (Oct 8 2026):** a simple meteogram for each point forecast we have, from the NBM, HRRR, ECMWF (only if we can get point data; **verify** what ECMWF open data gives at a point), and HRDPS. Variables: temperature, wind speed, humidity, precipitation. Not downscaled, so the page carries a visible warning that values are model grid cells, not the specific terrain point. Purpose: quick access for people who only want a basic forecast. Shares the Herbie extraction with the ski tool and corn model; one scheduled Action would write a compact JSON per point, and the page draws it client-side.
**Ski tool fixes (Oct 8 2026):** (a) mobile: the page title is overstretched; (b) the snow filter is wrong (Baker shows 7 inches of new snow when it should not); apply the same questionable-data checks the live conditions map uses (snow depth above 0 right now, a depth change over 36 in in 24 h, negative values; see `scripts/collect_live_conditions.py`) to every forecast location and to the recent-snow numbers feeding the ski tool. Find where the 7 inches comes from first (**verify** in `scripts/ski_features.py` and the page).
3. **Forecast Floater** (idea, Oct 2026): a "floater" forecast tool set for any region I care about or a friend might be going to: a hut trip in the Sawtooths, friends skiing in BC or Japan. By request: give a location (lat/lon or a named place) and a date range, and get a bundle of useful forecast data fast, instead of hunting for it when the time comes. Could start as an "in development" page in the tools section ("Forecast Floater"), and later become a form that builds the bundle on demand. Open questions: which sources cover which places (the NBM covers CONUS and southwest BC, not Japan; HRDPS covers western Canada; global models such as GFS, ECMWF and ICON for anywhere; Open-Meteo would be the easy global source but its non-commercial terms need a check, see the ski tool's open questions); what a bundle contains (point forecast of snow, snow level, wind and temperature; forecast sounding; nearby observations such as SNOTEL, which exists in Idaho; the regional avalanche forecast link); whether the static-site constraint means a page that builds links and client-side plots, or a scheduled Action for a short list of saved places. The plumbing (Herbie extraction at a point, the sounding derivations, the plume plots) is shared with the ski tool and the corn model.
4. Ski recommendation tool remaining tasks: 
the lowland fallback
NWAC avalanche forecasts (late November)
the drive-time pulls (eight daily runs)
tuning my guessed thresholds
checking its picks against what actually happened
---
# Done
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

**Slope bins (decided Oct 8 2026):** flat (placeholder limit 10 degrees, no aspect), 10-25, 25-35, 35-45, 45+ degrees, 8 aspect octants, 500 ft elevation bands. I read "flat plus edges at 25, 35 and 45" as adding 45 to the earlier 10/25/35 edges, so low-angle slopes keep their aspect; correct me if flat should mean everything under 25.

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