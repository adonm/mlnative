#!/usr/bin/env python3
"""
Download native binaries for mlnative.

This script downloads the appropriate native renderer binary for the current platform.
"""

import os
import platform
import sys
import urllib.request
from pathlib import Path


def get_platform():
    """Get platform identifier for binary download."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    # Normalize platform names
    if system == "darwin":
        system = "darwin"
    elif system == "linux":
        system = "linux"
    elif system == "windows":
        system = "win32"
    
    # Normalize architecture
    if machine in ("arm64", "aarch64"):
        arch = "arm64"
    elif machine in ("x86_64", "amd64"):
        arch = "x64"
    else:
        raise RuntimeError(f"Unsupported architecture: {machine}")
    
    return f"{system}-{arch}"


def download_binary(version="latest"):
    """Download the native binary for current platform."""
    platform_id = get_platform()
    binary_name = f"mlnative-render-{platform_id}"
    
    if sys.platform == "win32":
        binary_name += ".exe"
    
    # Determine destination
    pkg_dir = Path(__file__).parent.parent / "mlnative" / "bin"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    
    dest_path = pkg_dir / binary_name
    
    if dest_path.exists():
        print(f"Binary already exists: {dest_path}")
        return dest_path
    
    # Construct download URL
    base_url = "https://github.com/adonm/mlnative/releases/download"
    if version == "latest":
        url = f"{base_url}/latest/{binary_name}"
    else:
        url = f"{base_url}/{version}/{binary_name}"
    
    print(f"Downloading {binary_name}...")
    print(f"URL: {url}")
    
    try:
        urllib.request.urlretrieve(url, dest_path)
        os.chmod(dest_path, 0o755)
        print(f"Downloaded to: {dest_path}")
        return dest_path
    except Exception as e:
        print(f"Failed to download: {e}")
        raise


if __name__ == "__main__":
    download_binary()
