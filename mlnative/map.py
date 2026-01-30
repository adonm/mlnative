"""
Main Map class for mlnative.

Grug principles:
- One simple class, 4 methods max
- Synchronous by default
- Return PNG bytes (no PIL)
- Context manager support
"""

import json
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ._bridge import render_with_bun
from .exceptions import MlnativeError

# OpenFreeMap Liberty style as default
DEFAULT_STYLE = "https://tiles.openfreemap.org/styles/liberty"

# Validation limits
MAX_DIMENSION = 4096
MAX_ZOOM = 24
MAX_PITCH = 85


class Map:
    """
    A MapLibre GL Native map renderer.

    Simple usage:
        map = Map(512, 512)
        map.load_style("https://example.com/style.json")
        png_bytes = map.render(center=[-122.4, 37.8], zoom=12)

    With context manager (auto cleanup):
        with Map(512, 512) as map:
            map.load_style("style.json")
            png_bytes = map.render(center=[0, 0], zoom=5)
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
                           Receives a request object with 'url' and 'method' attributes.
                           Should return bytes or None for 404.
                           NOTE: Not yet implemented, will emit FutureWarning.
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
        self.request_handler = request_handler
        self.pixel_ratio = pixel_ratio
        self._style: str | dict[str, Any] | None = None
        self._closed = False

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

        config = {
            "width": self.width,
            "height": self.height,
            "center": center,
            "zoom": zoom,
            "bearing": bearing,
            "pitch": pitch,
            "pixelRatio": self.pixel_ratio,
            "style": self._style,
        }

        try:
            png_bytes = render_with_bun(config, self.request_handler)
            return png_bytes
        except Exception as e:
            raise MlnativeError(f"Render failed: {e}") from e

    def close(self) -> None:
        """Close the map and release resources."""
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
