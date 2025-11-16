#!/usr/bin/env python3
"""
Image Scraper Script
Downloads weather forecast images from various sources for use in blog posts
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
CW3E_WESTWRF_SNOW_URL = "https://cw3e.ucsd.edu/images/wwrf/images/ensemble/West-WRF_3hrSnow_Meteogram_Panel_MRNP.png"
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def download_cw3e_westwrf_snow() -> str:
    """
    Download CW3E West-WRF 3hr snow meteogram panel image.
    
    Downloads the Paradis West-WRF snow ensemble image from CW3E and saves it
    to assets/images/cw3e/ with both a current filename and a timestamped
    archival copy.
    
    Returns:
        str: Path to the saved file on success
        
    Raises:
        requests.exceptions.RequestException: On network or HTTP errors
        ValueError: On invalid response content
    """
    logger.info(f"Starting download of CW3E West-WRF snow meteogram from {CW3E_WESTWRF_SNOW_URL}")
    
    # Create target directory
    target_dir = Path('assets/images/cw3e')
    target_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Ensured target directory exists: {target_dir}")
    
    # Download with retry logic
    response = _download_with_retry(CW3E_WESTWRF_SNOW_URL, MAX_RETRIES)
    
    # Validate response
    _validate_response(response)
    
    # Save files
    current_filename = "West-WRF_3hrSnow_Meteogram_Panel_MRNP.png"
    current_path = target_dir / current_filename
    
    # Save current file
    _save_image_file(current_path, response.content)
    logger.info(f"Saved current file: {current_path}")
    
    # Save timestamped archive copy
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_filename = f"West-WRF_3hrSnow_Meteogram_Panel_MRNP_{timestamp}.png"
    archive_path = target_dir / archive_filename
    _save_image_file(archive_path, response.content)
    logger.info(f"Saved timestamped archive: {archive_path}")
    
    logger.info(f"Successfully downloaded and saved CW3E West-WRF snow meteogram")
    return str(current_path)


def _download_with_retry(url: str, max_retries: int) -> requests.Response:
    """
    Download a file with retry logic for transient failures.
    
    Args:
        url: URL to download
        max_retries: Maximum number of retry attempts
        
    Returns:
        requests.Response: Successful response object
        
    Raises:
        requests.exceptions.RequestException: After all retries exhausted
    """
    last_exception = None
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Attempt {attempt}/{max_retries}: Downloading from {url}")
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            logger.info(f"Successfully downloaded on attempt {attempt}")
            return response
            
        except requests.exceptions.RequestException as e:
            last_exception = e
            logger.warning(f"Attempt {attempt}/{max_retries} failed: {e}")
            
            if attempt < max_retries:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"All {max_retries} attempts failed")
    
    # If we get here, all retries failed
    raise last_exception


def _validate_response(response: requests.Response) -> None:
    """
    Validate HTTP response for image download.
    
    Args:
        response: Response object to validate
        
    Raises:
        ValueError: If response is invalid
    """
    # Check status code (should already be checked by raise_for_status(), but be explicit)
    if response.status_code != 200:
        raise ValueError(f"Invalid status code: {response.status_code}")
    
    # Check Content-Type
    content_type = response.headers.get('Content-Type', '')
    if not content_type.startswith('image/'):
        raise ValueError(f"Invalid Content-Type: {content_type} (expected image/*)")
    
    logger.info(f"Response validated: status={response.status_code}, content-type={content_type}")


def _save_image_file(path: Path, content: bytes) -> None:
    """
    Save image content to file with appropriate permissions.
    
    Args:
        path: Path to save the file
        content: Image content bytes
    """
    path.write_bytes(content)
    
    # Set appropriate file permissions (readable by owner and group, read-only for others)
    os.chmod(path, 0o644)
    
    logger.debug(f"Saved {len(content)} bytes to {path} with permissions 644")


def main() -> int:
    """
    Main entry point for the image scraper script.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Download weather forecast images from various sources'
    )
    parser.add_argument(
        '--cw3e-westwrf-snow',
        action='store_true',
        help='Download CW3E West-WRF 3hr snow meteogram panel'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Download all available images'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # If no specific scraper selected, run all or show help
    if not any([args.cw3e_westwrf_snow, args.all]):
        parser.print_help()
        logger.info("No scraper selected. Use --all to run all scrapers or specify individual scrapers.")
        return 0
    
    # Track success/failure
    success_count = 0
    failure_count = 0
    
    # Run requested scrapers
    if args.cw3e_westwrf_snow or args.all:
        try:
            path = download_cw3e_westwrf_snow()
            logger.info(f"✓ CW3E West-WRF snow meteogram: {path}")
            success_count += 1
        except Exception as e:
            logger.error(f"✗ CW3E West-WRF snow meteogram failed: {e}")
            failure_count += 1
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Summary: {success_count} succeeded, {failure_count} failed")
    logger.info(f"{'='*60}")
    
    return 0 if failure_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
