#!/usr/bin/env python3
"""
Image Scraper for CW3E West-WRF Snow Meteogram Panel Images

Downloads and saves CW3E West-WRF 3hr snow meteogram panel images into 
site-based directories under assets/images/cw3e/.
"""

import os
import time
from pathlib import Path
from typing import Dict, Optional, Union
from datetime import datetime

import requests


# Constants
BASE_URL = "https://cw3e.ucsd.edu/images/wwrf/images/ensemble/"
SITES: Dict[str, str] = {
    "paradis": "West-WRF_3hrSnow_Meteogram_Panel_MRNP.png"
}


def _download_file(
    url: str,
    dest_path: Path,
    session: Optional[requests.Session] = None,
    timeout: int = 10,
    retries: int = 3
) -> None:
    """
    Download a file from URL to destination path with retry logic.
    
    Args:
        url: URL to download from
        dest_path: Destination path to save file
        session: Optional requests.Session to use
        timeout: Timeout in seconds for the request
        retries: Number of retry attempts
        
    Raises:
        RuntimeError: If download fails after all retries
    """
    if session is None:
        session = requests.Session()
    
    last_exception = None
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=timeout)
            
            # Validate status code
            if response.status_code != 200:
                raise RuntimeError(
                    f"HTTP {response.status_code} error for URL: {url}"
                )
            
            # Validate Content-Type
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                raise RuntimeError(
                    f"Invalid Content-Type '{content_type}' for URL: {url}. "
                    f"Expected image/*"
                )
            
            # Write bytes to destination
            dest_path.write_bytes(response.content)
            
            # Set file permissions to 0o644
            os.chmod(dest_path, 0o644)
            
            return  # Success
            
        except Exception as e:
            last_exception = e
            if attempt < retries - 1:
                # Exponential backoff: wait 2^attempt seconds
                wait_time = 2 ** attempt
                time.sleep(wait_time)
            else:
                # Last attempt failed
                raise RuntimeError(
                    f"Failed to download {url} after {retries} attempts: {e}"
                ) from last_exception


def _ensure_dir(path: Path) -> None:
    """
    Ensure directory exists with proper permissions.
    
    Args:
        path: Directory path to create
    """
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o755)


def download_cw3e_westwrf_snow(
    sites: Optional[Dict[str, str]] = None,
    target_root: Union[str, Path] = "assets/images/cw3e/",
    timeout: int = 10,
    retries: int = 3
) -> Dict[str, Path]:
    """
    Download CW3E West-WRF snow meteogram panel images for specified sites.
    
    For each site, downloads the image to a canonical path and also creates
    a timestamped archival copy.
    
    Args:
        sites: Dictionary mapping site_name -> source_filename. 
               If None, uses SITES constant.
        target_root: Root directory for downloads
        timeout: Timeout in seconds for downloads
        retries: Number of retry attempts for each download
        
    Returns:
        Dictionary mapping site_name -> canonical file path
        
    Raises:
        RuntimeError: If any download fails
    """
    if sites is None:
        sites = SITES
    
    # Convert target_root to Path
    target_root = Path(target_root)
    
    # Create session for connection reuse
    session = requests.Session()
    
    result = {}
    
    for site_name, source_filename in sites.items():
        # Construct source URL
        url = BASE_URL + source_filename
        
        # Ensure site directory exists
        site_dir = target_root / site_name
        _ensure_dir(site_dir)
        
        # Define canonical path
        canonical_path = site_dir / source_filename
        
        # Download to canonical path
        try:
            _download_file(url, canonical_path, session, timeout, retries)
            print(f"Downloaded {site_name}: {canonical_path}")
        except RuntimeError as e:
            print(f"Error downloading {site_name}: {e}")
            raise
        
        # Create timestamped archival copy
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_filename = f"{timestamp}_{source_filename}"
        archive_path = site_dir / archive_filename
        
        try:
            # Copy the canonical file to archive
            archive_path.write_bytes(canonical_path.read_bytes())
            os.chmod(archive_path, 0o644)
            print(f"Archived {site_name}: {archive_path}")
        except Exception as e:
            print(f"Warning: Failed to create archive copy for {site_name}: {e}")
            # Don't fail the entire operation if archiving fails
        
        result[site_name] = canonical_path
    
    return result


def main():
    """Example usage of the image scraper."""
    print("CW3E West-WRF Snow Meteogram Image Scraper")
    print("=" * 60)
    print(f"\nBase URL: {BASE_URL}")
    print(f"Sites configured: {list(SITES.keys())}")
    print("\nDownloading images...")
    
    try:
        downloaded = download_cw3e_westwrf_snow()
        print("\n" + "=" * 60)
        print("Download complete!")
        print("\nDownloaded files:")
        for site_name, path in downloaded.items():
            print(f"  {site_name}: {path}")
    except Exception as e:
        print(f"\nError: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
