"""
mlnative - Simple Python wrapper for MapLibre GL Native

A grug-brained library for rendering static map images.
"""

from importlib.metadata import version

from .exceptions import MlnativeError
from .geo import (
    bounds_to_polygon,
    feature_collection,
    from_coordinates,
    from_latlng,
    point,
)
from .map import Bounds, Center, Map, RenderView

__version__ = version("mlnative")
__all__ = [
    "Bounds",
    "Center",
    "Map",
    "MlnativeError",
    "RenderView",
    "bounds_to_polygon",
    "feature_collection",
    "from_coordinates",
    "from_latlng",
    "point",
]
