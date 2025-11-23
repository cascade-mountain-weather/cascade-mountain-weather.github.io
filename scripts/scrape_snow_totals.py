from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import json

options = Options()
options.add_argument("--headless")
driver = webdriver.Chrome(options=options)
driver.get("https://www.stevenspass.com/the-mountain/mountain-conditions/weather-report.aspx")

soup = BeautifulSoup(driver.page_source, 'html.parser')
metrics = soup.find_all('li', class_='snow_report__metrics__metric')

results = {}

for metric in metrics:
    value_tag = metric.find('h5', class_='snow_report__metrics__measurement')
    desc_tag = metric.find('h6', class_='snow_report__metrics__description')
    if value_tag and desc_tag:
        desc = desc_tag.get_text(separator=' ', strip=True).lower()
        value = value_tag.get_text(strip=True)
        if "24 hour" in desc:
            results['24_hour_snowfall'] = value
        elif "48 hour" in desc:
            results['48_hour_snowfall'] = value
        elif "7 day" in desc:
            results['7_day_snowfall'] = value
        elif "base depth" in desc:
            results['base_depth'] = value

print("Stevens Pass Snow Metrics:", results)
with open("../data/stevens_snow.json", "w") as f:
    json.dump(results, f)

driver.quit()