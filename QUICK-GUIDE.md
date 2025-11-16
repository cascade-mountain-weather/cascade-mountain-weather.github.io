# Quick Guide to Posting

## Fast Workflow for Creating a New Weekend Forecast

### 1. Create New Post (Copy Template)
```bash
cp posts/TEMPLATE-post.html posts/2025-MM-DD-weekend-forecast.html
```

### 2. Edit New Post
Open the new file and search/replace `[UPDATE]` markers with your forecast data:
- Title and dates in `<title>` and `<h1>`
- Weekend summary box
- Temperature data for all ski areas
- Precipitation amounts and timing
- Freezing level information
- Wind conditions
- Extended outlook
- Your recommendations
- Safety notes

### 3. Add Weather Images
```bash
# Create images directory if needed
mkdir -p posts/images

# Save your weather charts/maps there
# Replace placeholder divs with:
# <img src="images/your-image.png" alt="Description">
```

### 4. Update Homepage
Edit `index.html`:
- Update "Latest Weekend Forecast" section (around line 28)
- Add to "Recent Forecasts" list (around line 66)

### 5. Update Archive
Edit `posts/archive.html`:
- Add your new post to the appropriate month section

### 6. Commit & Push
```bash
git add .
git commit -m "Add weekend forecast for [dates]"
git push
```

## Quick Checklist
- [ ] Created new post from template
- [ ] Updated all [UPDATE] markers
- [ ] Added weather images/figures
- [ ] Updated index.html (latest post + recent list)
- [ ] Updated archive.html
- [ ] Committed and pushed

## Common Weather Resources
- **NOAA Models**: https://www.weather.gov/
- **Windy**: https://www.windy.com
- **Tropical Tidbits**: https://www.tropicaltidbits.com/
- **Pivotal Weather**: https://www.pivotalweather.com/
- **NWAC**: https://nwac.us
- **WSDOT**: https://wsdot.wa.gov/travel

## File Naming Convention
Use format: `YYYY-MM-DD-descriptive-title.html`

Examples:
- `2025-01-22-weekend-forecast.html`
- `2025-02-05-powder-weekend.html`
- `2025-03-12-spring-skiing.html`

## Tips
- Post Thursday or Friday for weekend forecasts
- Be specific with snowfall amounts and timing
- Compare ski areas to help readers choose
- Include confidence levels if uncertain
- Add personality - make it fun to read!
