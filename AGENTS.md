# AGENTS.md - Guidelines for AI Coding Agents

## Prerequisites

This project uses **mise** for tool management. Install it first:
- macOS/Linux: `curl https://mise.run | sh`
- Or see: https://mise.jdx.dev/getting-started.html

**Requirements:** Python 3.12+

## Build/Test/Lint Commands

### Using Just (recommended)

```bash
# Install all tools (uv, just, bun) via mise
just install-tools

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
just clean

# Run examples
just serve       # FastAPI static maps API
just serve-test  # Interactive web test interface
just example     # Basic usage example

# Show code stats
just stats
```

### Interactive Web Test Interface

The web test interface provides a visual way to test the library:

```bash
just serve-test
```

Then open http://localhost:8000 to:
- Build API calls with an interactive form
- Set parameters (center, zoom, dimensions, style)
- Enable 2x/HighDPI mode for retina displays
- See the generated Python code
- Preview generated map images in real-time

### Using mise + just directly

```bash
# Run any just command through mise
mise exec -- just check

# Or activate mise in your shell
mise activate
just check
```

### Legacy: Using uv directly (no mise)

```bash
# Setup
cd /var/home/adonm/dev/maplibre-native/mlnative
uv venv
uv pip install -e ".[dev,web]"

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
- Private modules: `_bridge.py`, `_renderer.js`
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
- Skip tests gracefully when deps unavailable
- Run `just test-unit` for quick feedback (skips vendor binary tests)

## Project Structure

```
mlnative/
├── mlnative/           # Main package
│   ├── __init__.py     # Public exports
│   ├── map.py          # Main Map class
│   ├── _bridge.py      # Bun subprocess wrapper
│   ├── _renderer.js    # JS renderer
│   ├── exceptions.py   # MlnativeError
│   └── _vendor/        # Platform binaries
├── examples/           # Usage examples
│   ├── basic.py        # Simple example
│   ├── fastapi_server.py       # Static maps API
│   ├── web_test_server.py      # Interactive test UI
│   └── templates/      # HTML templates for web UI
├── tests/              # pytest tests
├── scripts/            # Build helpers
├── .github/workflows/  # CI/CD
├── Justfile            # Task runner commands
├── mise.toml           # Tool management (uv, just, bun)
└── pyproject.toml      # Config (ruff, mypy, deps)
```

## Key Dependencies

- `pybun>=1.3` - Bun runtime
- `pytest>=8.0` - Testing (dev)
- `ruff>=0.8.0` - Linting and formatting (dev)
- `mypy>=1.13.0` - Type checking (dev)
- `fastapi>=0.115` - Web framework (optional)
- `uvicorn[standard]>=0.32` - ASGI server (optional)
- `jinja2>=3.1` - Templating for web UI (optional)
- `httpx>=0.27` - HTTP client for tests (dev)

## CI/CD Pipeline

All CI jobs use **mise** for tool management and **just** for commands:

1. **lint job**: `just check` (lint + format-check + typecheck + test-unit)
2. **test job**: `just test-unit`
3. **build-vendor job**: `just ci-build-vendor <platform>`
4. **build-package job**: `just ci-build`
5. **publish jobs**: PyPA publish action

## Tool Management

Tools are managed via **mise** (see `mise.toml`):

```toml
[tools]
uv = "latest"     # Python package manager
just = "latest"   # Task runner
bun = "latest"    # JavaScript runtime
```

Update tools: `just update-tools`

## Notes

- **Python 3.12+ required** - Uses modern syntax throughout
- Uses **mise** for tool management (installs uv, just, bun)
- Uses **just** for task running (see Justfile)
- Uses **uv** for Python operations (not pip directly)
- Vendor binaries must be built per-platform (see `just build-vendor`)
- OpenFreeMap Liberty is the default style
- Returns PNG bytes (not PIL Image objects)
- Web test interface available at `just serve-test`

## System Library Compatibility

The native maplibre-gl-native binary requires specific system library versions:
- libjpeg.so.8
- ICU 74 (libicuuc.so.74, libicudata.so.74, libicui18n.so.74)

If your system has different versions (e.g., libjpeg-turbo, ICU 77+), integration tests will be automatically skipped. To run full tests:

1. **Use Docker**: `just test-docker` (recommended)
2. **Build from source**: Compile maplibre-gl-native against your system's libraries
3. **Install compatible libraries**: May conflict with system packages

Unit tests (validation, error handling) will always run regardless of system libraries.
