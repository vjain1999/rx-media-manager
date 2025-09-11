#!/usr/bin/env python3
"""
Test script to compare original vs improved Firecrawl search.
"""

import asyncio
import time
from typing import Dict, List, Tuple
from improved_firecrawl_search import enhanced_firecrawl_search_sync
from firecrawl_search import firecrawl_search_restaurant_instagram_sync

# Test cases from golden dataset - focusing on problematic ones
TEST_CASES = [
    {
        "name": "Green House Kitchen",
        "address": "435 Faneuil St, Boston, MA 02135, USA",
        "expected": "Not Available",
        "issue": "Found 'greenhousekitchenldn' (London location for Boston restaurant)"
    },
    {
        "name": "Umai Sushi", 
        "address": "224 Newbury Street, Boston, MA 02116, USA",
        "expected": "Not Available",
        "issue": "Found 'umaihalifax' (Halifax location for Boston restaurant)"
    },
    {
        "name": "Joe's American Bar & Grill",
        "address": "181 Newbury St, Boston, MA 02116, USA", 
        "expected": "joesamerican",
        "issue": "Failed to find expected handle"
    },
    {
        "name": "Rocco's Tavern Express",
        "address": "302 Main St, Oxford, MA 01540, USA",
        "expected": "roccostavern", 
        "issue": "Found 'roccos_tavern' (close but not exact match)"
    },
    {
        "name": "Davio's Northern Italian Steakhouse",
        "address": "75 Arlington St, Boston, MA 02116, USA",
        "expected": "daviosrestaurant",
        "issue": "Should work well (baseline for comparison)"
    }
]

def test_original_firecrawl():
    """Test the original Firecrawl implementation."""
    print("🔥 Testing Original Firecrawl Implementation")
    print("=" * 60)
    
    results = []
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n{i}. Testing: {test_case['name']}")
        print(f"   Expected: {test_case['expected']}")
        print(f"   Issue: {test_case['issue']}")
        
        start_time = time.time()
        try:
            handle, validation_data = firecrawl_search_restaurant_instagram_sync(
                test_case['name'], 
                test_case['address'], 
                ""
            )
            elapsed = time.time() - start_time
            
            result = {
                'test_case': test_case['name'],
                'found_handle': handle,
                'expected': test_case['expected'],
                'time_taken': elapsed,
                'validation_data': validation_data,
                'success': handle == test_case['expected'] if test_case['expected'] != "Not Available" else handle is None
            }
            
            print(f"   ✅ Found: {handle or 'None'}")
            print(f"   ⏱️  Time: {elapsed:.1f}s")
            print(f"   🎯 Match: {'✓' if result['success'] else '✗'}")
            
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
        
        # Rate limiting delay
        time.sleep(2)
    
    return results

def test_enhanced_firecrawl():
    """Test the enhanced Firecrawl implementation."""
    print("\n🚀 Testing Enhanced Firecrawl Implementation")
    print("=" * 60)
    
    results = []
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n{i}. Testing: {test_case['name']}")
        print(f"   Expected: {test_case['expected']}")
        print(f"   Issue: {test_case['issue']}")
        
        start_time = time.time()
        try:
            handle, validation_data = enhanced_firecrawl_search_sync(
                test_case['name'],
                test_case['address'], 
                ""
            )
            elapsed = time.time() - start_time
            
            result = {
                'test_case': test_case['name'],
                'found_handle': handle,
                'expected': test_case['expected'],
                'time_taken': elapsed,
                'validation_data': validation_data,
                'success': handle == test_case['expected'] if test_case['expected'] != "Not Available" else handle is None
            }
            
            print(f"   ✅ Found: {handle or 'None'}")
            print(f"   ⏱️  Time: {elapsed:.1f}s")
            print(f"   🎯 Match: {'✓' if result['success'] else '✗'}")
            
            # Show enhanced validation data
            if validation_data:
                strategies = validation_data.get('strategies_used', [])
                confidence = validation_data.get('confidence_indicators', [])
                if strategies:
                    print(f"   📊 Strategies: {', '.join(strategies)}")
                if confidence:
                    print(f"   🎯 Confidence: {', '.join(confidence)}")
            
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
        
        # Rate limiting delay
        time.sleep(2)
    
    return results

def compare_results(original_results: List[Dict], enhanced_results: List[Dict]):
    """Compare the results from both implementations."""
    print(f"\n📊 COMPARISON RESULTS")
    print("=" * 80)
    
    original_success = sum(1 for r in original_results if r.get('success', False))
    enhanced_success = sum(1 for r in enhanced_results if r.get('success', False))
    
    original_avg_time = sum(r.get('time_taken', 0) for r in original_results) / len(original_results)
    enhanced_avg_time = sum(r.get('time_taken', 0) for r in enhanced_results) / len(enhanced_results)
    
    print(f"📈 Accuracy Comparison:")
    print(f"   Original: {original_success}/{len(original_results)} ({original_success/len(original_results)*100:.1f}%)")
    print(f"   Enhanced: {enhanced_success}/{len(enhanced_results)} ({enhanced_success/len(enhanced_results)*100:.1f}%)")
    print(f"   Improvement: {enhanced_success - original_success} cases")
    
    print(f"\n⏱️  Speed Comparison:")
    print(f"   Original: {original_avg_time:.1f}s average")
    print(f"   Enhanced: {enhanced_avg_time:.1f}s average")
    print(f"   Difference: {enhanced_avg_time - original_avg_time:+.1f}s")
    
    print(f"\n🔍 Case-by-Case Analysis:")
    print(f"{'Restaurant':<30} {'Original':<15} {'Enhanced':<15} {'Improvement'}")
    print("-" * 75)
    
    for orig, enh in zip(original_results, enhanced_results):
        orig_result = orig.get('found_handle') or 'None'
        enh_result = enh.get('found_handle') or 'None'
        
        if orig.get('success') and enh.get('success'):
            improvement = "✓ Both correct"
        elif not orig.get('success') and enh.get('success'):
            improvement = "🎉 Fixed!"
        elif orig.get('success') and not enh.get('success'):
            improvement = "⚠️ Regressed"
        else:
            improvement = "❌ Both failed"
        
        print(f"{orig['test_case']:<30} {orig_result:<15} {enh_result:<15} {improvement}")

def main():
    """Run the comparison test."""
    print("🧪 FIRECRAWL IMPROVEMENTS COMPARISON TEST")
    print("=" * 80)
    print("Testing problematic cases from the golden dataset...")
    print("This will take a few minutes due to API rate limiting.\n")
    
    # Test original implementation
    original_results = test_original_firecrawl()
    
    # Test enhanced implementation  
    enhanced_results = test_enhanced_firecrawl()
    
    # Compare results
    compare_results(original_results, enhanced_results)
    
    print(f"\n✅ Comparison test completed!")
    print(f"📁 Check the console output above for detailed results.")

if __name__ == "__main__":
    main()
