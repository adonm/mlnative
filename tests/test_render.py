"""
Tests for mlnative.

Integration tests that actually render maps.
"""

import pytest

from mlnative import Map, MlnativeError, __version__
from mlnative._bridge import get_binary_path


def test_version():
    """Test that version is accessible."""
    assert __version__ is not None
    assert isinstance(__version__, str)


def test_binary_path():
    """Test that binary path can be resolved."""
    path = get_binary_path()
    assert path.exists()


class TestMap:
    """Tests for Map class."""

    def test_map_creation(self):
        """Test creating a map instance."""
        m = Map(width=512, height=512)
        assert m.width == 512
        assert m.height == 512

    @pytest.mark.integration
    def test_basic_render(self):
        """Test actually rendering a map to PNG."""
        with Map(width=256, height=256) as m:
            # Uses default OpenFreeMap Liberty style
            png_bytes = m.render(center=[0, 0], zoom=1)

            # Verify we got PNG data
            assert png_bytes is not None
            assert len(png_bytes) > 0
            assert png_bytes[:4] == b"\x89PNG"  # PNG magic bytes
            assert len(png_bytes) > 1000  # Should be a reasonable size

    def test_map_invalid_zoom(self):
        """Test that invalid zoom raises error."""
        m = Map(width=512, height=512)
        with pytest.raises(MlnativeError):
            m.render(center=[0, 0], zoom=25)  # zoom > 22

    def test_map_invalid_center(self):
        """Test that invalid center raises error."""
        m = Map(width=512, height=512)
        with pytest.raises(MlnativeError):
            m.render(center=[200, 0], zoom=10)  # longitude out of range


class TestValidation:
    """Tests for input validation."""

    def test_map_dimension_validation(self):
        """Test that invalid dimensions raise errors."""
        with pytest.raises(MlnativeError):
            Map(width=0, height=512)

        with pytest.raises(MlnativeError):
            Map(width=512, height=0)

        with pytest.raises(MlnativeError):
            Map(width=-100, height=512)

    def test_render_parameter_validation(self):
        """Test render parameter validation."""
        m = Map(width=512, height=512)

        with pytest.raises(MlnativeError):
            m.render(center=[0, 100], zoom=10)  # latitude out of range


class TestIntegration:
    """Integration tests that actually render PNGs."""

    @pytest.mark.integration
    def test_render_batch(self):
        """Test batch rendering multiple views."""
        with Map(width=256, height=256) as m:
            # Uses default OpenFreeMap Liberty style
            views = [
                {"center": [0, 0], "zoom": 1},
                {"center": [-122.4, 37.8], "zoom": 5},
            ]

            pngs = m.render_batch(views)

            assert len(pngs) == 2
            for png in pngs:
                assert png[:4] == b"\x89PNG"
                assert len(png) > 1000

    @pytest.mark.integration
    def test_fit_bounds_and_render(self):
        """Test fit_bounds combined with render using shapely geometry."""
        from shapely import MultiPoint, Point

        from mlnative import feature_collection

        # Create a simple style with markers source
        style = {
            "version": 8,
            "sources": {
                "markers": {
                    "type": "geojson",
                    "data": {"type": "FeatureCollection", "features": []},
                }
            },
            "layers": [],
        }

        with Map(width=512, height=512) as m:
            m.load_style(style)

            # Add markers using shapely geometry directly
            pts = MultiPoint([Point(-122.4194, 37.7749), Point(-122.2712, 37.8044)])
            m.set_geojson("markers", feature_collection(pts))

            # Fit to bounds and render
            bounds = (-122.5, 37.7, -122.2, 37.9)
            center, zoom = m.fit_bounds(bounds, padding=50)
            png = m.render(center=center, zoom=zoom)

            assert png[:4] == b"\x89PNG"
            assert len(png) > 1000
