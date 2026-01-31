# mlnative ⚠️ ALPHA RELEASE

> **⚠️ Warning: This is an alpha release (v0.2.0-alpha). The API may change significantly. Not recommended for production use.**

Simple Python wrapper for MapLibre GL Native using a native Rust renderer.

A grug-brained library for rendering static map images with minimal complexity.

## Features

- **Simple API**: One class, 4 methods, zero confusion
- **Native Performance**: Rust backend with MapLibre Native C++ core
- **No Runtime Dependencies**: Bundled native binaries, no system libraries needed
- **Batch Rendering**: Efficiently render hundreds of maps with one process
- **Mapbox-compatible**: Easy migration from Mapbox Static Images API
- **Default OpenFreeMap**: Uses Liberty style from OpenFreeMap by default

## Installation

```bash
pip install mlnative
```

Platform-specific wheels include the native renderer binary:
- Linux x86_64, aarch64
- macOS x86_64, arm64 (Apple Silicon)
- Windows x64

## Quick Start

```python
from mlnative import Map

# Render a single map
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
- `width`: Image width in pixels (1-4096)
- `height`: Image height in pixels (1-4096)
- `request_handler`: Optional function for custom tile requests (not yet implemented)
- `pixel_ratio`: Pixel ratio for high-DPI rendering

### `load_style(style)`

Load a map style. Accepts:
- URL string (http/https)
- File path to JSON file
- Style JSON dict

### `render(center, zoom, bearing=0, pitch=0)`

Render the map to PNG bytes.

**Parameters:**
- `center`: `[longitude, latitude]` list
- `zoom`: Zoom level (0-24)
- `bearing`: Rotation in degrees (0-360)
- `pitch`: Tilt in degrees (0-85)

**Returns:** PNG image bytes

### `render_batch(views)`

Render multiple map views efficiently.

**Parameters:**
- `views`: List of dicts with `center`, `zoom`, `bearing`, `pitch` keys

**Returns:** List of PNG image bytes

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

### Batch Rendering

```python
from mlnative import Map

views = [
    {"center": [0, 0], "zoom": 1},
    {"center": [10, 10], "zoom": 5},
    {"center": [-122.4, 37.8], "zoom": 12},
    # ... more views
]

with Map(512, 512) as m:
    m.load_style("https://tiles.openfreemap.org/styles/liberty")
    pngs = m.render_batch(views)
    
    for i, png in enumerate(pngs):
        with open(f"map_{i}.png", "wb") as f:
            f.write(png)
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

- Linux x86_64, aarch64
- macOS x86_64, arm64 (Apple Silicon)
- Windows x64

## Architecture

```
Python (mlnative) 
    ↓ JSON
Rust (mlnative-render daemon)
    ↓ FFI
MapLibre Native (C++ core with statically linked dependencies)
```

The native renderer uses pre-built "amalgam" libraries from MapLibre Native which include all dependencies (ICU, libjpeg, etc.) statically linked. This eliminates system dependency issues.

## Development

### Prerequisites

- Python 3.12+
- Rust toolchain (1.70+)
- uv (Python package manager)

### Setup

```bash
# Install Python dependencies
uv venv
uv pip install -e ".[dev,web]"

# Build Rust binary
cd rust && cargo build --release
```

### Run Tests

```bash
just test
```

### Build Wheels

```bash
# Local wheel (current platform only)
uv build

# All platforms (requires Docker)
just build-wheels
```

## License

Apache-2.0
