#!/usr/bin/env python3
"""
Forecast Verification Script
Compares forecasts against actual observations and generates verification reports
"""

import json
import os
from datetime import datetime
from pathlib import Path
import statistics

def load_forecast(forecast_date):
    """Load forecast data for a specific date"""
    forecast_file = Path(f'data/forecasts/forecast_{forecast_date}.json')
    if forecast_file.exists():
        with open(forecast_file, 'r') as f:
            return json.load(f)
    return None

def load_observations(area_name, year_month):
    """Load observation data for an area and month"""
    obs_file = Path(f'data/observations/{area_name}_{year_month}.json')
    if obs_file.exists():
        with open(obs_file, 'r') as f:
            return json.load(f)
    return None

def calculate_forecast_error(forecast_value, actual_value):
    """Calculate forecast error and related metrics"""
    error = actual_value - forecast_value
    abs_error = abs(error)
    pct_error = (abs_error / actual_value * 100) if actual_value != 0 else 0
    
    return {
        'error': round(error, 2),
        'absolute_error': round(abs_error, 2),
        'percent_error': round(pct_error, 1)
    }

def verify_forecast(forecast_date):
    """
    Verify a forecast against observations
    
    Args:
        forecast_date: Date of forecast to verify 'YYYY-MM-DD'
    
    Returns:
        dict: Verification results
    """
    forecast = load_forecast(forecast_date)
    if not forecast:
        return {'error': f'No forecast found for {forecast_date}'}
    
    results = {
        'forecast_date': forecast_date,
        'valid_dates': forecast['valid_dates'],
        'areas': {},
        'summary': {}
    }
    
    # For each ski area in the forecast
    for area_name, area_forecast in forecast['areas'].items():
        # Determine year-month for observations
        date_obj = datetime.strptime(forecast_date, '%Y-%m-%d')
        year_month = date_obj.strftime('%Y-%m')
        
        observations = load_observations(area_name, year_month)
        
        if observations:
            # Find matching observation
            area_obs = None
            for obs in observations['observations']:
                if obs['date'] in forecast['valid_dates']:
                    area_obs = obs['data']
                    break
            
            if area_obs:
                # Compare snowfall
                if 'snowfall_measured' in area_obs:
                    forecast_snow = area_forecast['snowfall_total']['forecast']
                    actual_snow = area_obs['snowfall_measured']
                    snow_error = calculate_forecast_error(forecast_snow, actual_snow)
                    
                    results['areas'][area_name] = {
                        'snowfall': {
                            'forecast': forecast_snow,
                            'actual': actual_snow,
                            'error': snow_error,
                            'within_range': (area_forecast['snowfall_total']['range'][0] <= 
                                           actual_snow <= 
                                           area_forecast['snowfall_total']['range'][1])
                        }
                    }
    
    return results

def generate_verification_report(forecast_date):
    """Generate a human-readable verification report"""
    results = verify_forecast(forecast_date)
    
    if 'error' in results:
        return results['error']
    
    report = []
    report.append(f"Forecast Verification Report")
    report.append(f"=" * 60)
    report.append(f"Forecast Date: {results['forecast_date']}")
    report.append(f"Valid For: {', '.join(results['valid_dates'])}")
    report.append("")
    
    for area_name, area_results in results['areas'].items():
        report.append(f"{area_name.upper()}")
        report.append("-" * 40)
        
        if 'snowfall' in area_results:
            sf = area_results['snowfall']
            report.append(f"  Snowfall:")
            report.append(f"    Forecast: {sf['forecast']} inches")
            report.append(f"    Actual:   {sf['actual']} inches")
            report.append(f"    Error:    {sf['error']['error']:+.1f} inches ({sf['error']['percent_error']:.1f}%)")
            report.append(f"    Within forecast range: {'✓ Yes' if sf['within_range'] else '✗ No'}")
        
        report.append("")
    
    return "\n".join(report)

def save_verification_report(forecast_date, report_text):
    """Save verification report to file"""
    report_dir = Path('data/verification_reports')
    report_dir.mkdir(parents=True, exist_ok=True)
    
    filename = report_dir / f"verification_{forecast_date}.txt"
    with open(filename, 'w') as f:
        f.write(report_text)
    
    print(f"Saved verification report to {filename}")

def generate_season_summary():
    """Generate summary statistics for entire season"""
    forecasts_dir = Path('data/forecasts')
    
    if not forecasts_dir.exists():
        return "No forecasts found"
    
    all_errors = []
    area_stats = {}
    
    for forecast_file in forecasts_dir.glob('forecast_*.json'):
        forecast_date = forecast_file.stem.replace('forecast_', '')
        results = verify_forecast(forecast_date)
        
        if 'areas' in results:
            for area, data in results['areas'].items():
                if area not in area_stats:
                    area_stats[area] = {'errors': [], 'within_range_count': 0, 'total': 0}
                
                if 'snowfall' in data:
                    area_stats[area]['errors'].append(data['snowfall']['error']['absolute_error'])
                    area_stats[area]['total'] += 1
                    if data['snowfall']['within_range']:
                        area_stats[area]['within_range_count'] += 1
    
    # Generate summary
    summary = []
    summary.append("Season Forecast Verification Summary")
    summary.append("=" * 60)
    
    for area, stats in area_stats.items():
        if stats['errors']:
            mae = statistics.mean(stats['errors'])
            accuracy = (stats['within_range_count'] / stats['total'] * 100) if stats['total'] > 0 else 0
            
            summary.append(f"\n{area.upper()}")
            summary.append(f"  Forecasts: {stats['total']}")
            summary.append(f"  Mean Absolute Error: {mae:.1f} inches")
            summary.append(f"  Within Range: {stats['within_range_count']}/{stats['total']} ({accuracy:.1f}%)")
    
    return "\n".join(summary)

def example_verification():
    """Example of running verification"""
    print("Example Verification")
    print("=" * 60)
    
    # This assumes you've already collected forecast and observation data
    forecast_date = '2025-01-15'
    
    # Generate report
    report = generate_verification_report(forecast_date)
    print(report)
    
    # Save report
    save_verification_report(forecast_date, report)

if __name__ == '__main__':
    print("Forecast Verification Script")
    print("=" * 60)
    print("\nThis script compares your forecasts against actual observations")
    print("to evaluate forecast accuracy.\n")
    
    print("Usage:")
    print("  1. After a forecast weekend, collect observation data")
    print("  2. Run this script to verify the forecast")
    print("  3. View verification reports in data/verification_reports/")
    print("\nExample:\n")
    
    example_verification()
