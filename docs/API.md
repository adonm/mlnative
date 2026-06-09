# mlnative API Reference

## Installation

```bash
pip install mlnative
```

Check your install:

```bash
python -m mlnative doctor
python -m mlnative doctor --render
```

## Quick Start

```python
from mlnative import Map

with Map(512, 512) as m:
    png = m.render(center=[-122.4, 37.8], zoom=12)
    with open("map.png", "wb") as f:
        f.write(png)
```

---

## Classes

### `Map`

Main class for rendering static maps using MapLibre GL Native.

#### Constructor

```python
Map(width: int, height: int, pixel_ratio: float = 1.0, timeout: float | None = None)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `width` | `int` | required | Image width in pixels (1-4096) |
| `height` | `int` | required | Image height in pixels (1-4096) |
| `pixel_ratio` | `float` | `1.0` | Pixel ratio for high-DPI (0 < x <= 4) |
| `timeout` | `float | None` | `None` | Renderer command timeout in seconds. Defaults to `MLNATIVE_TIMEOUT` or 30. |

**Raises:**

- `MlnativeError`: If dimensions are invalid

#### Methods

##### `load_style(style)`

Load a map style from URL, file path, or dict.

```python
load_style(style: str | dict[str, Any] | Path) -> None
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `style` | `str` | URL (`https://...`) or file path |
| `style` | `dict` | MapLibre style JSON object |
| `style` | `Path` | Path to style JSON file |

**Example:**

```python
# From URL
m.load_style("https://tiles.openfreemap.org/styles/liberty")

# From file
m.load_style("path/to/style.json")

# From dict
m.load_style({"version": 8, "sources": {...}, "layers": [...]})
```

##### `render(center, zoom, bearing=0, pitch=0)`

Render the map to PNG bytes.

```python
render(
    center: Sequence[float],
    zoom: float,
    bearing: float = 0,
    pitch: float = 0
) -> bytes
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `center` | `[lon, lat]` | required | Map center coordinates as a list or tuple of two finite numbers |
| `zoom` | `float` | required | Zoom level (0-24) |
| `bearing` | `float` | `0` | Rotation in degrees (normalized to 0-360) |
| `pitch` | `float` | `0` | Tilt in degrees (0-85) |

**Returns:** `bytes` - PNG image data

**Example:**

```python
png = m.render(center=[-122.4, 37.8], zoom=12, bearing=45)
```

##### `render_batch(views)`

Render multiple views efficiently (reuses the renderer process).

```python
render_batch(views: list[dict[str, Any]]) -> list[bytes]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `views` | `list[dict]` | List of view dictionaries |

**View dict keys:**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `center` | `[lon, lat]` | yes | Map center |
| `zoom` | `float` | yes | Zoom level |
| `bearing` | `float` | no | Rotation (default 0) |
| `pitch` | `float` | no | Tilt (default 0) |

**Returns:** `list[bytes]` - List of PNG images

**Note:** Per-view GeoJSON updates are not supported in batch mode. Use `set_geojson()` followed by `render()` in a loop when each image needs different source data.

**Example:**

```python
views = [
    {"center": [0, 0], "zoom": 5},
    {"center": [10, 10], "zoom": 8, "bearing": 45},
]
pngs = m.render_batch(views)
```

##### `fit_bounds(bounds, padding=0, max_zoom=24)`

Calculate center and zoom to fit geographic bounds.

```python
fit_bounds(
    bounds: Sequence[float],
    padding: int = 0,
    max_zoom: float = 24
) -> tuple[list[float], float]
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bounds` | `(xmin, ymin, xmax, ymax)` | required | Bounding box in degrees as a list or tuple |
| `padding` | `int` | `0` | Padding in pixels |
| `max_zoom` | `float` | `24` | Maximum zoom level |

**Returns:** `tuple[[lon, lat], zoom]`

**Example:**

```python
bounds = (-122.5, 37.7, -122.3, 37.9)
center, zoom = m.fit_bounds(bounds, padding=50)
png = m.render(center=center, zoom=zoom)
```

##### `set_geojson(source_id, geojson)`

