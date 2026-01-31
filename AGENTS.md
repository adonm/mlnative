# AGENTS.md - Guidelines for AI Coding Agents

## Prerequisites

**Requirements:** Python 3.12+, Rust 1.70+

## Build/Test/Lint Commands

### Using Just (recommended)

```bash
# Setup development environment
just setup

# Run all quality checks (lint + format + typecheck + test)
just check

# Run all tests
just test

# Run single test
just test-single tests/test_render.py::TestMap::test_basic_render

# Run tests matching pattern
just test-filter "test_render"

# Run only unit tests (skip integration)
just test-unit

# Run tests in Docker (if system libraries are incompatible)
just test-docker

# Linting and formatting
just lint          # Check linting
just lint-fix      # Auto-fix issues
just format        # Format code
just format-check  # Check formatting (CI)

# Type checking
just typecheck

# Build and clean
just build
just build-rust    # Build Rust binary only
just clean

# Build wheels for distribution
just build-wheels  # All platforms (requires Docker)

# Run examples
just serve       # FastAPI static maps API
just serve-test  # Interactive web test interface
just example     # Basic usage example

# Show code stats
just stats
```

### Using uv directly

```bash
# Setup
cd /var/home/adonm/dev/maplibre-native/mlnative
uv venv
uv pip install -e ".[dev,web]"

# Build Rust binary
cd rust && cargo build --release

# Run tests
uv run python -m pytest tests/ -v --tb=short

# Linting with ruff
uv run ruff check mlnative/ tests/ examples/
uv run ruff check mlnative/ tests/ examples/ --fix
uv run ruff format mlnative/ tests/ examples/

# Type checking with mypy
uv run mypy mlnative/

# Build package
uv build
```

## Code Style Guidelines

### Philosophy
- **Grug-brained**: Simple > Complex. One class, 4 methods max.
- **Explicit > Implicit**: No magic, clear error messages
- **80/20 solution**: Handle common cases simply

### Python Version
- **Minimum:** Python 3.12
- Use modern syntax: `dict[str, Any]` instead of `Dict[str, Any]`
- Use `|` union operator: `str | int` instead of `Union[str, int]`

### Imports
- Group: stdlib → third-party → local
- Use `from typing import` for common types
- Absolute imports for local modules: `from .module import Thing`
- Sorted by ruff (configured in pyproject.toml)

### Formatting (ruff)
- Line length: 100 characters
- Double quotes for strings
- 4 spaces indentation
- Run `just format` before committing

### Types (mypy)
- Use type hints for all function signatures
- Use `str | None` instead of `Optional[str]` (Python 3.10+ style)
- Use `dict[str, Any]` instead of `Dict[str, Any]`
- Run `just typecheck` to verify

### Naming
- `snake_case` for functions/variables
- `PascalCase` for classes
- `UPPER_CASE` for constants
- Private modules: `_bridge.py`
- Private functions: `_helper_function()`

### Error Handling
- Raise `MlnativeError` (or subclass) for all errors
- Include helpful context in error messages
- Use `hasattr()` checks in `__del__` to avoid AttributeError
- Keep error messages actionable

### Docstrings
- Google style: `Args:`, `Returns:`, `Raises:`
- Keep docstrings concise
- Include usage examples for public API

### Testing
- Integration tests preferred over unit tests
- Test class naming: `TestFeature`
- Use pytest fixtures where appropriate
- Run `just test-unit` for quick feedback

## Project Structure

```
mlnative/
├── mlnative/           # Main package
│   ├── __init__.py     # Public exports
│   ├── map.py          # Main Map class
│   ├── _bridge.py      # Rust subprocess wrapper
│   ├── exceptions.py   # MlnativeError
│   └── bin/            # Platform-specific binaries
├── rust/               # Rust native renderer
│   ├── Cargo.toml
│   └── src/
│       └── main.rs     # JSON daemon
├── examples/           # Usage examples
│   ├── basic.py        # Simple example
│   ├── fastapi_server.py       # Static maps API
│   ├── web_test_server.py      # Interactive test UI
│   └── templates/      # HTML templates for web UI
├── tests/              # pytest tests
├── scripts/            # Build helpers
├── .github/workflows/  # CI/CD
├── Justfile            # Task runner commands
└── pyproject.toml      # Config (ruff, mypy, deps)
```

## Key Dependencies

- `pytest>=8.0` - Testing (dev)
- `ruff>=0.8.0` - Linting and formatting (dev)
- `mypy>=1.13.0` - Type checking (dev)
- `cibuildwheel>=2.16` - Wheel building (dev)
- `fastapi>=0.115` - Web framework (optional)
- `uvicorn[standard]>=0.32` - ASGI server (optional)
- `jinja2>=3.1` - Templating for web UI (optional)
- `httpx>=0.27` - HTTP client for tests (dev)

## CI/CD Pipeline

All CI jobs use **GitHub Actions**:

1. **lint job**: `just check` (lint + format-check + typecheck + test-unit)
2. **test job**: `just test-unit`
3. **build-wheels job**: `cibuildwheel` (Linux, macOS, Windows)
4. **publish jobs**: PyPA publish action

## Tool Management

Tools are managed manually:

- **uv** - Python package manager (install via `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Rust** - Install via rustup (see https://rustup.rs/)
- **just** - Task runner (install via `cargo install just` or package manager)

Update tools: Check upstream for latest versions

## Notes

- **Python 3.12+ required** - Uses modern syntax throughout
- Uses **uv** for Python operations (not pip directly)
- Uses **just** for task running (see Justfile)
- Rust binary must be built before testing: `just build-rust`
- OpenFreeMap Liberty is the default style
- Returns PNG bytes (not PIL Image objects)
- Web test interface available at `just serve-test`

## Architecture

```
Python (mlnative) 
    ↓ JSON over stdin/stdout
Rust (mlnative-render daemon)
    ↓ FFI
MapLibre Native (C++ core)
    ↓
Pre-built amalgam libraries (statically linked ICU, jpeg, etc.)
```

The native renderer uses pre-built "amalgam" libraries from MapLibre Native which include all dependencies (ICU, libjpeg, libpng, etc.) statically linked. This eliminates system dependency issues.

## Rust Development

### Building the Renderer

```bash
cd rust
cargo build --release
```

The binary will be at `target/release/mlnative-render`.

### Cross-Compilation

The CI builds for multiple platforms:
- Linux x64 (x86_64-unknown-linux-gnu)
- Linux ARM64 (aarch64-unknown-linux-gnu)
- macOS x64 (x86_64-apple-darwin)
- macOS ARM64 (aarch64-apple-darwin)
- Windows x64 (x86_64-pc-windows-msvc)

### Communication Protocol

The daemon accepts JSON commands on stdin and outputs JSON responses on stdout.

**Commands:**
- `init` - Initialize with width, height, style
- `render` - Render single view
- `render_batch` - Render multiple views efficiently
- `quit` - Stop daemon

**Responses:**
```json
{"status": "ok", "png": "base64_encoded_data"}
{"status": "error", "error": "message"}
```
