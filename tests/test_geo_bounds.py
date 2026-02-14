"""Tests for bounds_to_polygon helper."""

from mlnative.geo import bounds_to_polygon


class TestBoundsToPolygon:
    """Tests for bounds_to_polygon()."""

    def test_basic_bounds(self):
        """Test creating polygon from basic bounds."""
        bounds = (-122.5, 37.7, -122.3, 37.9)
        poly = bounds_to_polygon(bounds)

        assert poly["type"] == "Feature"
        assert poly["geometry"]["type"] == "Polygon"

    def test_coordinates_form_closed_ring(self):
        """Test that polygon coordinates form a closed ring."""
        bounds = (-10, -10, 10, 10)
        poly = bounds_to_polygon(bounds)
        coords = poly["geometry"]["coordinates"][0]

        assert len(coords) == 5
        assert coords[0] == coords[-1], "Polygon ring should be closed"

    def test_coordinates_order(self):
        """Test that coordinates are in correct order (SW, SE, NE, NW, SW)."""
        bounds = (0, 0, 10, 10)
        poly = bounds_to_polygon(bounds)
        coords = poly["geometry"]["coordinates"][0]

        xmin, ymin, xmax, ymax = bounds
        assert coords[0] == [xmin, ymin]  # SW
        assert coords[1] == [xmax, ymin]  # SE
        assert coords[2] == [xmax, ymax]  # NE
        assert coords[3] == [xmin, ymax]  # NW
        assert coords[4] == [xmin, ymin]  # SW (close)

    def test_bounds_in_properties(self):
        """Test that original bounds are stored in properties."""
        bounds = (-122.5, 37.7, -122.3, 37.9)
        poly = bounds_to_polygon(bounds)

        assert poly["properties"]["bounds"] == bounds

    def test_global_bounds(self):
        """Test with global bounds."""
        bounds = (-180, -90, 180, 90)
        poly = bounds_to_polygon(bounds)

        assert poly["geometry"]["type"] == "Polygon"
        coords = poly["geometry"]["coordinates"][0]
        assert coords[0] == [-180, -90]
        assert coords[2] == [180, 90]

    def test_single_point_bounds(self):
        """Test with bounds that represent a single point."""
        bounds = (0, 0, 0, 0)
        poly = bounds_to_polygon(bounds)

        coords = poly["geometry"]["coordinates"][0]
        assert coords[0] == [0, 0]
        assert coords[2] == [0, 0]
