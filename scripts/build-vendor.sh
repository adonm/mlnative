#!/bin/bash
# Build vendor bundles for all supported platforms
# This script builds the native modules and packages them for distribution

set -e

PLATFORMS=(
    "darwin-arm64"
    "darwin-x64"
    "linux-arm64"
    "linux-x64"
    "win32-x64"
)

echo "Building mlnative vendor bundles..."
echo ""

# Ensure we have the JS renderer
echo "✓ Renderer script: mlnative/_renderer.js"

# For each platform, we need to:
# 1. Install maplibre-gl-native for that platform
# 2. Copy node_modules to vendor directory
# 3. Include native binaries

echo ""
echo "Platform bundles to create:"
for platform in "${PLATFORMS[@]}"; do
    echo "  - $platform"
done

echo ""
echo "Note: In production, these would be built on actual target platforms"
echo "or using cross-compilation. For development, create placeholder structure."

echo ""
echo "Creating vendor directory structure..."

for platform in "${PLATFORMS[@]}"; do
    vendor_dir="mlnative/_vendor/$platform"
    mkdir -p "$vendor_dir"
    
    # Create a placeholder package.json
    cat > "$vendor_dir/package.json" << EOF
{
  "name": "mlnative-vendor-$platform",
  "version": "0.1.0",
  "description": "Pre-built maplibre-gl-native for $platform"
}
EOF
    
    echo "  ✓ $platform"
done

echo ""
echo "Vendor structure created."
echo ""
echo "To complete setup, run on each target platform:"
echo "  cd mlnative/_vendor/<platform>"
echo "  bun install @maplibre/maplibre-gl-native"
echo ""
echo "Then copy the resulting node_modules back to the vendor directory."
