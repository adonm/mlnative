"""Visual regression testing - compare mlnative renders against Chrome.

Generates test renders using both mlnative and Chrome headless (MapLibre GL JS)
via Playwright, then saves them for AI visual comparison.

Usage:
    just visual-render   # Generate renders
    just visual-compare  # Compare with AI
    just visual-test     # Both
"""

from pathlib import Path

from mlnative import Map

OUTPUT_DIR = Path("test-output")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
  <link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
  <style>
    body {{ margin: 0; padding: 0; }}
    #map {{ width: {width}px; height: {height}px; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script>
    window.mapReady = false;
    const map = new maplibregl.Map({{
      container: 'map',
      style: '{style}',
      center: [{center_lon}, {center_lat}],
      zoom: {zoom},
      bearing: {bearing},
      pitch: {pitch},
      interactive: false,
      preserveDrawingBuffer: true
    }});
    map.on('idle', () => {{
      window.mapReady = true;
    }});
  </script>
</body>
</html>
"""


def render_mlnative(
    width: int,
    height: int,
    center: list[float],
    zoom: float,
    style: str,
    bearing: float = 0,
    pitch: float = 0,
) -> bytes:
    """Render using mlnative."""
    with Map(width, height) as m:
        m.load_style(style)
        return m.render(center=center, zoom=zoom, bearing=bearing, pitch=pitch)


def render_chrome(
    width: int,
    height: int,
    center: list[float],
    zoom: float,
    style: str,
    bearing: float = 0,
    pitch: float = 0,
) -> bytes:
    """Render using Playwright with Chrome and MapLibre GL JS."""
    from playwright.sync_api import sync_playwright

    html = HTML_TEMPLATE.format(
        width=width,
        height=height,
        style=style,
        center_lon=center[0],
        center_lat=center[1],
        zoom=zoom,
        bearing=bearing,
        pitch=pitch,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_content(html)

        page.wait_for_function("window.mapReady === true", timeout=30000)

        png_bytes = page.screenshot(type="png")
        browser.close()
        return png_bytes


def generate_test_renders():
    """Generate test renders for comparison."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    test_cases = [
        {
            "name": "simple",
            "width": 512,
            "height": 512,
            "center": [-122.4, 37.8],
            "zoom": 10,
            "style": "https://tiles.openfreemap.org/styles/liberty",
        },
        {
            "name": "zoomed-out",
            "width": 512,
            "height": 512,
            "center": [0, 20],
            "zoom": 2,
            "style": "https://tiles.openfreemap.org/styles/liberty",
        },
        {
            "name": "with-bearing",
            "width": 512,
            "height": 512,
            "center": [-73.9857, 40.7484],
            "zoom": 14,
            "bearing": 45,
            "style": "https://tiles.openfreemap.org/styles/liberty",
        },
    ]

    for case in test_cases:
        name = case["name"]
        print(f"Rendering {name}...")

        try:
            mlnative_png = render_mlnative(
                width=case["width"],
                height=case["height"],
                center=case["center"],
                zoom=case["zoom"],
                style=case["style"],
                bearing=case.get("bearing", 0),
                pitch=case.get("pitch", 0),
            )
            (OUTPUT_DIR / f"{name}-mlnative.png").write_bytes(mlnative_png)
            print(f"  mlnative: {len(mlnative_png)} bytes")
        except Exception as e:
            print(f"  mlnative FAILED: {e}")

        try:
            chrome_png = render_chrome(
                width=case["width"],
                height=case["height"],
                center=case["center"],
                zoom=case["zoom"],
                style=case["style"],
                bearing=case.get("bearing", 0),
                pitch=case.get("pitch", 0),
            )
            (OUTPUT_DIR / f"{name}-chrome.png").write_bytes(chrome_png)
            print(f"  chrome: {len(chrome_png)} bytes")
        except ImportError:
            print("  chrome SKIPPED: playwright not installed")
            print("    Install with: uv pip install playwright && playwright install chromium")
            break
        except Exception as e:
            print(f"  chrome FAILED: {e}")

    print(f"\nOutputs saved to {OUTPUT_DIR}/")
    print("\nTo compare with AI, run:")
    print(
        "  opencode run -m kimi-for-coding/k2p5 'Compare test-output/simple-mlnative.png with test-output/simple-chrome.png'"
    )


if __name__ == "__main__":
    generate_test_renders()
