#!/usr/bin/env python3
"""
Quick test of the fixed Firecrawl approach.
"""

import time
from fixed_firecrawl_search import fixed_firecrawl_search_sync
from firecrawl_search import firecrawl_search_restaurant_instagram_sync

# Test one case that should work
TEST_CASE = {
    "name": "Davio's Northern Italian Steakhouse",
    "address": "75 Arlington St, Boston, MA 02116, USA",
    "expected": "daviosrestaurant"
}

def test_fixed_vs_original():
    """Test fixed approach vs original."""
    print("🧪 Testing Fixed Firecrawl vs Original")
    print("=" * 50)
    
    print(f"Restaurant: {TEST_CASE['name']}")
    print(f"Expected: {TEST_CASE['expected']}")
    
    # Test original
    print(f"\n🔥 Original Firecrawl:")
    start = time.time()
    try:
        orig_handle, orig_data = firecrawl_search_restaurant_instagram_sync(
            TEST_CASE['name'], TEST_CASE['address'], ""
        )
        orig_time = time.time() - start
        print(f"   Result: {orig_handle}")
        print(f"   Time: {orig_time:.1f}s")
        print(f"   Match: {'✓' if orig_handle == TEST_CASE['expected'] else '✗'}")
    except Exception as e:
        print(f"   Error: {e}")
        orig_handle, orig_time = None, time.time() - start
    
    # Test fixed
    print(f"\n🔧 Fixed Firecrawl:")
    start = time.time()
    try:
        fixed_handle, fixed_data = fixed_firecrawl_search_sync(
            TEST_CASE['name'], TEST_CASE['address'], ""
        )
        fixed_time = time.time() - start
        print(f"   Result: {fixed_handle}")
        print(f"   Time: {fixed_time:.1f}s")
        print(f"   Match: {'✓' if fixed_handle == TEST_CASE['expected'] else '✗'}")
        
        if fixed_data:
            print(f"   Queries used: {len(fixed_data.get('queries_used', []))}")
            print(f"   Sources: {fixed_data.get('sources_found', [])}")
            
    except Exception as e:
        print(f"   Error: {e}")
        fixed_handle, fixed_time = None, time.time() - start
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"   Original: {orig_handle} ({orig_time:.1f}s)")
    print(f"   Fixed: {fixed_handle} ({fixed_time:.1f}s)")
    
    if orig_handle == TEST_CASE['expected'] and fixed_handle == TEST_CASE['expected']:
        print("   ✅ Both found correct handle!")
    elif fixed_handle == TEST_CASE['expected']:
        print("   🎉 Fixed version found it!")
    elif orig_handle == TEST_CASE['expected']:
        print("   ⚠️ Only original found it")
    else:
        print("   ❌ Neither found the correct handle")

if __name__ == "__main__":
    test_fixed_vs_original()
