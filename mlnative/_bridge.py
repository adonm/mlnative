"""
Bridge to Rust rendering daemon.

Handles subprocess communication with the native renderer.
Uses pre-built Rust binaries with statically linked MapLibre Native.
"""

import base64
import json
import os
import subprocess
import sys
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

from .exceptions import MlnativeError

DEFAULT_TIMEOUT = 30.0
PROTOCOL_VERSION = "1.0"


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
        # Ensure binary is executable (permissions may be stripped in wheels)
        if sys.platform != "win32" and not os.access(binary_path, os.X_OK):
            os.chmod(binary_path, 0o755)
        return binary_path

    # Check in PATH
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        path = Path(path_dir) / binary_name
        if path.exists():
            return path

    raise MlnativeError(
        f"Native renderer binary not found: {binary_name}\n"
        f"Searched in: {pkg_dir / 'bin'}\n"
        f"Ensure the binary is included in the package or available in PATH.\n"
        f"For source builds, run: just build-rust"
    )


class RenderDaemon:
    """Persistent daemon process for batch rendering."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._initialized = False
        self._stderr_thread: threading.Thread | None = None

    def _drain_stderr(self) -> None:
        """Background thread to drain stderr and prevent deadlock."""
        if self._process is not None and self._process.stderr is not None:
            for _line in self._process.stderr:
                pass  # Discard stderr silently

    def start(self, width: int, height: int, style: str, pixel_ratio: float = 1.0) -> None:
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
            # Start background thread to drain stderr and prevent deadlock
            self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
            self._stderr_thread.start()
        except OSError as e:
            raise MlnativeError(f"Failed to start renderer: {e}") from e

        # Initialize
        init_cmd = {
            "cmd": "init",
            "width": width,
            "height": height,
            "style": style,
            "pixel_ratio": pixel_ratio,
            "protocol_version": PROTOCOL_VERSION,
        }

        response = self._send_command(init_cmd)
        if response.get("status") != "ok":
            self.stop()
            error_msg = response.get("error", "Unknown error")
            if "protocol version" in error_msg.lower():
                error_msg = (
                    f"{error_msg}\n"
                    f"Client protocol: {PROTOCOL_VERSION}\n"
                    f"This usually means the Rust binary is outdated. "
                    f"Rebuild with: just build-rust"
                )
            raise MlnativeError(f"Failed to initialize renderer: {error_msg}")

        self._initialized = True

    def _send_command(
        self, cmd: dict[str, Any], timeout: float = DEFAULT_TIMEOUT
    ) -> dict[str, Any]:
        """Send a command to the daemon and get response.

        Args:
            cmd: Command dictionary to send
            timeout: Maximum time to wait for response in seconds

        Raises:
            MlnativeError: If daemon not started, timeout, or invalid response
        """
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise MlnativeError("Daemon not started")

        # Send command (write is typically fast, no timeout needed)
        cmd_json = json.dumps(cmd) + "\n"
        try:
            self._process.stdin.write(cmd_json)
            self._process.stdin.flush()
        except BrokenPipeError:
            raise MlnativeError("Renderer process closed unexpectedly") from None

        # Read response with timeout using a thread
        response_line: str = ""

        def read_line() -> None:
            nonlocal response_line
            assert self._process is not None and self._process.stdout is not None
            with suppress(Exception):
                response_line = self._process.stdout.readline()

        read_thread = threading.Thread(target=read_line, daemon=True)
        read_thread.start()
        read_thread.join(timeout=timeout)
        if read_thread.is_alive():
            raise MlnativeError(f"Timeout waiting for renderer response after {timeout}s")

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

        pngs_b64 = response.get("png", "").split(",")
        return [base64.b64decode(png) for png in pngs_b64 if png]

    def reload_style(self, style: str) -> None:
        """Reload the style without restarting the daemon.

        Args:
            style: Style URL string or JSON string

        Raises:
            MlnativeError: If style reload fails
        """
        if not self._initialized:
            raise MlnativeError("Renderer not initialized")

        cmd = {
            "cmd": "reload_style",
            "style": style,
        }

        response = self._send_command(cmd)

        if response.get("status") != "ok":
            raise MlnativeError(f"Style reload failed: {response.get('error')}")

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
