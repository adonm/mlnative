"""
Bridge to Rust rendering daemon.

Handles subprocess communication with the native renderer.
Uses pre-built Rust binaries with statically linked MapLibre Native.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

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


def get_binary_path() -> Path:
    """Get the path to the native renderer binary."""
    platform_name, arch = _get_platform_info()
    binary_name = f"mlnative-render-{platform_name}-{arch}"

    if sys.platform == "win32":
        binary_name += ".exe"

    # Check in package directory
    pkg_dir = Path(__file__).parent
    binary_path = pkg_dir / "bin" / binary_name

    if binary_path.exists():
        return binary_path

    # Check in PATH
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        path = Path(path_dir) / binary_name
        if path.exists():
            return path

    raise MlnativeError(
        f"Native renderer binary not found: {binary_name}\n"
        f"Please install with: pip install mlnative-binary"
    )


class RenderDaemon:
    """Persistent daemon process for batch rendering."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._initialized = False

    def start(self, width: int, height: int, style: str) -> None:
        """Start the daemon and initialize the renderer."""
        if self._process is not None:
            raise MlnativeError("Daemon already started")

        binary_path = get_binary_path()

        try:
            self._process = subprocess.Popen(
                [str(binary_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as e:
            raise MlnativeError(f"Failed to start renderer: {e}") from e

        # Initialize
        init_cmd = {
            "cmd": "init",
            "width": width,
            "height": height,
            "style": style,
        }

        response = self._send_command(init_cmd)
        if response.get("status") != "ok":
            self.stop()
            raise MlnativeError(f"Failed to initialize renderer: {response.get('error')}")

        self._initialized = True

    def _send_command(self, cmd: dict[str, Any]) -> dict[str, Any]:
        """Send a command to the daemon and get response."""
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise MlnativeError("Daemon not started")

        # Send command
        cmd_json = json.dumps(cmd) + "\n"
        self._process.stdin.write(cmd_json)
        self._process.stdin.flush()

        # Read response
        response_line = self._process.stdout.readline()
        if not response_line:
            raise MlnativeError("Renderer process closed unexpectedly")

        try:
            result: dict[str, Any] = json.loads(response_line)
            return result
        except json.JSONDecodeError as e:
            raise MlnativeError(f"Invalid response from renderer: {e}") from e

    def render(
        self, center: list[float], zoom: float, bearing: float = 0, pitch: float = 0
    ) -> bytes:
        """Render a single map view."""
        if not self._initialized:
            raise MlnativeError("Renderer not initialized")

        cmd = {
            "cmd": "render",
            "center": center,
            "zoom": zoom,
            "bearing": bearing,
            "pitch": pitch,
        }

        response = self._send_command(cmd)

        if response.get("status") != "ok":
            raise MlnativeError(f"Render failed: {response.get('error')}")

        import base64

        png_b64 = response.get("png")
        if not png_b64:
            raise MlnativeError("Render returned no image data")

        return base64.b64decode(png_b64)

    def render_batch(self, views: list[dict[str, Any]]) -> list[bytes]:
        """Render multiple views efficiently."""
        if not self._initialized:
            raise MlnativeError("Renderer not initialized")

        cmd = {
            "cmd": "render_batch",
            "views": views,
        }

        response = self._send_command(cmd)

        if response.get("status") != "ok":
            raise MlnativeError(f"Batch render failed: {response.get('error')}")

        import base64

        pngs_b64 = response.get("png", "").split(",")
        return [base64.b64decode(png) for png in pngs_b64 if png]

    def stop(self) -> None:
        """Stop the daemon."""
        if self._process is not None and self._process.poll() is None:
            try:
                self._send_command({"cmd": "quit"})
                self._process.wait(timeout=5)
            except Exception:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except Exception:
                    self._process.kill()

        self._process = None
        self._initialized = False

    def __enter__(self) -> "RenderDaemon":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.stop()