Update GeoJSON data for a source in the current style.

```python
set_geojson(
    source_id: str,
    geojson: dict[str, Any] | str | BaseGeometry
) -> None
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `source_id` | `str` | Source ID in the style |
| `geojson` | `dict` | GeoJSON object |
| `geojson` | `str` | JSON string |
| `geojson` | `BaseGeometry` | Shapely geometry |

**Note:** Style must be loaded as a dict, not a URL.

**Example:**

```python
from shapely import Point

m.load_style(style_dict)
m.set_geojson("markers", Point(-122.4, 37.8))
png = m.render(center=[-122.4, 37.8], zoom=12)
```

##### `close()`

Release resources. Called automatically when used as context manager.

---

## GeoJSON Helpers

Located in `mlnative.geo`:

Helpers validate longitude/latitude ranges and common wrong shapes near the input boundary. Coordinate helper inputs are explicit tuples: `(lng, lat)` for GeoJSON order or `(lat, lng)` for GPS order.

### `point(lng, lat, properties=None)`

Create a GeoJSON Point feature.

```python
from mlnative.geo import point

sf = point(-122.4, 37.8, {"name": "San Francisco"})
```

### `feature_collection(features)`

Create a GeoJSON FeatureCollection.

```python
from mlnative.geo import feature_collection

fc = feature_collection([point(-122.4, 37.8), point(-74.0, 40.7)])
```

### `bounds_to_polygon(bounds)`

Convert bounds tuple to a GeoJSON Polygon feature.

```python
from mlnative.geo import bounds_to_polygon

poly = bounds_to_polygon((-122.5, 37.7, -122.3, 37.9))
```

### `from_coordinates(coordinates, properties=None)`

Create FeatureCollection from (lng, lat) tuples.

```python
from mlnative.geo import from_coordinates

fc = from_coordinates([(-122.4, 37.8), (-74.0, 40.7)])
```

### `from_latlng(latlng, properties=None)`

Create FeatureCollection from (lat, lng) GPS tuples.

```python
from mlnative.geo import from_latlng

fc = from_latlng([(37.8, -122.4), (40.7, -74.0)])  # GPS order
```

## CLI diagnostics

Run installation checks with:

```bash
python -m mlnative doctor
```

Use `--render` to start the native renderer and render a tiny local-style PNG without remote tile access:

```bash
python -m mlnative doctor --render
```

The packaged wheel should find `mlnative/bin/mlnative-render-<platform>-<arch>`. PATH lookup is disabled unless `MLNATIVE_USE_SYSTEM_BINARY=1` is set.

---

## Exceptions

### `MlnativeError`

Base exception for all mlnative errors.

```python
from mlnative.exceptions import MlnativeError

try:
    m.render(center=[999, 999], zoom=12)
except MlnativeError as e:
    print(f"Error: {e}")
```

Common cases:

- Missing native binary: install a platform wheel or build with `just build-rust`.
- Protocol version mismatch: rebuild the Rust binary so it matches the Python package.
- Renderer timeout: the daemon is stopped to avoid stale responses; create a new `Map` to retry.
- GeoJSON source update on URL style: load the style JSON as a dict first.

---

## Example server safety

The included servers are examples, not production services. They bind to loopback and use style IDs from an allowlist. Public deployments should add authentication, quotas/rate limits, caching, concurrency budgets, and explicit network egress controls for style/tile requests.

---

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `DEFAULT_STYLE` | OpenFreeMap Liberty URL | Default map style |
| `MAX_DIMENSION` | `4096` | Maximum width/height |
| `MAX_ZOOM` | `24` | Maximum zoom level |
| `MAX_PITCH` | `85` | Maximum pitch degrees |

---

## Architecture

```
Python (mlnative)
    ↓ JSON over stdin/stdout
Rust (mlnative-render daemon)
    ↓ FFI
MapLibre Native (C++ core)
    ↓
Pre-built amalgam libraries
```

The native renderer uses pre-built libraries with statically linked dependencies (ICU, libjpeg, libpng, etc.), eliminating system dependency issues.
