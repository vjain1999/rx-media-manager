#!/usr/bin/env python3
"""
Run the complete Instagram handle discovery system on the golden dataset.
This uses the full pipeline with all search strategies (not just Firecrawl).
Provides comprehensive metrics including false positives, false negatives, precision, recall.
"""

import csv
import argparse
import random
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from web_search import RestaurantInstagramFinder

def load_golden_dataset(csv_path: Union[str, Path] = "data/golden_dataset.csv") -> List[Dict]:
    """Load the golden dataset from CSV file (default: data/golden_dataset.csv)."""
    dataset_path = Path(csv_path)
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
                'reasoning': (row.get('REASONING') or '').strip()
            })
    
    print(f"📊 Loaded {len(restaurants)} restaurants from golden dataset")
    return restaurants

def process_single_restaurant_full_system(restaurant: Dict, index: int, total: int) -> Dict:
    """Process a single restaurant using the complete Instagram discovery system."""
    
    print(f"\n{'='*70}")
    print(f"Processing {index}/{total}: {restaurant['restaurant_name']}")
    print(f"Expected handle: {restaurant['expected_handle']}")
    print(f"Address: {restaurant['address']}")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        # Use the complete RestaurantInstagramFinder system
        finder = RestaurantInstagramFinder()
        
        # Process using the full pipeline with all strategies
        result = finder._process_single_row({
            'business_id': restaurant['business_id'],
            'store_id': restaurant['store_id'],
            'restaurant_name': restaurant['restaurant_name'],
            'address': restaurant['address'],
            'phone': ''  # Not available in golden dataset
        })
        
        processing_time = time.time() - start_time
        
        # Add expected data for comparison
        result['expected_handle'] = restaurant['expected_handle']
        result['expected_reasoning'] = restaurant['reasoning']
        result['processing_time'] = processing_time
        
        # Calculate detailed accuracy metrics
        found_handle = result.get('instagram_handle', '').lower() if result.get('instagram_handle') else ""
        expected_handle = restaurant['expected_handle'].lower()
        
        # Determine ground truth and prediction
        ground_truth_positive = expected_handle and expected_handle != 'not available'
        prediction_positive = bool(found_handle)
        
        if ground_truth_positive and prediction_positive:
            # Both expect and found a handle - check if correct
            if found_handle == expected_handle:
                accuracy = 'true_positive'  # Correctly found the right handle
            else:
                accuracy = 'false_positive'  # Found wrong handle
        elif ground_truth_positive and not prediction_positive:
            accuracy = 'false_negative'  # Should have found handle but didn't
        elif not ground_truth_positive and prediction_positive:
            accuracy = 'false_positive'  # Found handle when shouldn't have
        else:
            accuracy = 'true_negative'  # Correctly found no handle
        
        # Legacy accuracy for comparison
        if expected_handle == 'not available':
            legacy_accuracy = 'correct' if not found_handle else 'false_positive'
        elif expected_handle and found_handle:
            legacy_accuracy = 'correct' if found_handle == expected_handle else 'incorrect'
        elif expected_handle and not found_handle:
            legacy_accuracy = 'missed'
        elif not expected_handle and found_handle:
            legacy_accuracy = 'unexpected_find'
        else:
            legacy_accuracy = 'correct'
        
        result['accuracy'] = accuracy
        result['legacy_accuracy'] = legacy_accuracy
        result['ground_truth_positive'] = ground_truth_positive
        result['prediction_positive'] = prediction_positive
        
        print(f"✅ Found: {result.get('instagram_handle') or 'None'}")
        print(f"📊 Accuracy: {accuracy}")
        print(f"📋 Legacy: {legacy_accuracy}")
        print(f"🎯 Confidence: {result.get('confidence_grade', 'Unknown')} ({result.get('confidence_score', 0):.2f})")
        print(f"⏱️  Time: {processing_time:.1f}s")
        
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
            'legacy_accuracy': 'error',
            'ground_truth_positive': False,
            'prediction_positive': False,
            'confidence_score': 0.0,
            'confidence_grade': 'Error'
        }

