"""
Main Map class for mlnative.

Uses native Rust renderer with statically linked MapLibre Native.
Provides synchronous and async APIs for static map rendering.
"""

import json
import math
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from shapely.geometry.base import BaseGeometry

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

            self._daemon.start(self.width, self.height, str(style), self.pixel_ratio)

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

        # Reload style in daemon if already running, otherwise it will pick up on next _get_daemon()
        if self._daemon is not None:
            # Get style string for daemon
            style_for_daemon = self._style
            if isinstance(style_for_daemon, dict):
                style_for_daemon = json.dumps(style_for_daemon)
            elif isinstance(style_for_daemon, Path):
                style_for_daemon = json.dumps(json.loads(style_for_daemon.read_text()))
            self._daemon.reload_style(str(style_for_daemon))

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
                   - geojson: dict[str, Any] (optional) - GeoJSON sources to update before render

        Returns:
            List of PNG image bytes

        Example:
            views = [
                {"center": [0, 0], "zoom": 5},
                {"center": [10, 10], "zoom": 8, "bearing": 45},
                {
                    "center": [20, 20],
                    "zoom": 10,
                    "geojson": {
                        "markers": {"type": "FeatureCollection", "features": [...]}
                    }
                },
            ]
            pngs = map.render_batch(views)
        """
        if self._closed:
            raise MlnativeError("Map has been closed")

        if self._style is None:
            self._style = DEFAULT_STYLE

        # Check if any view has geojson - requires dict style
        has_geojson = any(view.get("geojson") for view in views)
        if has_geojson and isinstance(self._style, str):
            raise MlnativeError(
                "Cannot use geojson in render_batch with URL-loaded style. "
                "Load the style as a dict first."
            )

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

            normalized_view = {
                "center": center,
                "zoom": zoom,
                "bearing": bearing,
                "pitch": pitch,
            }

            # Handle geojson if present
            if "geojson" in view:
                geojson = view["geojson"]
                if isinstance(geojson, dict):
                    normalized_view["geojson"] = geojson
                else:
                    raise MlnativeError(f"View {i}: geojson must be a dict")

            normalized_views.append(normalized_view)

        try:
            # Workaround: If any view has geojson, we can't use efficient batch rendering
            # because maplibre_native doesn't support dynamic source updates.
            # Fall back to individual renders with set_geojson() calls.
            if has_geojson:
                pngs = []
                for _i, view in enumerate(normalized_views):
                    # Update geojson sources if present
                    if "geojson" in view:
                        for source_id, geojson_data in view["geojson"].items():
                            self.set_geojson(source_id, geojson_data)

                    # Render this view
                    png = self.render(
                        center=view["center"],
                        zoom=view["zoom"],
                        bearing=view["bearing"],
                        pitch=view["pitch"],
                    )
                    pngs.append(png)
                return pngs
            else:
                # Use efficient batch rendering for views without geojson
                daemon = self._get_daemon()
                return daemon.render_batch(normalized_views)
        except Exception as e:
            raise MlnativeError(f"Batch render failed: {e}") from e

    def fit_bounds(
        self,
        bounds: tuple[float, float, float, float],
        padding: int = 0,
        max_zoom: float = MAX_ZOOM,
    ) -> tuple[list[float], float]:
        """Calculate center and zoom to fit geographic bounds.

        Uses spherical mercator projection to calculate the optimal zoom level
        for displaying the given bounds within the map dimensions.

        Args:
            bounds: (xmin, ymin, xmax, ymax) bounding box in degrees
            padding: Padding in pixels to add around the bounds (default 0)
            max_zoom: Maximum zoom level to use (default 24)

        Returns:
            Tuple of (center, zoom) where center is [lon, lat] and zoom is float.
            Pass these directly to render():
                center, zoom = map.fit_bounds(bounds)
                png = map.render(center=center, zoom=zoom)

        Example:
            # Fit to bounds of San Francisco Bay Area
            bounds = (-122.6, 37.7, -122.3, 37.9)  # xmin, ymin, xmax, ymax
            center, zoom = map.fit_bounds(bounds, padding=50)
            png = map.render(center=center, zoom=zoom)

        Raises:
            MlnativeError: If bounds are invalid
        """
        if self._closed:
            raise MlnativeError("Map has been closed")

        xmin, ymin, xmax, ymax = bounds

        # Validate bounds
        if not (-180 <= xmin <= 180 and -180 <= xmax <= 180):
            raise MlnativeError(f"Longitude must be -180 to 180, got {bounds}")
        if not (-90 <= ymin <= 90 and -90 <= ymax <= 90):
            raise MlnativeError(f"Latitude must be -90 to 90, got {bounds}")
        if xmin > xmax:
            raise MlnativeError(f"xmin must be <= xmax, got {bounds}")
        if ymin > ymax:
            raise MlnativeError(f"ymin must be <= ymax, got {bounds}")

        # Calculate center
        center_lon = (xmin + xmax) / 2
        center_lat = (ymin + ymax) / 2

        # Handle single point case (bounds are a point, not an area)
        if xmin == xmax and ymin == ymax:
            # For a single point, use a sensible default zoom
            return [center_lon, center_lat], min(14.0, max_zoom)

        # Calculate zoom using spherical mercator projection
        # Convert lat/lon to mercator meters
        def lat_to_y(lat: float) -> float:
            """Convert latitude to spherical mercator Y coordinate."""
            lat_rad = math.radians(lat)
            return math.log(math.tan(lat_rad / 2 + math.pi / 4))

        # Get bounds in mercator space
        y_min = lat_to_y(ymin)
        y_max = lat_to_y(ymax)

        # Longitude spans linearly in mercator
        x_range = xmax - xmin
        y_range = abs(y_max - y_min)

        # Account for padding
        width = self.width - 2 * padding
        height = self.height - 2 * padding

        if width <= 0 or height <= 0:
            raise MlnativeError(f"Padding too large for map size {self.width}x{self.height}")

        # Calculate zoom for each dimension
        # At zoom 0, the world is 256x256 pixels
        # Each zoom level doubles the resolution
        x_zoom = math.log2((width * 360) / (x_range * 256))
        y_zoom = math.log2((height * 2 * math.pi) / (y_range * 256))

        # Use the smaller zoom to ensure bounds fit in both dimensions
        zoom = min(x_zoom, y_zoom, max_zoom)

        # Adjust for pixel_ratio: higher pixel_ratio means we need lower zoom
        # to show the same geographic area (pixel_ratio=2 shows 2x less area at same zoom)
        zoom = zoom - math.log2(self.pixel_ratio)

        # Clamp to valid zoom range
        zoom = max(0.0, min(float(zoom), MAX_ZOOM))

        return [center_lon, center_lat], zoom

    def set_geojson(
        self,
        source_id: str,
        geojson: dict[str, Any] | str | BaseGeometry,
    ) -> None:
        """Update GeoJSON data for a source in the current style.

        Modifies the style to update or add a GeoJSON source with the given ID.
        The style must be loaded as a dict (not a URL). If the style was loaded
        from a URL, you need to fetch and load it as a dict first.

        Args:
            source_id: The ID of the source to update in the style
            geojson: GeoJSON data as dict, JSON string, or shapely geometry.
                    Shapely geometries are automatically converted to GeoJSON.

        Example:
            # Using GeoJSON dict
            geojson = {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]}}
                ]
            }
            map.set_geojson("markers", geojson)

            # Using shapely geometry
            from shapely import Point, MultiPoint
            pts = MultiPoint([Point(-122.4, 37.8), Point(-74.0, 40.7)])
            map.set_geojson("markers", pts)

        Raises:
            MlnativeError: If style is a URL (must be dict), or if geojson is invalid
        """
        if self._closed:
            raise MlnativeError("Map has been closed")

        # Check that style is a dict (not URL)
        if self._style is None:
            raise MlnativeError("No style loaded. Call load_style() first.")

        if isinstance(self._style, str):
            raise MlnativeError(
                "Cannot set GeoJSON on URL-loaded style. "
                "Load the style as a dict first: "
                "map.load_style(requests.get(url).json())"
            )

        # Convert geojson to dict if needed
        if isinstance(geojson, BaseGeometry):
            # Shapely geometry - convert to GeoJSON
            from shapely.geometry import mapping

            geojson = {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "geometry": mapping(geojson), "properties": {}}],
            }
        elif isinstance(geojson, str):
            # JSON string - parse it
            try:
                geojson = json.loads(geojson)
            except json.JSONDecodeError as e:
                raise MlnativeError(f"Invalid GeoJSON string: {e}") from e

        # Ensure sources dict exists
        if "sources" not in self._style:
            self._style["sources"] = {}

        # Update the source
        self._style["sources"][source_id] = {
            "type": "geojson",
            "data": geojson,
        }

        # Reload style in daemon if already running
        if self._daemon is not None:
            self._daemon.reload_style(json.dumps(self._style))

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
