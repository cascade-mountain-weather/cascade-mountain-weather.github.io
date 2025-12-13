#!/usr/bin/env python3
"""
Unit tests for verify_forecasts.py script
Tests forecast scraping, file updates, and report generation
"""
import unittest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys

# Mock heavy dependencies before importing verify_forecasts
sys.modules['selenium'] = MagicMock()
sys.modules['selenium.webdriver'] = MagicMock()
sys.modules['selenium.webdriver.common'] = MagicMock()
sys.modules['selenium.webdriver.common.by'] = MagicMock()
sys.modules['selenium.webdriver.chrome'] = MagicMock()
sys.modules['selenium.webdriver.chrome.service'] = MagicMock()
sys.modules['webdriver_manager'] = MagicMock()
sys.modules['webdriver_manager.chrome'] = MagicMock()
sys.modules['metloom'] = MagicMock()
sys.modules['metloom.pointdata'] = MagicMock()
sys.modules['metloom.variables'] = MagicMock()
sys.modules['pandas'] = MagicMock()

sys.path.insert(0, str(Path(__file__).parent))
from build_fx_evaluation import (
    scrape_forecast_ranges,
    update_forecast_with_our_forecast,
    calculate_forecast_error,
    new_snow_estimate
)


class TestScrapeForecasts(unittest.TestCase):
    """Tests for scraping forecast ranges from HTML"""
    
    def setUp(self):
        """Create temporary directory and test HTML file"""
        self.test_dir = tempfile.mkdtemp()
        self.html_file = Path(self.test_dir) / "test_forecast.html"
    
    def tearDown(self):
        """Clean up temporary files"""
        shutil.rmtree(self.test_dir)
    
    def create_test_html(self, forecast_data):
        """Helper to create test HTML with forecast data"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Test Forecast</title></head>
        <body>
            <section class="forecast-section">
                <h2>Precipitation & Snowfall</h2>
                <div class="forecast-details">
                    <h3>Weekend Snow Accumulation (through 4am Monday 1 Dec):</h3>
                    <ul>
                        {forecast_data}
                    </ul>
                </div>
            </section>
        </body>
        </html>
        """
        with open(self.html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def test_scrape_single_forecast(self):
        """Test scraping a single ski area forecast"""
        html = '<li><strong>Mt. Baker:</strong> 5-10"</li>'
        self.create_test_html(html)
        
        result = scrape_forecast_ranges(str(self.html_file))
        
        self.assertIn('Mt. Baker', result)
        self.assertEqual(result['Mt. Baker'], [5, 10])
    
    def test_scrape_multiple_forecasts(self):
        """Test scraping multiple ski area forecasts"""
        html = """
        <li><strong>Mt. Baker:</strong> 5-10"</li>
        <li><strong>Stevens Pass:</strong> 3-12"</li>
        <li><strong>Snoqualmie:</strong> 2-5"</li>
        """
        self.create_test_html(html)
        
        result = scrape_forecast_ranges(str(self.html_file))
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result['Mt. Baker'], [5, 10])
        self.assertEqual(result['Stevens Pass'], [3, 12])
        self.assertEqual(result['Snoqualmie'], [2, 5])
    
    def test_scrape_all_ski_areas(self):
        """Test scraping all ski areas in the forecast"""
        html = """
        <li><strong>Mt. Baker:</strong> 5-10"</li>
        <li><strong>Stevens Pass:</strong> 3-12"</li>
        <li><strong>Snoqualmie:</strong> 2-5"</li>
        <li><strong>Blewett Pass:</strong> 3-6"</li>
        <li><strong>Paradise:</strong> 2-12"</li>
        <li><strong>White Pass:</strong> 3-8"</li>
        """
        self.create_test_html(html)
        
        result = scrape_forecast_ranges(str(self.html_file))
        
        expected_sites = ['Mt. Baker', 'Stevens Pass', 'Snoqualmie', 
                         'Blewett Pass', 'Paradise', 'White Pass']
        for site in expected_sites:
            self.assertIn(site, result)
            self.assertEqual(len(result[site]), 2)  # [min, max]
            self.assertGreater(result[site][1], result[site][0])  # max > min
    
    def test_scrape_invalid_html(self):
        """Test scraping with invalid HTML file"""
        invalid_file = Path(self.test_dir) / "nonexistent.html"
        
        result = scrape_forecast_ranges(str(invalid_file))
        
        self.assertEqual(result, {})
    
    def test_scrape_empty_html(self):
        """Test scraping empty HTML"""
        with open(self.html_file, 'w') as f:
            f.write("<html><body></body></html>")
        
        result = scrape_forecast_ranges(str(self.html_file))
        
        self.assertEqual(result, {})


