"""
Main Map class for mlnative.

Uses native Rust renderer with statically linked MapLibre Native.
Provides synchronous API for static map rendering.
"""

import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from shapely.geometry.base import BaseGeometry

from ._bridge import MAX_BATCH_VIEWS, RenderDaemon
from .exceptions import MlnativeError

# OpenFreeMap Liberty style as default
DEFAULT_STYLE = "https://tiles.openfreemap.org/styles/liberty"

# Validation limits
MAX_DIMENSION = 4096
MAX_ZOOM = 24
MAX_PITCH = 85
WEB_MERCATOR_MAX_LAT = 85.05112878
MAX_BATCH_OUTPUT_PIXELS = 64_000_000
MAX_STYLE_JSON_BYTES = 5_000_000

type Center = Sequence[float]
type Bounds = Sequence[float]
type RenderView = dict[str, Any]


def _validate_dimension(width: int, height: int) -> None:
    """Validate logical map dimensions."""
    if width <= 0 or height <= 0:
        raise MlnativeError(f"Width and height must be positive, got {width}x{height}")

    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise MlnativeError(f"Width and height must be <= {MAX_DIMENSION}, got {width}x{height}")


def _validate_pixel_ratio(pixel_ratio: float) -> None:
    """Validate HiDPI scale factor."""
    if pixel_ratio <= 0 or pixel_ratio > 4:
        raise MlnativeError(f"pixel_ratio must be between 0 and 4 (exclusive), got {pixel_ratio}")


def _normalize_center(center: Center, label: str = "Center") -> list[float]:
    """Validate and return a [longitude, latitude] center."""
    if isinstance(center, (str, bytes)):
        raise MlnativeError(f"{label} must be [longitude, latitude], got {center!r}")

    try:
        lon_raw, lat_raw = center
    except (TypeError, ValueError) as e:
        raise MlnativeError(f"{label} must be [longitude, latitude], got {center}") from e

    try:
        lon = float(lon_raw)
        lat = float(lat_raw)
    except (TypeError, ValueError) as e:
        raise MlnativeError(f"{label} coordinates must be numbers, got {center}") from e

    if not (math.isfinite(lon) and math.isfinite(lat)):
        raise MlnativeError(f"{label} coordinates must be finite numbers, got {center}")

    if not (-180 <= lon <= 180):
        raise MlnativeError(f"{label} longitude must be -180 to 180, got {lon}")
    if not (-90 <= lat <= 90):
        raise MlnativeError(f"{label} latitude must be -90 to 90, got {lat}")

    return [lon, lat]


def _normalize_view(
    center: Center,
    zoom: float,
    bearing: float = 0,
    pitch: float = 0,
    label: str = "View",
) -> RenderView:
    """Validate and normalize render view parameters."""
    normalized_center = _normalize_center(center, label)

    try:
        zoom = float(zoom)
        bearing = float(bearing)
        pitch = float(pitch)
    except (TypeError, ValueError) as e:
        raise MlnativeError(f"{label} zoom, bearing, and pitch must be numbers") from e

    if not (math.isfinite(zoom) and math.isfinite(bearing) and math.isfinite(pitch)):
        raise MlnativeError(f"{label} zoom, bearing, and pitch must be finite numbers")

    if not (0 <= zoom <= MAX_ZOOM):
        raise MlnativeError(f"{label} zoom must be 0-{MAX_ZOOM}, got {zoom}")

    if not (0 <= pitch <= MAX_PITCH):
        raise MlnativeError(f"{label} pitch must be 0-{MAX_PITCH}, got {pitch}")

    return {
        "center": normalized_center,
        "zoom": zoom,
        "bearing": bearing % 360,
        "pitch": pitch,
    }


