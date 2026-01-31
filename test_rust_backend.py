#!/usr/bin/env python3
"""Test the mlnative library with the new Rust backend."""

import sys
sys.path.insert(0, '/var/home/adonm/dev/mlnative')

from mlnative import Map

def test_single_render():
    """Test single map render."""
    print("Testing single render...")
    
    with Map(256, 256) as m:
        m.load_style("https://tiles.openfreemap.org/styles/liberty")
        png = m.render(center=[115.86, -31.95], zoom=12)
        print(f"✓ Rendered single map: {len(png)} bytes")
        
        # Save to file
        with open('/tmp/test_single.png', 'wb') as f:
            f.write(png)
        print(f"✓ Saved to /tmp/test_single.png")

def test_batch_render():
    """Test batch rendering."""
    print("\nTesting batch render...")
    
    views = [
        {"center": [0, 0], "zoom": 1},
        {"center": [10, 10], "zoom": 5},
        {"center": [-122.4, 37.8], "zoom": 12},
        {"center": [115.86, -31.95], "zoom": 13, "bearing": 45},
    ]
    
    with Map(256, 256) as m:
        m.load_style("https://tiles.openfreemap.org/styles/liberty")
        pngs = m.render_batch(views)
        
        print(f"✓ Batch rendered {len(pngs)} maps")
        for i, png in enumerate(pngs):
            print(f"  Image {i+1}: {len(png)} bytes")
            with open(f'/tmp/test_batch_{i}.png', 'wb') as f:
                f.write(png)
        print(f"✓ Saved batch images to /tmp/test_batch_*.png")

def test_with_options():
    """Test rendering with bearing and pitch."""
    print("\nTesting with bearing and pitch...")
    
    with Map(512, 512) as m:
        m.load_style("https://tiles.openfreemap.org/styles/liberty")
        png = m.render(
            center=[-122.4194, 37.7749],  # San Francisco
            zoom=12,
            bearing=45,
            pitch=30
        )
        print(f"✓ Rendered with options: {len(png)} bytes")
        
        with open('/tmp/test_options.png', 'wb') as f:
            f.write(png)
        print(f"✓ Saved to /tmp/test_options.png")

if __name__ == "__main__":
    print("=" * 60)
    print("mlnative Test Suite")
    print("=" * 60)
    
    try:
        test_single_render()
        test_batch_render()
        test_with_options()
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
