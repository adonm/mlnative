# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.9] - 2025-02-15

### Fixed

- Removed unreachable Path handling code in `map.py` `_get_daemon()` and `load_style()`
- Moved `import base64` to module level in `_bridge.py` (was inside methods)
- Fixed potential panics in Rust daemon by replacing `.expect()` with proper error handling
- Removed duplicated style loading logic in Rust (extracted to `load_style()` helper)
- Fixed outdated error message in `preview.html` (now references `just build-rust`)

### Added

- Added `tests/conftest.py` with shared pytest fixtures
- Added `tests/test_bridge.py` for `_bridge.py` unit tests
- Added `tests/test_geo_bounds.py` for `bounds_to_polygon()` tests
- Added `docs/API.md` with comprehensive API reference
- Added visual regression testing with `just visual-render` and `just visual-compare`
- Added `scripts/visual_compare.py` for comparing mlnative vs Chrome renders
- Added `playwright` to dev dependencies for visual testing
- Added example scripts: `error_handling.py`, `geojson_layers.py`, `production_deployment.py`

### Changed

- Improved CI workflow with separate lint/test/build stages
- Added Rust clippy checks to CI
- Added code coverage reporting

## [0.3.8] - 2025-01-XX

### Added

- Initial public release
- `Map` class for static map rendering
- `render()` and `render_batch()` methods
- `fit_bounds()` for automatic zoom calculation
- `set_geojson()` for dynamic GeoJSON updates
- `load_style()` for URL, file path, or dict styles
- GeoJSON helper utilities in `mlnative.geo`
- FastAPI example server
- Web test interface
