#!/usr/bin/env python3
"""
Comprehensive test of fixed Firecrawl on all problematic golden dataset cases.
"""

import time
from fixed_firecrawl_search import fixed_firecrawl_search_sync

# All problematic cases from golden dataset
TEST_CASES = [
    {
        "name": "Green House Kitchen",
        "address": "435 Faneuil St, Boston, MA 02135, USA",
        "expected": "Not Available",
        "issue": "Original found 'greenhousekitchenldn' (London location for Boston restaurant)"
    },
    {
        "name": "Umai Sushi", 
        "address": "224 Newbury Street, Boston, MA 02116, USA",
        "expected": "Not Available",
        "issue": "Original found 'umaihalifax' (Halifax location for Boston restaurant)"
    },
    {
        "name": "Joe's American Bar & Grill",
        "address": "181 Newbury St, Boston, MA 02116, USA", 
        "expected": "joesamerican",
        "issue": "Enhanced failed to find expected handle"
    },
    {
        "name": "Rocco's Tavern Express",
        "address": "302 Main St, Oxford, MA 01540, USA",
        "expected": "roccostavern", 
        "issue": "Original found 'roccos_tavern' (close but not exact match)"
    },
    {
        "name": "Davio's Northern Italian Steakhouse",
        "address": "75 Arlington St, Boston, MA 02116, USA",
        "expected": "daviosrestaurant",
        "issue": "Should work well (baseline for comparison)"
    },
    {
        "name": "Anna's Taqueria (MGH)",
        "address": "242 Cambridge St, Boston, MA 02114, USA",
        "expected": "annastaqueria",
        "issue": "Original found 'annasboston' (corporate vs specific handle)"
    }
]

def test_fixed_comprehensive():
    """Test fixed approach on all problematic cases."""
    print("🔧 Comprehensive Test: Fixed Firecrawl on Golden Dataset Issues")
    print("=" * 70)
    
    results = []
    total_time = 0
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n{i}. Testing: {test_case['name']}")
        print(f"   Expected: {test_case['expected']}")
        print(f"   Issue: {test_case['issue']}")
        
        start_time = time.time()
        try:
            handle, validation_data = fixed_firecrawl_search_sync(
                test_case['name'],
                test_case['address'], 
                ""
            )
            elapsed = time.time() - start_time
            total_time += elapsed
            
            # Determine success
            if test_case['expected'] == "Not Available":
                success = handle is None
                status = "✅ Correctly found nothing" if success else f"❌ False positive: {handle}"
            else:
                success = handle == test_case['expected']
                status = "✅ Perfect match" if success else f"❌ Found: {handle or 'None'}"
            
            result = {
                'test_case': test_case['name'],
                'found_handle': handle,
                'expected': test_case['expected'],
                'time_taken': elapsed,
                'success': success,
                'validation_data': validation_data
            }
            
            print(f"   Result: {handle or 'None'}")
            print(f"   Status: {status}")
            print(f"   Time: {elapsed:.1f}s")
            
            if validation_data:
                queries_used = len(validation_data.get('queries_used', []))
                sources = validation_data.get('sources_found', [])
                print(f"   Queries: {queries_used}, Sources: {list(set(sources))}")
            
            results.append(result)
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append({
                'test_case': test_case['name'],
                'found_handle': None,
                'expected': test_case['expected'],
                'time_taken': time.time() - start_time,
                'error': str(e),
                'success': False
            })
            total_time += time.time() - start_time
        
        # Rate limiting delay
        if i < len(TEST_CASES):
            time.sleep(2)
    
    # Summary
    print(f"\n{'='*70}")
    print("📊 FIXED FIRECRAWL COMPREHENSIVE RESULTS")
    print(f"{'='*70}")
    
    successful = sum(1 for r in results if r.get('success', False))
    total = len(results)
    avg_time = total_time / total if total > 0 else 0
    
    print(f"Overall Performance:")
    print(f"  ✅ Success Rate: {successful}/{total} ({successful/total*100:.1f}%)")
    print(f"  ⏱️  Average Time: {avg_time:.1f}s per restaurant")
    print(f"  🏃 Total Time: {total_time:.1f}s")
    
    print(f"\nDetailed Results:")
    print(f"{'Restaurant':<35} {'Expected':<15} {'Found':<15} {'Status'}")
    print("-" * 80)
    
    for result in results:
        name = result['test_case'][:34]
        expected = result['expected'][:14] if result['expected'] != "Not Available" else "None"
        found = (result['found_handle'] or 'None')[:14]
        status = "✅" if result.get('success') else "❌"
        
        print(f"{name:<35} {expected:<15} {found:<15} {status}")
    
    print(f"\n🎯 Key Improvements vs Enhanced Version:")
    print(f"  • Enhanced Accuracy: 2/5 (40%) → Fixed: {successful}/{total} ({successful/total*100:.1f}%)")
    print(f"  • Maintained Speed: ~13s → {avg_time:.1f}s average")
    print(f"  • Better Extraction: Simple prompt works vs complex prompt failed")
    
    return results

if __name__ == "__main__":
    test_fixed_comprehensive()
