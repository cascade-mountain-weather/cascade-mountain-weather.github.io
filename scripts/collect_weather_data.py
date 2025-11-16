#!/usr/bin/env python3
"""
Weather Data Scraper and Storage Script
Fetches actual weather data from various sources for forecast verification
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# Note: This is a template. You'll need to install required packages:
# pip install requests beautifulsoup4 pandas

def fetch_snotel_data(site_id, start_date, end_date):
    """
    Fetch SNOTEL data (snow depth, temperature, precipitation)
    
    Args:
        site_id: SNOTEL site ID (e.g., '957' for Stevens Pass)
        start_date: Start date as string 'YYYY-MM-DD'
        end_date: End date as string 'YYYY-MM-DD'
    
    Returns:
        dict: Weather observations
    """
    # SNOTEL sites near WA ski areas:
    # Mt. Baker Area: 809 (Mt. Baker)
    # Stevens Pass: 957 (Stevens Pass)
    # Snoqualmie: 910 (Snoqualmie Pass)
    # Crystal Mountain: 623 (Crystal Mountain)
    # White Pass: 968 (White Pass)
    
    # Example using NRCS SNOTEL API
    # URL format: https://wcc.sc.egov.usda.gov/reportGenerator/view_csv/customSingleStationReport/daily/
    
    base_url = "https://wcc.sc.egov.usda.gov/reportGenerator/view_csv/customSingleStationReport/daily/"
    params = f"{site_id}:WA:SNTL|id=%22%22|name/{start_date},{end_date}/SNWD::value,TOBS::value,TMAX::value,TMIN::value,PREC::value"
    
    # For now, return template structure
    # In real use, you'd use requests.get() to fetch actual data
    return {
        'site_id': site_id,
        'start_date': start_date,
        'end_date': end_date,
        'observations': [
            # Example format:
            # {'date': '2025-01-16', 'snow_depth': 85, 'temp_obs': 22, 'temp_max': 28, 'temp_min': 18, 'precip': 1.2}
        ],
        'url': base_url + params
    }

def fetch_nws_data(station_id, start_date, end_date):
    """
    Fetch NWS/NOAA weather station data
    
    Args:
        station_id: NWS station ID
        start_date: Start date as string 'YYYY-MM-DD'
        end_date: End date as string 'YYYY-MM-DD'
    
    Returns:
        dict: Weather observations
    """
    # Example stations:
    # KBLI - Bellingham (near Baker)
    # KPAE - Everett/Paine Field
    # KSEA - Seattle-Tacoma
    
    return {
        'station_id': station_id,
        'start_date': start_date,
        'end_date': end_date,
        'observations': [],
        'note': 'Use NWS API: https://www.weather.gov/documentation/services-web-api'
    }

def save_observation_data(data, area_name, date):
    """
    Save observation data to JSON file
    
    Args:
        data: Dictionary with observation data
        area_name: Ski area name (e.g., 'baker', 'stevens')
        date: Date string 'YYYY-MM-DD'
    """
    data_dir = Path('data/observations')
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Organize by year and month
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    year_month = date_obj.strftime('%Y-%m')
    
    filename = data_dir / f"{area_name}_{year_month}.json"
    
    # Load existing data if file exists
    if filename.exists():
        with open(filename, 'r') as f:
            existing_data = json.load(f)
    else:
        existing_data = {'area': area_name, 'observations': []}
    
    # Append new data
    existing_data['observations'].append({
        'date': date,
        'data': data,
        'collected_at': datetime.now().isoformat()
    })
    
    # Save updated data
    with open(filename, 'w') as f:
        json.dump(existing_data, f, indent=2)
    
    print(f"Saved observation data to {filename}")

def save_forecast_data(forecast_dict, forecast_date):
    """
    Save forecast data for later verification
    
    Args:
        forecast_dict: Dictionary with forecast details
        forecast_date: Date the forecast was made 'YYYY-MM-DD'
    """
    data_dir = Path('data/forecasts')
    data_dir.mkdir(parents=True, exist_ok=True)
    
    filename = data_dir / f"forecast_{forecast_date}.json"
    
    with open(filename, 'w') as f:
        json.dump(forecast_dict, f, indent=2)
    
    print(f"Saved forecast data to {filename}")

def create_forecast_entry(post_date, valid_dates, ski_areas_forecast):
    """
    Create a forecast entry for verification
    
    Args:
        post_date: Date forecast was posted 'YYYY-MM-DD'
        valid_dates: List of dates forecast is valid for
        ski_areas_forecast: Dict with forecasts for each area
    
    Returns:
        dict: Formatted forecast entry
    """
    return {
        'post_date': post_date,
        'valid_dates': valid_dates,
        'areas': ski_areas_forecast,
        'created_at': datetime.now().isoformat()
    }

def example_usage():
    """Example of how to use these functions"""
    
    # Example: Save a forecast
    forecast = create_forecast_entry(
        post_date='2025-01-15',
        valid_dates=['2025-01-16', '2025-01-17'],
        ski_areas_forecast={
            'baker': {
                'snowfall_total': {'forecast': 20, 'range': [14, 24], 'units': 'inches'},
                'temp_base': {'sat': 25, 'sun': 22, 'units': 'F'},
                'temp_summit': {'sat': 15, 'sun': 12, 'units': 'F'}
            },
            'stevens': {
                'snowfall_total': {'forecast': 12, 'range': [8, 16], 'units': 'inches'},
                'temp_base': {'sat': 28, 'sun': 24, 'units': 'F'},
                'temp_summit': {'sat': 18, 'sun': 14, 'units': 'F'}
            },
            'crystal': {
                'snowfall_total': {'forecast': 9, 'range': [6, 12], 'units': 'inches'},
                'temp_base': {'sat': 26, 'sun': 24, 'units': 'F'},
                'temp_summit': {'sat': 10, 'sun': 8, 'units': 'F'}
            }
        }
    )
    save_forecast_data(forecast, '2025-01-15')
    
    # Example: Fetch and save observations (after the weekend)
    # This would typically run on Monday after the forecast weekend
    print("\nExample: Collecting observations after forecast weekend...")
    
    # Collect data for verification
    # In real use, you'd call the actual fetch functions
    obs_data_baker = {
        'snowfall_measured': 18,
        'temp_base_sat': 24,
        'temp_base_sun': 20,
        'source': 'SNOTEL Site 809'
    }
    save_observation_data(obs_data_baker, 'baker', '2025-01-17')

if __name__ == '__main__':
    print("Weather Data Collection Script")
    print("=" * 50)
    print("\nThis script helps you:")
    print("1. Save forecast data for verification")
    print("2. Collect actual weather observations")
    print("3. Store data for accuracy analysis")
    print("\nRunning example usage...\n")
    
    example_usage()
    
    print("\n" + "=" * 50)
    print("To use this script:")
    print("1. Install requirements: pip install requests beautifulsoup4 pandas")
    print("2. Customize the fetch functions for your data sources")
    print("3. Run after making a forecast and after the forecast period")
    print("\nData will be stored in:")
    print("  - data/forecasts/    : Your forecast predictions")
    print("  - data/observations/ : Actual observed weather")
