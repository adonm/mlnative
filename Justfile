# Justfile - Convenient commands for mlnative development
# Works with uv and cargo

# Default recipe - show help
_default:
    @just --list

# Setup development environment (installs deps)
setup:
    uv venv
    uv pip install -e ".[dev,web]"

# CI-friendly setup (assumes tools are pre-installed)
ci-setup:
    uv pip install -e ".[dev]"

# Build Rust native binary
build-rust:
    cd rust && cargo build --release

# Run all tests
test:
    uv run python -m pytest tests/ -v --tb=short

# Run specific test
test-single TEST:
    uv run python -m pytest {{TEST}} -v

# Run tests matching pattern
test-filter PATTERN:
    uv run python -m pytest tests/ -v -k "{{PATTERN}}"

# Run only unit tests (skip integration)
test-unit:
    uv run python -m pytest tests/ -v -k "Validation" --tb=short

# Run linting
lint:
    uv run ruff check mlnative/ tests/ examples/

# Run linting with auto-fix
lint-fix:
    uv run ruff check mlnative/ tests/ examples/ --fix

# Format code
format:
    uv run ruff format mlnative/ tests/ examples/

# Check formatting (CI)
format-check:
    uv run ruff format mlnative/ tests/ examples/ --check

# Run type checking
typecheck:
    uv run mypy mlnative/

# Run all quality checks (CI)
check: lint format-check typecheck test-unit

# Build package
build:
    uv build

# Build wheels for all platforms (requires Docker)
build-wheels:
    uv run cibuildwheel --platform linux

# Clean build artifacts
clean:
    rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache .ruff_cache wheelhouse
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete
    cd rust && cargo clean 2>/dev/null || true

# Run FastAPI example server
serve:
    uv run python examples/fastapi_server.py

# Run web test interface
serve-test:
    uv run python examples/web_test_server.py

# Run basic example
example:
    uv run python examples/basic.py

# Show code statistics
stats:
    scc --by-file --exclude-dir=.venv,__pycache__,bin,target

# Run tests in container (for systems with incompatible libraries)
test-docker:
    docker build -f Dockerfile.test -t mlnative-test .
    docker run --rm mlnative-test
