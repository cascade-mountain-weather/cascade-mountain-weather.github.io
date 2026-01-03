#!/usr/bin/env python3
"""
Forecast Evaluation Script
Compares forecasts against actual observations and generates evaluation reports
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import statistics
import pandas as pd
from metloom.pointdata import SnotelPointData
from metloom.variables import SnotelVariables
import shutil
import re
from bs4 import BeautifulSoup
import sys
import numpy as np

def load_forecast(site, output_dir):
    """Load forecast data for a specific date"""
    # check if today is a Thursday
    saved_path = output_dir / f"{site}.csv"
    
    if site == "Crystal" or site == "Paradise":
        return None  # No forecast available for these sites
    
    if datetime.today().weekday() != 4:  # 3 corresponds to Thursday
        print("Today is not Thursday, using existing forecast file if available.")
        if site == 'TBLEW':
            saved_path = output_dir / "Blewett Pass.csv"
        elif site == 'HURW1':
            saved_path = output_dir / "Hurricane Ridge.csv"
        return saved_path  # Only download on Thursdays
    
    # delete file to replace it
    if os.path.exists(saved_path):
        os.remove(saved_path)
    if site =="Blewett Pass":
        site = "TBLEW"
    if site == "Hurricane Ridge":
        site = "HURW1"
    
    options = webdriver.ChromeOptions()
    options.add_experimental_option("prefs", {
        "download.default_directory": str(output_dir.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1
    })

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    driver.get(
        f"https://apps.gsl.noaa.gov/nbmviewer/?col=2&hgt=1&obs=false&fontsize=1&location={site.replace(' ','+')}&selectedgroup=Observed&darkmode=on&graph=fa-chart-bar&probfield=Tmax&proboperator=%3E%3D&probvalue=40&colorfriendly=false&whiskers=false&boxes=true&median=false&det=true&tz=local"
    )

    time.sleep(2)

    # Locate the download button
    button = driver.find_element(By.CSS_SELECTOR, "button.fa-download")
    button.click()

    # Wait for download to finish
    time.sleep(8)

    driver.quit()

    # rename the downloaded file to the desired name for TBLEW and HURW1 to Blewett Pass and Hurricane Ridge
    if site == "TBLEW":
        downloaded_file = output_dir / "TBLEW.csv"
        new_name = output_dir / "Blewett Pass.csv"
        if downloaded_file.exists():
            downloaded_file.rename(new_name)
    if site == "HURW1":
        downloaded_file = output_dir / "HURW1.csv"
        new_name = output_dir / "Hurricane Ridge.csv"
        if downloaded_file.exists():
            downloaded_file.rename(new_name)
    return saved_path

def get_forecast_file(site, output_dir):
    """
    Verify a forecast against observations
    
    Args:
        forecast_date: Date of forecast to verify 'YYYY-MM-DD'
    
    Returns:
        dict: Evaluation results
    """
    saved_path = load_forecast(site, output_dir)
    # get date of most recent past thursday
    forecast_date = (datetime.today() - timedelta(days=(datetime.today().weekday() - 3) % 7)).strftime('%Y-%m-%d')
    
    # copy the template file if it doesnt exist:
    if not os.path.exists(os.path.join(output_dir, f'eval_forecast_{forecast_date}.json')):
        shutil.copyfile(os.path.join(output_dir, 'eval_forecast_template.json'),
                        os.path.join(output_dir, f'eval_forecast_{forecast_date}.json'))
    # open the file 
    with open(os.path.join(output_dir,  f'eval_forecast_{forecast_date}.json'), 'r') as f:
            eval_forecast_data = json.load(f)
    if saved_path is None:
        # If we could not locate or download a forecast file, bail out gracefully
        print(f"No forecast file found for {site} at {saved_path}. Skipping.")
        # get date for m
        # add site manually to avoid KeyError later and fill with all null values
        eval_forecast_data['areas'][site]['accumulated_snowfall']['nbm_forecast']['deterministic'] = None
    
        eval_forecast_data['areas'][site]['accumulated_snowfall']['nbm_forecast']['ensemble_iqr_range'] = [None, None]
        # add snow level info
        eval_forecast_data['areas'][site]['snow_level']['nbm_forecast']['weekend_min_max'] = [None, None]
    else:
        nbm_df = pd.read_csv(saved_path)
        nbm_df['ValidTime'] = pd.to_datetime(nbm_df['ValidTime'], format="%Y%m%d%H")
        nbm_df = nbm_df.set_index('ValidTime')

        if site == "HURW1":
                site = "Hurricane Ridge"
        elif site == "TBLEW":
                site = "Blewett Pass"
        elif site == "Mt. Baker Ski Area":
                site = "Mt. Baker"
        # get start data of forecast
        dates = slice(nbm_df.index[0], nbm_df.index[0] + pd.Timedelta(hours=96))
        # add 72-hr snowfall totals
        print("Calculating snowfall totals...")
        # update the date 
        eval_forecast_data['post_date'] = forecast_date
        eval_forecast_data['valid_dates'] = [str(pd.to_datetime(forecast_date) + pd.Timedelta(hours=24)), str((pd.to_datetime(forecast_date) + pd.Timedelta(hours=96)).date())]
        eval_forecast_data['areas'][site]['accumulated_snowfall']['nbm_forecast']['deterministic'] = round((nbm_df.loc[dates, 'ASNOW6hr_surface']*4*10).sum(), 1)
        
        eval_forecast_data['areas'][site]['accumulated_snowfall']['nbm_forecast']['ensemble_iqr_range'] = [round((nbm_df.loc[dates, 'ASNOW6hr_surface_25% level']*4*10).sum(), 1),
                                                            round((nbm_df.loc[dates, 'ASNOW6hr_surface_75% level']*4*10).sum(), 1)]
        # add snow level info
        min_snow_level = nbm_df['SNOWLVL_surface_50% level'].loc[dates].min() * 3.28084  # convert to feet
        max_snow_level = nbm_df['SNOWLVL_surface_50% level'].loc[dates].max() * 3.28084  # convert to feet
        eval_forecast_data['areas'][site]['snow_level']['nbm_forecast']['weekend_min_max'] = [round(min_snow_level, 1), round(max_snow_level, 1)]
    
    # update the file
    with open(os.path.join(output_dir, f'eval_forecast_{forecast_date}.json'), 'w') as f:
        json.dump(eval_forecast_data, f, indent=4)
    print(f"Updated forecast data for {site} on {forecast_date}")
    outfile = os.path.join(output_dir, f'eval_forecast_{forecast_date}.json')
    print(outfile, forecast_date)
    return Path(outfile), pd.to_datetime(forecast_date)

def new_snow_estimate(swe, temp):
    """Estimate snow density based on SWE and temperature using a simple empirical formula."""
    # convert temp to Kelvin
    temp = ((temp - 32) * 5.0/9.0) + 273.15
    # convert swe to m
    swe = swe * 25.4
    # Simple empirical formula for snow density estimation
    if temp <= 258.16:
        density = .50  # Very light, fluffy snow
    elif temp > 273.16:
        density = .250  # Wet, heavy snow
    else:
        density = 0.05 + 0.0017*((temp-258.16)**1.5) 
    new_snow_depth = ((swe) / density) 
    return round(new_snow_depth/25.4, 1)

def load_observations(site, fx_date, min_snow_level=None, max_snow_level=None):
    """Load observation data for an area and month"""
    start_date = fx_date + pd.Timedelta(days=1)
    end_date = start_date + pd.Timedelta(days=3)
    sites ={
    "Mt. Baker" : "909:WA:SNTL",
    "Stevens Pass" : "791:WA:SNTL",
    "Blewett Pass" : "352:WA:SNTL",
    "Snoqualmie Pass" : "672:WA:SNTL",
    "Crystal" : "418:WA:SNTL",
    "Paradise" : "679:WA:SNTL",
    "White Pass" : "863:WA:SNTL",
    "Hurricane Ridge" : "974:WA:SNTL",
    "Washington Pass" : "515:WA:SNTL"
    }
    observation_output_dict = {"areas": {}, 
                           "start_date": str(start_date.date()),
                            "end_date": str(end_date.date())}
    print(f"Getting observations for {site} from {sites[site]}")
    # get snotel data
    snotel_point = SnotelPointData(sites[site], site)
    if site == 'Mt. Baker':
        snotel_point_2 = SnotelPointData("998:WA:SNTL", "Easy Pass")
    try:
        sntl_df = snotel_point.get_daily_data(start_date, end_date, [snotel_point.ALLOWED_VARIABLES.SNOWDEPTH,
                                                                snotel_point.ALLOWED_VARIABLES.SWE,
                                                                snotel_point.ALLOWED_VARIABLES.TEMPMAX,
                                                                snotel_point.ALLOWED_VARIABLES.TEMPMIN,
                                                                snotel_point.ALLOWED_VARIABLES.TEMPAVG,
                                                                snotel_point.ALLOWED_VARIABLES.PRECIPITATION])
        if site == 'Mt. Baker':
            sntl_df_2 = snotel_point_2.get_daily_data(start_date, end_date, [snotel_point_2.ALLOWED_VARIABLES.SNOWDEPTH,
                                                                    snotel_point_2.ALLOWED_VARIABLES.SWE,
                                                                    snotel_point_2.ALLOWED_VARIABLES.TEMPMAX,
                                                                    snotel_point_2.ALLOWED_VARIABLES.TEMPMIN,
                                                                    snotel_point_2.ALLOWED_VARIABLES.PRECIPITATION])
            # average the two dataframes
            # reset_index to combine
            reset_sntl_df = sntl_df.reset_index().set_index('datetime', drop=True)[['SNOWDEPTH','SWE',]]
            reset_sntl_df2 = sntl_df_2.reset_index().set_index('datetime', drop=True)[['SNOWDEPTH','SWE',]]
            sntl_df = pd.concat([reset_sntl_df, reset_sntl_df2]).groupby(level=0).mean()
    except:
        raise Exception(f"Could not retrieve Snotel data for {site} ({sites[site]}) between {start_date.date()} and {end_date.date()}.")
        return None 
    print("Snotel data retrieved.")
    # get the cumulative maximum of consecutive swe values
    # drop any negative numbers
    sntl_df = sntl_df[sntl_df['SWE'] >= 0]
    # remove any really big numbers (> 200 inches)
    sntl_df = sntl_df[sntl_df['SWE'] <= 200]
    swe_change = sntl_df['SWE'].diff().clip(lower=0).sum()
    # estimate new snow depth from swe and temperature
    if "MAX AIR TEMP" and "MIN AIR TEMP" not in sntl_df.columns:
        print("Temperature data not available for snow depth estimation.")
        max_snow_depth_estimate_swe = swe_change / 0.08 # assume 10% density
        min_snow_depth_estimate_swe = swe_change / 0.25 # assume 25% density
        snowdepth_change_swe = swe_change/0.15

        print("assumed snow depth change:", snowdepth_change_swe)
    else:        
        if "PRECIPITATION" in sntl_df.columns:
            # lapse assumption:
            lapse = 1 # feet
            feet_to_meters = 3.28084
            lapse_rate_per_C = 6
            precip_total = sntl_df['PRECIPITATION'].diff().clip(lower=0).sum()
            # assume lapse rate for temperature
            lapse_rate_F_1000ft = ((lapse_rate_per_C*9/5)) / feet_to_meters * lapse 
            lapse_adjusted_temp = sntl_df['AVG AIR TEMP'] - lapse_rate_F_1000ft
            if (lapse_adjusted_temp.mean() < 32) and (sntl_df['MIN AIR TEMP'].mean() > 34):
                swe_change = precip_total
                print("using precip based swe change:", swe_change)
            
            max_snow_depth_estimate_swe = new_snow_estimate(swe_change, sntl_df['MIN AIR TEMP'].min())
            min_snow_depth_estimate_swe = new_snow_estimate(swe_change, sntl_df['MAX AIR TEMP'].max())
            snowdepth_change_swe = np.mean([max_snow_depth_estimate_swe, min_snow_depth_estimate_swe])
            print("snowdepth change from swe and temp:", snowdepth_change_swe)
            

    if ("SNOWDEPTH" in sntl_df.columns) and not (sntl_df['SNOWDEPTH'].isnull().all()):
        sntl_df = sntl_df[sntl_df['SNOWDEPTH'] >= 0]
        sntl_df = sntl_df[sntl_df['SNOWDEPTH'] <= 1000]
        max_snow_depth_estimate = sntl_df['SNOWDEPTH'].diff().clip(lower=0).sum()
        # settlement rate
        density = swe_change / max_snow_depth_estimate
        # density change  per 
        if density < 0.25:
            density += 0.01 * 24 * 4 / 2.54
            # max density is 0.25
            if density > 0.25:
                density = 0.25
        min_snow_depth_estimate = swe_change / density
        snowdepth_change = np.mean([min_snow_depth_estimate, max_snow_depth_estimate])

        if snowdepth_change < snowdepth_change_swe*0.8:
            snowdepth_change = snowdepth_change_swe
        elif snowdepth_change > snowdepth_change_swe*2:
            snowdepth_change = snowdepth_change_swe
        if min_snow_depth_estimate < min_snow_depth_estimate_swe*0.8:
            min_snow_depth_estimate = min_snow_depth_estimate_swe
        elif min_snow_depth_estimate > min_snow_depth_estimate_swe*2:
            min_snow_depth_estimate = min_snow_depth_estimate_swe
        if max_snow_depth_estimate < max_snow_depth_estimate_swe*0.8:
            max_snow_depth_estimate = max_snow_depth_estimate_swe
        elif max_snow_depth_estimate > max_snow_depth_estimate_swe*2:
            max_snow_depth_estimate = max_snow_depth_estimate_swe
        print("snowdepth change from snowdepth data:", snowdepth_change)
    else:
        snowdepth_change = snowdepth_change_swe
        min_snow_depth_estimate = min_snow_depth_estimate_swe
        max_snow_depth_estimate = max_snow_depth_estimate_swe
        print("no snowdepth data, using swe based estimate:", snowdepth_change)

    # replace any nans with 0
    snowdepth_change = 0 if pd.isna(snowdepth_change) else snowdepth_change
    min_snow_depth_estimate = 0 if pd.isna(min_snow_depth_estimate) else min_snow_depth_estimate
    max_snow_depth_estimate = 0 if pd.isna(max_snow_depth_estimate) else max_snow_depth_estimate

    snowdepth_change = round(float(snowdepth_change), 1)
    min_snow_depth_estimate = round(float(min_snow_depth_estimate), 1)
    max_snow_depth_estimate = round(float(max_snow_depth_estimate), 1)
    print("Final snow depth change estimate:", snowdepth_change)
    
    # inputs into the observation output dict
    observation_output_dict['areas'][site] = {"observed_snowfall": snowdepth_change, 
                                                "estimated_range":[min_snow_depth_estimate,
                                                                    max_snow_depth_estimate],
                                                "source": sites[site],
                                                "snow_level_range": [float(min_snow_level)*3.28084 if min_snow_level is not None else None, 
                                                                     float(max_snow_level)*3.28084 if max_snow_level is not None else None]
                                                }
    # provide full path relative to this script
    obs_dir = Path(__file__).parent.parent / 'data' / 'observations'
    obs_file = obs_dir / f"{site}.json"
    with open(obs_file, 'w') as f:
        json.dump(observation_output_dict['areas'][site], f, indent=4)
    print(f"Saved observations for {site} to {obs_file}")
    return obs_file

def scrape_forecast_ranges(html_file_path):
    """
    Scrape the weekend snow accumulation forecast ranges from the most recent forecast HTML post.
    Extracts values from the rightmost column of the forecast table.
    
    Args:
        html_file_path: Path to the forecast HTML file
    
    Returns:
        dict: Mapping of site names to forecast ranges [min, max]
    """
    forecast_ranges = {}

    def normalize_site_name(name: str) -> str:
        # Drop any parenthetical like "(4500')" or "(Heather Meadows)" and trim
        cleaned = re.sub(r"\s*\(.*?\)", "", name).strip()
        return cleaned
    
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the Weekend Snow Accumulation section and its table
        forecast_table = None
        for section in soup.find_all('div', class_='forecast-details'):
            for h3 in section.find_all('h3'):
                txt = h3.get_text(strip=True).lower()
                if 'weekend snow accumulation' in txt:
                    # Find the table in this section
                    forecast_table = section.find('table')
                    break
            if forecast_table:
                break
        
        if forecast_table:
            # Process each row in the table body
            rows = forecast_table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue
                
                # First cell contains the site name (may include elevation)
                site_cell = cells[0].get_text(strip=True)
                # Last cell contains the weekend total range
                total_cell = cells[-1].get_text(strip=True)
                
                print(f"Parsing row: {site_cell} | rightmost cell: {total_cell}")
                
                # Skip header rows
                if 'site' in site_cell.lower() or not total_cell:
                    continue
                
                # Normalize the site name (strip elevation parentheses)
                site_name = normalize_site_name(site_cell)
                
                # Parse the total: could be "24-36" or just "24"
                # Match patterns like "24-36" or "24" (with optional quotes)
                match = re.search(r'(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?', total_cell)
                if match:
                    min_snow = float(match.group(1))
                    max_snow = float(match.group(2)) if match.group(2) else min_snow
                    
                    forecast_ranges[site_name] = [
                        round(min_snow, 1),
                        round(max_snow, 1)
                    ]
                    print(f"  Extracted: {site_name} -> {min_snow}-{max_snow} inches")
        else:
            print("Weekend totals table not found in HTML; no forecast ranges scraped.")
        
        return forecast_ranges
    
    except Exception as e:
        print(f"Error scraping forecast ranges from {html_file_path}: {e}")
        import traceback
        traceback.print_exc()
        return {}

def update_forecast_with_our_forecast(forecast_file_path, forecast_ranges):
    """
    Update the forecast JSON file with our_forecast ranges from scraped HTML data.
    
    Args:
        forecast_file_path: Path to the eval_forecast JSON file
        forecast_ranges: Dict mapping site names to [min, max] forecast ranges
    """
    try:
        with open(forecast_file_path, 'r', encoding='utf-8') as f:
            forecast_data = json.load(f)
        
        # Build a normalized map of area keys to handle names like NAME (ELEVATION)
        def normalize(n: str) -> str:
            return re.sub(r"\s*\(.*?\)", "", n).strip().lower()

        # Filter to only valid area dictionaries (skip metadata like 'created_at')
        area_keys = [k for k, v in forecast_data.get('areas', {}).items() 
                     if isinstance(v, dict) and 'accumulated_snowfall' in v]
        normalized_map = {normalize(k): k for k in area_keys}

        # Provide a small synonyms map for consistency
        synonyms = {
            'mt. baker ski area': 'mt. baker',
            'heather meadows': 'mt. baker',
            'crystal mountain': 'crystal'
        }

        # Update each area with the scraped forecast range using normalized matching
        for scraped_name, forecast_range in forecast_ranges.items():
            norm = normalize(scraped_name)
            # apply synonyms to the normalized key if needed
            norm = synonyms.get(norm, norm)
            # find matching area key
            target_key = normalized_map.get(norm)
            if target_key:
                forecast_data['areas'][target_key]['accumulated_snowfall']['our_forecast']['range'] = forecast_range
                print(f"Updated {target_key}: {forecast_range[0]}-{forecast_range[1]} inches")

        # For areas without scraped ranges, set None
        for fx_key in area_keys:
            if normalize(fx_key) not in {normalize(n) for n in forecast_ranges.keys()}:
                forecast_data['areas'][fx_key]['accumulated_snowfall']['our_forecast']['range'] = [None, None]
        
        # Write updated data back to file
        with open(forecast_file_path, 'w', encoding='utf-8') as f:
            json.dump(forecast_data, f, indent=4)
        
        print(f"Successfully updated forecast file: {forecast_file_path}")
        return True
    
    except Exception as e:
        print(f"Error updating forecast file {forecast_file_path}: {e}")
        return False

def calculate_forecast_error(forecast_value, actual_value):
    """Calculate forecast error and related metrics"""
    error = actual_value - forecast_value
    abs_error = abs(error)
    pct_error = (abs_error / actual_value * 100) if actual_value != 0 else 0
    
    return {
        'error': round(error, 1),
        'absolute_error': round(abs_error, 1),
        'percent_error': round(pct_error, 1)
    }
    
def evaluate_forecast(sites, output_dir, min_snow_level=None, max_snow_level=None):
    results = {
        'forecast_date': [],
        'valid_dates': [],
        'areas': {}
    }
    fx_sites = [
        "Mt. Baker Ski Area",
        "Stevens Pass",
        "TBLEW",
        "Snoqualmie Pass",
        "Crystal",
        "Paradise",
        "White Pass",
        "HURW1",
        "Washington Pass",
    ]
    # For each ski area in the forecast
    for i, site in enumerate(sites):
        forecast_result = get_forecast_file(fx_sites[i], output_dir)
        # Handle error responses from get_forecast_file
        if isinstance(forecast_result, dict) and 'error' in forecast_result:
            print(forecast_result['error'])
            continue
        forecast_file, fx_date = forecast_result
        # Skip sites where no forecast file could be produced
        if not forecast_file or not fx_date or not forecast_file.exists():
            print(f"No forecast file found for {site}. Skipping evaluation.")
            continue
        with open(forecast_file, 'r') as f:
            forecast_data = json.load(f)
        try:
            observations_file = load_observations(site, fx_date, min_snow_level, max_snow_level)
            with open(observations_file, 'r') as f:
                observations_data = json.load(f)
            observations = observations_data
        except Exception as e:
            print(f"Error loading observations for {site}: {e}")
            observations = None
        results['forecast_date'] = forecast_data['post_date']
        results['valid_dates'] = forecast_data['valid_dates']
        if observations:
            # Find matching observation
            area_obs = observations
            area_fx = forecast_data['areas'][site]
            
            # Compare snowfall
            if 'observed_snowfall' in area_obs:
                actual_snow = round(area_obs['observed_snowfall'], 1)
                actual_snow_min = round(area_obs['estimated_range'][0], 1)
                actual_snow_max = round(area_obs['estimated_range'][1], 1)
                if forecast_file is not None:
                    try:
                        forecast_snow = round(area_fx['accumulated_snowfall']['nbm_forecast']['deterministic'], 1)
                        nbm_snow_error = calculate_forecast_error(forecast_snow, actual_snow)
                        # Check if actual falls within NBM ensemble IQR range
                        nbm_iqr_min = round(area_fx['accumulated_snowfall']['nbm_forecast']['ensemble_iqr_range'][0], 1)
                        nbm_iqr_max = round(area_fx['accumulated_snowfall']['nbm_forecast']['ensemble_iqr_range'][1], 1)
                        nbm_within_range = (nbm_iqr_min <= actual_snow <= nbm_iqr_max)
                    except:
                        forecast_snow = None
                        nbm_snow_error = None
                        nbm_within_range = False
                else:
                    nbm_snow_error = None
                    nbm_within_range = False
                try:
                    our_forecast_snow_min = round(area_fx['accumulated_snowfall']['our_forecast']['range'][0], 1)
                    our_forecast_snow_max = round(area_fx['accumulated_snowfall']['our_forecast']['range'][1], 1)
                    manual_snow_error_min = calculate_forecast_error(our_forecast_snow_min, actual_snow_min)
                    manual_snow_error_max = calculate_forecast_error(our_forecast_snow_max, actual_snow_max)
                except:
                    our_forecast_snow_min = None
                    our_forecast_snow_max = None
                    manual_snow_error_min = None
                    manual_snow_error_max = None
                
            if 'snow_level_range' in area_obs:
                actual_snow_level_min = area_obs['snow_level_range'][0]
                actual_snow_level_max = area_obs['snow_level_range'][1]
            else:
                actual_snow_level_min = None
                actual_snow_level_max = None

            try:
                fx_snow_level_min = round(area_fx['snow_level']['nbm_forecast']['weekend_min_max'][0], 1)
            except:
                fx_snow_level_min = None
            try:
                fx_snow_level_max = round(area_fx['snow_level']['nbm_forecast']['weekend_min_max'][1], 1)
            except:
                fx_snow_level_max = None
            
            try:
                
                our_max = area_fx['accumulated_snowfall']['our_forecast']['range'][1]
                our_min = area_fx['accumulated_snowfall']['our_forecast']['range'][0]
                within_range = (our_min <= actual_snow <= our_max)
            except:
                within_range = False
            results['areas'][site] = {
                'snowfall': {
                    'forecast': forecast_snow,
                    'our_forecast': area_fx['accumulated_snowfall']['our_forecast']['range'],
                    'actual': [actual_snow, actual_snow_min, actual_snow_max],
                    'nbm_error': nbm_snow_error,
                    'our_max_error': manual_snow_error_max,
                    'our_min_error': manual_snow_error_min,
                    'within_range': within_range,
                    'nbm_within_range': nbm_within_range
                },
                'snow_level': {
                    'forecast_range': [fx_snow_level_min, fx_snow_level_max],
                    'actual_range': [actual_snow_level_min, actual_snow_level_max],
                    'source': "NOAA PSL Radar Wind Profiler"
                }
            }
    
    return results

def generate_evaluation_report(sites, output_dir, min_snow_level=None, max_snow_level=None):
    """Generate a human-readable evaluation report"""
    results = evaluate_forecast(sites, output_dir, min_snow_level, max_snow_level)
    
    if 'error' in results:
        return results['error']
    
    report = []
    report.append(f"Forecast Evaluation Report")
    report.append(f"=" * 60)
    report.append(f"Forecast Date: {results['forecast_date']}")
    report.append(f"Valid For: {', '.join(results['valid_dates'])}")
    report.append("")
    
    for area_name, area_results in results['areas'].items():
        report.append(f"{area_name.upper()}")
        report.append("-" * 40)
        
        if 'snowfall' in area_results:
            sf = area_results['snowfall']
            report.append(f" Snowfall:")
            report.append(f"    ------- Observed -------")
            report.append(f"    Actual Snowfall: {sf['actual'][0]:.1f} inches")
            report.append(f"    Range (estimated): {sf['actual'][1]:.1f} - {sf['actual'][2]:.1f} inches")
            report.append(f"    ------- NBM Forecast -------")
            report.append(f"    NBM Forecast: {sf['forecast']} inches")
            if sf['nbm_error']:
                report.append(f"    Error:    {sf['nbm_error']['error']} inches ({sf['nbm_error']['percent_error']}%)")
            else:
                # If NBM error not available, fall back to our forecast error
                # Use the available our_min/our_max errors to compute a mean absolute error
                vals = []
                pcts = []
                if sf.get('our_min_error'):
                    vals.append(sf['our_min_error'].get('absolute_error'))
                    pcts.append(sf['our_min_error'].get('percent_error'))
                if sf.get('our_max_error'):
                    vals.append(sf['our_max_error'].get('absolute_error'))
                    pcts.append(sf['our_max_error'].get('percent_error'))
                if vals:
                    mean_abs = round(sum([v for v in vals if v is not None]) / len(vals), 1)
                    mean_pct = round(sum([p for p in pcts if p is not None]) / len(pcts), 1) if pcts else 0
                    report.append(f"    Error:    {mean_abs} inches ({mean_pct}%)")
            report.append(f"    Within NBM IQR range: {'✓ Yes' if sf.get('nbm_within_range', False) else '✗ No'}")
            report.append(f"    ------- Our Forecast -------")
            report.append(f"    Our Forecast Range: {sf['our_forecast'][0]} - {sf['our_forecast'][1]} inches")
            range_half = sf['actual'][2] - sf['actual'][1]
            report.append(f"    Actual:   {sf['actual'][0]:.1f} (+/- {range_half:.1f}) inches ")
            # report.append(f"    Min Error: {sf['our_min_error']['error']:+.1f} inches ({sf['our_min_error']['percent_error']:.1f}%)")
            # report.append(f"    Max Error: {sf['our_max_error']['error']:+.1f} inches ({sf['our_max_error']['percent_error']:.1f}%)")
            report.append(f"    Within forecast range: {'✓ Yes' if sf['within_range'] else '✗ No'}")
        if 'snow_level' in area_results:
            sl = area_results['snow_level']
            report.append(f" Snow Level:")
            report.append(f"    Forecast Range: {sl['forecast_range'][0]} - {sl['forecast_range'][1]} feet")
            report.append(f"    Actual Range:   {sl['actual_range'][0]} - {sl['actual_range'][1]} feet")
            report.append(f"    Source: {sl['source']}")
        
        report.append("")
    
    return "\n".join(report)

def save_evaluation_report(eval_date, report_text):
    """Save evaluation report to file"""
    # get current script directory
    script_dir = Path(__file__).parent
    report_dir = script_dir.parent / 'data' / 'evaluation_reports'
    report_dir.mkdir(parents=True, exist_ok=True)
    
    filename = report_dir / f"evaluation_{eval_date}.txt"
    # Use UTF-8 so checkmark/cross characters don't break on Windows default cp1252
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(f"Saved evaluation report to {filename}")

def generate_season_summary():
    """Generate summary statistics for entire season"""
    report_dir = Path(__file__).parent.parent / 'data' / 'evaluation_reports'
    return _build_summary_from_reports(report_dir)


def generate_weekly_summary(days=7, as_of=None):
    """Generate a summary over the most recent `days` worth of evaluation reports (defaults to 7)."""
    report_dir = Path(__file__).parent.parent / 'data' / 'evaluation_reports'
    return _build_summary_from_reports(report_dir, days=days, as_of=as_of)


def _build_summary_from_reports(report_dir: Path, days: int | None = None, as_of: datetime | None = None):
    """Internal helper to compute summary stats from evaluation report text files."""
    area_stats = {}
    if as_of is None:
        as_of = datetime.today()

    report_files = sorted(report_dir.glob('evaluation_*.txt'))

    # Filter by date window if days specified
    if days is not None:
        cutoff = (as_of - timedelta(days=days)).date()
        filtered = []
        for f in report_files:
            try:
                date_str = f.stem.replace('evaluation_', '')
                report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if report_date >= cutoff:
                    filtered.append(f)
            except Exception:
                continue
        report_files = filtered

    for report_file in report_files:
        with open(report_file, 'r', encoding='utf-8') as f:
            report_lines = f.readlines()
        
        current_area = None
        for line in report_lines:
            line = line.strip()
            if line and line.isupper() and not line.startswith("FORECAST EVALUATION REPORT"):
                current_area = line
                if current_area not in area_stats:
                    area_stats[current_area] = {
                        'errors': [],
                        'within_range_count': 0,
                        'nbm_within_range_count': 0,
                        'total': 0
                    }
                # Each evaluation report contributes one forecast count for this area
                area_stats[current_area]['total'] += 1
            elif line.startswith("Error:") and current_area:
                # Parse error value but DO NOT increment total here (we count once per area per file)
                parts = line.split()
                try:
                    error_value = float(parts[1])
                    area_stats[current_area]['errors'].append(abs(error_value))
                except Exception:
                    # ignore parse errors
                    pass
            elif line.startswith("Within NBM IQR range:") and current_area:
                if '✓ Yes' in line:
                    area_stats[current_area]['nbm_within_range_count'] += 1
            elif line.startswith("Within forecast range:") and current_area:
                if '✓ Yes' in line:
                    area_stats[current_area]['within_range_count'] += 1
    
    # Generate summary
    summary = []
    title = "Season Forecast Evaluation Summary" if days is None else f"Last {days}-Day Forecast Evaluation Summary"
    summary.append(title)
    summary.append("=" * 60)
    
    for area, stats in area_stats.items():
        # Include any area that had at least one forecast counted, even if no
        # explicit "Error:" lines were found — this ensures areas like
        # Crystal and Paradise appear in the seasonal summary.
        if stats['total'] > 0:
            mae = statistics.mean(stats['errors']) if stats['errors'] else 0.0
            our_accuracy = (stats['within_range_count'] / stats['total'] * 100) if stats['total'] > 0 else 0
            nbm_accuracy = (stats['nbm_within_range_count'] / stats['total'] * 100) if stats['total'] > 0 else 0

            summary.append(f"\n{area.upper()}")
            summary.append(f"  Forecasts: {stats['total']}")
            summary.append(f"  Mean Absolute Error (NBM): {mae:.1f} inches")
            summary.append(f"  Was the NBM within range? Range: {stats['nbm_within_range_count']}/{stats['total']} ({nbm_accuracy:.1f}%)")
            summary.append(f"  Our Forecast Within Range: {stats['within_range_count']}/{stats['total']} ({our_accuracy:.1f}%)")
    
    return "\n".join(summary)

def save_seasonal_evaluation_report(summary_text):
    """Save seasonal evaluation summary to file"""
    script_dir = Path(__file__).parent
    report_dir = script_dir.parent / 'data' / 'evaluation_reports'
    report_dir.mkdir(parents=True, exist_ok=True)
    
    filename = report_dir / 'season_evaluation_summary.txt'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(summary_text)
    
    print(f"Saved seasonal evaluation report to {filename}")

if __name__ == '__main__':
    sites = [
        "Mt. Baker",
        "Stevens Pass",
        "Blewett Pass",
        "Snoqualmie Pass",
        "Crystal",
        "Paradise",
        "White Pass",
        "Hurricane Ridge",
        "Washington Pass",
    ]

    # get the location of this script
    script_dir = Path(__file__).parent
    # this points to scripts/, so move one up to change to data/forecasts
    OUTPUT_DIR = script_dir.parent / 'data' / 'forecasts'
    posts_dir = script_dir.parent / 'posts'
    
    # Ensure output directories exist
    output_report_dir = OUTPUT_DIR.parent / 'evaluation_reports'
    output_report_dir.mkdir(parents=True, exist_ok=True)
    obs_dir = OUTPUT_DIR.parent / 'observations'
    obs_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        if len(sys.argv) > 1:
          snow_lvl_max = sys.argv[2]
          snow_lvl_min = sys.argv[1]
        else:
            snow_lvl_min = input("Enter minimum snow level in meters (e.g., 1439): ")
            snow_lvl_max = input("Enter maximum snow level in meters (e.g., 1646): ")
        print(f"Starting forecast evaluation for {len(sites)} ski areas...")
        print(f"Output directory: {OUTPUT_DIR}")
        
        # Step 1: Scrape the most recent forecast HTML post
        print("\n[Step 1] Scraping forecast ranges from latest post...")
        latest_post = max(posts_dir.glob('2025-*-weekend-forecast.html'), default=None)
        if latest_post:
            print(f"Found latest post: {latest_post.name}")
            forecast_ranges = scrape_forecast_ranges(latest_post)
            print(f"Scraped forecast ranges: {forecast_ranges}")
            
            # Step 2: Update forecast file for the current forecast date with scraped ranges
            # (Do NOT update all historical eval_forecast files.)
            print("\n[Step 2] Updating today's forecast file with scraped ranges...")
            # determine the forecast date (most recent past Thursday)
            forecast_date = (datetime.today() - timedelta(days=(datetime.today().weekday() - 3) % 7)).strftime('%Y-%m-%d')
            target_forecast_file = OUTPUT_DIR / f'eval_forecast_{forecast_date}.json'
            # Ensure the target file exists (copy template if needed)
            if not target_forecast_file.exists():
                shutil.copyfile(OUTPUT_DIR / 'eval_forecast_template.json', target_forecast_file)

            # Update only the target file with our forecast ranges
            update_forecast_with_our_forecast(target_forecast_file, forecast_ranges)
        else:
            print("Warning: No recent forecast post found. Skipping forecast range update.")
        
        # Step 3: Generate evaluation report
        print("\n[Step 3] Generating evaluation report...")
        report_text = generate_evaluation_report(sites, OUTPUT_DIR, min_snow_level=snow_lvl_min, max_snow_level=snow_lvl_max)
        
        # Save the report
        today_str = datetime.today().strftime('%Y-%m-%d')
        save_evaluation_report(today_str, report_text)

        # Optional: print weekly and season summaries
        weekly_summary = generate_weekly_summary(days=7)
        season_summary = generate_season_summary()
        
        # Save seasonal evaluation report
        save_seasonal_evaluation_report(season_summary)
        _build_summary_from_reports(output_report_dir)
        
        # Update evaluation.html with the latest statistics
        try:
            import subprocess
            populate_script = script_dir / 'populate_evaluation_html.py'
            subprocess.run(['python', str(populate_script)], check=True, cwd=str(script_dir))
            print(f"\n✓ Updated evaluation.html with latest statistics")
        except Exception as html_error:
            print(f"\n⚠ Warning: Could not update evaluation.html: {html_error}")
        
        print(f"\n{report_text}")
        print(f"\nForecast evaluation completed successfully!")
        
    except Exception as e:
        print(f"Error during forecast evaluation: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

