"""Example: Rendering maps from addresses using geopy.

This example shows how to use geopy with mlnative to easily render
maps from addresses without manually looking up coordinates.
"""

from geopy.geocoders import ArcGIS

from mlnative import Map


def render_address(address: str, width: int = 512, height: int = 512, zoom: int = 14):
    """Render a map centered on an address.

    Uses ArcGIS geocoder (no API key required for basic usage).
    """
    # Geocode the address
    geolocator = ArcGIS()
    location = geolocator.geocode(address)

    if not location:
        raise ValueError(f"Could not geocode address: {address}")

    # Render map at that location (uses default OpenFreeMap Liberty style)
    with Map(width, height) as m:
        png = m.render(center=[location.longitude, location.latitude], zoom=zoom)
        return png, location


if __name__ == "__main__":
    # Example: Render map of Sydney Opera House
    print("Rendering map of Sydney Opera House...")
    png, location = render_address("Sydney Opera House, Australia", zoom=16)

    output_path = "sydney_opera_house.png"
    with open(output_path, "wb") as f:
        f.write(png)

    print(f"Saved to {output_path}")
    print(f"Location: {location.latitude}, {location.longitude}")

    # Example: Render multiple famous landmarks
    landmarks = [
        "Eiffel Tower, Paris",
        "Statue of Liberty, New York",
        "Big Ben, London",
    ]

    print("\nRendering landmark maps...")
    for landmark in landmarks:
        try:
            png, loc = render_address(landmark, zoom=14)
            filename = landmark.lower().replace(", ", "_").replace(" ", "_") + ".png"
            with open(filename, "wb") as f:
                f.write(png)
            print(f"  {landmark}: {filename}")
        except Exception as e:
            print(f"  {landmark}: Error - {e}")
