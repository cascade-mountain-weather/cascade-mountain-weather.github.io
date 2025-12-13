from build_fx_evaluation import load_forecast, get_forecast_file
from pathlib import Path

sites = sites = [
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
script_dir = Path(__file__).parent
OUTPUT_DIR = script_dir.parent / 'data' / 'forecasts'

for site in sites:
    if site == "Mt. Baker":
        site = "Mt. Baker Ski Area"
    saved_path, fx_date =  get_forecast_file(site, OUTPUT_DIR)

    if site == "Blewett Pass":
        downloaded_file = OUTPUT_DIR / "TBLEW.csv"
        if downloaded_file.exists():
            downloaded_file.rename(saved_path)
    elif site == "Hurricane Ridge":
        downloaded_file = OUTPUT_DIR / "HURW1.csv"
        if downloaded_file.exists():
            downloaded_file.rename(saved_path)