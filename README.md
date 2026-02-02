# mlnative

[![PyPI version](https://badge.fury.io/py/mlnative.svg)](https://pypi.org/project/mlnative/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Render static map images from Python using MapLibre Native.

**Platform:** Linux x64, ARM64  
**Python:** 3.12+

## Quick Start

```bash
pip install mlnative
```

```python
from mlnative import Map

with Map(512, 512) as m:
    png = m.render(center=[-122.4, 37.8], zoom=12)
    open("map.png", "wb").write(png)
```

## Features

- **Zero config** - Works out of the box with OpenFreeMap tiles
- **HiDPI support** - `pixel_ratio=2` for sharp retina displays
- **Batch rendering** - Efficiently render hundreds of maps
- **Address geocoding** - Built-in support via geopy
- **Custom markers** - Add GeoJSON points, lines, polygons

## Examples

### Render from address

```python
from mlnative import Map
from geopy.geocoders import ArcGIS

geolocator = ArcGIS()
location = geolocator.geocode("Sydney Opera House")

with Map(512, 512) as m:
    png = m.render(
        center=[location.longitude, location.latitude],
        zoom=15
    )
```

### Fit bounds to show area

```python
from mlnative import Map, feature_collection, point

# Show multiple locations
markers = feature_collection([
    point(-122.4194, 37.7749),  # SF
    point(-122.2712, 37.8044),  # Oakland
])

with Map(800, 600) as m:
    # Load style as dict to modify it
    style = {"version": 8, ...}  # your style
    m.load_style(style)
    m.set_geojson("markers", markers)
    
    # Fit map to show all markers
    center, zoom = m.fit_bounds(
        (-122.5, 37.7, -122.2, 37.9),  # xmin, ymin, xmax, ymax
        padding=50
    )
    png = m.render(center=center, zoom=zoom)
```

### Batch render multiple views

```python
views = [
    {"center": [0, 0], "zoom": 1},
    {"center": [-122.4, 37.8], "zoom": 12},
    {"center": [151.2, -33.9], "zoom": 10, "bearing": 45},
]

with Map(512, 512) as m:
    pngs = m.render_batch(views)  # Returns list of PNG bytes
```

### HiDPI rendering

```python
# Retina/HiDPI display (2x resolution)
with Map(512, 512, pixel_ratio=2) as m:
    png = m.render(center=[0, 0], zoom=5)
    # Image is 1024x1024, text appears sharp
```

## API Reference

### Map(width, height, pixel_ratio=1.0)

Create map renderer. Context manager ensures cleanup.

### render(center, zoom, bearing=0, pitch=0)

Render single view. Returns PNG bytes.

- `center`: `[longitude, latitude]`
- `zoom`: 0-24
- `bearing`: Rotation in degrees (0-360)
- `pitch`: Tilt in degrees (0-85)

### render_batch(views)

Render multiple views efficiently.

```python
views = [
    {"center": [lon, lat], "zoom": z},
    {"center": [lon, lat], "zoom": z, "geojson": {"markers": {...}}},
]
```

### fit_bounds(bounds, padding=0, max_zoom=24)

Calculate center/zoom to fit bounding box.

```python
center, zoom = m.fit_bounds((xmin, ymin, xmax, ymax))
png = m.render(center=center, zoom=zoom)
```

### set_geojson(source_id, geojson)

Update GeoJSON source in style (requires dict style, not URL).

```python
m.set_geojson("markers", {"type": "FeatureCollection", "features": [...]})
```

### load_style(style)

Load custom style (URL, file path, or dict).

```python
# OpenFreeMap styles
m.load_style("https://tiles.openfreemap.org/styles/liberty")
m.load_style("https://tiles.openfreemap.org/styles/positron")

# MapLibre demo
m.load_style("https://demotiles.maplibre.org/style.json")

# Custom style dict
m.load_style({"version": 8, "sources": {...}, "layers": [...]})
```

## GeoJSON Helpers

```python
from mlnative import point, feature_collection, from_coordinates, from_latlng

# Create point
sf = point(-122.4194, 37.7749, {"name": "San Francisco"})

# From coordinate tuples
fc = from_coordinates([(-122.4, 37.8), (-74.0, 40.7)])

# From GPS (lat, lng) order
fc = from_latlng([(37.8, -122.4), (40.7, -74.0)])
```

## Notes

- **Default style**: OpenFreeMap Liberty (no configuration needed)
- **GeoJSON updates**: Requires style loaded as dict, not URL
- **pixel_ratio**: Higher values = larger image, same geographic area
- **Platform**: Linux only (macOS/Windows builds disabled due to upstream issues)

## License

Apache-2.0
