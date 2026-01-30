"""
Tests for mlnative.

Integration tests that actually render maps.
"""

import subprocess
import warnings

import pytest

from mlnative import Map, MlnativeError
from mlnative._bridge import get_vendor_dir


def vendor_binaries_available():
    """Check if vendor binaries are properly installed and system libraries compatible."""
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
        # Check if the native binary exists in any ABI directory
        native_binaries = [abi_dir / "mbgl.node" for abi_dir in abi_dirs]
        native_binary = next((b for b in native_binaries if b.exists()), None)
        if native_binary is None:
            return False

        # Check system library compatibility using ldd
        # This catches missing libjpeg.so.8, ICU libraries, etc.
        import sys

        if sys.platform == "linux":
            result = subprocess.run(
                ["ldd", str(native_binary)],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                return False
            # Check for "not found" in ldd output
            ldd_output = result.stdout.decode()
            if "not found" in ldd_output:
                return False

        return True
    except Exception:
        return False


# Skip integration tests if vendor binaries not available
requires_vendor = pytest.mark.skipif(
    not vendor_binaries_available(),
    reason="Vendor binaries not installed or system libraries missing. Run: just build-vendor",
)


class TestValidation:
    """Unit tests for input validation (no rendering required)."""

    def test_valid_map_creation(self):
        """Test creating a map with valid parameters."""
        m = Map(512, 512)
        assert m.width == 512
        assert m.height == 512
        m.close()

    def test_invalid_dimensions_zero(self):
        """Test error on zero dimensions."""
        with pytest.raises(MlnativeError, match="positive"):
            Map(0, 512)

    def test_invalid_dimensions_negative(self):
        """Test error on negative dimensions."""
        with pytest.raises(MlnativeError, match="positive"):
            Map(512, -1)

    def test_invalid_dimensions_too_large(self):
        """Test error on dimensions exceeding max."""
        with pytest.raises(MlnativeError, match="4096"):
            Map(5000, 512)

    def test_invalid_center_too_few(self):
        """Test error on center with one coordinate."""
        with Map(512, 512) as m, pytest.raises(MlnativeError, match="longitude, latitude"):
            m.render(center=[0], zoom=5)

    def test_invalid_center_too_many(self):
        """Test error on center with three coordinates."""
        with Map(512, 512) as m, pytest.raises(MlnativeError, match="longitude, latitude"):
            m.render(center=[0, 0, 0], zoom=5)

    def test_invalid_longitude(self):
        """Test error on longitude out of range."""
        with Map(512, 512) as m, pytest.raises(MlnativeError, match="Longitude"):
            m.render(center=[200, 0], zoom=5)

    def test_invalid_latitude(self):
        """Test error on latitude out of range."""
        with Map(512, 512) as m, pytest.raises(MlnativeError, match="Latitude"):
            m.render(center=[0, 100], zoom=5)

    def test_invalid_zoom_negative(self):
        """Test error on negative zoom."""
        with Map(512, 512) as m, pytest.raises(MlnativeError, match="Zoom"):
            m.render(center=[0, 0], zoom=-1)

    def test_invalid_zoom_too_high(self):
        """Test error on zoom exceeding max."""
        with Map(512, 512) as m, pytest.raises(MlnativeError, match="Zoom"):
            m.render(center=[0, 0], zoom=25)

    def test_invalid_pitch(self):
        """Test error on pitch out of range."""
        with Map(512, 512) as m, pytest.raises(MlnativeError, match="Pitch"):
            m.render(center=[0, 0], zoom=5, pitch=90)

    def test_bearing_normalized(self):
        """Test that bearing is normalized (doesn't raise error)."""
        # Bearing can be any value, gets normalized to 0-360
        with Map(512, 512) as m:
            # This should not raise, bearing will be normalized internally
            # (render will fail without vendor, but validation passes)
            try:
                m.render(center=[0, 0], zoom=5, bearing=720)
            except MlnativeError as e:
                # Only ok if it's a vendor/render error, not validation
                assert "bearing" not in str(e).lower()

    def test_request_handler_warning(self):
        """Test that request_handler emits FutureWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            m = Map(512, 512, request_handler=lambda x: b"")
            m.close()

            assert len(w) == 1
            assert issubclass(w[0].category, FutureWarning)
            assert "request_handler" in str(w[0].message)

    def test_missing_style_file(self):
        """Test error on missing style file."""
        with Map(512, 512) as m, pytest.raises(MlnativeError):
            m.load_style("/nonexistent/style.json")

    def test_close_prevents_operations(self):
        """Test that close prevents further operations."""
        m = Map(512, 512)
        m.close()

        with pytest.raises(MlnativeError, match="closed"):
            m.load_style("https://example.com/style.json")

        with pytest.raises(MlnativeError, match="closed"):
            m.render(center=[0, 0], zoom=5)


class TestMapIntegration:
    """Integration tests for Map class (require vendor binaries)."""

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

    @requires_vendor
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
