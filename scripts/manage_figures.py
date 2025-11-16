#!/usr/bin/env python3
"""
Figure Management Script
Downloads/saves weather figures to assets directory for use in blog posts
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

def setup_assets_directory():
    """Create assets directory structure"""
    assets_dir = Path('assets')
    subdirs = ['images', 'images/archive']
    
    for subdir in subdirs:
        (assets_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    return assets_dir

def save_figure(image_path, figure_name, archive=False):
    """
    Save a figure to the assets directory
    
    Args:
        image_path: Path to the source image file
        figure_name: Name to save the figure as
        archive: If True, also save a dated copy to archive
    
    Returns:
        str: Relative path to saved figure for use in HTML
    """
    assets_dir = setup_assets_directory()
    
    # Copy to main images directory (this gets overwritten each week)
    dest_path = assets_dir / 'images' / figure_name
    shutil.copy2(image_path, dest_path)
    print(f"Saved figure: {dest_path}")
    
    # Optionally save to archive with date
    if archive:
        date_str = datetime.now().strftime('%Y-%m-%d')
        archive_name = f"{date_str}_{figure_name}"
        archive_path = assets_dir / 'images' / 'archive' / archive_name
        shutil.copy2(image_path, archive_path)
        print(f"Archived figure: {archive_path}")
    
    # Return relative path for HTML
    return f"../assets/images/{figure_name}"

def organize_weekly_figures(forecast_date):
    """
    Organize figures for a weekly forecast
    
    Args:
        forecast_date: Date of forecast 'YYYY-MM-DD'
    
    Returns:
        dict: Mapping of figure types to filenames
    """
    # Standard figure names that can be overwritten each week
    figures = {
        'temperature': 'temp_forecast.png',
        'precipitation': 'precip_forecast.png',
        'freezing_level': 'freezing_level.png',
        'wind': 'wind_forecast.png',
        'extended_outlook': 'extended_outlook.png',
        'radar': 'current_radar.png',
        'snow_depth': 'snow_depth_chart.png'
    }
    
    return figures

def generate_html_figure_code(figure_path, alt_text, caption=None):
    """
    Generate HTML code for inserting a figure in a blog post
    
    Args:
        figure_path: Path to the figure
        alt_text: Alt text for accessibility
        caption: Optional caption text
    
    Returns:
        str: HTML code snippet
    """
    html = f'<img src="{figure_path}" alt="{alt_text}">'
    
    if caption:
        html = f'''<figure>
    {html}
    <figcaption>{caption}</figcaption>
</figure>'''
    
    return html

def list_current_figures():
    """List all current figures in assets directory"""
    assets_dir = Path('assets/images')
    
    if not assets_dir.exists():
        print("No figures found. Assets directory doesn't exist yet.")
        return
    
    print("\nCurrent Figures in assets/images/:")
    print("-" * 60)
    
    for img_file in sorted(assets_dir.glob('*.png')):
        size_kb = img_file.stat().st_size / 1024
        modified = datetime.fromtimestamp(img_file.stat().st_mtime)
        print(f"  {img_file.name:<30} {size_kb:>8.1f} KB  Modified: {modified.strftime('%Y-%m-%d %H:%M')}")
    
    for img_file in sorted(assets_dir.glob('*.jpg')):
        size_kb = img_file.stat().st_size / 1024
        modified = datetime.fromtimestamp(img_file.stat().st_mtime)
        print(f"  {img_file.name:<30} {size_kb:>8.1f} KB  Modified: {modified.strftime('%Y-%m-%d %H:%M')}")

def example_usage():
    """Example of how to use figure management"""
    
    # Setup directories
    setup_assets_directory()
    
    print("\nExample Figure Management Workflow:")
    print("=" * 60)
    
    print("\n1. Download/screenshot your weather figures")
    print("   Example sources:")
    print("   - Windy.com temperature map")
    print("   - NOAA precipitation forecast")
    print("   - Tropical Tidbits model output")
    
    print("\n2. Save figures using standard names:")
    figures = organize_weekly_figures('2025-01-15')
    for fig_type, filename in figures.items():
        print(f"   {fig_type:<20} -> {filename}")
    
    print("\n3. Use in blog post:")
    example_path = "../assets/images/temp_forecast.png"
    html_code = generate_html_figure_code(
        example_path, 
        "Temperature forecast for WA ski areas",
        "Weekend temperature forecast - Saturday & Sunday"
    )
    print(f"\n{html_code}")
    
    print("\n4. Figures can be overwritten each week for new forecasts")
    print("   Archive flag saves dated copy for historical reference")

if __name__ == '__main__':
    print("Figure Management Script")
    print("=" * 60)
    print("\nThis script helps you manage weather figures/images:")
    print("  - Organize figures in assets/images/")
    print("  - Use standard names that can be overwritten weekly")
    print("  - Optionally archive dated copies")
    print("  - Generate HTML code for blog posts")
    
    example_usage()
    
    print("\n" + "=" * 60)
    print("\nQuick workflow:")
    print("1. Save your weather screenshots/figures to a temp location")
    print("2. Use standard names: temp_forecast.png, precip_forecast.png, etc.")
    print("3. Move them to assets/images/ directory")
    print("4. Reference in posts: <img src='../assets/images/temp_forecast.png'>")
    print("\nNext week, just overwrite with new figures!")
