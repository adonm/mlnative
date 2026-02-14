"""Example: Error handling with mlnative.

Shows how to handle common errors gracefully.
"""

from mlnative import Map
from mlnative.exceptions import MlnativeError


def render_with_error_handling():
    """Render a map with proper error handling."""
    try:
        with Map(512, 512) as m:
            png = m.render(center=[-122.4, 37.8], zoom=12)
            print(f"Rendered map: {len(png)} bytes")
            return png
    except MlnativeError as e:
        print(f"Rendering failed: {e}")
        return None


def render_with_fallback(center: list[float], zoom: float) -> bytes | None:
    """Render with fallback to default location on error."""
    with Map(512, 512) as m:
        try:
            return m.render(center=center, zoom=zoom)
        except MlnativeError:
            print(f"Failed at {center}, falling back to default")
            return m.render(center=[0, 0], zoom=1)


def validate_before_render(m: Map, center: list[float], zoom: float) -> bool:
    """Validate parameters before rendering to avoid errors."""
    lon, lat = center

    if not (-180 <= lon <= 180):
        print(f"Invalid longitude: {lon}")
        return False
    if not (-90 <= lat <= 90):
        print(f"Invalid latitude: {lat}")
        return False
    if not (0 <= zoom <= 24):
        print(f"Invalid zoom: {zoom}")
        return False

    return True


def batch_render_with_skip():
    """Batch render, skipping invalid views instead of failing entirely."""
    views = [
        {"center": [0, 0], "zoom": 5},
        {"center": [999, 999], "zoom": 10},  # Invalid
        {"center": [10, 10], "zoom": 8},
    ]

    pngs = []
    with Map(512, 512) as m:
        for i, view in enumerate(views):
            try:
                png = m.render(**view)
                pngs.append(png)
                print(f"View {i}: OK ({len(png)} bytes)")
            except MlnativeError as e:
                print(f"View {i}: SKIPPED - {e}")
                continue

    print(f"Rendered {len(pngs)}/{len(views)} views")
    return pngs


if __name__ == "__main__":
    print("=== Basic error handling ===")
    render_with_error_handling()

    print("\n=== With fallback ===")
    render_with_fallback([-122.4, 37.8], 12)

    print("\n=== Batch with skip ===")
    batch_render_with_skip()
