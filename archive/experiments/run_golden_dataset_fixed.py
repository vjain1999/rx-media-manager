#!/usr/bin/env python3
"""
Run the entire golden dataset through the fixed Firecrawl implementation.
Parallelized for speed, with comprehensive analysis and comparison to original results.
"""

import csv
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from fixed_firecrawl_search import fixed_firecrawl_search_sync

def load_golden_dataset() -> List[Dict]:
    """Load the golden dataset from CSV file."""
    dataset_path = Path("golden_dataset.csv")
    if not dataset_path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {dataset_path}")
    
    restaurants = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            restaurants.append({
                'business_id': row.get('BUSINESS_ID', '').strip(),
                'store_id': row.get('STORE_ID', '').strip(),
                'restaurant_name': row.get('RESTAURANT NAME', '').strip(),
                'address': row.get('ADDRESS', '').strip(),
                'expected_handle': row.get('INSTAGRAM HANDLE', '').strip(),
                'reasoning': row.get('REASONING', '').strip()
            })
    
    print(f"📊 Loaded {len(restaurants)} restaurants from golden dataset")
    return restaurants

def process_single_restaurant_fixed(restaurant: Dict, index: int, total: int) -> Dict:
    """Process a single restaurant using the fixed Firecrawl implementation."""
    
    print(f"\n{'='*60}")
    print(f"Processing {index}/{total}: {restaurant['restaurant_name']}")
    print(f"Expected handle: {restaurant['expected_handle']}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # Use fixed Firecrawl implementation
        handle, validation_data = fixed_firecrawl_search_sync(
            restaurant['restaurant_name'],
            restaurant['address'],
            ""  # phone not available in golden dataset
        )
        
        processing_time = time.time() - start_time
        
        # Calculate accuracy
        found_handle = handle.lower() if handle else ""
        expected_handle = restaurant['expected_handle'].lower()
        
        if expected_handle == 'not available':
            # Expected to not find anything
            accuracy = 'correct' if not found_handle else 'false_positive'
        elif expected_handle and found_handle:
            # Both have handles - check if they match
            accuracy = 'correct' if found_handle == expected_handle else 'incorrect'
        elif expected_handle and not found_handle:
            # Expected handle but didn't find it
            accuracy = 'missed'
        elif not expected_handle and found_handle:
            # Found handle but wasn't expected
            accuracy = 'unexpected_find'
        else:
            # Both empty
            accuracy = 'correct'
        
        result = {
            'business_id': restaurant['business_id'],
            'store_id': restaurant['store_id'],
            'restaurant_name': restaurant['restaurant_name'],
            'address': restaurant['address'],
            'phone': '',
            'instagram_handle': handle or '',
            'status': 'ok' if handle else 'not_found',
            'message': '' if handle else 'No handle found',
            'processing_time': processing_time,
            'expected_handle': restaurant['expected_handle'],
            'expected_reasoning': restaurant['reasoning'],
            'accuracy': accuracy,
            'validation_data': validation_data or {},
            'method': 'fixed_firecrawl'
        }
        
        print(f"✅ Found: {handle or 'None'}")
        print(f"📊 Accuracy: {accuracy}")
        print(f"⏱️  Time: {processing_time:.1f}s")
        
        if validation_data:
            queries_used = len(validation_data.get('queries_used', []))
            sources = list(set(validation_data.get('sources_found', [])))
            print(f"📋 Queries: {queries_used}, Sources: {sources}")
        
        return result
        
    except Exception as e:
        processing_time = time.time() - start_time
        print(f"❌ Error processing {restaurant['restaurant_name']}: {e}")
        
        return {
            'business_id': restaurant['business_id'],
            'store_id': restaurant['store_id'],
            'restaurant_name': restaurant['restaurant_name'],
            'address': restaurant['address'],
            'phone': '',
            'instagram_handle': '',
            'status': 'error',
            'message': str(e),
            'processing_time': processing_time,
            'expected_handle': restaurant['expected_handle'],
            'expected_reasoning': restaurant['reasoning'],
            'accuracy': 'error',
            'validation_data': {},
            'method': 'fixed_firecrawl'
        }

def process_golden_dataset_parallel_fixed(restaurants: List[Dict], max_workers: int = 6) -> List[Dict]:
    """Process the golden dataset using fixed Firecrawl with parallel processing."""
    print(f"🚀 Starting parallel processing of {len(restaurants)} restaurants with {max_workers} workers...")
    print(f"🔧 Using Fixed Firecrawl implementation")
    start_time = time.time()
    
    results = []
    completed_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_restaurant = {
            executor.submit(process_single_restaurant_fixed, restaurant, i+1, len(restaurants)): restaurant 
            for i, restaurant in enumerate(restaurants)
        }
        
        # Process completed tasks
        for future in as_completed(future_to_restaurant):
            restaurant = future_to_restaurant[future]
            try:
                result = future.result()
                results.append(result)
                completed_count += 1
                
                print(f"\n🎯 Progress: {completed_count}/{len(restaurants)} completed")
                if completed_count < len(restaurants):
                    remaining_time = ((time.time() - start_time) / completed_count * (len(restaurants) - completed_count))
                    print(f"⏱️  Estimated time remaining: {remaining_time:.1f}s")
                
            except Exception as exc:
                print(f"❌ Error processing {restaurant['restaurant_name']}: {exc}")
                # Create error result
                error_result = {
                    'business_id': restaurant.get('business_id', ''),
                    'store_id': restaurant.get('store_id', ''),
                    'restaurant_name': restaurant.get('restaurant_name', ''),
                    'address': restaurant.get('address', ''),
                    'phone': '',
                    'instagram_handle': '',
                    'status': 'error',
                    'message': str(exc),
                    'processing_time': 0.0,
                    'expected_handle': restaurant.get('expected_handle', ''),
                    'expected_reasoning': restaurant.get('reasoning', ''),
                    'accuracy': 'error',
                    'validation_data': {},
                    'method': 'fixed_firecrawl'
                }
                results.append(error_result)
                completed_count += 1
    
    elapsed_time = time.time() - start_time
    print(f"\n🏁 Fixed Firecrawl processing completed in {elapsed_time:.1f} seconds")
    print(f"⚡ Average time per restaurant: {elapsed_time/len(restaurants):.1f}s")
    
    return results

def load_original_results() -> List[Dict]:
    """Load the original golden dataset results for comparison."""
    original_file = "golden_results_20250902_173325.csv"
    if not Path(original_file).exists():
        print(f"⚠️ Original results file {original_file} not found")
        return []
    
    original_results = []
    with open(original_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            original_results.append({
                'restaurant_name': row.get('restaurant_name', ''),
                'instagram_handle': row.get('instagram_handle', ''),
                'expected_handle': row.get('expected_handle', ''),
                'accuracy': row.get('accuracy', ''),
                'confidence_score': float(row.get('confidence_score', 0)),
                'confidence_grade': row.get('confidence_grade', ''),
                'method': 'original_system'
            })
    
    print(f"📋 Loaded {len(original_results)} original results for comparison")
    return original_results

def analyze_results_comprehensive(fixed_results: List[Dict], original_results: List[Dict]) -> Dict:
    """Comprehensive analysis comparing fixed vs original results."""
    
    total = len(fixed_results)
    
    # Analyze fixed results
    fixed_accuracy_counts = {}
    fixed_time_total = 0
    
    for result in fixed_results:
        accuracy = result.get('accuracy', 'unknown')
        fixed_accuracy_counts[accuracy] = fixed_accuracy_counts.get(accuracy, 0) + 1
        fixed_time_total += result.get('processing_time', 0)
    
    # Analyze original results
    original_accuracy_counts = {}
    for result in original_results:
        accuracy = result.get('accuracy', 'unknown')
        original_accuracy_counts[accuracy] = original_accuracy_counts.get(accuracy, 0) + 1
    
    # Calculate metrics
    fixed_correct = fixed_accuracy_counts.get('correct', 0)
    original_correct = original_accuracy_counts.get('correct', 0)
    
    fixed_accuracy_pct = (fixed_correct / total * 100) if total > 0 else 0
    original_accuracy_pct = (original_correct / len(original_results) * 100) if original_results else 0
    
    fixed_avg_time = fixed_time_total / total if total > 0 else 0
    
    # Case-by-case comparison
    case_comparisons = []
    for fixed_result in fixed_results:
        name = fixed_result['restaurant_name']
        
        # Find matching original result
        original_result = next((r for r in original_results if r['restaurant_name'] == name), None)
        
        comparison = {
            'restaurant_name': name,
            'expected': fixed_result['expected_handle'],
            'fixed_found': fixed_result['instagram_handle'],
            'fixed_accuracy': fixed_result['accuracy'],
            'original_found': original_result['instagram_handle'] if original_result else 'N/A',
            'original_accuracy': original_result['accuracy'] if original_result else 'N/A',
            'improvement': 'unknown'
        }
        
        if original_result:
            fixed_success = fixed_result['accuracy'] == 'correct'
            original_success = original_result['accuracy'] == 'correct'
            
            if fixed_success and original_success:
                comparison['improvement'] = 'both_correct'
            elif fixed_success and not original_success:
                comparison['improvement'] = 'fixed_better'
            elif not fixed_success and original_success:
                comparison['improvement'] = 'original_better'
            else:
                comparison['improvement'] = 'both_failed'
        
        case_comparisons.append(comparison)
    
    analysis = {
        'total_restaurants': total,
        'fixed_results': {
            'accuracy_breakdown': fixed_accuracy_counts,
            'overall_accuracy': f"{fixed_accuracy_pct:.1f}%",
            'correct_count': fixed_correct,
            'average_time': fixed_avg_time
        },
        'original_results': {
            'accuracy_breakdown': original_accuracy_counts,
            'overall_accuracy': f"{original_accuracy_pct:.1f}%",
            'correct_count': original_correct,
            'total_count': len(original_results)
        },
        'comparison': {
            'accuracy_improvement': fixed_accuracy_pct - original_accuracy_pct,
            'cases_improved': len([c for c in case_comparisons if c['improvement'] == 'fixed_better']),
            'cases_regressed': len([c for c in case_comparisons if c['improvement'] == 'original_better']),
            'cases_both_correct': len([c for c in case_comparisons if c['improvement'] == 'both_correct']),
            'case_by_case': case_comparisons
        },
        'processing_timestamp': datetime.now().isoformat()
    }
    
    return analysis

def save_results_comprehensive(results: List[Dict], analysis: Dict):
    """Save comprehensive results and analysis."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save detailed results
    results_file = f"fixed_golden_results_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"💾 Fixed results saved to: {results_file}")
    
    # Save comprehensive analysis
    analysis_file = f"fixed_golden_analysis_{timestamp}.json"
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print(f"📈 Comprehensive analysis saved to: {analysis_file}")
    
    # Save results as CSV
    csv_file = f"fixed_golden_results_{timestamp}.csv"
    if results:
        fieldnames = list(results[0].keys())
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"📊 CSV results saved to: {csv_file}")
    
    return results_file, analysis_file, csv_file

def print_comprehensive_summary(analysis: Dict):
    """Print comprehensive comparison summary."""
    print(f"\n{'='*90}")
    print("📊 COMPREHENSIVE GOLDEN DATASET COMPARISON: FIXED vs ORIGINAL")
    print(f"{'='*90}")
    
    fixed = analysis['fixed_results']
    original = analysis['original_results']
    comparison = analysis['comparison']
    
    print(f"📈 ACCURACY COMPARISON:")
    print(f"   Fixed Firecrawl:    {fixed['correct_count']}/{analysis['total_restaurants']} ({fixed['overall_accuracy']})")
    print(f"   Original System:    {original['correct_count']}/{original['total_count']} ({original['overall_accuracy']})")
    print(f"   Improvement:        {comparison['accuracy_improvement']:+.1f} percentage points")
    
    print(f"\n⏱️  PERFORMANCE:")
    print(f"   Fixed Average Time: {fixed['average_time']:.1f}s per restaurant")
    print(f"   Previous Avg Time:  19.3s per restaurant (from original test)")
    print(f"   Speed Improvement:  {19.3 - fixed['average_time']:.1f}s faster ({(19.3 - fixed['average_time'])/19.3*100:.1f}% improvement)")
    
    print(f"\n🔍 CASE-BY-CASE IMPROVEMENTS:")
    print(f"   Cases Improved:     {comparison['cases_improved']} restaurants")
    print(f"   Cases Regressed:    {comparison['cases_regressed']} restaurants") 
    print(f"   Both Correct:       {comparison['cases_both_correct']} restaurants")
    print(f"   Net Improvement:    {comparison['cases_improved'] - comparison['cases_regressed']} cases")
    
    print(f"\n📋 DETAILED BREAKDOWN:")
    print(f"{'Restaurant':<35} {'Expected':<15} {'Original':<15} {'Fixed':<15} {'Status'}")
    print("-" * 95)
    
    for case in comparison['case_by_case']:
        name = case['restaurant_name'][:34]
        expected = case['expected'][:14] if case['expected'] != 'Not Available' else 'None'
        original = case['original_found'][:14] if case['original_found'] != 'Not Available' else 'None'
        fixed = case['fixed_found'][:14] if case['fixed_found'] else 'None'
        
        if case['improvement'] == 'fixed_better':
            status = "🎉 IMPROVED"
        elif case['improvement'] == 'original_better':
            status = "⚠️  REGRESSED"
        elif case['improvement'] == 'both_correct':
            status = "✅ MAINTAINED"
        else:
            status = "❌ BOTH FAILED"
        
        print(f"{name:<35} {expected:<15} {original:<15} {fixed:<15} {status}")
    
    print(f"\n🎯 KEY INSIGHTS:")
    if comparison['accuracy_improvement'] > 0:
        print(f"   ✅ OVERALL IMPROVEMENT: +{comparison['accuracy_improvement']:.1f}% accuracy")
    else:
        print(f"   ⚠️  Overall change: {comparison['accuracy_improvement']:+.1f}% accuracy")
    
    if comparison['cases_improved'] > comparison['cases_regressed']:
        print(f"   ✅ NET POSITIVE: {comparison['cases_improved'] - comparison['cases_regressed']} more cases improved than regressed")
    elif comparison['cases_improved'] < comparison['cases_regressed']:
        print(f"   ⚠️  NET NEGATIVE: {comparison['cases_regressed'] - comparison['cases_improved']} more cases regressed than improved")
    else:
        print(f"   ➖ NET NEUTRAL: Equal improvements and regressions")
    
    print(f"\n⏰ Processing completed at: {analysis['processing_timestamp']}")
    print(f"{'='*90}")

def main():
    """Main function to run the comprehensive golden dataset analysis."""
    print("🔧 FIXED FIRECRAWL: COMPLETE GOLDEN DATASET ANALYSIS")
    print("=" * 70)
    
    try:
        # Load the dataset
        restaurants = load_golden_dataset()
        
        # Load original results for comparison
        original_results = load_original_results()
        
        # Process the restaurants with fixed implementation
        results = process_golden_dataset_parallel_fixed(restaurants, max_workers=6)
        
        # Comprehensive analysis
        analysis = analyze_results_comprehensive(results, original_results)
        
        # Save results
        results_file, analysis_file, csv_file = save_results_comprehensive(results, analysis)
        
        # Print comprehensive summary
        print_comprehensive_summary(analysis)
        
        # Print file locations
        print(f"\n📁 Output Files:")
        print(f"  • Detailed results: {results_file}")
        print(f"  • Comprehensive analysis: {analysis_file}")
        print(f"  • CSV export: {csv_file}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
