"""
Main Map class for mlnative.

Uses native Rust renderer with statically linked MapLibre Native.
Provides synchronous and async APIs for static map rendering.
"""

import json
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ._bridge import RenderDaemon
from .exceptions import MlnativeError

# OpenFreeMap Liberty style as default
DEFAULT_STYLE = "https://tiles.openfreemap.org/styles/liberty"

# Validation limits
MAX_DIMENSION = 4096
MAX_ZOOM = 24
MAX_PITCH = 85


class Map:
    """
    A MapLibre GL Native map renderer using native Rust backend.

    Simple usage:
        map = Map(512, 512)
        map.load_style("https://example.com/style.json")
        png_bytes = map.render(center=[-122.4, 37.8], zoom=12)

    With context manager (auto cleanup):
        with Map(512, 512) as map:
            map.load_style("style.json")
            png_bytes = map.render(center=[0, 0], zoom=5)

    Batch rendering (efficient):
        with Map(512, 512) as map:
            map.load_style("style.json")
            views = [
                {"center": [0, 0], "zoom": 5},
                {"center": [10, 10], "zoom": 8},
                # ... more views
            ]
            pngs = map.render_batch(views)
    """

    def __init__(
        self,
        width: int,
        height: int,
        request_handler: Callable[[Any], bytes] | None = None,
        pixel_ratio: float = 1.0,
    ):
        """
        Create a new map renderer.

        Args:
            width: Image width in pixels (1-4096)
            height: Image height in pixels (1-4096)
            request_handler: Optional function to handle custom tile requests.
                           Not yet implemented.
            pixel_ratio: Pixel ratio for high-DPI rendering (default 1.0)
        """
        if width <= 0 or height <= 0:
            raise MlnativeError(f"Width and height must be positive, got {width}x{height}")

        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            raise MlnativeError(
                f"Width and height must be <= {MAX_DIMENSION}, got {width}x{height}"
            )

        if request_handler is not None:
            warnings.warn(
                "request_handler is not yet implemented and will be ignored. "
                "This feature is planned for a future release.",
                FutureWarning,
                stacklevel=2,
            )

        self.width = width
        self.height = height
        self.pixel_ratio = pixel_ratio
        self._style: str | dict[str, Any] | None = None
        self._daemon: RenderDaemon | None = None
        self._closed = False

    def _get_daemon(self) -> RenderDaemon:
        """Get or create the render daemon."""
        if self._daemon is None:
            self._daemon = RenderDaemon()

            # Get style string
            style = self._style
            if style is None:
                style = DEFAULT_STYLE

            if isinstance(style, dict):
                style = json.dumps(style)
            elif isinstance(style, Path):
                style = json.dumps(json.loads(style.read_text()))

            self._daemon.start(self.width, self.height, str(style))

        return self._daemon

    def load_style(self, style: str | dict[str, Any] | Path) -> None:
        """
        Load a map style.

        Args:
            style: URL string, file path, or style JSON dict

        Raises:
            MlnativeError: If style format is invalid
        """
        if self._closed:
            raise MlnativeError("Map has been closed")

        if isinstance(style, dict):
            self._style = style
        elif isinstance(style, (str, Path)):
            style_str = str(style)
            parsed = urlparse(style_str)

            if parsed.scheme in ("http", "https"):
                # URL style
                self._style = style_str
            elif parsed.scheme == "":
                # File path
                path = Path(style)
                if not path.exists():
                    raise MlnativeError(f"Style file not found: {style}")
                try:
                    with open(path) as f:
                        self._style = json.load(f)
                except json.JSONDecodeError as e:
                    raise MlnativeError(f"Invalid JSON in style file: {e}") from e
            else:
                raise MlnativeError(f"Unsupported style format: {style}")
        else:
            raise MlnativeError(f"Style must be str, dict, or Path, got {type(style)}")

        # Reset daemon so it picks up new style
        if self._daemon is not None:
            self._daemon.stop()
            self._daemon = None

    def render(
        self, center: list[float], zoom: float, bearing: float = 0, pitch: float = 0
    ) -> bytes:
        """
        Render the map to PNG bytes.

        Args:
            center: [longitude, latitude] of map center
            zoom: Zoom level (0-24)
            bearing: Rotation in degrees (default 0, normalized to 0-360)
            pitch: Tilt in degrees (0-85, default 0)

        Returns:
            PNG image bytes

        Raises:
            MlnativeError: If rendering fails or parameters are invalid
        """
        if self._closed:
            raise MlnativeError("Map has been closed")

        if self._style is None:
            # Use default OpenFreeMap Liberty style
            self._style = DEFAULT_STYLE

        # Validate center
        if len(center) != 2:
            raise MlnativeError(f"Center must be [longitude, latitude], got {center}")

        lon, lat = center
        if not (-180 <= lon <= 180):
            raise MlnativeError(f"Longitude must be -180 to 180, got {lon}")
        if not (-90 <= lat <= 90):
            raise MlnativeError(f"Latitude must be -90 to 90, got {lat}")

        # Validate zoom
        if not (0 <= zoom <= MAX_ZOOM):
            raise MlnativeError(f"Zoom must be 0-{MAX_ZOOM}, got {zoom}")

        # Validate pitch
        if not (0 <= pitch <= MAX_PITCH):
            raise MlnativeError(f"Pitch must be 0-{MAX_PITCH}, got {pitch}")

        # Normalize bearing to 0-360
        bearing = bearing % 360

        try:
            daemon = self._get_daemon()
            return daemon.render(center, zoom, bearing, pitch)
        except Exception as e:
            raise MlnativeError(f"Render failed: {e}") from e

    def render_batch(self, views: list[dict[str, Any]]) -> list[bytes]:
        """
        Render multiple map views efficiently.

        This is much faster than calling render() multiple times because
        the renderer process stays alive and reuses the loaded style.

        Args:
            views: List of view dictionaries, each with keys:
                   - center: [longitude, latitude]
                   - zoom: float
                   - bearing: float (optional, default 0)
                   - pitch: float (optional, default 0)

        Returns:
            List of PNG image bytes

        Example:
            views = [
                {"center": [0, 0], "zoom": 5},
                {"center": [10, 10], "zoom": 8, "bearing": 45},
            ]
            pngs = map.render_batch(views)
        """
        if self._closed:
            raise MlnativeError("Map has been closed")

        if self._style is None:
            self._style = DEFAULT_STYLE

        # Validate and normalize views
        normalized_views = []
        for i, view in enumerate(views):
            center = view.get("center")
            if not center or len(center) != 2:
                raise MlnativeError(f"View {i}: Invalid center")

            lon, lat = center
            if not (-180 <= lon <= 180):
                raise MlnativeError(f"View {i}: Longitude must be -180 to 180")
            if not (-90 <= lat <= 90):
                raise MlnativeError(f"View {i}: Latitude must be -90 to 90")

            zoom = view.get("zoom", 0)
            if not (0 <= zoom <= MAX_ZOOM):
                raise MlnativeError(f"View {i}: Zoom must be 0-{MAX_ZOOM}")

            pitch = view.get("pitch", 0)
            if not (0 <= pitch <= MAX_PITCH):
                raise MlnativeError(f"View {i}: Pitch must be 0-{MAX_PITCH}")

            bearing = view.get("bearing", 0) % 360

            normalized_views.append(
                {
                    "center": center,
                    "zoom": zoom,
                    "bearing": bearing,
                    "pitch": pitch,
                }
            )

        try:
            daemon = self._get_daemon()
            return daemon.render_batch(normalized_views)
        except Exception as e:
            raise MlnativeError(f"Batch render failed: {e}") from e

    def close(self) -> None:
        """Close the map and release resources."""
        if self._daemon is not None:
            self._daemon.stop()
            self._daemon = None
        self._closed = True
        self._style = None

    def __enter__(self) -> "Map":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    def __del__(self) -> None:
        """Destructor - ensure cleanup."""
        if hasattr(self, "_closed") and not self._closed:
            self.close()
