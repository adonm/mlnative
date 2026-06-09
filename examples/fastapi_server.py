#!/usr/bin/env python3
"""
FastAPI static maps server example.

Emulates Mapbox Static Images API:
GET /static/{lon},{lat},{zoom}/{width}x{height}.png

Query parameters:
- bearing: Rotation in degrees (default 0)
- pitch: Tilt in degrees (default 0)
- style: Style ID from the allowlist (default: liberty)
"""

import logging

import uvicorn
from fastapi import FastAPI, Query, Response
from fastapi.responses import JSONResponse
from style_catalog import DEFAULT_STYLE_ID, STYLES, resolve_style

from mlnative import Map, MlnativeError

logger = logging.getLogger(__name__)

app = FastAPI(title="mlnative Static Maps API")


@app.get("/")
def root():
    """API info."""
    return {
        "name": "mlnative Static Maps API",
        "version": "0.3.10",
        "endpoints": {"static_map": "/static/{lon},{lat},{zoom}/{width}x{height}.png"},
        "default_style": DEFAULT_STYLE_ID,
        "styles": sorted(STYLES),
    }


@app.get("/static/{lon},{lat},{zoom}/{width}x{height}.png")
def static_map(
    lon: float,
    lat: float,
    zoom: float,
    width: int,
    height: int,
    bearing: float = Query(0, ge=0, le=360),
    pitch: float = Query(0, ge=0, le=60),
    style: str = Query(DEFAULT_STYLE_ID),
):
    """
    Generate a static map image.

    Parameters:
    - lon: Longitude (-180 to 180)
    - lat: Latitude (-90 to 90)
    - zoom: Zoom level (0-22)
    - width: Image width in pixels (max 2048)
    - height: Image height in pixels (max 2048)
    - bearing: Rotation in degrees (0-360)
    - pitch: Tilt in degrees (0-60)
    - style: Map style ID: liberty, positron, or dark
    """
    # Validate dimensions
    if width > 2048 or height > 2048:
        return JSONResponse(
            status_code=400, content={"error": "Dimensions too large (max 2048x2048)"}
        )

    if width <= 0 or height <= 0:
        return JSONResponse(status_code=400, content={"error": "Dimensions must be positive"})

    try:
        style_url = resolve_style(style)
    except MlnativeError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    try:
        # Render map
        with Map(width=width, height=height) as m:
            m.load_style(style_url)
            png_bytes = m.render(center=[lon, lat], zoom=zoom, bearing=bearing, pitch=pitch)

        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=map_{lon}_{lat}_{zoom}.png"},
        )

    except MlnativeError:
        logger.exception(
            "static map render failed",
            extra={"lon": lon, "lat": lat, "zoom": zoom, "width": width, "height": height},
        )
        return JSONResponse(status_code=500, content={"error": "Render failed"})
    except Exception:
        logger.exception("unexpected static map server error")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    print("Starting mlnative Static Maps API server...")
    print(f"Default style: {DEFAULT_STYLE_ID}")
    print(f"Available styles: {', '.join(sorted(STYLES))}")
    print("\nExample URLs:")
    print("  http://localhost:8000/static/-122.4194,37.7749,12/512x512.png")
    print("  http://localhost:8000/static/-74.0060,40.7128,11/800x600.png?bearing=45&pitch=30")
    print("\nAPI docs: http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop")

    uvicorn.run(app, host="127.0.0.1", port=8000)