def _normalize_bounds(bounds: Bounds) -> tuple[float, float, float, float]:
    """Validate and return a numeric (xmin, ymin, xmax, ymax) tuple."""
    if isinstance(bounds, (str, bytes)):
        raise MlnativeError(f"Bounds must be (xmin, ymin, xmax, ymax), got {bounds!r}")

    try:
        xmin_raw, ymin_raw, xmax_raw, ymax_raw = bounds
    except (TypeError, ValueError) as e:
        raise MlnativeError(f"Bounds must be (xmin, ymin, xmax, ymax), got {bounds}") from e

    try:
        xmin = float(xmin_raw)
        ymin = float(ymin_raw)
        xmax = float(xmax_raw)
        ymax = float(ymax_raw)
    except (TypeError, ValueError) as e:
        raise MlnativeError(f"Bounds values must be numbers, got {bounds}") from e

    if not all(math.isfinite(value) for value in (xmin, ymin, xmax, ymax)):
        raise MlnativeError(f"Bounds values must be finite numbers, got {bounds}")

    if not (-180 <= xmin <= 180 and -180 <= xmax <= 180):
        raise MlnativeError(f"Longitude must be -180 to 180, got {bounds}")
    if not (-90 <= ymin <= 90 and -90 <= ymax <= 90):
        raise MlnativeError(f"Latitude must be -90 to 90, got {bounds}")
    if not (
        -WEB_MERCATOR_MAX_LAT <= ymin <= WEB_MERCATOR_MAX_LAT
        and -WEB_MERCATOR_MAX_LAT <= ymax <= WEB_MERCATOR_MAX_LAT
    ):
        raise MlnativeError(
            f"Latitude must be within Web Mercator bounds (±{WEB_MERCATOR_MAX_LAT}), got {bounds}"
        )
    if xmin > xmax:
        raise MlnativeError(f"xmin must be <= xmax, got {bounds}")
    if ymin > ymax:
        raise MlnativeError(f"ymin must be <= ymax, got {bounds}")

    return xmin, ymin, xmax, ymax


def _load_style_file(path: Path) -> dict[str, Any]:
    """Load style JSON from a local file path."""
    if not path.exists():
        raise MlnativeError(f"Style file not found: {path}")
    try:
        with path.open() as f:
            style = json.load(f)
    except json.JSONDecodeError as e:
        raise MlnativeError(f"Invalid JSON in style file: {e}") from e
    if not isinstance(style, dict):
        raise MlnativeError(f"Style file must contain a JSON object: {path}")
    return style


def _normalize_style_input(style: str | dict[str, Any] | Path) -> str | dict[str, Any]:
    """Normalize public style input into URL string, path-loaded dict, or dict."""
    if isinstance(style, dict):
        return style

    if isinstance(style, (str, Path)):
        style_str = str(style)
        parsed = urlparse(style_str)

        if parsed.scheme in ("http", "https"):
            return style_str
        if parsed.scheme == "":
            return _load_style_file(Path(style))
        raise MlnativeError(f"Unsupported style format: {style}")

    raise MlnativeError(f"Style must be str, dict, or Path, got {type(style)}")


