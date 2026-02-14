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

# CI: Build binary for current platform
# Usage: just ci-build-binary <platform>
# Platform format: linux-x64, darwin-arm64, win32-x64, etc.
ci-build-binary PLATFORM:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Building binary for {{PLATFORM}}..."
    cd rust && cargo build --release
    mkdir -p ../mlnative/bin
    if [[ "{{PLATFORM}}" == win32-* ]]; then
        cp target/release/mlnative-render.exe ../mlnative/bin/mlnative-render-{{PLATFORM}}.exe
    else
        cp target/release/mlnative-render ../mlnative/bin/mlnative-render-{{PLATFORM}}
        chmod +x ../mlnative/bin/mlnative-render-{{PLATFORM}}
    fi
    echo "✓ Binary built: mlnative/bin/mlnative-render-{{PLATFORM}}"

# CI: Build platform wheel with binary
# Usage: just ci-build-wheel <platform>
ci-build-wheel PLATFORM:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Building wheel for {{PLATFORM}}..."
    uv pip install build
    uv run python -m build --wheel
    # Rename wheel with correct platform tag
    python3 << EOF
    import os
    import glob
    
    platform_map = {
        "linux-x64": "manylinux_2_28_x86_64",
        "linux-arm64": "manylinux_2_28_aarch64",
        "darwin-x64": "macosx_10_12_x86_64",
        "darwin-arm64": "macosx_11_0_arm64",
        "win32-x64": "win_amd64"
    }
    tag = platform_map.get("{{PLATFORM}}", "any")
    
    for wheel in glob.glob("dist/*.whl"):
        new_name = wheel.replace("-any.whl", f"-{tag}.whl")
        os.rename(wheel, new_name)
        print(f"Created: {new_name}")
    EOF

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