class TestUpdateForecast(unittest.TestCase):
    """Tests for updating forecast JSON files"""
    
    def setUp(self):
        """Create temporary directory and test forecast JSON"""
        self.test_dir = tempfile.mkdtemp()
        self.forecast_file = Path(self.test_dir) / "test_forecast.json"
        
        # Create a sample forecast JSON
        self.sample_forecast = {
            "post_date": "2025-11-27",
            "valid_dates": ["2025-11-28", "2025-11-30"],
            "areas": {
                "Mt. Baker": {
                    "accumulated_snowfall": {
                        "nbm_forecast": {"deterministic": 11.68},
                        "our_forecast": {"range": [0, 0], "units": "inches"}
                    }
                },
                "Stevens Pass": {
                    "accumulated_snowfall": {
                        "nbm_forecast": {"deterministic": 8.5},
                        "our_forecast": {"range": [0, 0], "units": "inches"}
                    }
                }
            }
        }
        
        with open(self.forecast_file, 'w') as f:
            json.dump(self.sample_forecast, f)
    
    def tearDown(self):
        """Clean up temporary files"""
        shutil.rmtree(self.test_dir)
    
    def test_update_single_forecast(self):
        """Test updating a single ski area forecast"""
        forecast_ranges = {'Mt. Baker': [5, 10]}
        
        result = update_forecast_with_our_forecast(str(self.forecast_file), forecast_ranges)
        
        self.assertTrue(result)
        
        with open(self.forecast_file, 'r') as f:
            updated = json.load(f)
        
        self.assertEqual(updated['areas']['Mt. Baker']['accumulated_snowfall']['our_forecast']['range'], [5, 10])
    
    def test_update_multiple_forecasts(self):
        """Test updating multiple ski area forecasts"""
        forecast_ranges = {
            'Mt. Baker': [5, 10],
            'Stevens Pass': [3, 12]
        }
        
        result = update_forecast_with_our_forecast(str(self.forecast_file), forecast_ranges)
        
        self.assertTrue(result)
        
        with open(self.forecast_file, 'r') as f:
            updated = json.load(f)
        
        self.assertEqual(updated['areas']['Mt. Baker']['accumulated_snowfall']['our_forecast']['range'], [5, 10])
        self.assertEqual(updated['areas']['Stevens Pass']['accumulated_snowfall']['our_forecast']['range'], [3, 12])
    
    def test_update_preserves_other_data(self):
        """Test that update preserves other forecast data"""
        forecast_ranges = {'Mt. Baker': [5, 10]}
        
        update_forecast_with_our_forecast(str(self.forecast_file), forecast_ranges)
        
        with open(self.forecast_file, 'r') as f:
            updated = json.load(f)
        
        # Verify other fields are preserved
        self.assertEqual(updated['post_date'], "2025-11-27")
        self.assertEqual(updated['valid_dates'], ["2025-11-28", "2025-11-30"])
        self.assertEqual(updated['areas']['Mt. Baker']['accumulated_snowfall']['nbm_forecast']['deterministic'], 11.68)
    
    def test_update_nonexistent_file(self):
        """Test updating a nonexistent forecast file"""
        nonexistent = Path(self.test_dir) / "nonexistent.json"
        forecast_ranges = {'Mt. Baker': [5, 10]}
        
        result = update_forecast_with_our_forecast(str(nonexistent), forecast_ranges)
        
        self.assertFalse(result)
    
    def test_update_with_empty_ranges(self):
        """Test updating with empty forecast ranges dict"""
        forecast_ranges = {}
        
        result = update_forecast_with_our_forecast(str(self.forecast_file), forecast_ranges)
        
        # Should succeed but not change anything
        self.assertTrue(result)
        
        with open(self.forecast_file, 'r') as f:
            updated = json.load(f)
        
        # Original values should remain
        self.assertEqual(updated['areas']['Mt. Baker']['accumulated_snowfall']['our_forecast']['range'], [0, 0])


