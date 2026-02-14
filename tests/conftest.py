"""Shared pytest fixtures for mlnative tests."""

import pytest

from mlnative import Map


@pytest.fixture
def simple_map() -> Map:
    """Create a simple Map instance for testing."""
    return Map(width=512, height=512)


@pytest.fixture
def simple_style() -> dict:
    """Return a minimal valid MapLibre style."""
    return {
        "version": 8,
        "sources": {},
        "layers": [],
    }


@pytest.fixture
def simple_geojson() -> dict:
    """Return a simple GeoJSON FeatureCollection."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-122.4, 37.8]},
                "properties": {"name": "San Francisco"},
            }
        ],
    }
