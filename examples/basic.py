#!/usr/bin/env python3
"""
Basic usage example for mlnative.

Renders a simple map using OpenFreeMap Liberty style.
"""

from mlnative import Map


def main():
    print("Rendering map with OpenFreeMap Liberty style...")

    # Create map with context manager (auto cleanup)
    with Map(width=512, height=512) as m:
        # Load OpenFreeMap Liberty style (default)
        m.load_style("https://tiles.openfreemap.org/styles/liberty")

        # Render San Francisco
        print("Rendering San Francisco...")
        png_bytes = m.render(
            center=[-122.4194, 37.7749],  # [lon, lat]
            zoom=12,
        )

        # Save to file
        output_path = "san_francisco.png"
        with open(output_path, "wb") as f:
            f.write(png_bytes)

        print(f"Saved to {output_path} ({len(png_bytes)} bytes)")

    # Or without context manager (manual cleanup)
    print("\nRendering New York...")
    m = Map(width=800, height=600)
    try:
        m.load_style("https://tiles.openfreemap.org/styles/liberty")
        png_bytes = m.render(
            center=[-74.0060, 40.7128],
            zoom=11,
            bearing=45,  # Rotate 45 degrees
            pitch=30,  # Tilt 30 degrees
        )

        output_path = "new_york.png"
        with open(output_path, "wb") as f:
            f.write(png_bytes)

        print(f"Saved to {output_path} ({len(png_bytes)} bytes)")
    finally:
        m.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
