# Cascski Alpine Insights

A simple, easy-to-maintain weather blog focused on Washington state ski area forecasts. Provides weekly weekend forecasts for Mt. Baker, Stevens Pass, Snoqualmie Pass, Blewett Pass, Crystal Mountain, and White Pass.

## 🎿 Features

- **Weekly Weekend Forecasts**: Detailed predictions for the best skiing conditions
- **Multiple Forecast Sections**: 
  - Temperature forecasts
  - Precipitation & snowfall
  - Freezing level analysis
  - Wind conditions
  - Extended 7-10 day outlook
- **Ski Area Focus**: Coverage of 6 major Washington ski areas
- **Easy Navigation**: Clean, responsive design
- **Quick Updates**: Simple HTML structure for fast posting

## 📁 Project Structure

```
Dawg-Winter-Weather-Blog/
├── index.html              # Homepage
├── style.css               # Main stylesheet
├── verification.html       # Forecast verification page
├── posts/                  # Blog posts directory
│   ├── archive.html        # Archive page
│   ├── post-style.css      # Post-specific styles
│   ├── images/             # Weather images/figures (create as needed)
│   └── YYYY-MM-DD-title.html  # Individual blog posts
├── assets/                 # Images for blog posts
│   └── images/             # Forecast figures (can be overwritten weekly)
│       └── archive/        # Optional: Dated copies of figures
├── data/                   # Verification data
│   ├── forecasts/          # Your forecast predictions (JSON)
│   ├── observations/       # Actual weather data (JSON)
│   └── verification_reports/ # Generated verification reports
├── scripts/                # Python scripts for data & verification
│   ├── collect_weather_data.py
│   ├── verify_forecasts.py
│   └── manage_figures.py
└── README.md               # This file
```

## 🚀 Quick Start Guide

### Viewing the Blog

1. **Locally**: Open `index.html` in any web browser
2. **GitHub Pages** (Recommended):
   - Go to repository Settings → Pages
   - Under "Source", select `main` branch
   - Click Save
   - Your blog will be available at: `https://[username].github.io/Dawg-Winter-Weather-Blog/`

### Using the Forecast Verification System

The blog includes a built-in verification system to track forecast accuracy:

1. **Save your forecasts** as JSON in `data/forecasts/`
2. **Collect actual observations** from SNOTEL/NWS after the forecast period
3. **Run verification scripts** to compare and generate accuracy reports
4. **Update the verification page** with results

See [VERIFICATION-GUIDE.md](VERIFICATION-GUIDE.md) for detailed instructions.

### Creating a New Blog Post

1. **Copy the Template**
   ```bash
   cp posts/2025-01-15-weekend-forecast.html posts/YYYY-MM-DD-your-title.html
   ```
   Use format: `YYYY-MM-DD-descriptive-title.html`

2. **Edit the New Post**
   - Update the `<title>` tag
   - Update the post header (title and dates)
   - Fill in each forecast section:
     - Temperature forecasts for each ski area
     - Precipitation amounts and timing
     - Freezing level information
     - Wind speeds and direction
     - Extended outlook
   - Update your recommendations
   - Modify safety notes as needed

3. **Add Weather Images/Figures**
   - Create `posts/images/` directory if it doesn't exist
   - Save your weather charts, maps, or model outputs there
   - Replace the placeholder `<div class="figure-placeholder">` sections with:
     ```html
     <img src="images/your-image.png" alt="Description">
     ```

4. **Update the Homepage**
   - Edit `index.html`
   - Update the "Latest Weekend Forecast" section with your new post info
   - Add link to "Recent Forecasts" list

5. **Update the Archive**
   - Edit `posts/archive.html`
   - Add your new post to the appropriate month section

### Example Workflow

```bash
# 1. Create new post file
cp posts/2025-01-15-weekend-forecast.html posts/2025-01-22-weekend-forecast.html

# 2. Edit the file with your forecast data
# (Use your favorite text editor)

# 3. Add any weather images
mkdir -p posts/images
# Save your weather maps/charts to posts/images/

# 4. Update index.html and posts/archive.html with links to new post

# 5. Commit and push
git add .
git commit -m "Add weekend forecast for Jan 22-24"
git push
```

## 📊 Adding Weather Figures

The blog is designed to easily incorporate weather images from various sources:

### Figure Storage Options

1. **assets/images/** - Use for current forecast figures that you'll overwrite each week
   - Standard names: `temp_forecast.png`, `precip_forecast.png`, etc.
   - Easy to reference: `<img src="../assets/images/temp_forecast.png">`
   - Old figures are automatically replaced with new ones

2. **assets/images/archive/** - Optional dated copies for historical reference
   - Use for figures you want to preserve
   - Name with date: `2025-01-15_temp_forecast.png`

3. **posts/images/** - For figures specific to individual posts
   - Won't be overwritten
   - Good for unique analysis or special events

### Recommended Weather Resources

- **NOAA/NWS**: Weather models, radar, forecasts
- **Tropical Tidbits**: Model outputs, analysis tools
- **Windy.com**: Interactive weather maps
- **Mountain Weather Forecast**: Specialized mountain forecasts
- **NWAC**: Avalanche and mountain weather data
- **Pivotal Weather**: Model comparison tools

### Image Guidelines

1. **Save screenshots** from weather resources
2. **Crop and optimize** images for web (consider using PNG or JPEG)
3. **Name descriptively**: `temp-chart-jan15.png`, `precip-map-weekend.png`
4. **Store in** `posts/images/` directory
5. **Add to post** with `<img>` tags

## 🎨 Customization

### Styling
- Modify `style.css` for site-wide changes
- Modify `posts/post-style.css` for blog post styling
- Color scheme uses blues (ski/winter theme)

### Adding Ski Areas
To add more ski areas:
1. Edit `index.html` - add to the ski areas grid
2. Include in your forecast posts

### Changing Layout
The blog uses simple HTML/CSS - no JavaScript framework required. Easy to customize!

## 📱 Mobile Friendly

The blog is fully responsive and works great on phones and tablets. The navigation menu adapts for smaller screens.

## ⚠️ Important Notes

- **Disclaimer**: This is for educational/informational purposes
- **Always**: Check official sources and avalanche forecasts
- **Road Conditions**: Link to WSDOT for current pass conditions
- **Avalanche Info**: Link to NWAC for avalanche forecasts

## 🔗 Useful Links

- [NWAC - Northwest Avalanche Center](https://nwac.us)
- [WSDOT - Mountain Pass Reports](https://wsdot.wa.gov/travel)
- [NWS Seattle](https://www.weather.gov/sew/)
- [Mountain Weather Forecast](https://www.mountain-forecast.com/)

## 📝 Tips for Writing Forecasts

1. **Post on Thursday or Friday** for weekend forecasts
2. **Be specific** about timing and amounts
3. **Compare ski areas** to help readers choose
4. **Include confidence levels** when uncertain
5. **Update if conditions change** significantly
6. **Add personality** - make it engaging!

## 🤝 Contributing

This is a personal blog, but feel free to fork and create your own version for different regions!

## 📄 License

See LICENSE file for details.

---

**Have fun and stay safe in the mountains!** 🎿❄️
