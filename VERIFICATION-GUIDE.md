# Forecast Verification System Guide

This guide explains how to use the forecast verification system to track forecast accuracy and improve your predictions over time.

## Overview

The verification system has three main components:

1. **Data Collection** (`scripts/collect_weather_data.py`) - Save forecasts and collect observations
2. **Verification** (`scripts/verify_forecasts.py`) - Compare forecasts to actual conditions
3. **Figure Management** (`scripts/manage_figures.py`) - Organize weather images/figures

## Directory Structure

```
Dawg-Winter-Weather-Blog/
├── assets/
│   └── images/              # Current forecast figures (overwritten weekly)
│       └── archive/         # Dated copies of figures (optional)
├── data/
│   ├── forecasts/           # Your forecast predictions (JSON)
│   ├── observations/        # Actual weather data (JSON)
│   └── verification_reports/ # Generated verification reports
└── scripts/
    ├── collect_weather_data.py
    ├── verify_forecasts.py
    └── manage_figures.py
```

## Workflow

### Step 1: Create Your Weekly Forecast

When you write your weekend forecast blog post:

1. **Save Forecast Data** for verification:
   ```bash
   python3 scripts/collect_weather_data.py
   ```
   
   Or manually create a forecast JSON file in `data/forecasts/`:
   ```json
   {
     "post_date": "2025-01-15",
     "valid_dates": ["2025-01-16", "2025-01-17"],
     "areas": {
       "baker": {
         "snowfall_total": {"forecast": 20, "range": [14, 24], "units": "inches"},
         "temp_base": {"sat": 25, "sun": 22, "units": "F"},
         "temp_summit": {"sat": 15, "sun": 12, "units": "F"}
       },
       "stevens": {
         "snowfall_total": {"forecast": 12, "range": [8, 16], "units": "inches"},
         "temp_base": {"sat": 28, "sun": 24, "units": "F"},
         "temp_summit": {"sat": 18, "sun": 14, "units": "F"}
       }
     }
   }
   ```

2. **Add Your Forecast Figures**:
   ```bash
   # Save your weather screenshots/charts to assets/images/
   # Use standard names that you'll overwrite each week:
   cp ~/Downloads/temp_map.png assets/images/temp_forecast.png
   cp ~/Downloads/precip_map.png assets/images/precip_forecast.png
   cp ~/Downloads/wind_map.png assets/images/wind_forecast.png
   ```

3. **Reference Figures in Your Post**:
   ```html
   <img src="../assets/images/temp_forecast.png" alt="Temperature Forecast">
   <img src="../assets/images/precip_forecast.png" alt="Precipitation Forecast">
   ```

### Step 2: Collect Observation Data (After Weekend)

After the forecast weekend (typically Monday or Tuesday):

1. **Collect Actual Observations**:
   - Visit SNOTEL websites for snow depth and temperature
   - Check NWS stations for additional data
   - Check resort snow reports
   
   **SNOTEL Sites:**
   - Mt. Baker: https://wcc.sc.egov.usda.gov/nwcc/site?sitenum=809
   - Stevens Pass: https://wcc.sc.egov.usda.gov/nwcc/site?sitenum=957
   - Snoqualmie: https://wcc.sc.egov.usda.gov/nwcc/site?sitenum=910
   - Crystal Mountain: https://wcc.sc.egov.usda.gov/nwcc/site?sitenum=623
   - White Pass: https://wcc.sc.egov.usda.gov/nwcc/site?sitenum=968

2. **Save Observation Data**:
   Create JSON file in `data/observations/` (e.g., `baker_2025-01.json`):
   ```json
   {
     "area": "baker",
     "observations": [
       {
         "date": "2025-01-17",
         "data": {
           "snowfall_measured": 18,
           "temp_base_sat": 24,
           "temp_base_sun": 20,
           "source": "SNOTEL Site 809"
         },
         "collected_at": "2025-01-17T12:00:00"
       }
     ]
   }
   ```

### Step 3: Verify Your Forecast

After collecting observations:

```bash
python3 scripts/verify_forecasts.py
```

This will:
- Compare your forecasts to actual observations
- Calculate error metrics
- Generate verification reports in `data/verification_reports/`

### Step 4: Update Verification Page

Manually update `verification.html` with the results, or create a script to auto-generate the HTML from verification reports.

