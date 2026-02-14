"""Example: Rendering maps with GeoJSON overlays.

Shows how to use GeoJSON data with mlnative for markers,
polygons, and other geographic features.
"""

from mlnative import Map
from mlnative.geo import (
    bounds_to_polygon,
    feature_collection,
    from_latlng,
    point,
)


def simple_markers():
    """Add point markers using GeoJSON."""
    style = {
        "version": 8,
        "sources": {
            "markers": {"type": "geojson", "data": {"type": "FeatureCollection", "features": []}}
        },
        "layers": [
            {
                "id": "markers-layer",
                "type": "circle",
                "source": "markers",
                "paint": {
                    "circle-radius": 8,
                    "circle-color": "#e74c3c",
                },
            }
        ],
    }

    with Map(512, 512) as m:
        m.load_style(style)

        markers = feature_collection(
            [
                point(-122.4, 37.8, {"name": "San Francisco"}),
                point(-74.0, 40.7, {"name": "New York"}),
                point(-0.1, 51.5, {"name": "London"}),
            ]
        )

        m.set_geojson("markers", markers)
        center, zoom = m.fit_bounds((-122.5, 37.7, -74.1, 40.8))
        png = m.render(center=center, zoom=zoom)
        print(f"Rendered markers map: {len(png)} bytes")
        return png


def polygon_overlay():
    """Render a polygon (bounding box) overlay."""
    style = {
        "version": 8,
        "sources": {
            "bbox": {"type": "geojson", "data": {"type": "FeatureCollection", "features": []}}
        },
        "layers": [
            {
                "id": "bbox-fill",
                "type": "fill",
                "source": "bbox",
                "paint": {
                    "fill-color": "#3498db",
                    "fill-opacity": 0.3,
                },
            },
            {
                "id": "bbox-outline",
                "type": "line",
                "source": "bbox",
                "paint": {
                    "line-color": "#2980b9",
                    "line-width": 2,
                },
            },
        ],
    }

    with Map(512, 512) as m:
        m.load_style(style)

        bounds = (-122.5, 37.7, -122.3, 37.9)
        polygon = bounds_to_polygon(bounds)
        m.set_geojson("bbox", polygon)

        center, zoom = m.fit_bounds(bounds, padding=50)
        png = m.render(center=center, zoom=zoom)
        print(f"Rendered polygon map: {len(png)} bytes")
        return png


def from_gps_coordinates():
    """Convert GPS coordinates (lat, lng) to map."""
    style = {
        "version": 8,
        "sources": {
            "gps-points": {"type": "geojson", "data": {"type": "FeatureCollection", "features": []}}
        },
        "layers": [
            {
                "id": "gps-layer",
                "type": "circle",
                "source": "gps-points",
                "paint": {
                    "circle-radius": 6,
                    "circle-color": "#27ae60",
                },
            }
        ],
    }

    gps_coords = [
        (37.7749, -122.4194),  # SF (lat, lng order from GPS)
        (40.7128, -74.0060),  # NYC
        (51.5074, -0.1278),  # London
    ]

    with Map(512, 512) as m:
        m.load_style(style)

        geojson = from_latlng(gps_coords)
        m.set_geojson("gps-points", geojson)

        png = m.render(center=[-40, 45], zoom=2)
        print(f"Rendered GPS map: {len(png)} bytes")
        return png


def batch_with_different_geojson():
    """Render multiple views with different GeoJSON per view."""
    style = {
        "version": 8,
        "sources": {
            "cities": {"type": "geojson", "data": {"type": "FeatureCollection", "features": []}}
        },
        "layers": [
            {
                "id": "city-markers",
                "type": "circle",
                "source": "cities",
                "paint": {
                    "circle-radius": 10,
                    "circle-color": "#9b59b6",
                },
            }
        ],
    }

    cities = [
        ([-122.4, 37.8], "San Francisco", 10),
        ([-74.0, 40.7], "New York", 8),
        ([-0.1, 51.5], "London", 6),
    ]

    with Map(512, 512) as m:
        m.load_style(style)

        pngs = []
        for center, name, zoom in cities:
            m.set_geojson("cities", point(center[0], center[1], {"name": name}))
            png = m.render(center=center, zoom=zoom)
            pngs.append(png)
            print(f"Rendered {name}: {len(png)} bytes")

        return pngs


if __name__ == "__main__":
    print("=== Simple markers ===")
    simple_markers()

    print("\n=== Polygon overlay ===")
    polygon_overlay()

    print("\n=== From GPS coordinates ===")
    from_gps_coordinates()

    print("\n=== Batch with different GeoJSON ===")
    batch_with_different_geojson()
