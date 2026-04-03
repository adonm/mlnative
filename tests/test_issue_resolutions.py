"""Regression tests for audit issues 3-11."""

import importlib.util
import json
import logging
import re
import tomllib
from pathlib import Path

import pytest

from mlnative import Map
from mlnative._bridge import PATH_BINARY_OPT_IN_ENV, RenderDaemon, get_binary_path
from mlnative.exceptions import MlnativeError
from mlnative.map import MAX_STYLE_JSON_BYTES

ROOT = Path(__file__).resolve().parents[1]


class FakeDaemon:
    """Minimal daemon stub for style reload tests."""

    def __init__(self) -> None:
        self.reloaded_style: str | None = None

    def reload_style(self, style: str) -> None:
        self.reloaded_style = style

    def stop(self) -> None:
        """Match the bridge daemon cleanup interface."""


def _load_download_binary_module():
    script_path = ROOT / "scripts" / "download-binary.py"
    spec = importlib.util.spec_from_file_location("download_binary", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bridge_logs_recent_renderer_stderr(caplog):
    """Renderer stderr should be retained for logs without leaking to callers."""
    daemon = RenderDaemon()
    daemon._stderr_lines.extend(["renderer detail 1", "renderer detail 2"])

    with caplog.at_level(logging.ERROR, logger="mlnative._bridge"):
        daemon._log_renderer_error("renderer render failed", "Render failed")

    assert "renderer render failed" in caplog.text
    assert "renderer detail 1" in caplog.text
    assert "renderer detail 2" in caplog.text
    assert daemon._format_renderer_error("Render failed") == "Render failed"


@pytest.mark.parametrize(
    ("relative_path", "masked_error"),
    [
        ("examples/fastapi_server.py", 'content={"error": "Render failed"}'),
        ("examples/web_test_server.py", 'content=b"Error: Render failed"'),
    ],
)
def test_example_servers_mask_client_errors_and_log_server_side(
    relative_path: str, masked_error: str
):
    """Example servers should keep client errors generic and log exceptions."""
    source = (ROOT / relative_path).read_text()

    assert "logger.exception(" in source
    assert masked_error in source


def test_get_binary_path_uses_path_only_with_explicit_opt_in(monkeypatch, tmp_path):
    """PATH fallback should work only when the caller explicitly enables it."""
    import mlnative._bridge as bridge

    platform_name, arch = bridge._get_platform_info()
    binary_name = f"mlnative-render-{platform_name}-{arch}"
    if platform_name == "win32":
        binary_name += ".exe"

    fake_dir = tmp_path / "bin"
    fake_dir.mkdir()
    fake_binary = fake_dir / binary_name
    fake_binary.write_bytes(b"binary")

    package_binary = Path(bridge.__file__).parent / "bin" / binary_name
    original_exists = Path.exists

    def fake_exists(self: Path) -> bool:
        if self == package_binary:
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setenv("PATH", str(fake_dir))
    monkeypatch.setenv(PATH_BINARY_OPT_IN_ENV, "1")

    assert get_binary_path() == fake_binary


@pytest.mark.parametrize("version", ["latest", "v0.3.9"])
def test_download_binary_helper_fails_closed(version: str):
    """The helper must refuse unverified executable downloads."""
    module = _load_download_binary_module()

    with pytest.raises(RuntimeError, match="Refusing to download and execute an unverified") as exc:
        module.download_binary(version)

    assert "github.com/adonm/mlnative/releases/download" in str(exc.value)


def test_ci_security_scan_uses_uv_with_pip_audit():
    """CI should run pip-audit from the uv-managed environment."""
    source = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "uv run --frozen --with pip-audit pip-audit" in source


def test_toolchain_and_dependency_versions_are_pinned():
    """Pinned tool versions avoid floating CI and build inputs."""
    mise = tomllib.loads((ROOT / ".mise.toml").read_text())
    cargo = tomllib.loads((ROOT / "rust/Cargo.toml").read_text())

    for tool in ("python", "rust", "just", "uv"):
        assert re.fullmatch(r"\d+\.\d+\.\d+", mise["tools"][tool])

    assert re.fullmatch(r"\d+\.\d+(?:\.\d+)?", cargo["dependencies"]["tempfile"])


def test_release_workflow_attest_action_is_digest_pinned():
    """Release provenance attestations should use pinned action digests."""
    source = (ROOT / ".github/workflows/release.yml").read_text()
    pinned = "actions/attest-build-provenance@b3e506e8c389afc651c5bacf2b8f2a1ea0557215"
    assert source.count(pinned) == 2


def test_rust_renderer_reuses_one_temp_style_file_for_json_reload():
    """Rust renderer should reuse one NamedTempFile instead of leaking them."""
    source = (ROOT / "rust/src/main.rs").read_text()

    assert "temp_style_file: Option<NamedTempFile>" in source
    assert source.count("NamedTempFile::new()") == 1
    assert "if temp_style_file.is_none()" in source
    assert "temp_file.as_file_mut().set_len(0)?;" in source


def test_set_geojson_reloads_updated_style_for_running_daemon(simple_style, simple_geojson):
    """GeoJSON updates should reload the active style with the new source data."""
    m = Map(width=512, height=512)
    m.load_style(simple_style)
    fake_daemon = FakeDaemon()
    m._daemon = fake_daemon

    m.set_geojson("markers", simple_geojson)

    assert fake_daemon.reloaded_style is not None
    reloaded_style = json.loads(fake_daemon.reloaded_style)
    assert reloaded_style["sources"]["markers"] == {
        "type": "geojson",
        "data": simple_geojson,
    }


def test_set_geojson_rejects_large_reload_payload(simple_style):
    """GeoJSON reloads should cap oversized style payloads before daemon reload."""
    m = Map(width=512, height=512)
    m.load_style(simple_style)
    fake_daemon = FakeDaemon()
    m._daemon = fake_daemon

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"blob": "x" * MAX_STYLE_JSON_BYTES},
            }
        ],
    }

    with pytest.raises(MlnativeError, match="larger than 5 MB"):
        m.set_geojson("markers", geojson)

    assert fake_daemon.reloaded_style is None


def test_geopy_is_optional_to_core_package_install():
    """Core installs should not pull geopy; the geo extra should."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

    core_dependencies = pyproject["project"]["dependencies"]
    geo_dependencies = pyproject["project"]["optional-dependencies"]["geo"]

    assert all("geopy" not in dependency for dependency in core_dependencies)
    assert any(dependency.startswith("geopy>=") for dependency in geo_dependencies)


def test_geo_extra_is_documented_in_readme_and_example():
    """Docs and examples should point users to the optional geo extra."""
    readme = (ROOT / "README.md").read_text()
    example = (ROOT / "examples/address_rendering.py").read_text()

    assert "mlnative[geo]" in readme
    assert "mlnative[geo]" in example
