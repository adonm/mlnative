"""
Bridge to Bun/JavaScript renderer.

Handles subprocess communication with the bundled JS renderer.
"""

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pybun

from .exceptions import MlnativeError


def _get_platform_info() -> tuple[str, str]:
    """Get normalized platform and architecture."""
    system = sys.platform
    machine = os.uname().machine if hasattr(os, "uname") else "x86_64"

    # Normalize platform names
    platform_map = {
        "darwin": "darwin",
        "linux": "linux",
        "win32": "win32",
    }
    platform_name = platform_map.get(system)
    if not platform_name:
        raise MlnativeError(f"Unsupported platform: {system}")

    # Normalize architecture
    arch_map = {
        "arm64": "arm64",
        "aarch64": "arm64",
        "x86_64": "x64",
        "amd64": "x64",
    }
    arch = arch_map.get(machine)
    if not arch:
        raise MlnativeError(f"Unsupported architecture: {machine}")

    return platform_name, arch


def get_vendor_dir() -> Path:
    """Get the platform-specific vendor directory with bundled node_modules."""
    platform_name, arch = _get_platform_info()
    vendor_name = f"{platform_name}-{arch}"
    vendor_dir = Path(__file__).parent / "_vendor" / vendor_name

    if not vendor_dir.exists():
        raise MlnativeError(
            f"No bundled binaries for {vendor_name}. "
            f"Supported platforms: darwin-arm64, darwin-x64, linux-arm64, linux-x64, win32-x64"
        )

    return vendor_dir


def _validate_png_output(stdout: bytes) -> bytes:
    """Validate that output is valid PNG bytes."""
    if not stdout.startswith(b"\x89PNG"):
        # Might be an error message
        try:
            error_msg = stdout.decode("utf-8", errors="replace")
            raise MlnativeError(f"Render error: {error_msg}")
        except UnicodeDecodeError:
            raise MlnativeError("Render failed: output is not valid PNG") from None
    return stdout


def _run_bun_process(
    bun_path: str, renderer_js: Path, config: dict[str, Any], vendor_dir: Path
) -> bytes:
    """Execute Bun subprocess and return output."""
    env = os.environ.copy()
    env["MLNATIVE_VENDOR_DIR"] = str(vendor_dir)

    try:
        result = subprocess.run(
            [bun_path, str(renderer_js)],
            input=json.dumps(config).encode("utf-8"),
            capture_output=True,
            env=env,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise MlnativeError("Render timeout (60s exceeded)") from None
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else "Unknown error"
        raise MlnativeError(f"Bun process failed:\n{stderr}") from e

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise MlnativeError(f"Bun render failed:\n{stderr}")

    return result.stdout


def render_with_bun(
    config: dict[str, Any], request_handler: Callable[[Any], bytes] | None = None
) -> bytes:
    """
    Render map using Bun subprocess.

    Args:
        config: Map configuration dict
        request_handler: Optional custom request handler

    Returns:
        PNG image bytes

    Raises:
        MlnativeError: If rendering fails
    """
    vendor_dir = get_vendor_dir()
    renderer_js = Path(__file__).parent / "_renderer.js"

    if not renderer_js.exists():
        raise MlnativeError(f"Renderer script not found: {renderer_js}")

    # Get bun path from pybun package (bundled binary)
    bun_path = str(Path(pybun.__file__).parent / "bun")

    # Flag for custom handler (JS side uses temp file protocol)
    config["_hasCustomHandler"] = request_handler is not None

    stdout = _run_bun_process(bun_path, renderer_js, config, vendor_dir)
    return _validate_png_output(stdout)
