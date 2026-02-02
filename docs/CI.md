# CI/CD Requirements

This document describes the CI/CD setup and requirements for mlnative.

## Overview

The project uses GitHub Actions for continuous integration and deployment. The workflow is defined in `.github/workflows/release.yml`.

## Workflow Jobs

### 1. Lint and Type Check
- Runs on: `ubuntu-latest`
- Checks code formatting, linting, and type safety
- Uses: `just check`

### 2. Unit Tests
- Runs on: `ubuntu-latest`
- Runs fast unit tests (no rendering)
- Uses: `just test-unit`
- Skips integration tests marked with `@pytest.mark.integration`

### 3. Smoke Test
- Runs on: `ubuntu-latest`
- Depends on: `build-binary`
- **Purpose**: Quick validation that rendering works
- **Requirements**:
  - System dependencies: `libcurl4-openssl-dev`, `pkg-config`, `xvfb`
  - Native binary artifact from `build-binary` job
  - Network access (downloads tiles from openfreemap.org)
- Tests: Basic render with 256x256 map at zoom 1

### 4. Integration Tests
- Runs on: `ubuntu-latest`
- Depends on: `build-binary`
- **Purpose**: Full rendering tests including fit_bounds, pixel_ratio, etc.
- **Requirements**:
  - Same as smoke test
  - Longer timeout (10 minutes)
- Tests: All tests marked with `@pytest.mark.integration`

### 5. Build Binary
- Runs on: `ubuntu-latest` (x64) and `ubuntu-24.04-arm` (ARM64)
- **Purpose**: Build Rust native renderer
- **Requirements**:
  - Rust toolchain
  - System dependencies: `libcurl4-openssl-dev`, `pkg-config`
  - ~30 minute timeout (downloads and compiles maplibre-native)

### 6. Build Wheels
- Runs on: Same matrix as build-binary
- Depends on: `build-binary` and `smoke-test`
- **Purpose**: Create platform-specific Python wheels
- **Requirements**:
  - Binary artifact from build-binary job
  - Proper file permissions on binary (`chmod +x`)

### 7. Build Source Distribution
- Runs on: `ubuntu-latest`
- **Purpose**: Create source distribution for PyPI

### 8. GitHub Release
- Runs on: `ubuntu-latest`
- Depends on: `build-wheels` and `build-sdist`
- Triggered on: Tags starting with `v`
- **Purpose**: Create GitHub release with wheels and attestations

### 9. Publish to PyPI
- Runs on: `ubuntu-latest`
- Depends on: `build-wheels` and `build-sdist`
- Triggered on: Tags starting with `v`
- **Purpose**: Publish wheels to PyPI
- Uses: Trusted publishing (OIDC)

## System Requirements

### For Rendering (Smoke/Integration Tests)

The native renderer requires:

1. **libcurl4-openssl-dev**: For HTTP tile requests
2. **pkg-config**: For build configuration
3. **libglfw3-dev**: GLFW library for windowing
4. **libuv1-dev**: libuv for async I/O
5. **libz-dev**: zlib compression library
6. **Network access**: Must reach tiles.openfreemap.org

### For Building

1. **Rust 1.70+**: For compiling the native renderer
2. **libcurl4-openssl-dev**: System dependency
3. **pkg-config**: Build configuration
4. **libglfw3-dev**: GLFW library
5. **libuv1-dev**: libuv for async I/O
6. **libz-dev**: zlib compression
7. **CMake**: Required by maplibre-native build

## Network Requirements

- **Outbound HTTPS (443)**: Required for downloading:
  - Map tiles from `tiles.openfreemap.org`
  - Style JSON from `openfreemap.org`
  - Fonts and sprites as needed

## Common Issues

### Permission Denied on Binary
If the binary loses execute permissions (common in artifacts), the Python code automatically fixes this by checking and setting permissions in `mlnative/_bridge.py`.

### Missing System Libraries
Error: `cannot find -lcurl`
Solution: Install `libcurl4-openssl-dev`

### Graphics/Display Issues
Error: `Failed to initialize graphics`
Solution: Ensure all graphics libraries are installed (`libglfw3-dev`, `libuv1-dev`)

### Network Timeouts
Error: `Failed to fetch tile`
Solution: Ensure outbound HTTPS is allowed and OpenFreeMap is accessible

## Testing Locally

To run the same tests as CI:

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get install -y \
  libcurl4-openssl-dev \
  pkg-config \
  libglfw3-dev \
  libuv1-dev \
  libz-dev

# Build the binary
just build-rust

# Run unit tests
just test-unit

# Run smoke test
python -c "
from mlnative import Map
with Map(256, 256) as m:
    png = m.render(center=[0, 0], zoom=1)
    print(f'Rendered: {len(png)} bytes')
"

# Run integration tests
pytest tests/ -m integration -v
```

## Troubleshooting

### Debug Renderer Issues
Set debug environment variable:
```bash
MLNATIVE_DEBUG=1 python your_script.py
```

### Check Binary Permissions
```bash
ls -la mlnative/bin/
# Should show: -rwxr-xr-x
```

### Verify Network Access
```bash
curl -I https://tiles.openfreemap.org/styles/liberty
# Should return HTTP 200
```