Example table entry:
```html
<tr>
    <td>Jan 15, 2025</td>
    <td>Mt. Baker</td>
    <td>20" (14-24")</td>
    <td>18"</td>
    <td>-2" (-10%)</td>
    <td><span class="accuracy-good">✓ Within Range</span></td>
</tr>
```

## Data Sources

### SNOTEL (NRCS)
- **Website:** https://wcc.sc.egov.usda.gov/
- **Data:** Snow depth, temperature, precipitation
- **Frequency:** Daily (updates every few hours)
- **API:** Available for programmatic access

### NWS (National Weather Service)
- **Website:** https://www.weather.gov/
- **API:** https://www.weather.gov/documentation/services-web-api
- **Data:** Temperature, precipitation, wind

### Resort Reports
- Check individual ski resort websites for official snow reports
- Usually available 24-48 hours after the event

## Automation Ideas

### Option 1: Manual (Simplest)
- Copy template JSON files
- Fill in forecast and observation data by hand
- Run verification script weekly

### Option 2: Semi-Automated
- Use Python scripts to fetch SNOTEL data automatically
- Manual entry of forecasts
- Automated verification

### Option 3: Fully Automated (Advanced)
- Web scraping or API calls for all data sources
- Automated forecast parsing from blog posts
- Scheduled verification runs
- Auto-generated verification page updates

## Example Python Code for SNOTEL

```python
import requests
import json
from datetime import datetime, timedelta

def fetch_snotel_data(site_id, start_date, end_date):
    """Fetch data from SNOTEL site"""
    base_url = "https://wcc.sc.egov.usda.gov/reportGenerator/view_csv/"
    url = f"{base_url}customSingleStationReport/daily/{site_id}:WA:SNTL|id=%22%22|name/{start_date},{end_date}/SNWD::value,TOBS::value,PREC::value"
    
    response = requests.get(url)
    if response.status_code == 200:
        # Parse CSV data
        lines = response.text.strip().split('\n')
        # Skip header lines (typically first 60+ lines are metadata)
        data_start = 0
        for i, line in enumerate(lines):
            if line.startswith('Date,'):
                data_start = i + 1
                break
        
        observations = []
        for line in lines[data_start:]:
            if line.strip():
                parts = line.split(',')
                if len(parts) >= 4:
                    observations.append({
                        'date': parts[0],
                        'snow_depth': float(parts[1]) if parts[1] else None,
                        'temp_obs': float(parts[2]) if parts[2] else None,
                        'precip': float(parts[3]) if parts[3] else None
                    })
        
        return observations
    return None

# Example usage:
# data = fetch_snotel_data('809', '2025-01-16', '2025-01-17')
# print(json.dumps(data, indent=2))
```

## Tips for Better Verification

1. **Be Consistent**: Use the same data sources for all verifications
2. **Document Sources**: Always note where observation data came from
3. **Account for Timing**: SNOTEL data may not capture all snowfall if it melts quickly
4. **Multiple Sources**: Cross-reference resort reports with SNOTEL when possible
5. **Learn from Errors**: Look for patterns in over/under-forecasting
6. **Be Honest**: Don't cherry-pick data - include all forecasts

## Metrics Explained

### Mean Absolute Error (MAE)
Average of the absolute differences between forecast and actual:
- `MAE = mean(|forecast - actual|)`
- Lower is better
- Units match what you're measuring (inches, degrees, etc.)

### Within Range Percentage
How often actual values fall within your forecast range:
- `Within Range % = (count of hits / total forecasts) × 100`
- Target: >70% is good for snowfall forecasts

### Percentage Error
Relative error compared to actual value:
- `% Error = (|forecast - actual| / actual) × 100`
- Useful for comparing different magnitudes

## Troubleshooting

**Q: SNOTEL site shows no new data**
- Wait 24-48 hours after an event for data to be complete
- Some sites have transmission issues in heavy snow
- Use nearby sites as backup

**Q: Verification script shows no matching observations**
- Check date formats are consistent (YYYY-MM-DD)
- Ensure observation files are in correct directory
- Verify JSON formatting is valid

**Q: Figures not showing in blog posts**
- Check relative paths are correct (../assets/images/)
- Ensure images are in assets/images/ directory
- Verify image file names match HTML references

## Next Steps

1. Run your first forecast and save the data
2. Collect observations after the weekend
3. Run verification and review results
4. Update verification.html with findings
5. Use insights to improve next forecast!

Remember: The goal is continuous improvement, not perfection!
