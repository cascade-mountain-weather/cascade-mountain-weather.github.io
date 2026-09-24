Goals: 
1. For this season, I want to give readers and users a broader range of tools, from custom ones I create (will describe what I want below) that are simple to use and provide quick and easy answers for users, to more nitty gritty and raw data that they can do with what they want. 
2. I want to improve the evaluation page and its methodology. I kind of threw it together, but I want a more robust way to estimate these things. This would mean grabbing the SNOTEL data, cleaning it, and presenting the information in plots and tables more interactively/automatically updating.  This will update on Monday mornings.
3. I want better mobile functionality that makes it easier for a user to click through images that show data I am presenting, whether that is a timeseries of modeled output or satellite data images. 
4. I want to more simply host older, archived posts with greater efficientc 
5. I want to build a radiosonde tool to visualize the radiosonde data from certain sites that is collected each day and be able to incorporate that information into forecast creation and later evaluation (mostly for freezing level and dendritic growth zone stuff). I want to also include precipitatble water in here, if I can estimate that data. This will update twice daily for the morning and afternoon soundings. Can also build upon request as a script.
6. We want to build out the newsletter that will send out the forecast to those who sign up each week. We are setting this up with mail chimp, but just want the sign up to work. This will be done for us using mailchimp, but we will need to prep a forecast for it.
7. I want to make a some flags for dendritic growth zone height, east flow/strong inversions, atmospheric river signal. This will update with model conditions
8. I want to run some additional analyses myself for some "reading the tea leaves" ideas. That is I want pages to look at the states of the Pacific North American climate teleconnection, the Madden-Julian Oscialltion and the status of the ENSO state. I want to run a rudimentary analysis on the phases of the MJO that locally have corresponded to good conditions for snow (e.g. cold and wet). This will update weekly, but I will need to work through the analysis myself to build the background. We will do this later. Under consturction for now.
9. I want a page on climate outlooks, taking estimates from ensembles and the CPC from NOAA that can populate with toggles between product types. This will update on Thursday's alongside the forecast for the longer term outlooks.We can also add this to the reading the tea leaves page (longer term outlooks)
10. I want to improve how the CW3E/University of Utah data is presented to the user. I want it to be an easier click through/play/pause set up. And i want a better presentation of the time conversion from UTC to Pacific Standard time. this is currently done in a very clunky and ugly manner. I also want a click/map for these locations so we have an easier time navigating. This will update with each posting, which I think is every 6 hours. 
11. I want to find a way to access and present UW WRF data. Their page is free and open to the public but I would like to see if we can find a way to grab their data for presentation purposes. This might be possible, we will try. 
12. We want to make a merchendise page that will link to a simple and clean merch provider. I think there are some low cost/free ones we can try to use, I'll look into that later. Provide some options if there are any. I've seen it where you can upload a logo and the site will process and print and ship all your stuff, so you dont actually have to hold onto inventory and deal with shipping. This should be able to run in the background on its own.
13. On the main page, I also want to show bar plot comparisons of % normal conditions for accumulated precipitation (for day of year), SWE (for day of year), and temperature anomaly (for prior week [was it colder or warmer than normal], and up temperature anomaly up to that day of the water year) for each ski area we reference. This will update daily. 
14. I want to turn the "Areas We Cover" into an interactive map with the location and names of ski resorts/forecast areas. On hover, the user should see the location name. On click, the user gets a read out of live conditions and info [elevation, temperature, wind speed (if available), 24 hr prcp.], along with a checklist of recent snowfall or SWE increase (within the last 72 hours), recent precip (same thing), temperature, humidity, visibility flag (if dew point temperature and air temperature are super close together). We will set this up for the following locations and add a box around each location with smaller icons for the specific sites we present: Hurricane ridge  (if we can get NWAC data from synoptic -- otherwise use Waterhole Snotel), Mt Baker - Heather Meadows (can gather Easy Pass, too), Washington Pass (SNOTEL), Mazama (NWAC station, there may be a snotel out there, too now?), Stevens Pass (NWAC stations and snotel. Default to Brooks NWAC station if available), Leavenworth/Icicle Creek (use new Icicle Creek (1338) SNOTEL), Blewett Pass (NWAC or Snotel), Salmon La Sac (use Sasse Ridge SNOTEL), Snoqualmie - East (use Stampede Pass), Snoqualmie West (Ollalie meadows), Alpental (alpental base mid-mountain and summit), Crystal Mountain (use Green Valley NWAC or summit NWAC and Base NWAC, or Morse Lake Snotel if not available), Mt. Rainier - Paradise (use SNOTEL), Mt. St. Helens (Swift Creek SNOTEL), White Pass (White Pass SNOTEL or NWAC), Mt. Adams region (caveat with the fact there are no nearby stations, this is approximate conditions using the Surprise Lakes SNOTEL to the mountain's southwest). For locations with multiple sites, show all available as an ordered list from top to bottom. I think the pop up should be a mini table maybe? if thats possible. Then there should be a link to dive in further for more data on that specific site that currently lies under the precipitation tools sector.
     We should caution certain sites as questionable if: one, the snow depth is currently above 0 (as in right now. for instanvce, brooks chair at stevens pass is at 59 right now, definitely not right), two: snowdepth increases or decreases by more than 36 inches in 24 hours (this is a flag remember, just cautioning that the data may not be trustworthy), or negative. 

Development goals: tools to be constructed in the background before posting
1. The primary tool I want to develop is one that allows a site visitor to select several options to create a recommendation for where they should ski. This should essentially be a simple ML model, or something like a decision tree, to recommend the ski area of choice. The options I want the user to be able to balance are: Drive time (up to 5 hours), precipitation chances,snow quality (powder/fresh/corn/cascade concrete/I don't care), temperature (do you want it to be warm or are you okay with it being cold?), visibility (are you okay with clouds and fog? Or do you want bluebird?), driving hazard/difficulty (pass closure risk?), windy/not windy (caveat with uncertainty), elevation range, avalanche danger flag (directly taken from NWAC, DO NOT RECOMMEND during a high danger day ANYWHERE, considerable danger is also bad). We can recommend any of the ski resorts in Washington and souther British Columbia. We will use these as jumping off points for backcountry touring. So that means: Snoqualmie, Stevens, Crystal, White Pass, Mission Ridge, Mazama, Mt. Baker, Whistleyr, Vancouver ski hills,. Also, no recommendation/ a null recommendation can be provided if criterion are not met/something like a huge AR is coming or there are a bunch of pass closures. So essentially we would have somehting like a pass closure risk flag/warning. Then we can provide "what we would do" ski type recommendation  (nordic, downhill, backcountry -- nordic would be okay with slightly different conditions and can recommend any sno-park with a nordic ski area that is groomed), could also update with parking restrictions (need sno-park pass, free parking, ski resort reservation needed, etc. -- would have to research this). We can work through questions for this part of the project.
2. I eventually want to build a simple "corn" model. That is estimate the time, aspects, and elevations where corn will be good. This will essentially be an energy balance model. We could either build it ourselves or try and use an open source snowpack energy balance model. The thing is we only really have to worry about the top 6 inches or so of the snowpack for this to work effectively. Corn is best to ski when it is like 2-10 centimeters. This will essentially require inputs of short and longwave radiation, windspeed, temperature, humidity (an use bulk aerodynamic methods to estimate latent and sensible heat fluxes), a terrain dem, and a solar angle model. The vision is a map of the region with a toggle for the day (upcoming from Thursday-Sunday), a time of day slider, and shading for optimal corn timing. For example, most north facing slopes would not have good corn during this period, but a southwesterly slope at lets say 11am would be pretty good on a May day after a freeze. The model would require a freeze. We could test out the model using observations from nearby SNOTEL sites and days that I found the corn skiing to be pretty good. We can then compare those obs based model results to forcing data from model output. Mayb e achived HRRR if we can get it? It would be nice to also use something like RRFS, HRDPS, or data from the NBM. This would also require a warning for days since the last snowfall. A few days are required before the snow metamorphoses into melt forms that are good for skiing. We could use SNOWPACK, or a simple snow metamorphosis model to estimate when snow starts to become melt forms, or just do a simple number of melt freezecycles greater than 2.

---

## UI changes

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
| Ski-area recommendation tool | Composes: NWAC avalanche danger, pass-closure/driving-hazard flags, CW3E/model conditions, drive time | new `tools/find-your-ski-day.html` (name TBD) | Live, driven by current forecast/model data |
| Corn model | Energy-balance model (shortwave/longwave, wind, temp, humidity, terrain DEM, solar angle) validated against SNOTEL obs and Danny's own field observations of good corn days; forcing from HRRR/RRFS/HRDPS/NBM if accessible | new `tools/corn-model.html` (see `.claude/skills/corn-forecast-model/SKILL.md`) | Thu-Sun outlook, spring season only |

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
7. **Ski-area recommendation tool** — capstone; composes outputs from phases 3-6 (avalanche flag, closure risk, model conditions, drive time).
8. **Corn model** — physics/validation work can happen through winter, but real-world testing needs actual corn conditions, so target a March launch rather than racing it now.

## Open questions

- UW WRF ensemble page: is `plumes.html` actually scrapeable, or does it need a different access path? (Phase 6 spike will answer this.)
- Merch provider: which print-on-demand service — Printful, Bonfire, Threadless, something else? Needs a quick comparison of cost/quality/ease of logo upload.
- Corn model: build the energy-balance model from scratch, or adapt an existing open-source snow-metamorphosis model (e.g. a simplified SNOWPACK)? Depends on what forcing data (HRRR/RRFS/HRDPS/NBM) turns out to be accessible.
- Ski-recommendation tool: exact decision logic (weighting/thresholds for each input) needs to be worked through with Danny before building — this is a "we can work through questions for this part" item, not something to guess at.
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

West WRF figures from CW3E:
- https://cw3e.ucsd.edu/west-wrf_ensemble_meteograms?station=US2

CW3E freezing level and precipitation maps:
- https://cw3e.ucsd.edu/DSMaps/DS_freezing.html

NOAA CPC teleconnection/outlook products (for the climate outlook + teleconnections page):
- PNA ensemble: https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna_index_ensm.shtml
- MJO: https://www.cpc.ncep.noaa.gov/products/precip/CWlink/MJO/mjo.shtml
- ENSO: https://www.cpc.ncep.noaa.gov/products/precip/CWlink/MJO/enso.shtml
