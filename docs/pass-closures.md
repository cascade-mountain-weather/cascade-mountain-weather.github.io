# Pass closure and delay risk (Oct 2026)

## Sources

- **WSDOT, Snoqualmie Winter Operations Study, December 2024**, Figure 4 "Closure Map":
  <https://wsdot.wa.gov/sites/default/files/2024-12/Snoqualmie-Winter-Operations-Study-December2024.pdf>.
  120 I-90 delays, Nov 2017 to Mar 2024, with date, mileposts, weather, cause and length (printed total 458 h 7 min of closure, $13.6 million).
  Extracted from the PDF text by `scripts/pass_i90_parse.py` (an earlier hand transcription from the picture matched all 120 rows).
  The study says traction non-compliance caused 63% of closure time (299 h 41 min), and that avalanche control closes both directions up to 6 hours
  before artillery work. One entry is dated "November 31, 2021" in the study; it is treated as Nov 30 and flagged.
- **NPS, Longmire-to-Paradise Winter Road Opening Matrix** (Mount Rainier): <https://www.nps.gov/mora/planyourvisit/upload/PUBLIC-winter-matrix_Nov2018_access.pdf>.
  The Paradise road is held CLOSED when NWAC danger is High or Extreme at or below treeline, avalanches are observed, or an avalanche specialist
  calls it; and it is closed to the public for unsafe traffic or road conditions, insufficient staffing, priority snow removal or other hazards.
  Staffing has also meant weekday closures in some winters, which no weather forecast predicts.
- **WSDOT road alerts feed** (public, current events only, no history): <https://data.wsdot.wa.gov/arcgis/rest/services/TravelInformation/TravelInfoRoadAlerts/FeatureServer>.
- **NPS Mount Rainier** conditions: <https://www.nps.gov/mora/planyourvisit/conditions.htm> (alerts feed `/mora/park-alerts-mora.json`) and road status table
  <https://www.nps.gov/mora/planyourvisit/road-status.htm> (the Longmire to Paradise row).
- **WSDOT seasonal opening and closing dates** for SR 410, SR 123 and SR 20 (`scripts/pass_seasonal_dates.py`, `data/passes/seasonal_closures.csv`); a pilot against SNOTEL is in `docs/passes/seasonal_pilot.png`.

## The risk curve (`scripts/pass_i90_analysis.py`, `scripts/pass_risk.py`)

Daily new snow water equivalent at the Meadows Pass SNOTEL (3,230 ft, nearest in elevation to the 3,022 ft summit) ranks I-90 delay days well
(AUC about 0.84 over 1,269 winter days; 81 delay days, 77 of them in snowing weather). A logistic fit on the square root of SWE (chosen by leave-one-winter-out
log loss) gives the chance of a weather delay that day: about 1% at 0 in, 11% at 0.5 in, 24% at 1 in, 40% at 1.5 in, 56% at 2 in; for a delay of 3 hours or more:
4%, 10%, 19%, 30%. Curves are in `assets/data/pass_risk_curve.json`.

Applied, by decision (Oct 2026), to US 2 (Stevens), US 12 (White), SR 410 (Chinook/Crystal), SR 542 (Baker), US 97 (Blewett) and SR 20, on the assumption that
other Cascade passes behave like I-90. Limits: seven winters; the study lists delays above some length and gives no clock times, so the unit is the day; the forecast
input is the NBM snowfall converted to water equivalent; the curve says nothing about collisions on clear days (about 1% of days); I-90 has avalanche bridges and a
heavy truck share that other passes do not.

## Paradise (`road_risk.model: nps_gate` in `data/ski/destinations.yml`)

Per the NPS matrix: avalanche danger High or Extreme holds the gate (a hard gate in the scorer, from the NWAC forecast); otherwise the same snow-based delay chance
stands in for unsafe road conditions and priority snow removal, and the card carries a standing note that staffing and plowing also close it. No history of gate closures is
published, so the logger below starts the record.

## Logger (`scripts/pass_log.py`, workflow `pass_log.yml`, three runs a day, best effort)

Road status matters for the morning decision, so it runs at 14:30, 15:30 and 16:30 UTC (6:30, 7:30 and 8:30 am in winter, an hour later in daylight time).
It records every closure or restriction on the pass corridors (WSDOT alerts inside a box around each pass), the NPS Rainier alerts, and changes in the NPS Longmire to Paradise
status, into `data/passes/log/` (`events.jsonl` for finished events with first seen, last seen, ended and text history; `nps_gate.jsonl`; `state.json` for what is open). The tool
reads `assets/data/pass_now.json` (rewritten every run) and treats a closure as current for today only if the file is under 6 hours old. With three morning polls, event times are only
good to within hours: enough to say a pass was closed that morning and why, not for how long. If we later want closure lengths for the calibration, add an afternoon run.

## What to do with the log

After a season: pair each event with the forecast and the observed snow at the nearest SNOTEL, refit the curve per pass (starting with US 2 and US 12), check the gate matrix
against the Paradise status log (and ask the park about staffing-related closures), and replace the borrowed I-90 curve where a pass has its own record.
