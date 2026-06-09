"""GeoJSON building utilities using shapely.

Provides convenient helpers for creating GeoJSON features and feature collections
from coordinates or shapely geometries.
"""

from __future__ import annotations

from typing import Any

from shapely import Point
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from .exceptions import MlnativeError


def _validate_lng_lat(lng: float, lat: float) -> None:
    """Validate a GeoJSON longitude/latitude coordinate pair."""
    if not (-180 <= lng <= 180):
        raise MlnativeError(f"Longitude must be -180 to 180, got {lng}")
    if not (-90 <= lat <= 90):
        raise MlnativeError(f"Latitude must be -90 to 90, got {lat}")


def _validate_feature(feature: dict[str, Any], index: int) -> None:
    """Validate the small subset of GeoJSON Feature shape this helper promises."""
    if not isinstance(feature, dict):
        raise MlnativeError(f"Feature {index} must be a dict")
    if feature.get("type") != "Feature":
        raise MlnativeError(f"Feature {index} must have type='Feature'")
    if "geometry" not in feature:
        raise MlnativeError(f"Feature {index} must include geometry")


def point(lng: float, lat: float, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a GeoJSON Point feature.

    Args:
        lng: Longitude (x coordinate)
        lat: Latitude (y coordinate)
        properties: Optional properties dict for the feature

    Returns:
        GeoJSON Feature dict with Point geometry

    Example:
        >>> sf = point(-122.4194, 37.7749, {"name": "San Francisco"})
        >>> sf["geometry"]
        {'type': 'Point', 'coordinates': [-122.4194, 37.7749]}
    """
    _validate_lng_lat(lng, lat)
    if properties is not None and not isinstance(properties, dict):
        raise MlnativeError("properties must be a dict when provided")

    geom = Point(lng, lat)
    return {
        "type": "Feature",
        "geometry": mapping(geom),
        "properties": properties or {},
    }


def feature_collection(
    features: list[dict[str, Any]] | BaseGeometry,
) -> dict[str, Any]:
    """Create a GeoJSON FeatureCollection.

    Accepts either a list of GeoJSON feature dicts or a shapely geometry.
    When given a shapely geometry, creates a FeatureCollection with a single
    feature containing that geometry.

    Args:
        features: List of feature dicts, or a shapely geometry (Point,
                 MultiPoint, Polygon, etc.)

    Returns:
        GeoJSON FeatureCollection dict

    Example with features:
        >>> features = [
        ...     point(-122.4194, 37.7749, {"name": "SF"}),
        ...     point(-74.0060, 40.7128, {"name": "NYC"}),
        ... ]
        >>> fc = feature_collection(features)

    Example with shapely geometry:
        >>> from shapely import Point, MultiPoint
        >>> pts = [Point(-122.4, 37.8), Point(-74.0, 40.7)]
        >>> fc = feature_collection(MultiPoint(pts))
    """
    if isinstance(features, BaseGeometry):
        # Single geometry - wrap in a feature
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": mapping(features),
                    "properties": {},
                }
            ],
        }
    if not isinstance(features, list):
        raise MlnativeError(
            "features must be a list of GeoJSON Feature dicts or a shapely geometry"
        )

    for index, feature in enumerate(features):
        _validate_feature(feature, index)

    return {
        "type": "FeatureCollection",
        "features": list(features),
    }


def bounds_to_polygon(
    bounds: tuple[float, float, float, float],
) -> dict[str, Any]:
    """Convert bounds tuple to a GeoJSON Polygon feature.

    Args:
        bounds: (xmin, ymin, xmax, ymax) in degrees

    Returns:
        GeoJSON Polygon feature dict

    Example:
        >>> bbox = (-122.5, 37.7, -122.3, 37.9)  # SF area
        >>> poly = bounds_to_polygon(bbox)
    """
    xmin, ymin, xmax, ymax = bounds
    _validate_lng_lat(xmin, ymin)
    _validate_lng_lat(xmax, ymax)
    if xmin > xmax:
        raise MlnativeError(f"xmin must be <= xmax, got {bounds}")
    if ymin > ymax:
        raise MlnativeError(f"ymin must be <= ymax, got {bounds}")

    coords = [
        [xmin, ymin],
        [xmax, ymin],
        [xmax, ymax],
        [xmin, ymax],
        [xmin, ymin],  # Close the ring
    ]
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords],
        },
        "properties": {"bounds": bounds},
    }


def from_coordinates(
    coordinates: list[tuple[float, float]],
    properties: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a FeatureCollection from a list of (lng, lat) coordinate tuples.

    Args:
        coordinates: List of (longitude, latitude) tuples
        properties: Optional list of property dicts (one per coordinate)

    Returns:
        GeoJSON FeatureCollection with Point features

    Example:
        >>> coords = [(-122.4194, 37.7749), (-74.0060, 40.7128)]
        >>> fc = from_coordinates(coords)

        With properties:
        >>> props = [{"name": "SF"}, {"name": "NYC"}]
        >>> fc = from_coordinates(coords, props)
    """
    if not isinstance(coordinates, list):
        raise MlnativeError("coordinates must be a list of (longitude, latitude) tuples")

    for index, coordinate in enumerate(coordinates):
        if not isinstance(coordinate, tuple) or len(coordinate) != 2:
            raise MlnativeError(f"Coordinate {index} must be a (longitude, latitude) tuple")
        lng, lat = coordinate
        _validate_lng_lat(lng, lat)

    if properties is None:
        properties = [{} for _ in coordinates]

    if not isinstance(properties, list):
        raise MlnativeError("properties must be a list of dicts when provided")

    if len(properties) != len(coordinates):
        raise MlnativeError(
            f"Number of properties ({len(properties)}) must match "
            f"number of coordinates ({len(coordinates)})"
        )

    for index, props in enumerate(properties):
        if not isinstance(props, dict):
            raise MlnativeError(f"Properties {index} must be a dict")

    features = [
        point(lng, lat, props) for (lng, lat), props in zip(coordinates, properties, strict=False)
    ]

    return feature_collection(features)


def from_latlng(
    latlng: list[tuple[float, float]],
    properties: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a FeatureCollection from (lat, lng) tuples (common GPS format).

    This is a convenience wrapper that swaps the coordinate order from the
    common GPS (lat, lng) format to GeoJSON's (lng, lat) format.

    Args:
        latlng: List of (latitude, longitude) tuples (GPS order)
        properties: Optional list of property dicts (one per coordinate)

    Returns:
        GeoJSON FeatureCollection with Point features

    Example:
        >>> coords = [(37.7749, -122.4194), (40.7128, -74.0060)]  # (lat, lng)
        >>> fc = from_latlng(coords)
    """
    if not isinstance(latlng, list):
        raise MlnativeError("latlng must be a list of (latitude, longitude) tuples")
    for index, coordinate in enumerate(latlng):
        if not isinstance(coordinate, tuple) or len(coordinate) != 2:
            raise MlnativeError(f"Coordinate {index} must be a (latitude, longitude) tuple")

    # Swap from (lat, lng) to (lng, lat)
    coordinates = [(lng, lat) for lat, lng in latlng]
    return from_coordinates(coordinates, properties)
