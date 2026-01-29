#!/usr/bin/env python3
"""
Interactive web test interface for mlnative.

Provides a simple form to build API calls and see the generated Python code,
plus generate actual map images with various options including 2x/highdpi.
"""

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from mlnative import Map

app = FastAPI(title="mlnative Test Interface")
templates = Jinja2Templates(directory="examples/templates")

# Default OpenFreeMap Liberty style
DEFAULT_STYLE = "https://tiles.openfreemap.org/styles/liberty"


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Render the test form."""
    return templates.TemplateResponse(
        "test_form.html",
        {
            "request": request,
            "default_style": DEFAULT_STYLE,
            "default_lon": -122.4194,
            "default_lat": 37.7749,
            "default_zoom": 12,
            "default_width": 512,
            "default_height": 512,
        },
    )


@app.post("/preview", response_class=HTMLResponse)
def preview(
    request: Request,
    lon: float = Form(-122.4194),
    lat: float = Form(37.7749),
    zoom: float = Form(12),
    width: int = Form(512),
    height: int = Form(512),
    style: str = Form(DEFAULT_STYLE),
    bearing: float = Form(0),
    pitch: float = Form(0),
    highdpi: bool = Form(False),
):
    """Show the Python code and generate preview."""
    pixel_ratio = 2.0 if highdpi else 1.0

    # Generate Python code example
    python_code = f'''from mlnative import Map

# Create map ({width}x{height}{" @2x" if highdpi else ""})
map = Map(
    width={width},
    height={height},
    pixel_ratio={pixel_ratio}
)

# Load style
map.load_style("{style}")

# Render map
png_bytes = map.render(
    center=[{lon}, {lat}],
    zoom={zoom},
    bearing={bearing},
    pitch={pitch}
)

# Save to file
with open("map.png", "wb") as f:
    f.write(png_bytes)
'''

    # Build API URL
    api_url = f"/map.png?lon={lon}&lat={lat}&zoom={zoom}&width={width}&height={height}&style={style}&bearing={bearing}&pitch={pitch}"
    if highdpi:
        api_url += "&highdpi=1"

    return templates.TemplateResponse(
        "preview.html",
        {
            "request": request,
            "python_code": python_code,
            "api_url": api_url,
            "map_url": api_url,
            "lon": lon,
            "lat": lat,
            "zoom": zoom,
            "width": width,
            "height": height,
            "style": style,
            "bearing": bearing,
            "pitch": pitch,
            "highdpi": highdpi,
        },
    )


@app.get("/map.png")
def generate_map(
    lon: float,
    lat: float,
    zoom: float,
    width: int = 512,
    height: int = 512,
    style: str = DEFAULT_STYLE,
    bearing: float = 0,
    pitch: float = 0,
    highdpi: bool = False,
):
    """Generate map image from query parameters."""
    pixel_ratio = 2.0 if highdpi else 1.0

    try:
        with Map(width=width, height=height, pixel_ratio=pixel_ratio) as m:
            m.load_style(style)
            png_bytes = m.render(center=[lon, lat], zoom=zoom, bearing=bearing, pitch=pitch)

        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f'inline; filename="map_{lon}_{lat}_{zoom}.png"'},
        )
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        # Log the full error for debugging
        import traceback

        traceback.print_exc()
        return Response(
            content=error_msg.encode(),
            media_type="text/plain",
            status_code=500,
        )


if __name__ == "__main__":
    print("Starting mlnative web test interface...")
    print("\nOpen http://localhost:8000 in your browser")
    print("\nFeatures:")
    print("  - Interactive form to build map parameters")
    print("  - See generated Python code")
    print("  - Preview generated map images")
    print("  - Support for 2x/HighDPI rendering")
    print("\nPress Ctrl+C to stop")

    uvicorn.run(app, host="0.0.0.0", port=8000)
