# mlnative-render

Native Rust binary for rendering static MapLibre maps using the official MapLibre Native C++ core library.

## Overview

This binary provides a high-performance, statically-linked renderer that communicates via JSON over stdin/stdout. It's designed to be used by the Python `mlnative` package for efficient batch map rendering.

## Architecture

```
Python (mlnative) <-- JSON --> Rust (mlnative-render) <-- FFI --> MapLibre Native (C++)
```

The binary uses pre-built **amalgam** libraries from MapLibre Native which include all dependencies (ICU, libjpeg, etc.) statically linked. This eliminates system dependency issues.

## Communication Protocol

The daemon accepts JSON commands on stdin and outputs JSON responses on stdout.

### Commands

#### Initialize
```json
{"cmd": "init", "width": 512, "height": 512, "style": "https://...", "pixel_ratio": 2.0}
```

**Parameters:**
- `width`, `height`: Logical dimensions in CSS pixels
- `style`: URL or JSON string of map style
- `pixel_ratio` (optional): Scale factor for HiDPI rendering (default 1.0)
  - Output image will be `width × pixel_ratio` by `height × pixel_ratio` pixels
  - Use 2.0 for retina displays, 3.0 for ultra-HD

#### Render Single View
```json
{"cmd": "render", "center": [115.86, -31.95], "zoom": 12, "bearing": 0, "pitch": 0}
```

#### Render Batch
```json
{"cmd": "render_batch", "views": [{"center": [0, 0], "zoom": 5}, ...]}
```

#### Quit
```json
{"cmd": "quit"}
```

### Responses

Success:
```json
{"status": "ok", "png": "base64_encoded_png_data"}
```

Error:
```json
{"status": "error", "error": "error message"}
```

## Building

### Prerequisites

- Rust toolchain pinned in `.mise.toml`
- CMake (for building)
- libcurl, OpenSSL, libjpeg, libpng, WebP, ICU, libuv, and zlib development headers plus pkg-config on Linux

### Build

```bash
cd rust
cargo build --release --locked
```

The binary will be at `target/release/mlnative-render`.

### Cross-compilation

The CI currently builds Linux wheels for:
- Linux x64 (x86_64-unknown-linux-gnu)
- Linux ARM64 (aarch64-unknown-linux-gnu)

## Dependencies

This crate uses `maplibre_native` which:
1. Downloads pre-built MapLibre Native amalgam libraries automatically
2. Links them statically (no dynamic dependencies)
3. Provides a safe Rust API

The amalgam libraries include:
- MapLibre Native core
- ICU (libicuuc, libicudata, libicui18n)
- libjpeg
- libpng
- And other dependencies

## Testing

```bash
echo '{"cmd": "init", "width": 512, "height": 512, "style": "https://tiles.openfreemap.org/styles/liberty"}' | ./mlnative-render
echo '{"cmd": "render", "center": [0, 0], "zoom": 1}' | ./mlnative-render
echo '{"cmd": "quit"}' | ./mlnative-render
```

## License

Apache-2.0 - same as MapLibre Native
