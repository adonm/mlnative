#!/bin/bash
# Build vendor bundles for mlnative
# 
# Usage:
#   ./scripts/build-vendor.sh          # Build for current platform
#   ./scripts/build-vendor.sh all      # Show info for all platforms (CI builds each separately)

set -e

# Detect current platform
detect_platform() {
    local system arch
    
    case "$(uname -s)" in
        Darwin) system="darwin" ;;
        Linux)  system="linux" ;;
        MINGW*|MSYS*|CYGWIN*) system="win32" ;;
        *)
            echo "Error: Unsupported OS: $(uname -s)"
            exit 1
            ;;
    esac
    
    case "$(uname -m)" in
        arm64|aarch64) arch="arm64" ;;
        x86_64|amd64)  arch="x64" ;;
        *)
            echo "Error: Unsupported architecture: $(uname -m)"
            exit 1
            ;;
    esac
    
    echo "${system}-${arch}"
}

# Build vendor for a specific platform
build_platform() {
    local platform="$1"
    local vendor_dir="mlnative/_vendor/$platform"
    
    echo "Building vendor bundle for $platform..."
    
    mkdir -p "$vendor_dir"
    
    # Create package.json with maplibre-gl-native dependency
    cat > "$vendor_dir/package.json" << 'EOF'
{
  "name": "mlnative-vendor",
  "version": "0.1.0",
  "dependencies": {
    "@maplibre/maplibre-gl-native": "^6.3.0"
  }
}
EOF
    
    # Install dependencies with bun
    echo "Running bun install in $vendor_dir..."
    (cd "$vendor_dir" && bun install)
    
    # Verify installation
    if [ -d "$vendor_dir/node_modules/@maplibre/maplibre-gl-native" ]; then
        echo "✓ Successfully built vendor bundle for $platform"
    else
        echo "✗ Failed to install maplibre-gl-native for $platform"
        exit 1
    fi
}

# Main
if [ "$1" = "all" ]; then
    echo "Supported platforms (build on each target or in CI matrix):"
    echo "  - darwin-arm64  (macOS Apple Silicon)"
    echo "  - darwin-x64    (macOS Intel)"
    echo "  - linux-arm64   (Linux ARM64)"
    echo "  - linux-x64     (Linux x86_64)"
    echo "  - win32-x64     (Windows x64)"
    echo ""
    echo "CI builds each platform via: just ci-build-vendor <platform>"
    echo "Local dev builds current platform via: just build-vendor"
    exit 0
fi

# Build for current platform
platform=$(detect_platform)
build_platform "$platform"

echo ""
echo "Done! Vendor binaries installed for $platform"
echo "You can now run: just test"
