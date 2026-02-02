"""Tests for Map class methods: fit_bounds and set_geojson."""

import json

import pytest
from shapely import Point

from mlnative import Map
from mlnative.exceptions import MlnativeError


class TestFitBounds:
    """Tests for fit_bounds() method."""

    def test_fit_bounds_basic(self):
        """Test basic bounds fitting."""
        m = Map(width=512, height=512)
        bounds = (-122.5, 37.7, -122.3, 37.9)
        center, zoom = m.fit_bounds(bounds)

        # Center should be middle of bounds
        assert center[0] == pytest.approx(-122.4, abs=0.01)
        assert center[1] == pytest.approx(37.8, abs=0.01)
        assert 0 < zoom < 24

    def test_fit_bounds_with_padding(self):
        """Test bounds fitting with padding."""
        m = Map(width=512, height=512)
        bounds = (-122.5, 37.7, -122.3, 37.9)

        # With padding, zoom should be lower
        center1, zoom1 = m.fit_bounds(bounds, padding=0)
        center2, zoom2 = m.fit_bounds(bounds, padding=100)

        assert zoom2 < zoom1
        assert center1 == center2

    def test_fit_bounds_invalid_longitude(self):
        """Test error on invalid longitude."""
        m = Map(width=512, height=512)
        with pytest.raises(MlnativeError, match="Longitude"):
            m.fit_bounds((-200, 37.7, -122.3, 37.9))

    def test_fit_bounds_invalid_latitude(self):
        """Test error on invalid latitude."""
        m = Map(width=512, height=512)
        with pytest.raises(MlnativeError, match="Latitude"):
            m.fit_bounds((-122.5, -100, -122.3, 37.9))

    def test_fit_bounds_invalid_order(self):
        """Test error when xmin >= xmax."""
        m = Map(width=512, height=512)
        with pytest.raises(MlnativeError, match="xmin"):
            m.fit_bounds((-122.3, 37.7, -122.5, 37.9))

    def test_fit_bounds_excessive_padding(self):
        """Test error when padding is too large."""
        m = Map(width=100, height=100)
        with pytest.raises(MlnativeError, match="Padding"):
            m.fit_bounds((-122.5, 37.7, -122.3, 37.9), padding=60)

    def test_fit_bounds_closed_map(self):
        """Test error when map is closed."""
        m = Map(width=512, height=512)
        m.close()
        with pytest.raises(MlnativeError, match="closed"):
            m.fit_bounds((-122.5, 37.7, -122.3, 37.9))

    def test_fit_bounds_single_point(self):
        """Test fitting bounds to a single point (e.g., from shapely Point.bounds)."""
        m = Map(width=512, height=512)
        # Single point bounds (xmin==xmax, ymin==ymax)
        bounds = (115.85542, -31.95415, 115.85542, -31.95415)
        center, zoom = m.fit_bounds(bounds)

        # Center should be the point itself
        assert center[0] == pytest.approx(115.85542, abs=0.00001)
        assert center[1] == pytest.approx(-31.95415, abs=0.00001)
        # Should get a sensible default zoom for a single point
        assert zoom == pytest.approx(14.0, abs=0.1)

    def test_fit_bounds_single_point_with_max_zoom(self):
        """Test single point with custom max_zoom."""
        m = Map(width=512, height=512)
        bounds = (115.85542, -31.95415, 115.85542, -31.95415)
        center, zoom = m.fit_bounds(bounds, max_zoom=10)

        # Should respect the max_zoom limit
        assert zoom <= 10.0


class TestSetGeojson:
    """Tests for set_geojson() method."""

    def test_set_geojson_dict(self):
        """Test setting GeoJSON from dict."""
        m = Map(width=512, height=512)
        m.load_style({"version": 8, "sources": {}, "layers": []})

        geojson = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]}}],
        }
        m.set_geojson("markers", geojson)

        # Check style was updated
        style = m._style
        assert isinstance(style, dict)
        assert "markers" in style.get("sources", {})

    def test_set_geojson_string(self):
        """Test setting GeoJSON from JSON string."""
        m = Map(width=512, height=512)
        m.load_style({"version": 8, "sources": {}, "layers": []})

        geojson_str = json.dumps({"type": "FeatureCollection", "features": []})
        m.set_geojson("markers", geojson_str)

        style = m._style
        assert isinstance(style, dict)
        assert "markers" in style.get("sources", {})

    def test_set_geojson_shapely_geometry(self):
        """Test setting GeoJSON from shapely geometry."""
        m = Map(width=512, height=512)
        m.load_style({"version": 8, "sources": {}, "layers": []})

        geom = Point(-122.4, 37.8)
        m.set_geojson("markers", geom)

        style = m._style
        assert isinstance(style, dict)
        sources = style.get("sources", {})
        assert "markers" in sources

    def test_set_geojson_no_style(self):
        """Test error when no style loaded."""
        m = Map(width=512, height=512)
        with pytest.raises(MlnativeError, match="No style loaded"):
            m.set_geojson("markers", {"type": "FeatureCollection", "features": []})

    def test_set_geojson_url_style(self):
        """Test error when style is URL."""
        m = Map(width=512, height=512)
        m.load_style("https://example.com/style.json")
        with pytest.raises(MlnativeError, match="URL-loaded style"):
            m.set_geojson("markers", {"type": "FeatureCollection", "features": []})

    def test_set_geojson_invalid_json_string(self):
        """Test error on invalid JSON string."""
        m = Map(width=512, height=512)
        m.load_style({"version": 8, "sources": {}, "layers": []})

        with pytest.raises(MlnativeError, match="Invalid GeoJSON"):
            m.set_geojson("markers", "not valid json")

    def test_set_geojson_closed_map(self):
        """Test error when map is closed."""
        m = Map(width=512, height=512)
        m.load_style({"version": 8, "sources": {}, "layers": []})
        m.close()

        with pytest.raises(MlnativeError, match="closed"):
            m.set_geojson("markers", {"type": "FeatureCollection", "features": []})

    def test_set_geojson_resets_daemon(self):
        """Test that daemon is reset after setting geojson."""
        m = Map(width=512, height=512)
        m.load_style({"version": 8, "sources": {}, "layers": []})

        # Force daemon creation
        m._get_daemon()
        assert m._daemon is not None

        # Set geojson should reset daemon
        m.set_geojson("markers", {"type": "FeatureCollection", "features": []})
        assert m._daemon is None