class TestCalculateForecastError(unittest.TestCase):
    """Tests for forecast error calculation"""
    
    def test_zero_error(self):
        """Test when forecast equals actual"""
        result = calculate_forecast_error(10.0, 10.0)
        
        self.assertEqual(result['error'], 0.0)
        self.assertEqual(result['absolute_error'], 0.0)
        self.assertEqual(result['percent_error'], 0.0)
    
    def test_positive_error(self):
        """Test when actual is greater than forecast"""
        result = calculate_forecast_error(10.0, 15.0)
        
        self.assertEqual(result['error'], 5.0)
        self.assertEqual(result['absolute_error'], 5.0)
        # percent error = (abs_error / actual) * 100 = (5.0 / 15.0) * 100 = 33.3%
        self.assertAlmostEqual(result['percent_error'], 33.3, places=1)
    
    def test_negative_error(self):
        """Test when forecast is greater than actual"""
        result = calculate_forecast_error(15.0, 10.0)
        
        self.assertEqual(result['error'], -5.0)
        self.assertEqual(result['absolute_error'], 5.0)
        self.assertEqual(result['percent_error'], 50.0)
    
    def test_zero_actual_value(self):
        """Test when actual value is zero"""
        result = calculate_forecast_error(10.0, 0.0)
        
        self.assertEqual(result['error'], -10.0)
        self.assertEqual(result['absolute_error'], 10.0)
        self.assertEqual(result['percent_error'], 0.0)  # Should be 0 to avoid division by zero
    
    def test_rounding(self):
        """Test that values are properly rounded"""
        result = calculate_forecast_error(10.123, 10.456)
        
        self.assertEqual(result['error'], 0.33)  # Rounded to 2 decimals
        self.assertEqual(result['absolute_error'], 0.33)
        self.assertIsInstance(result['percent_error'], float)


class TestNewSnowEstimate(unittest.TestCase):
    """Tests for snow density estimation"""
    
    def test_very_cold_snow(self):
        """Test snow density for very cold temperatures"""
        # -20F should produce light, fluffy snow
        result = new_snow_estimate(1.0, -20)
        
        self.assertGreater(result, 0)  # Should produce positive depth
        # Very cold snow should have high depth ratio (low density)
    
    def test_warm_snow(self):
        """Test snow density for warm temperatures"""
        # 35F (just above freezing) should produce denser snow
        result = new_snow_estimate(1.0, 35)
        
        self.assertGreater(result, 0)
    
    def test_swe_calculation(self):
        """Test that SWE is converted correctly"""
        # Higher SWE should produce deeper snow (all else equal)
        result1 = new_snow_estimate(0.5, -10)
        result2 = new_snow_estimate(1.0, -10)
        
        self.assertGreater(result2, result1)
    
    def test_zero_swe(self):
        """Test with zero SWE"""
        result = new_snow_estimate(0.0, -10)
        
        self.assertEqual(result, 0.0)


class TestIntegration(unittest.TestCase):
    """Integration tests for the full workflow"""
    
    def setUp(self):
        """Create temporary directory structure"""
        self.test_dir = tempfile.mkdtemp()
        self.forecast_dir = Path(self.test_dir) / "forecast"
        self.forecast_dir.mkdir()
    
    def tearDown(self):
        """Clean up temporary files"""
        shutil.rmtree(self.test_dir)
    
    def test_scrape_and_update_workflow(self):
        """Test the complete scrape and update workflow"""
        # Create test HTML
        html_file = Path(self.test_dir) / "test_forecast.html"
        html_content = """
        <section class="forecast-section">
            <h2>Precipitation & Snowfall</h2>
            <ul>
                <li><strong>Mt. Baker:</strong> 5-10"</li>
                <li><strong>Stevens Pass:</strong> 3-12"</li>
            </ul>
        </section>
        """
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Create test forecast JSON
        forecast_file = self.forecast_dir / "test_forecast.json"
        forecast_data = {
            "post_date": "2025-11-27",
            "valid_dates": ["2025-11-28"],
            "areas": {
                "Mt. Baker": {
                    "accumulated_snowfall": {
                        "our_forecast": {"range": [0, 0]}
                    }
                },
                "Stevens Pass": {
                    "accumulated_snowfall": {
                        "our_forecast": {"range": [0, 0]}
                    }
                }
            }
        }
        with open(forecast_file, 'w') as f:
            json.dump(forecast_data, f)
        
        # Step 1: Scrape
        ranges = scrape_forecast_ranges(str(html_file))
        self.assertEqual(len(ranges), 2)
        
        # Step 2: Update
        success = update_forecast_with_our_forecast(str(forecast_file), ranges)
        self.assertTrue(success)
        
        # Step 3: Verify
        with open(forecast_file, 'r') as f:
            updated = json.load(f)
        
        self.assertEqual(updated['areas']['Mt. Baker']['accumulated_snowfall']['our_forecast']['range'], [5, 10])
        self.assertEqual(updated['areas']['Stevens Pass']['accumulated_snowfall']['our_forecast']['range'], [3, 12])


if __name__ == '__main__':
    unittest.main()
