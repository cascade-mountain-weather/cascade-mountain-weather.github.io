# Teleconnections vs. SNOTEL observations: first pass (Oct 2026)

Exploratory. Nothing here is on the site yet. Figures sit next to this file; the numbers behind them are in
`data/teleconnections/results/` (git-tracked CSVs, `composites.csv` is the master table).

## What was done

- **Stations:** 36 Washington SNOTEL sites with records back to 1990 or earlier (Oct 1980 for most), 2,930 to 6,490 ft, from the Olympics and
  southern Cascades to the northeast corner. Daily data from NRCS AWDB (`scripts/tele_fetch.py`).
- **Period:** every day November 1 to May 31, seasons 1992 to 2026 (35 winters). OMI starts in 1991, which sets the start.
- **Measures (per station per day):** temperature anomaly (vs. the station's own smoothed day-of-year mean), snowfall (daily SWE gain),
  precipitation, rain (precip that did not become SWE), and **big days** (SWE gain or precip above the station's own 90th percentile).
- **Indices:** MJO phase from NOAA PSL's OMI (amplitude at least 1; phases rotated to match the BoM RMM diagram, they agree within one phase on 91% of the
  5,000 overlap days). PNA from the CPC daily index (5-day mean, quintile-style classes). ENSO from the monthly ONI.
- **Lags:** the response is the station on day *t*, the index is its state *lag* days earlier (0 to 14 days, in 2-day steps).
- **Uncertainty:** 90% bootstrap over whole winters (300 resamples). A dot on the heatmaps means the interval excludes "no change".
- Code: `scripts/tele_fetch.py`, `tele_analysis.py`, `tele_figures.py`, `tele_modes.py`.

## Headline results (average of the 36 stations)

**MJO, snowiest: phase 2, six to ten days later.** Snowfall runs 24 to 32% above normal and big-snow days 33 to 49% more often (lag 6 to 10 d).
86% of stations are individually significant at lag 8. It holds in every month Nov to Feb (strongest in Nov and Jan, weakest in Mar).
**Least snow: phase 7** (about 15% below normal) with phases 8 and 1 near 5% below. Phases 4 and 5 add some big-snow days (+30%) but they are the warm phases.

**MJO, warmest and coldest:** warm phases are **4 and 5** (+0.6 to +0.8 F at lag 8, up to +1.1 F at lag 10), cold phase is **3** (about -0.9 F), and phase 1 and 2
run cool too. Month matters a lot: in November phase 5 runs +3.5 F and phase 1 -4.5 F, in April the sign flips for phases 4 and 5.

**MJO, rainiest:** the regional rain ratio is highest for **phases 5 and 6** and again 8 (about +10 to 12%) and lowest for **phase 3** (0.72) and phase 1 and 2 (0.8 to 0.87).
"Big precipitation days" are most frequent in **phases 4 to 6** (+20 to 26%) and least in phase 3 and 7. Put together: **phase 2 = cold, snowy; phases 4 to 5 = warm and wet (the rain-on-snow risk window); phase 3 = cold and dry; phase 7 = dry.**

**PNA** is the stronger and more immediate control (lag 0): the strongest negative decile gives snowfall +29% and big-snow days +41% (and a temperature anomaly of -3.8 F); the strongest
positive decile gives snowfall -25%, big-snow days -37% and +3.5 F. The temperature response is nearly linear with the index. Rain rises with positive PNA (+16%). Negative PNA is the cold and snowy state.

**ENSO** (monthly ONI): La Nina (ONI at or below -1) gives snowfall +53%, big-snow days +82%, big precip days +74% and -0.8 F; El Nino is warmer (+1.3 to +1.5 F) but not clearly less snowy at the
strongest end (1.06), while weak El Nino winters are the lowest (0.77). Only about 5 to 8 winters sit in each ONI class, so treat these as soft.

**How strong it really is:** these are changes in odds and averages. Day by day the MJO explains well under 1% of daily variance (R^2 of the harmonic fit is about 0.003) and the PNA's daily link is larger but still modest, because daily weather is mostly noise. (Not computed here: the explained variance of the PNA itself; ask if you want it.) The useful framing is "the weeks after phase 2 are a third snowier on average".

## Geography: elevation, latitude, longitude

Most of the signal is **statewide**; the best and worst MJO phase is the same (2 and 7) at almost every station (map: `mjo_map_snow.png`). The differences are in the size.
Regression of station effect sizes on standardized elevation, latitude and longitude (`station_gradients.csv`):

| effect | what the spread across stations explains |
|---|---|
| Strong +PNA temperature anomaly | **R^2 0.41**: stronger warming at higher elevations (t=4.3) and further south (t=-2.0 for latitude) |
| Strong +/-PNA snowfall | R^2 0.56 (+PNA) and 0.69 (-PNA), latitude t of about 5: the snowfall swing is larger for **lower, more southern** stations, and the cold-PNA boost is biggest at low elevation (the <4000 ft group: +42% vs +20% at 5000+ ft) |
| MJO phase 2 snowfall | R^2 0.37: the boost is larger at **low elevation and in the south** |
| MJO phase 5 temperature | R^2 0.27: warmer at **higher elevations** (t=2.6) and further south (t=-2.3 for latitude) |
| La Nina snowfall / temperature | R^2 0.28 / 0.36: low-elevation stations gain more snow (t=-3.4); the cooling is stronger toward the west (t=3.2 for longitude) and at lower elevations (t=-3.4) |

Reading: the low, marginal stations (3,000 to 4,000 ft, mostly Gifford Pinchot and the Snoqualmie corridor) swing most, which makes sense because they sit near the rain-snow line, where a temperature
change flips rain to snow. The highest stations (5,000+ ft) respond mostly with temperature.
Leading modes (`eofs.png`): the first mode of daily snowfall is basically "storm day or not" for the whole state (52% of variance); the second mode (7%) is a **north-south dipole**
(loadings correlate +0.79 with latitude, +0.43 with elevation). For temperature the first mode is statewide (84%), the second is a north versus south/low-versus-high dipole.

## Caveats (please push back on any of these)

1. **SWE gain is a biased snowfall estimate**: it misses snow that melts or compacts the same day and is noisy at warm sites. It is the same quantity the evaluation scoring uses (QC'd: cap by precipitation, no spikes).
2. **Lag is a choice.** The strongest regional snowfall contrast is at 8 days, but 0 to 14 days all show phase 2 high and phase 7 low. The MJO takes days to affect the Northwest.
3. **Multiple comparisons:** 36 stations x 8 phases x 4 metrics x 8 lags. Dots are not corrected for that, and the stations are not independent (they all see the same storms), so the "86% of stations significant" is closer to one result than 31.
4. **Month x phase cells are small** (about 100 days each); the month figure is for pattern spotting, not for numbers.
5. **Overlap of indices** is not removed (La Nina years bias the MJO composites, ENSO affects MJO behavior). A joint model is a next step.
6. The harmonic (linear in PC1/PC2) fit is weak and its "peak phase" is not the same thing as the composite's best phase. The phase-composites are the better description.
7. 35 winters of data is short for ENSO classes.

## Files

- `mjo_region_by_lag.png`: phase x lag heatmaps for six measures
- `mjo_region_lag0.png`, `mjo_region_lag8.png`, `pna_region.png`, `enso_region.png`: regional response by class and elevation tier
- `mjo_stations_lag0.png`, `mjo_stations_lag8.png`, `pna_stations.png`, `enso_stations.png`: every station (north to south) x class
- `mjo_map_snow.png`, `mjo_map_temp.png`: best and worst MJO phase per station
- `month_by_class.png`: month x phase / class
- `eofs.png`, `mjo_harmonic_map.png`: modes of variability
