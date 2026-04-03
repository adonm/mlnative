"""
Bridge to Rust rendering daemon.

Handles subprocess communication with the native renderer.
Uses pre-built Rust binaries with statically linked MapLibre Native.
"""

import json
import logging
import os
import queue
import subprocess
import sys
import threading
from collections import deque
from contextlib import suppress
from pathlib import Path
from typing import Any

from .exceptions import MlnativeError

DEFAULT_TIMEOUT = 30.0
PROTOCOL_VERSION = "2.0"
STDERR_BUFFER_LINES = 50
MAX_BATCH_VIEWS = 128
PATH_BINARY_OPT_IN_ENV = "MLNATIVE_USE_SYSTEM_BINARY"

logger = logging.getLogger(__name__)


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


def _get_timeout(timeout: float | None = None) -> float:
    """Return the configured renderer timeout in seconds."""
    raw_value: str | float = (
        os.environ.get("MLNATIVE_TIMEOUT", DEFAULT_TIMEOUT) if timeout is None else timeout
    )

    try:
        parsed_timeout = float(raw_value)
    except (TypeError, ValueError) as e:
        raise MlnativeError("MLNATIVE_TIMEOUT must be a positive number") from e

    if parsed_timeout <= 0:
        raise MlnativeError("MLNATIVE_TIMEOUT must be a positive number")

    return parsed_timeout


def _env_flag_enabled(name: str) -> bool:
    """Return true when an environment flag is explicitly enabled."""
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


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

    # Check PATH only when explicitly enabled.
    if _env_flag_enabled(PATH_BINARY_OPT_IN_ENV):
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            path = Path(path_dir) / binary_name
            if path.exists():
                return path

    raise MlnativeError(
        f"Native renderer binary not found: {binary_name}\n"
        f"Searched in: {pkg_dir / 'bin'}\n"
        f"PATH lookup is disabled by default. Set {PATH_BINARY_OPT_IN_ENV}=1 to opt in.\n"
        f"For source builds, run: just build-rust"
    )