def process_golden_dataset_full_system(restaurants: List[Dict], max_workers: int = 4, starts_per_sec: float = 0.0, shuffle: bool = False) -> List[Dict]:
    """Process the golden dataset using the complete system with parallel processing."""
    print(f"🚀 Starting full system processing of {len(restaurants)} restaurants with {max_workers} workers...")
    if shuffle:
        print("🔀 Shuffling input order to spread out brand bursts and domains")
        random.shuffle(restaurants)
    print(f"🔧 Using Complete Instagram Discovery Pipeline (All Strategies)")
    start_time = time.time()
    
    results = []
    completed_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks with optional start-rate throttling to avoid API burst limits
        future_to_restaurant = {}
        last_start_ts = 0.0
        min_interval = (1.0 / starts_per_sec) if starts_per_sec and starts_per_sec > 0 else 0.0
        total = len(restaurants)
        for i, restaurant in enumerate(restaurants):
            if min_interval > 0:
                now = time.time()
                elapsed = now - last_start_ts
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                last_start_ts = time.time()
            fut = executor.submit(process_single_restaurant_full_system, restaurant, i+1, total)
            future_to_restaurant[fut] = restaurant
        
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
                    'legacy_accuracy': 'error',
                    'ground_truth_positive': False,
                    'prediction_positive': False,
                    'confidence_score': 0.0,
                    'confidence_grade': 'Error'
                }
                results.append(error_result)
                completed_count += 1
    
    elapsed_time = time.time() - start_time
    print(f"\n🏁 Full system processing completed in {elapsed_time:.1f} seconds")
    print(f"⚡ Average time per restaurant: {elapsed_time/len(restaurants):.1f}s")
    
    return results

def add_review_flags(results: List[Dict]) -> List[Dict]:
    """Add a 'review' flag when the same business_id has conflicting found handles across stores.

    Rule: If within a given business_id there exist >1 distinct, non-empty instagram_handle values
    found by the system, mark all rows with that business_id as 'FLAG' in a new 'review' column.
    Else, set 'review' to an empty string.
    """
    # Normalize handles and group by business_id
    business_id_to_handles: Dict[str, set] = {}
    for r in results:
        business_id = (r.get('business_id') or '').strip()
        handle = (r.get('instagram_handle') or '').strip().lower()
        if business_id:
            if business_id not in business_id_to_handles:
                business_id_to_handles[business_id] = set()
            if handle:
                business_id_to_handles[business_id].add(handle)

    # Determine which business_ids are conflicting
    conflicting_business_ids = {bid for bid, handles in business_id_to_handles.items() if len(handles) > 1}

    # Annotate results with 'review'
    for r in results:
        bid = (r.get('business_id') or '').strip()
        r['review'] = 'FLAG' if bid in conflicting_business_ids else ''

    return results

def calculate_comprehensive_metrics(results: List[Dict]) -> Dict:
    """Calculate comprehensive metrics including precision, recall, F1, etc."""
    
    # Count different types of results
    true_positives = len([r for r in results if r['accuracy'] == 'true_positive'])
    false_positives = len([r for r in results if r['accuracy'] == 'false_positive'])
    false_negatives = len([r for r in results if r['accuracy'] == 'false_negative'])
    true_negatives = len([r for r in results if r['accuracy'] == 'true_negative'])
    errors = len([r for r in results if r['accuracy'] == 'error'])
    
    total = len(results)
    
    # Calculate standard metrics
    accuracy = (true_positives + true_negatives) / total if total > 0 else 0
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # Calculate rates
    false_positive_rate = false_positives / (false_positives + true_negatives) if (false_positives + true_negatives) > 0 else 0
    false_negative_rate = false_negatives / (false_negatives + true_positives) if (false_negatives + true_positives) > 0 else 0
    
    # Legacy accuracy for comparison
    legacy_correct = len([r for r in results if r['legacy_accuracy'] == 'correct'])
    legacy_accuracy = legacy_correct / total if total > 0 else 0
    
    # Confidence analysis
    confidence_distribution = {'High': 0, 'Medium': 0, 'Low': 0, 'Error': 0, 'Unknown': 0}
    for result in results:
        conf_grade = result.get('confidence_grade', 'Unknown')
        confidence_distribution[conf_grade] = confidence_distribution.get(conf_grade, 0) + 1
    
    # Performance analysis
    processing_times = [r.get('processing_time', 0) for r in results if r.get('processing_time', 0) > 0]
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    
    return {
        'total_restaurants': total,
        'confusion_matrix': {
            'true_positives': true_positives,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'true_negatives': true_negatives,
            'errors': errors
        },
        'classification_metrics': {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score,
            'false_positive_rate': false_positive_rate,
            'false_negative_rate': false_negative_rate
        },
        'legacy_metrics': {
            'legacy_accuracy': legacy_accuracy,
            'legacy_correct_count': legacy_correct
        },
        'confidence_distribution': confidence_distribution,
        'performance': {
            'average_processing_time': avg_processing_time,
            'total_processing_time': sum(processing_times)
        },
        'detailed_breakdown': {
            'should_find_handle': len([r for r in results if r['ground_truth_positive']]),
            'should_not_find_handle': len([r for r in results if not r['ground_truth_positive']]),
            'system_found_handle': len([r for r in results if r['prediction_positive']]),
            'system_found_nothing': len([r for r in results if not r['prediction_positive']])
        }
    }

