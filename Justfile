# Justfile - Convenient commands for mlnative development
# Works locally with mise and in CI with GitHub Actions

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

# Run all tests
test:
    uv run python -m pytest tests/ -v --tb=short

# Run specific test
test-single TEST:
    uv run python -m pytest {{TEST}} -v

# Run tests matching pattern
test-filter PATTERN:
    uv run python -m pytest tests/ -v -k "{{PATTERN}}"

# Run only unit tests (skip integration tests that need vendor binaries)
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

# Build package for CI (with vendor artifacts already in place)
ci-build:
    ls -la mlnative/_vendor/
    uv build

# Clean build artifacts
clean:
    rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete

# Run FastAPI example server (builds vendor first)
serve: build-vendor
    uv run python examples/fastapi_server.py

# Run web test interface (builds vendor first)
serve-test: build-vendor
    uv run python examples/web_test_server.py

# Run basic example
example:
    uv run python examples/basic.py

# Build vendor binaries for current platform
build-vendor:
    ./scripts/build-vendor.sh

# Build vendor for specific platform (CI)
ci-build-vendor PLATFORM:
    #!/usr/bin/env bash
    set -e
    mkdir -p mlnative/_vendor/{{PLATFORM}}
    cd mlnative/_vendor/{{PLATFORM}}
    
    # Create package.json
    cat > package.json << 'EOF'
    {
      "name": "mlnative-vendor",
      "version": "0.1.0",
      "dependencies": {
        "@maplibre/maplibre-gl-native": "^6.3.0"
      }
    }
    EOF
    
    # Install dependencies with bun
    bun install

# Show code statistics
stats:
    scc --by-file --exclude-dir=.venv,__pycache__,_vendor

# Run tests in container (for systems with incompatible libraries)
test-docker:
    docker build -f Dockerfile.test -t mlnative-test .
    docker run --rm mlnative-test

# Install all tools via mise (local dev)
install-tools:
    mise install

# Update all tools
update-tools:
    mise upgrade
