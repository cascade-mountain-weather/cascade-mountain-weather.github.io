# Data Directory

This directory stores forecast and observation data for verification purposes.

## Directory Structure

```
data/
├── forecasts/              # Your forecast predictions (saved as JSON)
├── observations/           # Actual weather observations (saved as JSON)
└── verification_reports/   # Generated verification reports (TXT)
```

## Purpose

- **Track forecast accuracy** over time
- **Store structured data** for analysis
- **Enable automated verification** with scripts
- **Build historical record** of forecasts and outcomes

## File Formats

### Forecasts (`forecasts/forecast_YYYY-MM-DD.json`)

Example: `forecast_2025-01-15.json`
```json
{
  "post_date": "2025-01-15",
  "valid_dates": ["2025-01-16", "2025-01-17"],
  "areas": {
    "baker": {
      "snowfall_total": {
        "forecast": 20,
        "range": [14, 24],
        "units": "inches"
      },
      "temp_base": {"sat": 25, "sun": 22, "units": "F"},
      "temp_summit": {"sat": 15, "sun": 12, "units": "F"}
    }
  }
}
```

### Observations (`observations/AREA_YYYY-MM.json`)

Example: `baker_2025-01.json`
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

## Usage

See `VERIFICATION-GUIDE.md` in the root directory for detailed instructions on:
- Creating forecast data files
- Collecting observation data
- Running verification scripts
- Generating reports

## Git Tracking

These directories and their contents are tracked in git to maintain a complete history of forecasts and verification. If you have very large datasets, consider adding specific exclusions to `.gitignore`.
