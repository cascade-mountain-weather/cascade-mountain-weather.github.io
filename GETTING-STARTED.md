# Getting Started with Your Weather Blog

Congratulations! Your Washington Skiing Weather Blog is ready to use. Here's everything you need to know to get started.

## What You Have

✅ **Complete Blog Website**
- Homepage with ski area information
- Sample weekend forecast post
- Archive page for past forecasts
- Verification page for tracking accuracy
- Responsive design (works on phones, tablets, desktops)

✅ **Forecast Verification System**
- Python scripts for data collection
- Automated forecast verification
- Figure management tools
- Data storage structure

✅ **Comprehensive Documentation**
- README.md - Full project guide
- QUICK-GUIDE.md - Fast workflow reference
- VERIFICATION-GUIDE.md - Verification details

## Next Steps

### 1. View Your Blog Locally

```bash
# Open index.html in your browser, or run:
python3 -m http.server 8000
# Then visit: http://localhost:8000
```

### 2. Deploy to GitHub Pages (Recommended)

1. Go to your repository on GitHub
2. Click **Settings** → **Pages**
3. Under "Source", select **main** branch
4. Click **Save**
5. Your blog will be live at: `https://dlhogan97.github.io/Dawg-Winter-Weather-Blog/`

### 3. Create Your First Real Forecast

```bash
# 1. Copy the template
cp posts/TEMPLATE-post.html posts/2025-11-22-weekend-forecast.html

# 2. Edit the file with your forecast data
# - Update title and dates
# - Fill in temperatures for each ski area
# - Add precipitation amounts
# - Include freezing levels
# - Add wind conditions
# - Write extended outlook
# - Add your recommendations

# 3. Update homepage (index.html)
# - Change "Latest Weekend Forecast" section
# - Add to "Recent Forecasts" list

# 4. Update archive (posts/archive.html)
# - Add entry to archive list

# 5. Commit and push
git add .
git commit -m "Add weekend forecast for Nov 22-24"
git push
```

### 4. Add Weather Figures

```bash
# Create images directory
mkdir -p assets/images

# Save your weather screenshots with standard names:
# - temp_forecast.png
# - precip_forecast.png
# - wind_forecast.png
# - extended_outlook.png
# etc.

# Reference in your post:
# <img src="../assets/images/temp_forecast.png" alt="Temperature Forecast">
```

### 5. Use the Verification System

**After you post a forecast:**
```bash
# Save your forecast data
python3 scripts/collect_weather_data.py
# Edit data/forecasts/forecast_YYYY-MM-DD.json with your predictions
```

**After the forecast weekend:**
```bash
# Collect actual observations from SNOTEL/NWS
# Visit: https://wcc.sc.egov.usda.gov/ for SNOTEL data
# Save to data/observations/

# Run verification
python3 scripts/verify_forecasts.py

# Update verification.html with results
```

## Useful Resources

### Weather Data Sources

**SNOTEL Stations (Snow & Temperature):**
- Mt. Baker: https://wcc.sc.egov.usda.gov/nwcc/site?sitenum=809
- Stevens Pass: https://wcc.sc.egov.usda.gov/nwcc/site?sitenum=957
- Snoqualmie: https://wcc.sc.egov.usda.gov/nwcc/site?sitenum=910
- Crystal Mountain: https://wcc.sc.egov.usda.gov/nwcc/site?sitenum=623
- White Pass: https://wcc.sc.egov.usda.gov/nwcc/site?sitenum=968

**Weather Forecasts & Models:**
- NWS Seattle: https://www.weather.gov/sew/
- Windy.com: https://www.windy.com
- Tropical Tidbits: https://www.tropicaltidbits.com/
- Pivotal Weather: https://www.pivotalweather.com/

**Safety Information:**
- NWAC (Avalanche): https://nwac.us
- WSDOT (Road Conditions): https://wsdot.wa.gov/travel

### File Naming Conventions

**Blog Posts:** `YYYY-MM-DD-descriptive-title.html`
- Example: `2025-01-22-weekend-forecast.html`

**Forecast Data:** `forecast_YYYY-MM-DD.json`
- Example: `forecast_2025-01-22.json`

**Observation Data:** `AREA_YYYY-MM.json`
- Example: `baker_2025-01.json`

**Figures:** Use standard names for easy overwriting
- `temp_forecast.png`
- `precip_forecast.png`
- `wind_forecast.png`

## Tips for Success

### Writing Forecasts
1. **Post Thursday or Friday** for weekend forecasts
2. **Be specific** about amounts and timing
3. **Give ranges** for snowfall (e.g., 8-14")
4. **Compare areas** to help readers decide
5. **Include confidence** when uncertain
6. **Add personality** - make it engaging!

### Using Figures
1. **Screenshot** weather maps/models
2. **Crop** to relevant area (Washington)
3. **Save** to assets/images/ with standard names
4. **Reference** in posts with `<img>` tags
5. **Overwrite** each week with new figures

### Verification
1. **Always save** forecast data at time of posting
2. **Wait 24-48 hours** after weekend for complete observations
3. **Cross-reference** multiple sources (SNOTEL, NWS, resorts)
4. **Be honest** - include all forecasts, good and bad
5. **Learn** from errors to improve

## Common Tasks

### Update Navigation Links
All navigation is in each HTML file's `<nav>` section. If you add new pages, update the nav in:
- index.html
- verification.html
- posts/*.html

### Change Colors/Styling
- **Site-wide:** Edit `style.css`
- **Blog posts:** Edit `posts/post-style.css`

### Add a New Ski Area
1. Add card to homepage ski areas grid (index.html)
2. Include in forecast posts
3. Add SNOTEL data source to verification guide

## Troubleshooting

**Images not showing?**
- Check file paths are correct (../assets/images/)
- Verify images are in assets/images/ directory
- Check file names match HTML references

**Verification scripts not working?**
- Install requirements: `pip install -r requirements.txt`
- Check JSON formatting is valid
- Verify file paths in scripts

**Blog not updating on GitHub Pages?**
- Check Settings → Pages is configured
- Changes may take 1-2 minutes to deploy
- Clear browser cache if old version shows

## Need Help?

- Check README.md for detailed information
- See QUICK-GUIDE.md for fast workflow tips
- Read VERIFICATION-GUIDE.md for verification details
- Review example post: posts/2025-01-15-weekend-forecast.html

## Let's Go!

You're all set! Start by:
1. Deploying to GitHub Pages (if you haven't)
2. Creating your first forecast post
3. Sharing with friends and fellow skiers
4. Building a track record of accurate forecasts

Have fun and enjoy the snow! 🎿❄️
