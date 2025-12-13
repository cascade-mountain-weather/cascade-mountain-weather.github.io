#!/usr/bin/env python3
"""
Populate evaluation.html with data from evaluation reports.

This script reads:
1. Season summary (data/evaluation_reports/season_evaluation_summary.txt)
2. Most recent weekly evaluation report (data/evaluation_reports/evaluation_YYYY-MM-DD.txt)

Then updates evaluation.html with:
- Season statistics cards (total forecasts, within range %, mean error)
- Recent forecast evaluation table (area-by-area breakdown)
- By-area performance sections (Mt. Baker, Stevens Pass, Crystal Mountain)

Usage:
    python populate_evaluation_html.py

This script is automatically called by verify_forecasts.py after generating
evaluation reports, so you typically don't need to run it manually.

Requirements:
    - Python 3.x (no external dependencies beyond standard library)
    - Evaluation reports must exist in data/evaluation_reports/
"""

import re
import os
from datetime import datetime
from pathlib import Path


def parse_season_summary(filepath):
    """
    Parse season_evaluation_summary.txt and extract statistics.
    
    Returns:
        dict: {
            'total_forecasts': int,
            'overall_mae': float,
            'overall_nbm_within': str (percentage),
            'overall_our_within': str (percentage),
            'areas': {
                'MT. BAKER': {'forecasts': int, 'mae': float, 'nbm_within': str, 'our_within': str},
                ...
            }
        }
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    data = {
        'total_forecasts': 0,
        'overall_mae': 0.0,
        'overall_nbm_within': '0%',
        'overall_our_within': '0%',
        'areas': {}
    }
    
    # Split by area sections
    area_pattern = r'^([A-Z][A-Z\s\.]+)\n\s+Forecasts:\s+(\d+)\n\s+Mean Absolute Error \(NBM\):\s+([\d.]+)\s+inches\n\s+Was the NBM within range? Range:\s+(\d+)/(\d+)\s+\(([\d.]+)%\)\n\s+Our Forecast Within Range:\s+(\d+)/(\d+)\s+\(([\d.]+)%\)'
    
    matches = re.finditer(area_pattern, content, re.MULTILINE)
    
    total_nbm_within = 0
    total_nbm_forecasts = 0
    total_our_within = 0
    total_our_forecasts = 0
    total_mae_sum = 0.0
    area_count = 0
    
    for match in matches:
        area_name = match.group(1).strip()
        forecasts = int(match.group(2))
        mae = float(match.group(3))
        nbm_within = int(match.group(4))
        nbm_total = int(match.group(5))
        nbm_pct = match.group(6)
        our_within = int(match.group(7))
        our_total = int(match.group(8))
        our_pct = match.group(9)
        
        data['areas'][area_name] = {
            'forecasts': forecasts,
            'mae': mae,
            'nbm_within': f"{nbm_within}/{nbm_total}",
            'nbm_within_pct': f"{nbm_pct}%",
            'our_within': f"{our_within}/{our_total}",
            'our_within_pct': f"{our_pct}%"
        }
        
        data['total_forecasts'] += forecasts
        total_nbm_within += nbm_within
        total_nbm_forecasts += nbm_total
        total_our_within += our_within
        total_our_forecasts += our_total
        total_mae_sum += mae
        area_count += 1
    
    # Calculate overall statistics
    if area_count > 0:
        data['overall_mae'] = round(total_mae_sum / area_count, 1)
    if total_nbm_forecasts > 0:
        data['overall_nbm_within'] = f"{round(100 * total_nbm_within / total_nbm_forecasts, 1)}%"
    if total_our_forecasts > 0:
        data['overall_our_within'] = f"{round(100 * total_our_within / total_our_forecasts, 1)}%"
    
    return data


def parse_recent_evaluation(filepath):
    """
    Parse the most recent evaluation_YYYY-MM-DD.txt file.
    
    Returns:
        list of dicts with area evaluation data
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    results = []
    current_area = None
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Check if this is an area header (e.g., "MT. BAKER")
        if line and line.isupper() and not line.startswith('---') and i + 1 < len(lines) and lines[i + 1].strip().startswith('-'):
            current_area = line
            area_data = {'area': format_area_name(current_area)}
            
            # Parse the following lines for this area
            i += 2  # Skip the dashes line
            
            while i < len(lines):
                line = lines[i].strip()
                
                # Stop if we hit the next area
                if line and line.isupper() and i + 1 < len(lines) and lines[i + 1].strip().startswith('-'):
                    break
                
                # Extract Actual Snowfall
                if 'Actual Snowfall:' in line:
                    match = re.search(r'Actual Snowfall:\s+([\d.]+)\s+inches', line)
                    if match:
                        area_data['actual'] = float(match.group(1))
                
                # Extract Actual Snowfall Range
                if 'Range (estimated):' in line:
                    match = re.search(r'Range \(estimated\):\s+([\d.]+)\s*-\s*([\d.]+)\s+inches', line)
                    if match:
                        area_data['actual_low'] = float(match.group(1))
                        area_data['actual_high'] = float(match.group(2))
                
                # Extract NBM Forecast
                if 'NBM Forecast:' in line:
                    match = re.search(r'NBM Forecast:\s+([\d.]+|None)\s+inches', line)
                    if match:
                        val = match.group(1)
                        area_data['nbm_forecast'] = float(val) if val != 'None' else None
                
                # Extract NBM Error
                if 'Error:' in line and 'NBM' in lines[i-1] if i > 0 else False:
                    match = re.search(r'Error:\s+([\d.]+|-)\s+inches', line)
                    if match:
                        val = match.group(1)
                        area_data['nbm_error'] = float(val) if val != '-' else None
                
                # Extract Within NBM IQR range
                if 'Within NBM IQR range:' in line:
                    match = re.search(r'Within NBM IQR range:\s+([✓✗])\s+(Yes|No)', line)
                    if match:
                        area_data['nbm_within_range'] = match.group(2) == 'Yes'
                
                # Extract Our Forecast Range
                if 'Our Forecast Range:' in line:
                    match = re.search(r'Our Forecast Range:\s+([\d.]+|None)\s*-\s*([\d.]+|None)\s+inches', line)
                    if match:
                        low, high = match.group(1), match.group(2)
                        area_data['our_forecast_low'] = float(low) if low != 'None' else None
                        area_data['our_forecast_high'] = float(high) if high != 'None' else None
                
                # Extract Within forecast range
                if 'Within forecast range:' in line:
                    match = re.search(r'Within forecast range:\s+([✓✗])\s+(Yes|No)', line)
                    if match:
                        area_data['our_within_range'] = match.group(2) == 'Yes'
                
                # Extract Snow Level Forecast Range
                if 'Snow Level:' in line and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if 'Forecast Range:' in next_line:
                        match = re.search(r'Forecast Range:\s+([\d.]+|None)\s*-\s*([\d.]+|None)\s+feet', next_line)
                        if match:
                            low, high = match.group(1), match.group(2)
                            area_data['snow_level_forecast_low'] = float(low) if low != 'None' else None
                            area_data['snow_level_forecast_high'] = float(high) if high != 'None' else None
                    if i + 2 < len(lines):
                        actual_line = lines[i + 2].strip()
                        if 'Actual Range:' in actual_line:
                            match = re.search(r'Actual Range:\s+([\d.]+|None)\s*-\s*([\d.]+|None)\s+feet', actual_line)
                            if match:
                                low, high = match.group(1), match.group(2)
                                area_data['snow_level_actual_low'] = float(low) if low != 'None' else None
                                area_data['snow_level_actual_high'] = float(high) if high != 'None' else None
                
                i += 1
            
            # Fill in missing values
            if 'nbm_forecast' not in area_data:
                area_data['nbm_forecast'] = None
            if 'nbm_error' not in area_data:
                area_data['nbm_error'] = None
            if 'nbm_within_range' not in area_data:
                area_data['nbm_within_range'] = False
            if 'our_forecast_low' not in area_data:
                area_data['our_forecast_low'] = None
            if 'our_forecast_high' not in area_data:
                area_data['our_forecast_high'] = None
            if 'our_within_range' not in area_data:
                area_data['our_within_range'] = False
            if 'snow_level_forecast_low' not in area_data:
                area_data['snow_level_forecast_low'] = None
            if 'snow_level_forecast_high' not in area_data:
                area_data['snow_level_forecast_high'] = None
            if 'actual_low' not in area_data:
                area_data['actual_low'] = None
            if 'actual_high' not in area_data:
                area_data['actual_high'] = None
            if 'snow_level_actual_low' not in area_data:
                area_data['snow_level_actual_low'] = None
            if 'snow_level_actual_high' not in area_data:
                area_data['snow_level_actual_high'] = None
            
            # Determine overall accuracy class
            if area_data.get('our_forecast_low') is None:
                area_data['accuracy_class'] = 'neutral'
            elif area_data.get('our_within_range'):
                area_data['accuracy_class'] = 'good'
            else:
                area_data['accuracy_class'] = 'poor'
            
            results.append(area_data)
        
        else:
            i += 1
    
    return results


