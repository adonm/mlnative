#!/usr/bin/env python3
"""
Basic usage example for mlnative.

Renders maps using addresses instead of hardcoded coordinates.
"""

from geopy.geocoders import ArcGIS

from mlnative import Map


def main():
    print("Rendering maps from addresses...")
    geolocator = ArcGIS()

    # Example 1: Simple map
    print("\n1. Rendering San Francisco...")
    location = geolocator.geocode("San Francisco")

    with Map(width=512, height=512) as m:
        png_bytes = m.render(
            center=[location.longitude, location.latitude],
            zoom=12,
        )

        output_path = "san_francisco.png"
        with open(output_path, "wb") as f:
            f.write(png_bytes)
        print(f"   Saved to {output_path} ({len(png_bytes)} bytes)")

    # Example 2: With rotation and tilt
    print("\n2. Rendering New York (with rotation and tilt)...")
    location = geolocator.geocode("New York City")

    with Map(width=800, height=600) as m:
        png_bytes = m.render(
            center=[location.longitude, location.latitude],
            zoom=11,
            bearing=45,  # Rotate 45 degrees
            pitch=30,  # Tilt 30 degrees
        )

        output_path = "new_york.png"
        with open(output_path, "wb") as f:
            f.write(png_bytes)
        print(f"   Saved to {output_path} ({len(png_bytes)} bytes)")

    # Example 3: HiDPI / Retina rendering
    print("\n3. Rendering Sydney in HiDPI (2x resolution)...")
    location = geolocator.geocode("Sydney Opera House")

    with Map(width=512, height=512, pixel_ratio=2) as m:
        png_bytes = m.render(
            center=[location.longitude, location.latitude],
            zoom=15,
        )

        output_path = "sydney_hidpi.png"
        with open(output_path, "wb") as f:
            f.write(png_bytes)
        print(f"   Saved to {output_path} ({len(png_bytes)} bytes)")
        print("   Image is 1024x1024 pixels - sharp on retina displays")

    print("\nDone!")


if __name__ == "__main__":
    main()
