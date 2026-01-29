#!/usr/bin/env bun
/**
 * MapLibre GL Native renderer for mlnative.
 * 
 * Reads JSON config from stdin, renders map, outputs PNG bytes to stdout.
 */

const fs = require('fs');
const path = require('path');

// Get vendor directory from environment
const vendorDir = process.env.MLNATIVE_VENDOR_DIR;
if (!vendorDir) {
    console.error('MLNATIVE_VENDOR_DIR not set');
    process.exit(1);
}

// Load maplibre-gl-native from vendor directory
const mbglPath = path.join(vendorDir, 'node_modules', '@maplibre', 'maplibre-gl-native');
let mbgl;

try {
    mbgl = require(mbglPath);
} catch (e) {
    console.error(`Failed to load maplibre-gl-native from ${mbglPath}: ${e.message}`);
    process.exit(1);
}

// Read config from stdin
let config;
try {
    const stdin = fs.readFileSync(0, 'utf-8');
    config = JSON.parse(stdin);
} catch (e) {
    console.error(`Failed to parse config: ${e.message}`);
    process.exit(1);
}

// Validate required fields
const required = ['width', 'height', 'center', 'zoom'];
for (const field of required) {
    if (!(field in config)) {
        console.error(`Missing required field: ${field}`);
        process.exit(1);
    }
}

// Set up map options
const mapOptions = {
    request: (req, callback) => {
        // Default request handler - fetch from URL
        fetch(req.url)
            .then(res => {
                if (!res.ok) {
                    callback(new Error(`HTTP ${res.status}: ${res.statusText}`));
                    return;
                }
                return res.arrayBuffer();
            })
            .then(buffer => {
                if (buffer) {
                    callback(null, { data: Buffer.from(buffer) });
                }
            })
            .catch(err => {
                callback(err);
            });
    },
    ratio: config.pixelRatio || 1
};

// Handle style
let style = config.style;
if (typeof style === 'string') {
    // URL - will be fetched by request handler
    // Nothing to do
} else if (typeof style === 'object') {
    // Inline style object
    // Already set
}

// Create and configure map
const map = new mbgl.Map(mapOptions);

// Load style
try {
    map.load(style);
} catch (e) {
    console.error(`Failed to load style: ${e.message}`);
    process.exit(1);
}

// Render options
const renderOptions = {
    zoom: config.zoom,
    center: config.center,
    bearing: config.bearing || 0,
    pitch: config.pitch || 0,
    width: config.width,
    height: config.height
};

// Render
map.render(renderOptions, (err, buffer) => {
    if (err) {
        console.error(`Render error: ${err.message}`);
        map.release();
        process.exit(1);
    }
    
    // Output PNG bytes to stdout
    process.stdout.write(buffer);
    map.release();
    process.exit(0);
});