def _serialize_style(style: str | dict[str, Any] | None) -> str:
    """Serialize the active style for the Rust daemon."""
    if style is None:
        return DEFAULT_STYLE
    if isinstance(style, dict):
        return json.dumps(style)
    return style


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
        pixel_ratio: float = 1.0,
        timeout: float | None = None,
    ) -> None:
        """
        Create a new map renderer.

        Args:
            width: Image width in pixels (1-4096)
            height: Image height in pixels (1-4096)
            pixel_ratio: Pixel ratio for high-DPI rendering (default 1.0, max 4.0)
            timeout: Renderer command timeout in seconds. Defaults to MLNATIVE_TIMEOUT or 30.
        """
        _validate_dimension(width, height)
        _validate_pixel_ratio(pixel_ratio)

        self.width = width
        self.height = height
        self.pixel_ratio = pixel_ratio
        self.timeout = timeout
        self._style: str | dict[str, Any] | None = None
        self._daemon: RenderDaemon | None = None
        self._closed = False

    def _get_daemon(self) -> RenderDaemon:
        """Get or create the render daemon."""
        if self._daemon is None:
            self._daemon = RenderDaemon(timeout=self.timeout)
            self._daemon.start(
                self.width,
                self.height,
                _serialize_style(self._style),
                self.pixel_ratio,
            )

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

        self._style = _normalize_style_input(style)

        if self._daemon is not None:
            self._daemon.reload_style(_serialize_style(self._style))

    def render(self, center: Center, zoom: float, bearing: float = 0, pitch: float = 0) -> bytes:
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

        view = _normalize_view(center, zoom, bearing, pitch, "Center")

        try:
            daemon = self._get_daemon()
            return daemon.render(view["center"], view["zoom"], view["bearing"], view["pitch"])
        except Exception as e:
            raise MlnativeError(f"Render failed: {e}") from e

    def render_batch(self, views: list[RenderView]) -> list[bytes]:
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

        Note:
            Per-view GeoJSON updates are not supported in batch mode. Use
            set_geojson() + render() in a loop when each view needs different
            source data.
        """
        if self._closed:
            raise MlnativeError("Map has been closed")

        if self._style is None:
            self._style = DEFAULT_STYLE

        if len(views) > MAX_BATCH_VIEWS:
            raise MlnativeError(
                f"render_batch supports at most {MAX_BATCH_VIEWS} views, got {len(views)}"
            )

        output_pixels = int(self.width * self.height * (self.pixel_ratio**2) * len(views))
        if output_pixels > MAX_BATCH_OUTPUT_PIXELS:
            raise MlnativeError(
                "render_batch output is too large for one in-memory batch. "
                "Use fewer views or smaller dimensions."
            )

        # Per-view GeoJSON updates are intentionally unsupported in batch mode.
        if any(view.get("geojson") for view in views):
            raise MlnativeError(
                "render_batch does not support per-view geojson updates. "
                "Use set_geojson() and render() in a loop instead."
            )

        # Validate and normalize views
        normalized_views = []
        for i, view in enumerate(views):
            center = view.get("center")
            if center is None:
                raise MlnativeError(f"View {i} center must be [longitude, latitude]")
            normalized_views.append(
                _normalize_view(
                    center,
                    view.get("zoom", 0),
                    view.get("bearing", 0),
                    view.get("pitch", 0),
                    f"View {i}",
                )
            )

        try:
            daemon = self._get_daemon()
            return daemon.render_batch(normalized_views)
        except Exception as e:
            raise MlnativeError(f"Batch render failed: {e}") from e

    def fit_bounds(
        self,
        bounds: Bounds,
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

        xmin, ymin, xmax, ymax = _normalize_bounds(bounds)

        if padding < 0:
            raise MlnativeError(f"Padding must be non-negative, got {padding}")
        if not (0 <= max_zoom <= MAX_ZOOM):
            raise MlnativeError(f"max_zoom must be 0-{MAX_ZOOM}, got {max_zoom}")

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

        try:
            # Get bounds in mercator space
            y_min = lat_to_y(ymin)
            y_max = lat_to_y(ymax)
        except ValueError as e:
            raise MlnativeError("Bounds cannot be projected in Web Mercator") from e

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
        x_zoom = math.inf if x_range == 0 else math.log2((width * 360) / (x_range * 256))
        y_zoom = math.inf if y_range == 0 else math.log2((height * 2 * math.pi) / (y_range * 256))

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

        # Reload style in daemon if already running.
        # This rewrites the full style JSON each time; keep source data small.
        if self._daemon is not None:
            style_json = json.dumps(self._style)
            if len(style_json.encode("utf-8")) > MAX_STYLE_JSON_BYTES:
                raise MlnativeError(
                    "GeoJSON update would reload a style larger than 5 MB. "
                    "Keep source data smaller or recreate the map less often."
                )
            self._daemon.reload_style(style_json)

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
