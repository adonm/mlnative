"""
mlnative - Simple Python wrapper for MapLibre GL Native

A grug-brained library for rendering static map images.
"""

from importlib.metadata import version

from .exceptions import MlnativeError
from .map import Map

__version__ = version("mlnative")
__all__ = ["Map", "MlnativeError"]
