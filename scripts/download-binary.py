#!/usr/bin/env python3
"""
Native binary helper for mlnative.

This helper now fails closed instead of downloading unverified executables.
"""

import platform
import sys


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
    """Refuse unverified binary downloads."""
    platform_id = get_platform()
    binary_name = f"mlnative-render-{platform_id}"

    if sys.platform == "win32":
        binary_name += ".exe"

    base_url = "https://github.com/adonm/mlnative/releases/download"
    if version == "latest":
        url = f"{base_url}/latest/{binary_name}"
    else:
        url = f"{base_url}/{version}/{binary_name}"

    raise RuntimeError(
        "Refusing to download and execute an unverified binary artifact. "
        f"Fetch {url} through a verified release process or install mlnative from a trusted package."
    )


if __name__ == "__main__":
    download_binary()
