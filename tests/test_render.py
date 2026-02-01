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

    def test_map_with_style_url(self):
        """Test creating map with style URL."""
        m = Map(width=512, height=512, style="https://demotiles.maplibre.org/style.json")
        assert m.style == "https://demotiles.maplibre.org/style.json"

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
        with pytest.raises(ValueError):
            Map(width=0, height=512)

        with pytest.raises(ValueError):
            Map(width=512, height=0)

        with pytest.raises(ValueError):
            Map(width=-100, height=512)

    def test_render_parameter_validation(self):
        """Test render parameter validation."""
        m = Map(width=512, height=512)

        with pytest.raises(MlnativeError):
            m.render(center=[0, 100], zoom=10)  # latitude out of range
