"""Tests for _bridge module."""

import pytest

from mlnative._bridge import (
    PATH_BINARY_OPT_IN_ENV,
    _get_platform_info,
    _get_timeout,
    get_binary_path,
)
from mlnative.exceptions import MlnativeError


class TestGetPlatformInfo:
    """Tests for _get_platform_info()."""

    def test_returns_tuple(self):
        """Test that function returns a tuple of two strings."""
        platform, arch = _get_platform_info()
        assert isinstance(platform, str)
        assert isinstance(arch, str)

    def test_valid_platform(self):
        """Test that platform is one of the supported values."""
        platform, _ = _get_platform_info()
        assert platform in ("darwin", "linux", "win32")

    def test_valid_arch(self):
        """Test that arch is one of the supported values."""
        _, arch = _get_platform_info()
        assert arch in ("arm64", "x64")


class TestGetBinaryPath:
    """Tests for get_binary_path()."""

    def test_path_lookup_requires_opt_in(self, monkeypatch, tmp_path):
        """PATH fallback should stay disabled unless explicitly enabled."""
        platform, arch = _get_platform_info()
        binary_name = f"mlnative-render-{platform}-{arch}"
        if platform == "win32":
            binary_name += ".exe"

        fake_dir = tmp_path / "bin"
        fake_dir.mkdir()
        fake_binary = fake_dir / binary_name
        fake_binary.write_bytes(b"#!/bin/sh\n")

        monkeypatch.setenv("PATH", str(fake_dir))
        monkeypatch.setenv(PATH_BINARY_OPT_IN_ENV, "0")

        try:
            path = get_binary_path()
            if path == fake_binary:
                pytest.fail("PATH fallback should require explicit opt-in")
        except MlnativeError as e:
            assert PATH_BINARY_OPT_IN_ENV in str(e)


    def test_binary_name_format(self):
        """Test that binary name follows expected format."""
        try:
            path = get_binary_path()
            name = path.name
            assert "mlnative-render-" in name
        except MlnativeError as e:
            if "not found" in str(e):
                pytest.skip("Binary not built yet")
            raise

    def test_binary_exists_or_error(self):
        """Test that function either finds binary or raises clear error."""
        try:
            path = get_binary_path()
            assert path.exists()
        except MlnativeError as e:
            assert "not found" in str(e).lower() or "unsupported" in str(e).lower()


class TestRenderDaemonValidation:
    """Tests for RenderDaemon input validation."""

    def test_render_without_init(self):
        """Test that render fails if daemon not initialized."""
        from mlnative._bridge import RenderDaemon

        daemon = RenderDaemon()
        with pytest.raises(MlnativeError, match="not initialized"):
            daemon.render([0, 0], 1)

    def test_render_batch_without_init(self):
        """Test that render_batch fails if daemon not initialized."""
        from mlnative._bridge import RenderDaemon

        daemon = RenderDaemon()
        with pytest.raises(MlnativeError, match="not initialized"):
            daemon.render_batch([{"center": [0, 0], "zoom": 1}])

    def test_reload_style_without_init(self):
        """Test that reload_style fails if daemon not initialized."""
        from mlnative._bridge import RenderDaemon

        daemon = RenderDaemon()
        with pytest.raises(MlnativeError, match="not initialized"):
            daemon.reload_style("{}")

    def test_double_start(self):
        """Test that starting twice raises error."""
        from mlnative._bridge import RenderDaemon

        daemon = RenderDaemon()
        try:
            daemon.start(256, 256, "https://tiles.openfreemap.org/styles/liberty")
            with pytest.raises(MlnativeError, match="already started"):
                daemon.start(256, 256, "https://tiles.openfreemap.org/styles/liberty")
        except MlnativeError as e:
            if "not found" in str(e):
                pytest.skip("Binary not built yet")
            raise
        finally:
            daemon.stop()


class TestTimeoutConfiguration:
    """Tests for daemon timeout configuration."""

    def test_default_timeout(self, monkeypatch):
        """Test default timeout when env var is unset."""
        monkeypatch.delenv("MLNATIVE_TIMEOUT", raising=False)
        assert _get_timeout() == pytest.approx(30.0)

    def test_env_timeout(self, monkeypatch):
        """Test timeout can be configured via environment."""
        monkeypatch.setenv("MLNATIVE_TIMEOUT", "12.5")
        assert _get_timeout() == pytest.approx(12.5)

    def test_invalid_env_timeout(self, monkeypatch):
        """Test invalid timeout values are rejected."""
        monkeypatch.setenv("MLNATIVE_TIMEOUT", "nope")
        with pytest.raises(MlnativeError, match="MLNATIVE_TIMEOUT"):
            _get_timeout()

    def test_non_positive_timeout(self):
        """Test timeout must be positive."""
        with pytest.raises(MlnativeError, match="MLNATIVE_TIMEOUT"):
            _get_timeout(0)
