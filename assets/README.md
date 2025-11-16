# Assets Directory

This directory stores weather figures and images used in blog posts.

## Directory Structure

```
assets/
└── images/              # Current forecast figures
    └── archive/         # Dated copies (optional)
```

## Usage

### Current Forecast Figures (`images/`)

Use standard filenames that you'll **overwrite each week**:

- `temp_forecast.png` - Temperature forecast map/chart
- `precip_forecast.png` - Precipitation forecast
- `freezing_level.png` - Freezing level chart
- `wind_forecast.png` - Wind speed/direction map
- `extended_outlook.png` - Extended forecast chart
- `current_radar.png` - Current radar/satellite
- `snow_depth_chart.png` - Snow depth trends

### Archive (`images/archive/`)

Optionally save dated copies for historical reference:

- `2025-01-15_temp_forecast.png`
- `2025-01-15_precip_forecast.png`

Note: Archive images are excluded from git tracking by default (see `.gitignore`)

## Workflow

1. **Download/screenshot weather figures** from your favorite sources
2. **Save with standard names** to `assets/images/`
3. **Reference in blog posts**:
   ```html
   <img src="../assets/images/temp_forecast.png" alt="Temperature Forecast">
   ```
4. **Next week**, simply overwrite with new figures!

## Benefits

- **Consistent naming** makes updates easy
- **Simple references** in blog post HTML
- **No accumulation** of old files (unless archived)
- **Fast workflow** for weekly updates

## Tips

- Keep images reasonably sized (< 500KB when possible)
- Use descriptive alt text for accessibility
- PNG works great for charts/maps
- JPEG works for photos/satellite imagery

See `scripts/manage_figures.py` for helper functions to organize figures.
