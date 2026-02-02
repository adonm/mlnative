# mlnative

[![PyPI version](https://badge.fury.io/py/mlnative.svg)](https://pypi.org/project/mlnative/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/adonm/mlnative/blob/main/LICENSE)

> **⚠️ Warning: This is an alpha release. The API may change significantly. Not recommended for production use.**

Simple Python wrapper for MapLibre GL Native using a native Rust renderer.

A grug-brained library for rendering static map images with minimal complexity.

## Features

- **Simple API**: One class, minimal methods, zero confusion
- **Native Performance**: Rust backend with MapLibre Native C++ core
- **Built-in Defaults**: Uses OpenFreeMap Liberty style by default - no configuration needed
- **Address Support**: Built-in geocoding with geopy for rendering addresses directly
- **Geometry Support**: Shapely integration for bounds fitting and GeoJSON

## Installation

```bash
pip install mlnative
```

Platform-specific wheels include the native renderer binary:
- Linux x86_64, aarch64

## Quick Start

```python
from mlnative import Map

# Render a map - uses OpenFreeMap Liberty style by default
with Map(512, 512) as m:
    png_bytes = m.render(center=[-122.4, 37.8], zoom=12)
    
    with open("map.png", "wb") as f:
        f.write(png_bytes)
```

## Rendering from Addresses

```python
from mlnative import Map
from geopy.geocoders import ArcGIS

# Geocode an address and render
geolocator = ArcGIS()
location = geolocator.geocode("Sydney Opera House")

with Map(512, 512) as m:
    png = m.render(
        center=[location.longitude, location.latitude],
        zoom=15  # Good for landmark/building view
    )
    open("sydney.png", "wb").write(png)
```

## Custom Styles

While OpenFreeMap Liberty is the default, you can override it:

```python
# OpenFreeMap styles
m.load_style("https://tiles.openfreemap.org/styles/liberty")
m.load_style("https://tiles.openfreemap.org/styles/positron")
m.load_style("https://tiles.openfreemap.org/styles/dark")

# MapLibre demo tiles (good for testing)
m.load_style("https://demotiles.maplibre.org/style.json")

# Or load from dict
m.load_style({"version": 8, "sources": {...}, "layers": [...]})
```

## API Reference

### Map Class

**`Map(width, height, pixel_ratio=1.0)`**

Create a new map renderer.

- `width`: Image width in pixels (1-4096)
- `height`: Image height in pixels (1-4096)
- `pixel_ratio`: Pixel ratio for high-DPI rendering

**`render(center, zoom, bearing=0, pitch=0)`**

Render the map to PNG bytes. Uses OpenFreeMap Liberty style by default.

- `center`: `[longitude, latitude]` list
- `zoom`: Zoom level (0-24)
- `bearing`: Rotation in degrees (0-360)
- `pitch`: Tilt in degrees (0-85)

**`render_batch(views)`**

Render multiple views efficiently.

**`fit_bounds(bounds, padding=0, max_zoom=24)`**

Calculate center/zoom to fit bounds. Returns `(center, zoom)`.

```python
bounds = (-122.6, 37.7, -122.3, 37.9)  # (xmin, ymin, xmax, ymax)
center, zoom = m.fit_bounds(bounds)
png = m.render(center=center, zoom=zoom)
```

**`set_geojson(source_id, geojson)`**

Update GeoJSON source data (requires style loaded as dict).

```python
from shapely import Point
m.set_geojson("markers", Point(-122.4, 37.8))
```

**`load_style(style)`**

Load custom style (URL, file path, or dict). Call before render if not using default.

### GeoJSON Helpers

```python
from mlnative import point, feature_collection, from_coordinates, from_latlng

# From coordinates (lng, lat)
fc = from_coordinates([(-122.4, 37.8), (-74.0, 40.7)])

# From GPS coordinates (lat, lng)  
fc = from_latlng([(37.8, -122.4), (40.7, -74.0)])

# From shapely
from shapely import MultiPoint, Point
fc = feature_collection(MultiPoint([Point(-122.4, 37.8), Point(-74.0, 40.7)]))
```

## Examples

See `examples/` directory:
- `basic.py` - Simple usage
- `address_rendering.py` - Render from addresses
- `fastapi_server.py` - Static maps API

## Supported Platforms

- Linux x86_64, aarch64

> **Note:** macOS and Windows support limited due to upstream MapLibre Native build constraints.

## Development

Requires Python 3.12+, Rust 1.70+, and uv.

```bash
# Setup
uv pip install -e ".[dev,web]"
cd rust && cargo build --release

# Run tests
just test
```

## License

Apache-2.0