def analyze_error_cases(results: List[Dict]) -> Dict:
    """Analyze specific error cases in detail."""
    
    false_positives = [r for r in results if r['accuracy'] == 'false_positive']
    false_negatives = [r for r in results if r['accuracy'] == 'false_negative']
    
    # Analyze false positives
    fp_analysis = {
        'total': len(false_positives),
        'cases': [],
        'common_patterns': []
    }
    
    for fp in false_positives:
        fp_analysis['cases'].append({
            'restaurant': fp['restaurant_name'],
            'expected': fp['expected_handle'],
            'found': fp['instagram_handle'],
            'confidence': fp.get('confidence_grade', 'Unknown'),
            'reasoning': fp.get('expected_reasoning', '')
        })
    
    # Analyze false negatives
    fn_analysis = {
        'total': len(false_negatives),
        'cases': [],
        'common_patterns': []
    }
    
    for fn in false_negatives:
        fn_analysis['cases'].append({
            'restaurant': fn['restaurant_name'],
            'expected': fn['expected_handle'],
            'found': fn['instagram_handle'],
            'confidence': fn.get('confidence_grade', 'Unknown'),
            'reasoning': fn.get('expected_reasoning', '')
        })
    
    return {
        'false_positives': fp_analysis,
        'false_negatives': fn_analysis
    }