def format_area_name(area_name):
    """Convert area name from ALL CAPS to display format."""
    name_map = {
        'MT. BAKER': 'Mt. Baker',
        'STEVENS PASS': 'Stevens Pass',
        'CRYSTAL': 'Crystal Mountain',
        'PARADISE': 'Paradise',
        'SNOQUALMIE PASS': 'Snoqualmie Pass',
        'BLEWETT PASS': 'Blewett Pass',
        'WHITE PASS': 'White Pass',
        'HURRICANE RIDGE': 'Hurricane Ridge',
        'WASHINGTON PASS': 'Washington Pass'
    }
    return name_map.get(area_name, area_name.title())


def get_latest_evaluation_report(reports_dir):
    """Find the most recent evaluation_YYYY-MM-DD.txt file."""
    report_files = list(Path(reports_dir).glob('evaluation_*.txt'))
    if not report_files:
        return None
    
    # Sort by date in filename
    report_files.sort(reverse=True)
    return report_files[0]


def populate_html(html_path, season_data, recent_evals):
    """
    Update evaluation.html with parsed data.
    
    Args:
        html_path: Path to evaluation.html
        season_data: Dict from parse_season_summary
        recent_evals: List of dicts from parse_recent_evaluation
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Update season statistics cards
    html = re.sub(
        r'(<div class="stat-label">Total Forecasts Evaluated</div>\s+<div class="stat-number">)--',
        r'\g<1>' + str(season_data['total_forecasts']),
        html
    )
    
    html = re.sub(
        r'(<div class="stat-label">Within Range</div>\s+<div class="stat-number">)--%',
        r'\g<1>' + season_data['overall_our_within'],
        html
    )
    
    html = re.sub(
        r'(<div class="stat-label">Mean Error</div>\s+<div class="stat-number">)--\s+in',
        r'\g<1>' + f"{season_data['overall_mae']:.1f} in",
        html
    )
    
    # Build recent forecast evaluation cards
    if recent_evals:
        cards_html = []
        for eval_item in recent_evals:
            # Determine accuracy display
            if eval_item['accuracy_class'] == 'neutral':
                accuracy_label = 'No Forecast'
                accuracy_text = 'No Forecast'
            elif eval_item['accuracy_class'] == 'good':
                accuracy_label = 'Within Range'
                accuracy_text = '✓ Our Forecast Within Range'
            else:
                accuracy_label = 'Outside Range'
                accuracy_text = '✗ Outside Range'
            
            # Build metrics
            actual_display = f"{eval_item['actual']:.1f}"
            if eval_item['actual_low'] is not None and eval_item['actual_high'] is not None:
                actual_display += f" ({eval_item['actual_low']:.1f}-{eval_item['actual_high']:.1f}\")" 
            else:
                actual_display += "\""
            
            metrics = f"""                <div class="evaluation-metric">
                    <span class="evaluation-metric-label">Actual Snowfall:</span>
                    <span class="evaluation-metric-value">{actual_display}</span>
                </div>"""
            
            # NBM metrics
            if eval_item['nbm_forecast'] is not None:
                nbm_status = '✓' if eval_item['nbm_within_range'] else '✗'
                nbm_error_val = f"{eval_item['nbm_error']:+.1f}" if eval_item['nbm_error'] is not None else 'N/A'
                metrics += f"""
                <div class="evaluation-metric">
                    <span class="evaluation-metric-label">NBM Forecast:</span>
                    <span class="evaluation-metric-value">{eval_item['nbm_forecast']:.1f}"</span>
                </div>
                <div class="evaluation-metric">
                    <span class="evaluation-metric-label">NBM Error:</span>
                    <span class="evaluation-metric-value">{nbm_error_val}</span>
                </div>
                <div class="evaluation-metric">
                    <span class="evaluation-metric-label">Was the NBM within range?:</span>
                    <span class="evaluation-metric-value">{nbm_status}</span>
                </div>"""
            
            # Our forecast metrics
            if eval_item['our_forecast_low'] is not None:
                our_mid = (eval_item['our_forecast_low'] + eval_item['our_forecast_high']) / 2
                our_error = eval_item['actual'] - our_mid
                our_status = '✓' if eval_item['our_within_range'] else '✗'
                metrics += f"""
                <div class="evaluation-metric">
                    <span class="evaluation-metric-label">Our Forecast:</span>
                    <span class="evaluation-metric-value">{our_mid:.0f}" ({eval_item['our_forecast_low']:.0f}-{eval_item['our_forecast_high']:.0f}")</span>
                </div>
                <div class="evaluation-metric">
                    <span class="evaluation-metric-label">Our Error:</span>
                    <span class="evaluation-metric-value">{our_error:+.1f}"</span>
                </div>
                <div class="evaluation-metric">
                    <span class="evaluation-metric-label">Were we within range?:</span>
                    <span class="evaluation-metric-value">{our_status}</span>
                </div>"""
            else:
                metrics += """
                <div class="evaluation-metric">
                    <span class="evaluation-metric-label">Our Forecast:</span>
                    <span class="evaluation-metric-value">Not Issued</span>
                </div>"""
            
            # Snow level metrics
            if eval_item['snow_level_forecast_low'] is not None:
                metrics += f"""
                <div class="evaluation-metric">
                    <span class="evaluation-metric-label">Forecast Snow Level:</span>
                    <span class="evaluation-metric-value">{eval_item['snow_level_forecast_low']:.0f}-{eval_item['snow_level_forecast_high']:.0f} ft</span>
                </div>"""
            if eval_item['snow_level_actual_low'] is not None:
                metrics += f"""
                <div class="evaluation-metric">
                    <span class="evaluation-metric-label">Actual Snow Level:</span>
                    <span class="evaluation-metric-value">{eval_item['snow_level_actual_low']:.0f}-{eval_item['snow_level_actual_high']:.0f} ft</span>
                </div>"""
            
            card = f"""                <div class="evaluation-card">
                    <div class="evaluation-card-header">
                        <h3 class="evaluation-card-title">{eval_item['area']}</h3>
                        <span class="evaluation-card-accuracy {eval_item['accuracy_class']}">{accuracy_label}</span>
                    </div>
                    <div class="evaluation-card-body">
{metrics}
                    </div>
                </div>"""
            
            cards_html.append(card)
        
        cards_grid = '\n'.join(cards_html)
        
        # Replace the placeholder cards container
        html = re.sub(
            r'<div class="evaluation-cards-grid" id="evaluation-cards-data" style="display: none;">.*?</div>\s*</section>',
            f'<div class="evaluation-cards-grid" id="evaluation-cards-data" style="display: none;">\n                <!-- All cards stored here for reference, hidden from view -->\n{cards_grid}\n            </div>\n        </section>',
            html,
            flags=re.DOTALL
        )
    
    # Update by-area performance sections using non-greedy matching
    # that doesn't cross h3 tags
    
    def update_area_section(html, area_key, html_heading):
        """Update a single area section with data."""
        if area_key not in season_data['areas']:
            return html
        
        area_data = season_data['areas'][area_key]
        
        # Pattern that matches only within one h3 section
        pattern = rf'(<h3>{re.escape(html_heading)}</h3>\s+<p><strong>Forecasts Evaluated:</strong>)\s+--'
        html = re.sub(pattern, r'\g<1> ' + str(area_data['forecasts']), html)
        
        pattern = rf'(<h3>{re.escape(html_heading)}</h3>\s+<p><strong>Forecasts Evaluated:</strong>[^<]+</p>\s+<p><strong>Mean Absolute Error:</strong>)\s+--\s+inches'
        html = re.sub(pattern, r'\g<1> ' + f"{area_data['mae']:.1f} inches", html)
        
        pattern = rf'(<h3>{re.escape(html_heading)}</h3>\s+<p><strong>Forecasts Evaluated:</strong>[^<]+</p>\s+<p><strong>Mean Absolute Error:</strong>[^<]+</p>\s+<p><strong>Within Range:</strong>)\s+--/--\s+\(--(%)\)'
        html = re.sub(pattern, r'\g<1> ' + area_data['our_within'] + f" ({area_data['our_within_pct']})", html)
        
        return html
    
    # Update all areas
    html = update_area_section(html, 'MT. BAKER', 'Mt. Baker')
    html = update_area_section(html, 'STEVENS PASS', 'Stevens Pass')
    html = update_area_section(html, 'CRYSTAL', 'Crystal Mountain')
    html = update_area_section(html, 'SNOQUALMIE PASS', 'Snoqualmie Pass')
    html = update_area_section(html, 'BLEWETT PASS', 'Blewett Pass')
    html = update_area_section(html, 'WHITE PASS', 'White Pass')
    html = update_area_section(html, 'HURRICANE RIDGE', 'Hurricane Ridge')
    html = update_area_section(html, 'WASHINGTON PASS', 'Washington Pass')
    html = update_area_section(html, 'PARADISE', 'Paradise')
    
    # Write updated HTML
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✓ Updated {html_path}")


def main():
    """Main execution function."""
    # Set up paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    reports_dir = repo_root / 'data' / 'evaluation_reports'
    html_path = repo_root / 'evaluation.html'
    
    print("Populating evaluation.html with forecast evaluation data...")
    print()
    
    # Parse season summary
    season_file = reports_dir / 'season_evaluation_summary.txt'
    if not season_file.exists():
        print(f"ERROR: Season summary not found at {season_file}")
        print("Run verify_forecasts.py first to generate evaluation reports.")
        return
    
    print(f"Reading season summary: {season_file}")
    season_data = parse_season_summary(season_file)
    print(f"  Total forecasts: {season_data['total_forecasts']}")
    print(f"  Overall MAE: {season_data['overall_mae']:.1f} inches")
    print(f"  Our forecasts within range: {season_data['overall_our_within']}")
    print()
    
    # Parse most recent evaluation report
    latest_report = get_latest_evaluation_report(reports_dir)
    if latest_report:
        print(f"Reading latest evaluation: {latest_report}")
        recent_evals = parse_recent_evaluation(latest_report)
        print(f"  Found {len(recent_evals)} area evaluations")
        print()
    else:
        print("WARNING: No evaluation reports found")
        recent_evals = []
        print()
    
    # Update HTML
    populate_html(html_path, season_data, recent_evals)
    print()
    print("Done! Open evaluation.html in a browser to see the updated statistics.")


if __name__ == '__main__':
    main()
