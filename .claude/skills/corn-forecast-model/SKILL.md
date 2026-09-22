---
name: corn-forecast-model
description: Create a corn forecast model for the site. This is a more advanced tool that will require some data processing and modeling, but will provide users with a unique and valuable resource for planning their skiing trips in the spring during volcano season and during warmer dry periods.
---

# New weekly forecast post

Ask the user for anything not already provided: the datasets required, model decisions, model structure, and any other relevant information. Never invent physics based decisions, numbers. Always provide sources of information that is presented

## Steps
The final product will be a model that can estimate the time, aspects, and elevations where corn will be good. 
1. This will essentially be a snowpack energy balance model. We could either build it ourselves or try and use an open source snowpack energy balance model. 
2. The thing is we only really have to worry about the top 6 inches or so of the snowpack for this to work effectively. Corn is best to ski when it is like 2-10 centimeters. 
3. This will essentially require inputs of short and longwave radiation, windspeed, temperature, humidity (an use bulk aerodynamic methods to estimate latent and sensible heat fluxes), a terrain dem, and a solar angle model. 
4. The vision is a map of the region with a toggle for the day (upcoming from Thursday-Sunday), a time of day slider, and shading for optimal corn timing. For example, most north facing slopes would not have good corn during this period, but a southwesterly slope at lets say 11am would be pretty good on a May day after a freeze. 
5. The model would require a prior nights freeze. We could test out the model using observations from nearby SNOTEL sites and days that I found the corn skiing to be pretty good. We can then compare those obs based model results to forcing data from model output. Mayb e achived HRRR if we can get it? It would be nice to also use something like RRFS, HRDPS, or data from the NBM. 
6. The model would also need to account for the effects of wind and precipitation on the snowpack. This could be done by incorporating wind speed and direction data, as well as precipitation forecasts, into the model.
7. The model would also need to account for the effects of temperature and humidity on the snowpack. This could be done by incorporating temperature and humidity data into the model.
8. This would also require a warning for days since the last snowfall. A few days are required before the snow metamorphoses into melt forms that are good for skiing. We could use SNOWPACK, or a simple snow metamorphosis model to estimate when snow starts to become melt forms, or just do a simple number of melt freezecycles greater than 2.

We will need to create a page for the model that will allow users to input their desired parameters and view the results. This page should be designed to be user-friendly and intuitive, with clear instructions and visualizations of the model output.
