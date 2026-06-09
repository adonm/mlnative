"""Tests for GeoJSON helpers."""

import pytest
from shapely import Point

from mlnative.exceptions import MlnativeError
from mlnative.geo import (
    bounds_to_polygon,
    feature_collection,
    from_coordinates,
    from_latlng,
    point,
)


class TestPoint:
    """Tests for point() helper."""

    def test_point_basic(self):
        """Test creating a basic point."""
        p = point(-122.4194, 37.7749)
        assert p["type"] == "Feature"
        assert p["geometry"]["type"] == "Point"

    def test_point_with_properties(self):
        """Test creating a point with properties."""
        p = point(-122.4194, 37.7749, {"name": "SF"})
        assert p["properties"]["name"] == "SF"

    def test_point_rejects_invalid_longitude(self):
        """Longitude validation should be near helper input."""
        with pytest.raises(MlnativeError, match="Longitude"):
            point(-200, 37.7749)


class TestFeatureCollection:
    """Tests for feature_collection() helper."""

    def test_from_features_list(self):
        """Test creating from list of features."""
        features = [point(-122.4194, 37.7749), point(-74.0060, 40.7128)]
        fc = feature_collection(features)
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 2

    def test_from_shapely_geometry(self):
        """Test creating from shapely geometry."""
        geom = Point(-122.4, 37.8)
        fc = feature_collection(geom)
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 1

    def test_rejects_non_feature_dict(self):
        """Feature collections should reject common wrong shapes."""
        with pytest.raises(MlnativeError, match="Feature 0"):
            feature_collection([{"type": "Point", "coordinates": [0, 0]}])


class TestFromCoordinates:
    """Tests for from_coordinates() helper."""

    def test_basic_coordinates(self):
        """Test creating from list of (lng, lat) tuples."""
        coords = [(-122.4194, 37.7749), (-74.0060, 40.7128)]
        fc = from_coordinates(coords)
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 2

    def test_with_properties(self):
        """Test creating with properties."""
        coords = [(-122.4194, 37.7749)]
        props = [{"name": "SF"}]
        fc = from_coordinates(coords, props)
        assert fc["features"][0]["properties"]["name"] == "SF"

    def test_properties_length_mismatch(self):
        """Test error when properties list length doesn't match coordinates."""
        coords = [(-122.4194, 37.7749), (-74.0060, 40.7128)]
        props = [{"name": "SF"}]
        with pytest.raises(MlnativeError, match="Number of properties"):
            from_coordinates(coords, props)

    def test_rejects_list_coordinate(self):
        """Coordinates should be explicit tuples to avoid order ambiguity."""
        with pytest.raises(MlnativeError, match="Coordinate 0"):
            from_coordinates([[-122.4194, 37.7749]])


class TestFromLatLng:
    """Tests for from_latlng() helper."""

    def test_basic_latlng(self):
        """Test creating from (lat, lng) tuples."""
        latlng = [(37.7749, -122.4194), (40.7128, -74.0060)]
        fc = from_latlng(latlng)
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 2


class TestBoundsToPolygon:
    """Tests for bounds_to_polygon() helper."""

    def test_rejects_reversed_bounds(self):
        """Reversed bounds should fail before creating a polygon."""
        with pytest.raises(MlnativeError, match="xmin"):
            bounds_to_polygon((1, 0, -1, 2))
