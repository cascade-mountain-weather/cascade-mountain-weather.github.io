#!/usr/bin/env python3
from pathlib import Path
import json
import re
import sys
from bs4 import BeautifulSoup


def normalize(n: str) -> str:
    return re.sub(r"\s*\(.*?\)", "", n).strip().lower()

# Common synonyms to align scraped names to area keys
SYNONYMS = {
    'mt. baker ski area': 'mt. baker',
    'heather meadows': 'mt. baker',
    'crystal mountain': 'crystal'
}


def main():
    script_dir = Path(__file__).parent
    posts_dir = script_dir.parent / 'posts'
    output_dir = script_dir.parent / 'data' / 'forecasts'

    latest_post = max(posts_dir.glob('*-weekend-forecast.html'), default=None)
    if not latest_post:
        print('No forecast post found.')
        sys.exit(0)

    print(f"Latest post: {latest_post.name}")
    # Light scrape: find the Snowfall section and collect lines that look like site names,
    # including parentheses (e.g., NAME (ELEVATION)).
    with open(latest_post, 'r', encoding='utf-8') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')

    snowfall_h2 = None
    for h2 in soup.find_all('h2'):
        if 'snowfall' in h2.get_text(strip=True).lower():
            snowfall_h2 = h2
            break

    search_root = soup
    if snowfall_h2 is not None and snowfall_h2.parent:
        search_root = snowfall_h2.parent

    # Collect candidate site names anchored to known tokens; include elevation parentheses and strip trailing numbers
    known_sites = [
        'Mt. Baker', 'Stevens Pass', 'Crystal', 'White Pass',
        'Snoqualmie Pass', 'Blewett Pass', 'Washington Pass',
        'Hurricane Ridge', 'Paradise'
    ]
    candidate_names = []
    for node in search_root.find_all(['li', 'tr']):
        txt = ' '.join(node.get_text(separator=' ', strip=True).split())
        lower = txt.lower()
        for site in known_sites:
            if site.lower() in lower:
                paren = re.search(r"\(\s*[\d,]+\s*'\s*\)", txt)
                display = site
                if paren:
                    display = f"{site} {paren.group(0)}"
                if display not in candidate_names:
                    candidate_names.append(display)
                break

    print(f"Scraped display names: {candidate_names}")

    template_file = output_dir / 'eval_forecast_template.json'
    if not template_file.exists():
        print(f"Template not found: {template_file}")
        sys.exit(1)

    with open(template_file, 'r', encoding='utf-8') as f:
        template = json.load(f)

    area_keys = list(template.get('areas', {}).keys())
    normalized_map = {normalize(k): k for k in area_keys}

    # Build a set of normalized scraped names for unmatched reporting
    scraped_norm_set = set()

    print("\nMapping scraped names → area keys")
    for scraped_name in candidate_names:
        norm = normalize(scraped_name)
        norm = SYNONYMS.get(norm, norm)
        scraped_norm_set.add(norm)
        target_key = normalized_map.get(norm)
        if target_key:
            print(f"  {scraped_name} → {target_key}")
        else:
            print(f"  {scraped_name} → (no match)")

    unmatched_areas = [k for k in area_keys if normalize(k) not in scraped_norm_set]
    if unmatched_areas:
        print("\nAreas without scraped ranges:")
        for k in unmatched_areas:
            print(f"  {k}")


if __name__ == '__main__':
    main()