class RenderDaemon:
    """Persistent daemon process for batch rendering."""

    def _format_renderer_error(self, error: Any) -> str:
        """Format a renderer error for callers without leaking stderr details."""
        return str(error)

    def _log_renderer_error(self, message: str, error: Any) -> None:
        """Log renderer failures with recent stderr for debugging."""
        if self._stderr_lines:
            logger.error(
                "%s: %s | recent_stderr=%s",
                message,
                error,
                list(self._stderr_lines),
            )
        else:
            logger.error("%s: %s", message, error)


    def __init__(self, timeout: float | None = None) -> None:
        self._process: subprocess.Popen[bytes] | None = None
        self._stderr_lines: deque[str] = deque(maxlen=STDERR_BUFFER_LINES)
        self._initialized = False
        self._stderr_thread: threading.Thread | None = None
        self._reader_thread: threading.Thread | None = None
        self._command_lock = threading.Lock()
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._timeout = _get_timeout(timeout)

    def _drain_stderr(self) -> None:
        """Background thread to drain stderr, retain recent lines, and log them."""
        if self._process is None or self._process.stderr is None:
            return

        for raw_line in self._process.stderr:
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            self._stderr_lines.append(line)
            logger.debug("renderer.stderr: %s", line)

    def _read_exact(self, size: int) -> bytes:
        """Read an exact number of bytes from stdout."""
        if self._process is None or self._process.stdout is None:
            raise EOFError("Renderer process not started")

        remaining = size
        chunks: list[bytes] = []
        while remaining > 0:
            chunk = self._process.stdout.read(remaining)
            if not chunk:
                raise EOFError("Renderer process closed unexpectedly")
            chunks.append(chunk)
            remaining -= len(chunk)

        return b"".join(chunks)

    def _read_responses(self) -> None:
        """Background thread to parse daemon responses."""
        if self._process is None or self._process.stdout is None:
            return

        try:
            while True:
                header_line = self._process.stdout.readline()
                if not header_line:
                    self._responses.put(
                        {
                            "status": "error",
                            "error": "Renderer process closed unexpectedly",
                        }
                    )
                    return

                try:
                    response: dict[str, Any] = json.loads(header_line.decode("utf-8"))
                except json.JSONDecodeError as e:
                    self._responses.put(
                        {
                            "status": "error",
                            "error": f"Invalid response from renderer: {e}",
                        }
                    )
                    return

                if "png_len" in response:
                    png_len = int(response["png_len"])
                    response["png"] = self._read_exact(png_len)
                elif "png_lengths" in response:
                    lengths = [int(length) for length in response.get("png_lengths", [])]
                    payload = self._read_exact(sum(lengths))
                    cursor = 0
                    pngs: list[bytes] = []
                    for length in lengths:
                        next_cursor = cursor + length
                        pngs.append(payload[cursor:next_cursor])
                        cursor = next_cursor
                    response["pngs"] = pngs

                self._responses.put(response)
        except EOFError:
            self._responses.put(
                {
                    "status": "error",
                    "error": "Renderer process closed unexpectedly",
                }
            )
        except Exception as e:
            self._responses.put(
                {
                    "status": "error",
                    "error": f"Renderer reader failed: {e}",
                }
            )

    def start(self, width: int, height: int, style: str, pixel_ratio: float = 1.0) -> None:
        """Start the daemon and initialize the renderer."""
        if self._process is not None:
            raise MlnativeError("Daemon already started")

        self._stderr_lines.clear()
        binary_path = get_binary_path()

        try:
            self._process = subprocess.Popen(
                [str(binary_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
            )
            self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
            self._stderr_thread.start()
            self._reader_thread = threading.Thread(target=self._read_responses, daemon=True)
            self._reader_thread.start()
        except OSError as e:
            raise MlnativeError(f"Failed to start renderer: {e}") from e

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
            self._log_renderer_error("renderer init failed", response.get("error", "Unknown error"))
            self.stop()
            error_msg = self._format_renderer_error(response.get("error", "Unknown error"))
            if "protocol version" in str(error_msg).lower():
                error_msg = (
                    f"{error_msg}\n"
                    f"Client protocol: {PROTOCOL_VERSION}\n"
                    f"This usually means the Rust binary is outdated. "
                    f"Rebuild with: just build-rust"
                )
            raise MlnativeError(f"Failed to initialize renderer: {error_msg}")

        self._initialized = True

    def _send_command(
        self, cmd: dict[str, Any], timeout: float | None = None
    ) -> dict[str, Any]:
        """Send a command to the daemon and get response.

        Args:
            cmd: Command dictionary to send
            timeout: Maximum time to wait for response in seconds

        Raises:
            MlnativeError: If daemon not started, timeout, or invalid response
        """
        if self._process is None or self._process.stdin is None:
            raise MlnativeError("Daemon not started")

        wait_timeout = self._timeout if timeout is None else _get_timeout(timeout)
        cmd_json = (json.dumps(cmd) + "\n").encode("utf-8")

        with self._command_lock:
            try:
                self._process.stdin.write(cmd_json)
                self._process.stdin.flush()
            except BrokenPipeError:
                raise MlnativeError("Renderer process closed unexpectedly") from None

            try:
                return self._responses.get(timeout=wait_timeout)
            except queue.Empty as e:
                raise MlnativeError(
                    f"Timeout waiting for renderer response after {wait_timeout}s"
                ) from e

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
            self._log_renderer_error("renderer render failed", response.get("error"))
            raise MlnativeError(
                f"Render failed: {self._format_renderer_error(response.get('error'))}"
            )

        png = response.get("png")
        if not isinstance(png, bytes) or not png:
            raise MlnativeError("Render returned no image data")

        return png

    def render_batch(self, views: list[dict[str, Any]]) -> list[bytes]:
        """Render multiple views efficiently."""
        if not self._initialized:
            raise MlnativeError("Renderer not initialized")
        if len(views) > MAX_BATCH_VIEWS:
            raise MlnativeError(
                f"Batch render supports at most {MAX_BATCH_VIEWS} views, got {len(views)}"
            )

        cmd = {
            "cmd": "render_batch",
            "views": views,
        }

        response = self._send_command(cmd)

        if response.get("status") != "ok":
            self._log_renderer_error("renderer batch failed", response.get("error"))
            raise MlnativeError(
                f"Batch render failed: {self._format_renderer_error(response.get('error'))}"
            )

        pngs = response.get("pngs")
        if not isinstance(pngs, list):
            raise MlnativeError("Batch render returned no image data")

        return pngs

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
            self._log_renderer_error("renderer style reload failed", response.get("error"))
            raise MlnativeError(
                f"Style reload failed: {self._format_renderer_error(response.get('error'))}"
            )

    def stop(self) -> None:
        """Stop the daemon."""
        if self._process is not None and self._process.poll() is None:
            with suppress(Exception):
                if self._process.stdin is not None:
                    self._process.stdin.write(b'{"cmd":"quit"}\n')
                    self._process.stdin.flush()

            try:
                self._process.wait(timeout=5)
            except Exception:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except Exception:
                    self._process.kill()

        self._process = None
        self._initialized = False
        self._stderr_lines.clear()
        self._stderr_thread = None
        self._reader_thread = None
        while True:
            try:
                self._responses.get_nowait()
            except queue.Empty:
                break

    def __enter__(self) -> "RenderDaemon":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.stop()
