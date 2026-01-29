# mlnative ⚠️ ALPHA RELEASE

> **⚠️ Warning: This is an alpha release (v0.1.0-alpha). The API may change significantly. Not recommended for production use.**

Simple Python wrapper for MapLibre GL Native using Bun.

A grug-brained library for rendering static map images with minimal complexity.

## Features

- **Simple API**: One class, 4 methods, zero confusion
- **Offline capable**: Bundled native binaries, no runtime dependencies
- **Fast**: Uses Bun for JavaScript execution
- **Mapbox-compatible**: Easy migration from Mapbox Static Images API
- **Default OpenFreeMap**: Uses Liberty style from OpenFreeMap by default

## Installation

```bash
pip install mlnative
```

## Quick Start

```python
from mlnative import Map

# Render a map
with Map(512, 512) as m:
    m.load_style("https://tiles.openfreemap.org/styles/liberty")
    png_bytes = m.render(center=[-122.4, 37.8], zoom=12)
    
    with open("map.png", "wb") as f:
        f.write(png_bytes)
```

## API

### `Map(width, height, request_handler=None, pixel_ratio=1.0)`

Create a new map renderer.

**Parameters:**
- `width`: Image width in pixels
- `height`: Image height in pixels  
- `request_handler`: Optional function for custom tile requests
- `pixel_ratio`: Pixel ratio for high-DPI rendering

### `load_style(style)`

Load a map style. Accepts:
- URL string (http/https)
- File path
- Style JSON dict

### `render(center, zoom, bearing=0, pitch=0)`

Render the map to PNG bytes.

**Parameters:**
- `center`: `[longitude, latitude]` list
- `zoom`: Zoom level (0-22)
- `bearing`: Rotation in degrees (0-360)
- `pitch`: Tilt in degrees (0-60)

**Returns:** PNG image bytes

### `close()`

Release resources. Called automatically with context manager.

## Examples

### Basic Usage

```python
from mlnative import Map

# San Francisco
with Map(800, 600) as m:
    m.load_style("https://tiles.openfreemap.org/styles/liberty")
    png = m.render(
        center=[-122.4194, 37.7749],
        zoom=12,
        bearing=45,
        pitch=30
    )
    open("sf.png", "wb").write(png)
```

### Custom Tile Handler

```python
def tile_handler(request):
    """Handle custom tile requests."""
    if request.url.startswith("mbtiles://"):
        # Load from local MBTiles
        return load_from_mbtiles(request.url)
    return None  # 404

map = Map(512, 512, request_handler=tile_handler)
```

### FastAPI Server

```bash
pip install mlnative[web]
python examples/fastapi_server.py
```

Then visit:
```
http://localhost:8000/static/-122.4194,37.7749,12/512x512.png
```

## Supported Platforms

- Linux x64, arm64
- macOS x64, arm64 (Apple Silicon)
- Windows x64

## Development

```bash
# Install dev dependencies
pip install -e ".[dev,web]"

# Run tests
pytest tests/

# Build vendor bundles
./scripts/build-vendor.sh
```

## License

MIT
