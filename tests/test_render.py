"""
Tests for mlnative.

Integration tests that actually render maps.
"""

import os
from pathlib import Path

import pytest

from mlnative import Map, MlnativeError
from mlnative._bridge import get_vendor_dir


def vendor_binaries_available():
    """Check if vendor binaries are properly installed and working."""
    try:
        vendor_dir = get_vendor_dir()
        # Check if the maplibre-gl-native module exists
        mbgl_path = vendor_dir / "node_modules" / "@maplibre" / "maplibre-gl-native"
        if not mbgl_path.exists():
            return False
        # Check if lib directory exists with ABI-specific subdirectory
        lib_dir = mbgl_path / "lib"
        if not lib_dir.exists():
            return False
        # Check for any ABI version directory (node-v*)
        abi_dirs = list(lib_dir.glob("node-v*"))
        if not abi_dirs:
            return False
        # Check if the native binary exists
        for abi_dir in abi_dirs:
            if (abi_dir / "mbgl.node").exists():
                return True
        return False
    except Exception:
        return False


# Skip integration tests if vendor binaries not available
requires_vendor = pytest.mark.skipif(
    not vendor_binaries_available(),
    reason="Vendor binaries not installed or system libraries missing. Run: just build-vendor",
)


class TestMap:
    """Integration tests for Map class."""

    @requires_vendor
    def test_basic_render(self):
        """Test basic map rendering."""
        with Map(256, 256) as m:
            m.load_style("https://tiles.openfreemap.org/styles/liberty")
            png = m.render(center=[0, 0], zoom=1)

            # Check it's valid PNG
            assert png.startswith(b"\x89PNG")
            assert len(png) > 100  # Should have some content

    @requires_vendor
    def test_render_with_options(self):
        """Test rendering with bearing and pitch."""
        with Map(512, 512) as m:
            m.load_style("https://tiles.openfreemap.org/styles/liberty")
            png = m.render(center=[-122.4194, 37.7749], zoom=10, bearing=45, pitch=30)
            assert png.startswith(b"\x89PNG")

    @requires_vendor
    def test_different_sizes(self):
        """Test various image sizes."""
        sizes = [(128, 128), (512, 512), (1024, 768)]

        for width, height in sizes:
            with Map(width, height) as m:
                m.load_style("https://tiles.openfreemap.org/styles/liberty")
                png = m.render(center=[0, 0], zoom=2)
                assert png.startswith(b"\x89PNG")

    def test_invalid_dimensions(self):
        """Test error on invalid dimensions."""
        with pytest.raises(MlnativeError):
            Map(0, 512)

        with pytest.raises(MlnativeError):
            Map(512, -1)

    def test_invalid_center(self):
        """Test error on invalid center."""
        with Map(512, 512) as m:
            m.load_style("https://tiles.openfreemap.org/styles/liberty")
            with pytest.raises(MlnativeError):
                m.render(center=[0], zoom=5)  # Only one coordinate

    def test_style_dict(self):
        """Test loading style from dict."""
        style = {
            "version": 8,
            "sources": {
                "osm": {
                    "type": "raster",
                    "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                    "tileSize": 256,
                }
            },
            "layers": [{"id": "osm", "type": "raster", "source": "osm"}],
        }

        with Map(256, 256) as m:
            m.load_style(style)
            # Note: This might fail if OSM blocks requests, but tests the API
            try:
                png = m.render(center=[0, 0], zoom=1)
                assert png.startswith(b"\x89PNG")
            except MlnativeError:
                pass  # Network issues are ok for this test

    def test_explicit_close(self):
        """Test explicit close method."""
        m = Map(512, 512)
        m.load_style("https://tiles.openfreemap.org/styles/liberty")
        m.close()

        # Should error after close
        with pytest.raises(MlnativeError):
            m.render(center=[0, 0], zoom=5)

    def test_missing_style(self):
        """Test error on missing style file."""
        with Map(512, 512) as m:
            with pytest.raises(MlnativeError):
                m.load_style("/nonexistent/style.json")


class TestFastAPI:
    """Tests for FastAPI example (if dependencies installed)."""

    @pytest.fixture
    def client(self):
        try:
            from fastapi.testclient import TestClient

            from examples.fastapi_server import app

            return TestClient(app)
        except ImportError:
            pytest.skip("FastAPI not installed")

    def test_api_root(self, client):
        """Test API info endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        assert "mlnative" in response.json()["name"].lower()

    @requires_vendor
    def test_static_map_endpoint(self, client):
        """Test static map endpoint."""
        response = client.get("/static/0,0,1/256x256.png")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG")

    @requires_vendor
    def test_static_map_with_params(self, client):
        """Test static map with query params."""
        response = client.get("/static/-122.4194,37.7749,12/512x512.png?bearing=45&pitch=30")
        assert response.status_code == 200
        assert response.content.startswith(b"\x89PNG")

    def test_invalid_dimensions(self, client):
        """Test error on invalid dimensions."""
        response = client.get("/static/0,0,1/0x512.png")
        assert response.status_code == 400

    def test_oversized_dimensions(self, client):
        """Test error on oversized dimensions."""
        response = client.get("/static/0,0,1/3000x3000.png")
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
