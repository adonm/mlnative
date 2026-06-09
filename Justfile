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
    uv venv
    uv pip install -e ".[dev]"

# Build Rust native binary
build-rust:
    cd rust && cargo build --release --locked

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
    uv run python -m pytest tests/ -v -m "not integration" --tb=short

# Run linting
lint:
    uv run ruff check mlnative/ tests/ examples/ scripts/

# Run linting with auto-fix
lint-fix:
    uv run ruff check mlnative/ tests/ examples/ scripts/ --fix

# Format code
format:
    uv run ruff format mlnative/ tests/ examples/ scripts/

# Check formatting (CI)
format-check:
    uv run ruff format mlnative/ tests/ examples/ scripts/ --check

# Run type checking
typecheck:
    uv run mypy mlnative/

# Check packaged runtime wiring without starting renderer
doctor:
    uv run python -m mlnative doctor

# Smoke-check native renderer with a local empty style
smoke:
    uv run python -m mlnative doctor --render

# Run all quality checks (CI)
check: lint format-check typecheck test-unit

# Build package
build:
    uv build

# Build the local manylinux image used by cibuildwheel
build-cibw-image:
    #!/usr/bin/env bash
    set -euo pipefail
    case "$(uname -m)" in
        x86_64) base_image="quay.io/pypa/manylinux_2_28_x86_64" ;;
        aarch64|arm64) base_image="quay.io/pypa/manylinux_2_28_aarch64" ;;
        *) echo "Unsupported cibuildwheel host architecture: $(uname -m)" >&2; exit 1 ;;
    esac
    docker build \
        --build-arg BASE_IMAGE="${base_image}" \
        -t mlnative-manylinux:latest \
        -f docker/cibuildwheel-manylinux.Dockerfile .

# Build wheels for all platforms (requires Docker)
build-wheels: build-cibw-image
    uv run cibuildwheel --platform linux --output-dir wheelhouse

# Clean build artifacts
clean:
    rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache .ruff_cache wheelhouse
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete
    cd rust && cargo clean 2>/dev/null || true

# CI: Build binary for current platform
# Usage: just ci-build-binary <platform>
# Platform format: linux-x64, darwin-arm64, win32-x64, etc.
ci-build-binary PLATFORM:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Building binary for {{PLATFORM}}..."
    cd rust && cargo build --release --locked
    mkdir -p ../mlnative/bin
    if [[ "{{PLATFORM}}" == win32-* ]]; then
        cp target/release/mlnative-render.exe ../mlnative/bin/mlnative-render-{{PLATFORM}}.exe
    else
        cp target/release/mlnative-render ../mlnative/bin/mlnative-render-{{PLATFORM}}
        chmod +x ../mlnative/bin/mlnative-render-{{PLATFORM}}
    fi
    echo "✓ Binary built: mlnative/bin/mlnative-render-{{PLATFORM}}"

# CI: Build platform wheels with cibuildwheel
ci-build-wheels: build-cibw-image
    uv run cibuildwheel --platform linux --output-dir dist

# CI: Build source distribution
ci-build-sdist:
    uv pip install build
    uv run python -m build --sdist

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

# Generate visual comparison renders (mlnative vs Chrome)
visual-render:
    #!/usr/bin/env bash
    set -e
    if ! uv run python -c "import playwright" 2>/dev/null; then
        echo "Installing playwright..."
        uv pip install playwright
    fi
    if ! uv run python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.chromium.executable_path; p.stop()" 2>/dev/null; then
        echo "Installing chromium browser..."
        uv run playwright install chromium
    fi
    uv run python scripts/visual_compare.py

# Compare renders using AI (requires opencode with kimi model)
visual-compare:
    @echo "Comparing renders with AI..."
    @echo ""
    @echo "Simple map:"
    opencode run -m kimi-for-coding/k2p5 "Compare test-output/simple-mlnative.png with test-output/simple-chrome.png. What rendering differences exist? Focus on layout, colors, and text."
    @echo ""
    @echo "Zoomed out map:"
    opencode run -m kimi-for-coding/k2p5 "Compare test-output/zoomed-out-mlnative.png with test-output/zoomed-out-chrome.png. What rendering differences exist?"
    @echo ""
    @echo "With bearing:"
    opencode run -m kimi-for-coding/k2p5 "Compare test-output/with-bearing-mlnative.png with test-output/with-bearing-chrome.png. What rendering differences exist?"

# Full visual test: render + compare
visual-test: visual-render visual-compare
