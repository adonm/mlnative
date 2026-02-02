#!/usr/bin/env python3
"""Generate example screenshots for README.

Run this script to regenerate screenshots after style changes or updates.
"""

from geopy.geocoders import ArcGIS

from mlnative import Map

# Geocode location for screenshots
geolocator = ArcGIS()
location = geolocator.geocode("Sydney Opera House")
center = [location.longitude, location.latitude]
zoom = 15
width, height = 400, 300  # Smaller size for docs


def generate_style_comparison():
    """Generate screenshots of different OpenFreeMap styles."""
    styles = [
        ("liberty", "OpenFreeMap Liberty (default)"),
        ("positron", "OpenFreeMap Positron (light)"),
        ("dark", "OpenFreeMap Dark Matter (dark)"),
    ]

    print("Generating style comparison screenshots...")
    for style_name, description in styles:
        style_url = f"https://tiles.openfreemap.org/styles/{style_name}"
        with Map(width, height) as m:
            m.load_style(style_url)
            png = m.render(center=center, zoom=zoom)

            filename = f"docs/images/style-{style_name}.png"
            with open(filename, "wb") as f:
                f.write(png)
            print(f"  Generated: {filename} ({description})")


def generate_pixel_ratio_comparison():
    """Generate screenshots showing pixel ratio difference."""
    print("\nGenerating pixel ratio comparison screenshots...")

    # Generate at 1x (standard)
    with Map(width, height, pixel_ratio=1) as m:
        png = m.render(center=center, zoom=zoom)
        filename = "docs/images/pixelratio-1x.png"
        with open(filename, "wb") as f:
            f.write(png)
        print(f"  Generated: {filename} (1x standard)")

    # Generate at 2x (HiDPI/Retina)
    with Map(width, height, pixel_ratio=2) as m:
        png = m.render(center=center, zoom=zoom)
        filename = "docs/images/pixelratio-2x.png"
        with open(filename, "wb") as f:
            f.write(png)
        print(f"  Generated: {filename} (2x HiDPI)")

    print("\nNote: Both images show the same geographic area.")
    print("The 2x version is 800x600 pixels but displays sharply at 400x300.")


if __name__ == "__main__":
    generate_style_comparison()
    generate_pixel_ratio_comparison()
    print("\n✓ All screenshots generated in docs/images/")
