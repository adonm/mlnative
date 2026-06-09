#!/usr/bin/env python3
"""
Interactive web test interface for mlnative.

Provides a simple form to build API calls and see the generated Python code,
plus generate actual map images with various options including 2x/highdpi.
"""

import logging
from typing import Annotated

import uvicorn
from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from style_catalog import DEFAULT_STYLE_ID, STYLES, resolve_style

from mlnative import Map, MlnativeError

logger = logging.getLogger(__name__)

app = FastAPI(title="mlnative Test Interface")
templates = Jinja2Templates(directory="examples/templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Render the test form."""
    return templates.TemplateResponse(
        "test_form.html",
        {
            "request": request,
            "default_style": DEFAULT_STYLE_ID,
            "styles": STYLES,
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
    lon: Annotated[float, Form(ge=-180, le=180)] = -122.4194,
    lat: Annotated[float, Form(ge=-90, le=90)] = 37.7749,
    zoom: Annotated[float, Form(ge=0, le=22)] = 12,
    width: Annotated[int, Form(gt=0, le=2048)] = 512,
    height: Annotated[int, Form(gt=0, le=2048)] = 512,
    style: Annotated[str, Form()] = DEFAULT_STYLE_ID,
    bearing: Annotated[float, Form(ge=0, le=360)] = 0,
    pitch: Annotated[float, Form(ge=0, le=60)] = 0,
    highdpi: Annotated[bool, Form()] = False,
):
    """Show the Python code and generate preview."""
    pixel_ratio = 2.0 if highdpi else 1.0
    try:
        style_url = resolve_style(style)
    except MlnativeError:
        style = DEFAULT_STYLE_ID
        style_url = resolve_style(style)

    # Generate Python code example
    python_code = f'''from mlnative import Map

# Create map ({width}x{height}{" @2x" if highdpi else ""})
map = Map(
    width={width},
    height={height},
    pixel_ratio={pixel_ratio}
)

# Load style
map.load_style("{style_url}")

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
            "style_url": style_url,
            "bearing": bearing,
            "pitch": pitch,
            "highdpi": highdpi,
        },
    )


@app.get("/map.png")
def generate_map(
    lon: Annotated[float, Query(ge=-180, le=180)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    zoom: Annotated[float, Query(ge=0, le=22)],
    width: Annotated[int, Query(gt=0, le=2048)] = 512,
    height: Annotated[int, Query(gt=0, le=2048)] = 512,
    style: Annotated[str, Query()] = DEFAULT_STYLE_ID,
    bearing: Annotated[float, Query(ge=0, le=360)] = 0,
    pitch: Annotated[float, Query(ge=0, le=60)] = 0,
    highdpi: Annotated[bool, Query()] = False,
):
    """Generate map image from query parameters."""
    pixel_ratio = 2.0 if highdpi else 1.0

    try:
        style_url = resolve_style(style)
    except MlnativeError as e:
        return Response(content=str(e).encode(), media_type="text/plain", status_code=400)

    try:
        with Map(width=width, height=height, pixel_ratio=pixel_ratio) as m:
            m.load_style(style_url)
            png_bytes = m.render(center=[lon, lat], zoom=zoom, bearing=bearing, pitch=pitch)

        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f'inline; filename="map_{lon}_{lat}_{zoom}.png"'},
        )
    except MlnativeError:
        logger.exception(
            "preview map render failed",
            extra={"lon": lon, "lat": lat, "zoom": zoom, "width": width, "height": height},
        )
        return Response(
            content=b"Error: Render failed",
            media_type="text/plain",
            status_code=500,
        )
    except Exception:
        logger.exception("unexpected preview server error")
        return Response(
            content=b"Error: Internal server error",
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

    uvicorn.run(app, host="127.0.0.1", port=8000)
