"""Integration test for fit_bounds with distant points and pixel ratio."""

import io

import pytest
from PIL import Image
from shapely import Point

from mlnative import Map, feature_collection


def find_marker_pixels(
    img: Image.Image, marker_color: tuple[int, int, int], tolerance: int = 30
) -> list[tuple[int, int]]:
    """Find pixels matching marker color (within tolerance).

    Returns list of (x, y) coordinates where marker-like pixels are found.
    """
    pixels = []
    width, height = img.size

    # Convert marker color to RGB if needed
    if len(marker_color) == 3:
        r_target, g_target, b_target = marker_color
    else:
        r_target, g_target, b_target = marker_color[:3]

    # Convert image to RGB for consistent pixel access
    img_rgb = img.convert("RGB")
    pixel_data = img_rgb.load()

    for y in range(height):
        for x in range(width):
            r, g, b = pixel_data[x, y]
            # Check if pixel is close to target color
            if (
                abs(r - r_target) < tolerance
                and abs(g - g_target) < tolerance
                and abs(b - b_target) < tolerance
            ):
                pixels.append((x, y))

    return pixels


class TestFitBoundsIntegration:
    """Integration tests for fit_bounds functionality."""

    @pytest.mark.integration
    def test_fit_bounds_two_distant_points_with_pixel_ratio(self):
        """Test fit_bounds with 2 distant points, zoom out, and verify both visible.

        This test:
        1. Creates 2 markers at distant locations (Sydney and London)
        2. Uses fit_bounds to calculate zoom for both points
        3. Zooms out by 0.2 to ensure padding
        4. Renders at pixel_ratio=2 (HiDPI)
        5. Verifies both points are visible in the output by checking for marker pixels
        """
        # Two distant points: Sydney Opera House and Big Ben London
        sydney = Point(151.2153, -33.8568)  # lon, lat
        london = Point(-0.1246, 51.5007)  # lon, lat

        # Create markers GeoJSON - red circles
        markers_geojson = feature_collection([sydney, london])

        # Create style with markers source
        style = {
            "version": 8,
            "sources": {
                "openmaptiles": {"type": "vector", "url": "https://tiles.openfreemap.org/planet"},
                "markers": {
                    "type": "geojson",
                    "data": {"type": "FeatureCollection", "features": []},
                },
            },
            "layers": [
                {
                    "id": "background",
                    "type": "background",
                    "paint": {"background-color": "#f8f4f0"},
                },
                {
                    "id": "markers",
                    "type": "circle",
                    "source": "markers",
                    "paint": {
                        "circle-radius": 10,
                        "circle-color": "#ff0000",  # Red markers
                        "circle-stroke-width": 3,
                        "circle-stroke-color": "#ffffff",
                    },
                },
            ],
        }

        # Use HiDPI rendering (pixel_ratio=2)
        with Map(width=840, height=480, pixel_ratio=2) as m:
            m.load_style(style)

            # Calculate bounds from the two points
            bounds = (
                min(sydney.x, london.x),  # xmin
                min(sydney.y, london.y),  # ymin
                max(sydney.x, london.x),  # xmax
                max(sydney.y, london.y),  # ymax
            )

            # Get center and zoom for fitting both points
            center, zoom = m.fit_bounds(bounds, padding=50)

            # Zoom out by 0.2 to ensure both points are comfortably visible
            zoom_out = 0.2
            final_zoom = zoom - zoom_out

            # Set the markers
            m.set_geojson("markers", markers_geojson)

            # Render
            png = m.render(center=center, zoom=final_zoom)

            # Load image
            img = Image.open(io.BytesIO(png))

            # Image should be 1680x960 (840x480 * 2 for pixel_ratio=2)
            assert img.width == 1680, f"Expected width 1680, got {img.width}"
            assert img.height == 960, f"Expected height 960, got {img.height}"

            # Verify PNG is valid
            assert img.format == "PNG"

            # Look for red marker pixels
            marker_pixels = find_marker_pixels(img, (255, 0, 0), tolerance=40)

            # We should find marker pixels (red circles)
            assert len(marker_pixels) > 0, "No marker pixels found in image"

            # Group nearby pixels to find distinct markers
            # Simple clustering: group pixels within 50px of each other
            def cluster_pixels(
                pixels: list[tuple[int, int]], distance: int = 50
            ) -> list[list[tuple[int, int]]]:
                """Group pixels into clusters based on distance."""
                if not pixels:
                    return []

                clusters = []
                remaining = set(pixels)

                while remaining:
                    # Start new cluster with first pixel
                    pixel = remaining.pop()
                    cluster = [pixel]
                    to_check = [pixel]

                    while to_check:
                        current = to_check.pop()
                        # Find all pixels within distance
                        neighbors = set()
                        for p in remaining:
                            dx = p[0] - current[0]
                            dy = p[1] - current[1]
                            if dx * dx + dy * dy <= distance * distance:
                                neighbors.add(p)

                        for n in neighbors:
                            remaining.remove(n)
                            cluster.append(n)
                            to_check.append(n)

                    clusters.append(cluster)

                return clusters

            clusters = cluster_pixels(marker_pixels)

            # We expect 2 distinct marker clusters (one for each point)
            # But we might get more due to noise, so just check we have at least 2
            assert len(clusters) >= 2, f"Expected at least 2 marker clusters, found {len(clusters)}"

            # Check that markers are in different parts of the image
            # Sydney should be on the right side (higher longitude), London on left
            cluster_centers = []
            for cluster in clusters[:2]:  # Take first 2 clusters
                avg_x = sum(p[0] for p in cluster) / len(cluster)
                avg_y = sum(p[1] for p in cluster) / len(cluster)
                cluster_centers.append((avg_x, avg_y))

            # Sort by x coordinate
            cluster_centers.sort(key=lambda c: c[0])

            # Leftmost cluster should be London (lower longitude), rightmost Sydney (higher)
            # This is a sanity check that both hemispheres are visible
            assert cluster_centers[0][0] < cluster_centers[1][0], (
                "Markers not horizontally separated"
            )

            # Check vertical separation too (different latitudes)
            lat_diff = abs(cluster_centers[0][1] - cluster_centers[1][1])
            assert lat_diff > 50, f"Markers not vertically separated enough ({lat_diff}px)"

    @pytest.mark.integration
    def test_fit_bounds_pixel_ratio_compensation(self):
        """Verify fit_bounds accounts for pixel_ratio correctly.

        When pixel_ratio=2, the same zoom should show the same geographic area
        as pixel_ratio=1, just at higher resolution.
        """
        # Same bounds for both tests
        bounds = (-122.5, 37.7, -122.3, 37.9)  # San Francisco area

        # Get zoom at pixel_ratio=1
        with Map(width=512, height=512, pixel_ratio=1) as m1:
            center1, zoom1 = m1.fit_bounds(bounds)

        # Get zoom at pixel_ratio=2
        with Map(width=512, height=512, pixel_ratio=2) as m2:
            center2, zoom2 = m2.fit_bounds(bounds)

        # Centers should be the same
        assert center1[0] == pytest.approx(center2[0], abs=0.001)
        assert center1[1] == pytest.approx(center2[1], abs=0.001)

        # Zoom2 should be 1 level lower (log2(2) = 1)
        assert zoom2 == pytest.approx(zoom1 - 1.0, abs=0.01)