def save_comprehensive_results(results: List[Dict], metrics: Dict, error_analysis: Dict):
    """Save comprehensive results with all metrics."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Ensure results directory exists
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Save detailed results
    results_file = str(results_dir / f"full_system_golden_results_{timestamp}.json")
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"💾 Detailed results saved to: {results_file}")
    
    # Save comprehensive metrics
    metrics_file = str(results_dir / f"full_system_golden_metrics_{timestamp}.json")
    comprehensive_data = {
        'metrics': metrics,
        'error_analysis': error_analysis,
        'processing_timestamp': datetime.now().isoformat()
    }
    with open(metrics_file, 'w', encoding='utf-8') as f:
        json.dump(comprehensive_data, f, indent=2, ensure_ascii=False)
    print(f"📈 Comprehensive metrics saved to: {metrics_file}")
    
    # Save results as CSV
    csv_file = str(results_dir / f"full_system_golden_results_{timestamp}.csv")
    if results:
        fieldnames = list(results[0].keys())
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"📊 CSV results saved to: {csv_file}")
    
    return results_file, metrics_file, csv_file

def print_comprehensive_analysis(metrics: Dict, error_analysis: Dict):
    """Print comprehensive analysis with all metrics."""
    
    print(f"\n{'='*100}")
    print("📊 COMPREHENSIVE GOLDEN DATASET ANALYSIS: FULL INSTAGRAM DISCOVERY SYSTEM")
    print(f"{'='*100}")
    
    cm = metrics['confusion_matrix']
    clf = metrics['classification_metrics']
    legacy = metrics['legacy_metrics']
    conf_dist = metrics['confidence_distribution']
    perf = metrics['performance']
    breakdown = metrics['detailed_breakdown']
    
    print(f"\n🎯 CLASSIFICATION RESULTS:")
    print(f"   Total Restaurants: {metrics['total_restaurants']}")
    print(f"   Should Find Handle: {breakdown['should_find_handle']}")
    print(f"   Should NOT Find Handle: {breakdown['should_not_find_handle']}")
    
    print(f"\n📊 CONFUSION MATRIX:")
    print(f"                    Predicted")
    print(f"                 Handle  No Handle")
    print(f"   Actual Handle    {cm['true_positives']:2d}      {cm['false_negatives']:2d}     (True Pos / False Neg)")
    print(f"   Actual No Handle {cm['false_positives']:2d}      {cm['true_negatives']:2d}     (False Pos / True Neg)")
    print(f"   Errors: {cm['errors']}")
    
    print(f"\n📈 CLASSIFICATION METRICS:")
    print(f"   Accuracy:      {clf['accuracy']:.3f} ({clf['accuracy']*100:.1f}%)")
    print(f"   Precision:     {clf['precision']:.3f} ({clf['precision']*100:.1f}%)")
    print(f"   Recall:        {clf['recall']:.3f} ({clf['recall']*100:.1f}%)")
    print(f"   F1-Score:      {clf['f1_score']:.3f}")
    print(f"   False Pos Rate: {clf['false_positive_rate']:.3f} ({clf['false_positive_rate']*100:.1f}%)")
    print(f"   False Neg Rate: {clf['false_negative_rate']:.3f} ({clf['false_negative_rate']*100:.1f}%)")
    
    print(f"\n📋 LEGACY COMPARISON:")
    print(f"   Legacy Accuracy: {legacy['legacy_accuracy']:.3f} ({legacy['legacy_accuracy']*100:.1f}%)")
    print(f"   Legacy Correct: {legacy['legacy_correct_count']}/{metrics['total_restaurants']}")
    
    print(f"\n🎯 CONFIDENCE DISTRIBUTION:")
    for conf_level, count in conf_dist.items():
        if count > 0:
            percentage = count / metrics['total_restaurants'] * 100
            print(f"   {conf_level}: {count} ({percentage:.1f}%)")
    
    print(f"\n⏱️  PERFORMANCE:")
    print(f"   Average Time: {perf['average_processing_time']:.1f}s per restaurant")
    print(f"   Total Time: {perf['total_processing_time']:.1f}s")
    
    print(f"\n❌ ERROR ANALYSIS:")
    fp_analysis = error_analysis['false_positives']
    fn_analysis = error_analysis['false_negatives']
    
    print(f"   False Positives: {fp_analysis['total']} cases")
    if fp_analysis['cases']:
        print(f"   False Positive Cases:")
        for case in fp_analysis['cases']:
            print(f"     • {case['restaurant']}: Expected '{case['expected']}', Found '{case['found']}'")
    
    print(f"   False Negatives: {fn_analysis['total']} cases")
    if fn_analysis['cases']:
        print(f"   False Negative Cases:")
        for case in fn_analysis['cases']:
            print(f"     • {case['restaurant']}: Expected '{case['expected']}', Found '{case['found'] or 'None'}'")
    
    print(f"\n🎯 KEY INSIGHTS:")
    if clf['precision'] > 0.8:
        print(f"   ✅ HIGH PRECISION: System rarely finds wrong handles")
    elif clf['precision'] < 0.6:
        print(f"   ⚠️  LOW PRECISION: System often finds wrong handles")
    
    if clf['recall'] > 0.8:
        print(f"   ✅ HIGH RECALL: System finds most available handles")
    elif clf['recall'] < 0.6:
        print(f"   ⚠️  LOW RECALL: System misses many available handles")
    
    if clf['f1_score'] > 0.8:
        print(f"   ✅ EXCELLENT F1: Great balance of precision and recall")
    elif clf['f1_score'] < 0.6:
        print(f"   ⚠️  POOR F1: Needs improvement in precision or recall")

def main():
    """Main function to run the comprehensive analysis."""
    print("🔧 FULL INSTAGRAM DISCOVERY SYSTEM: COMPLETE GOLDEN DATASET ANALYSIS")
    print("=" * 80)
    
    try:
        # CLI args
        parser = argparse.ArgumentParser(description="Run full IG discovery on a dataset")
        parser.add_argument("--csv", dest="csv_path", default="data/golden_dataset.csv", help="Path to CSV dataset")
        parser.add_argument("--workers", dest="workers", type=int, default=6, help="Max workers for parallelism")
        parser.add_argument("--starts-per-sec", dest="starts_per_sec", type=float, default=1.5, help="Throttle task starts per second (0 to disable)")
        parser.add_argument("--shuffle", dest="shuffle", action="store_true", help="Shuffle input rows before processing")
        args = parser.parse_args()
        
        # Load the dataset
        restaurants = load_golden_dataset(args.csv_path)
        
        # Process with full system (reduced workers to avoid rate limits)
        results = process_golden_dataset_full_system(
            restaurants,
            max_workers=max(1, args.workers),
            starts_per_sec=max(0.0, args.starts_per_sec),
            shuffle=bool(args.shuffle)
        )

        # Add review flags prior to metrics and saving
        results = add_review_flags(results)
        
        # Calculate comprehensive metrics
        metrics = calculate_comprehensive_metrics(results)
        
        # Analyze error cases
        error_analysis = analyze_error_cases(results)
        
        # Save results
        results_file, metrics_file, csv_file = save_comprehensive_results(results, metrics, error_analysis)
        
        # Print comprehensive analysis
        print_comprehensive_analysis(metrics, error_analysis)
        
        # Print file locations
        print(f"\n📁 Output Files:")
        print(f"  • Detailed results: {results_file}")
        print(f"  • Comprehensive metrics: {metrics_file}")
        print(f"  • CSV export: {csv_file}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
