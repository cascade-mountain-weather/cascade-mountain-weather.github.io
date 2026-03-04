# PWA (Progressive Web App) Installation Guide

Your Cascade Mountain Weather website is now a Progressive Web App! Users can install it on their devices for an app-like experience.

## For Users: How to Install

### On iPhone/iPad (Safari)
1. Visit https://www.cascademountainweather.com in Safari
2. Tap the **Share** button (square with arrow pointing up)
3. Scroll down and tap **"Add to Home Screen"**
4. Tap **"Add"** in the top right
5. The app icon will appear on your home screen

### On Android (Chrome)
1. Visit https://www.cascademountainweather.com in Chrome
2. Tap the **menu** (three dots) in the top right
3. Tap **"Add to Home screen"** or **"Install app"**
4. Tap **"Install"** or **"Add"**
5. The app icon will appear on your home screen

### On Desktop (Chrome, Edge, or other Chromium browsers)
1. Visit https://www.cascademountainweather.com
2. Look for the **install icon** (⊕ or computer screen icon) in the address bar
3. Click it and then click **"Install"**
4. The app will open in its own window

## What Features Does the App Have?

✅ **Offline Access** - View cached forecasts even without internet  
✅ **Home Screen Icon** - Quick access like a native app  
✅ **Standalone Mode** - Opens without browser UI  
✅ **App Shortcuts** - Long-press the icon for quick links (Latest Forecast, Current Weather, Archive)

## For Developers: Missing Icon Files

To complete the PWA setup, you need to create PNG icons from the existing SVG:

**Required files:**
- `/assets/images/icon-192.png` (192x192 pixels)
- `/assets/images/icon-512.png` (512x512 pixels)

**Quick creation:**
1. Open `assets/images/favicon.svg` in an image editor
2. Export as PNG at 192x192 and 512x512 resolutions
3. Save to the paths above

Alternatively, update `manifest.json` to use only the SVG icon if you prefer to keep it simple.

## Files Added

- `/manifest.json` - PWA configuration
- `/service-worker.js` - Offline caching logic
- Updated HTML files to link manifest and register service worker

## Customization

Edit `manifest.json` to change:
- App name, colors, icons
- Start URL and display mode
- App shortcuts

Edit `service-worker.js` to change:
- Which files are cached
- Caching strategy (currently: network-first with cache fallback)
