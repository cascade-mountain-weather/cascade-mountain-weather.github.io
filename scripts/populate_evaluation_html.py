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
    area_pattern = r'^([A-Z][A-Z\s\.]+)\n\s+Forecasts:\s+(\d+)\n\s+Mean Absolute Error \(NBM\):\s+([\d.]+)\s+inches\n\s+NBM Within IQR Range:\s+(\d+)/(\d+)\s+\(([\d.]+)%\)\n\s+Our Forecast Within Range:\s+(\d+)/(\d+)\s+\(([\d.]+)%\)'
    
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
        list of dicts: [
            {
                'date': 'Jan 15, 2025',
                'area': 'Mt. Baker',
                'forecast': '20" (14-24")',
                'actual': '18.0"',
                'error': '-2.0" (-10.0%)',
                'accuracy': 'Within Range' or 'Outside Range',
                'accuracy_class': 'good' or 'poor'
            },
            ...
        ]
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    results = []
    
    # Extract forecast date from header
    date_match = re.search(r'Forecast Date:\s+(\d{4}-\d{2}-\d{2})', content)
    if date_match:
        date_str = date_match.group(1)
        forecast_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%b %d, %Y')
    else:
        forecast_date = 'Unknown'
    
    # Parse each area section
    area_pattern = r'^([A-Z][A-Z\s\.]+)\n-+\n\s+Snowfall:\n.*?Our Forecast Range:\s+([\d.]+|None)\s*-\s*([\d.]+|None)\s+inches\n\s+Actual:\s+([\d.]+)\s+\(\+/-\s+[\d.]+\)\s+inches\s+\n\s+Within forecast range:\s+([✓✗])\s+(Yes|No)'
    
    matches = re.finditer(area_pattern, content, re.MULTILINE | re.DOTALL)
    
    for match in matches:
        area_name = match.group(1).strip()
        forecast_low = match.group(2)
        forecast_high = match.group(3)
        actual = float(match.group(4))
        within_symbol = match.group(5)
        within_text = match.group(6)
        
        # Format area name for display (title case, etc.)
        display_name = format_area_name(area_name)
        
        # Handle areas with no forecast
        if forecast_low == 'None' or forecast_high == 'None':
            forecast_str = "No Forecast"
            actual_str = f"{actual:.1f}\""
            error_str = "N/A"
            accuracy = 'No Forecast'
            accuracy_class = 'neutral'
        else:
            forecast_low = float(forecast_low)
            forecast_high = float(forecast_high)
            
            # Calculate error (use midpoint of forecast range)
            forecast_mid = (forecast_low + forecast_high) / 2
            error = actual - forecast_mid
            if actual > 0:
                error_pct = (error / actual) * 100
            else:
                error_pct = 0.0
            
            # Format strings
            forecast_str = f"{forecast_mid:.0f}\" ({forecast_low:.0f}-{forecast_high:.0f}\")"
            actual_str = f"{actual:.1f}\""
            error_str = f"{error:+.1f}\" ({error_pct:+.1f}%)"
            
            accuracy = 'Within Range' if within_text == 'Yes' else 'Outside Range'
            accuracy_class = 'good' if within_text == 'Yes' else 'poor'
        
        results.append({
            'date': forecast_date,
            'area': display_name,
            'forecast': forecast_str,
            'actual': actual_str,
            'error': error_str,
            'accuracy': accuracy,
            'accuracy_class': accuracy_class
        })
    
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
    
    # Build recent forecast evaluation table rows
    if recent_evals:
        table_rows = []
        for eval_item in recent_evals:
            accuracy_html = f'<span class="accuracy-{eval_item["accuracy_class"]}">{eval_item["accuracy"]}</span>'
            row = f"""                    <tr>
                        <td>{eval_item['date']}</td>
                        <td>{eval_item['area']}</td>
                        <td>{eval_item['forecast']}</td>
                        <td>{eval_item['actual']}</td>
                        <td>{eval_item['error']}</td>
                        <td>{accuracy_html}</td>
                    </tr>"""
            table_rows.append(row)
        
        table_body = '\n'.join(table_rows)
        
        # Replace the placeholder tbody content
        html = re.sub(
            r'<tbody>.*?</tbody>',
            f'<tbody>\n{table_body}\n                </tbody>',
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
