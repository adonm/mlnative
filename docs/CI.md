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

### Build-Time Dependencies (for compiling the Rust binary)

Required when building the native renderer from source:

| Package | Purpose |
|---------|---------|
| **Rust 1.70+** | Compiler toolchain |
| **libcurl4-openssl-dev** | HTTP client library (development headers) |
| **pkg-config** | Build configuration tool |
| **libglfw3-dev** | GLFW windowing library (development headers) |
| **libuv1-dev** | Async I/O library (development headers) |
| **libz-dev** | zlib compression (development headers) |
| **CMake** | Build system generator |

**Ubuntu/Debian:**
```bash
sudo apt-get install -y \
  libcurl4-openssl-dev \
  pkg-config \
  libglfw3-dev \
  libuv1-dev \
  libz-dev \
  cmake
```

### Runtime Dependencies (for using pre-built wheels)

Required when using mlnative from PyPI (pre-built wheels):

| Package | Purpose | Critical |
|---------|---------|----------|
| **mesa-vulkan-drivers** | Vulkan graphics drivers | **YES** |
| **libcurl4** | HTTP client library | Yes |
| **libglfw3** | GLFW windowing library | Yes |
| **libuv1** | Async I/O library | Yes |
| **zlib1g** | zlib compression | Yes |
| **Network access** | Must reach tiles.openfreemap.org | Yes |

**⚠️ CRITICAL:** `mesa-vulkan-drivers` is required for GPU rendering. Without it, the renderer will crash immediately.

**Ubuntu/Debian:**
```bash
sudo apt-get install -y \
  mesa-vulkan-drivers \
  libcurl4 \
  libglfw3 \
  libuv1 \
  zlib1g
```

**Why different packages?**
- Build uses `-dev` packages (headers + libraries)
- Runtime uses base packages (libraries only, smaller/faster)

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
Error: `Failed to initialize graphics` or `Renderer process closed unexpectedly`
Solution: Install **mesa-vulkan-drivers** (critical runtime dependency):
```bash
sudo apt-get install -y mesa-vulkan-drivers
```

### Missing System Libraries
Error: `cannot find -lcurl` (during build)
Solution: Install development package:
```bash
sudo apt-get install -y libcurl4-openssl-dev
```

### Network Timeouts
Error: `Failed to fetch tile`
Solution: Ensure outbound HTTPS is allowed and OpenFreeMap is accessible

## Testing Locally

### Option 1: Using Pre-built Wheel (Recommended for testing)

If you just want to test rendering without building:

```bash
# Install runtime dependencies only
sudo apt-get install -y \
  mesa-vulkan-drivers \
  libcurl4 \
  libglfw3 \
  libuv1 \
  zlib1g

# Install mlnative from PyPI
pip install mlnative

# Run tests
python -c "
from mlnative import Map
with Map(256, 256) as m:
    png = m.render(center=[0, 0], zoom=1)
    print(f'Rendered: {len(png)} bytes')
"
```

### Option 2: Building from Source

If you need to modify and build the Rust binary:

```bash
# Install build dependencies
sudo apt-get install -y \
  libcurl4-openssl-dev \
  pkg-config \
  libglfw3-dev \
  libuv1-dev \
  libz-dev \
  cmake

# Build the binary
just build-rust

# Run tests
just test-unit
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
