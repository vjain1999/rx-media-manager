#!/usr/bin/env python3
"""
Script to run the golden dataset and examine results.
This processes the golden_dataset.csv file to find Instagram handles for restaurants
and compares the results with the expected handles.
"""

import csv
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from web_search import RestaurantInstagramFinder
from config import settings

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

def process_single_restaurant(restaurant: Dict, index: int, total: int) -> Dict:
    """Process a single restaurant and return the result."""
    finder = RestaurantInstagramFinder()
    
    print(f"\n{'='*60}")
    print(f"Processing {index}/{total}: {restaurant['restaurant_name']}")
    print(f"Expected handle: {restaurant['expected_handle']}")
    print(f"{'='*60}")
    
    # Process the restaurant
    result = finder._process_single_row(restaurant)
    
    # Add expected data for comparison
    result['expected_handle'] = restaurant['expected_handle']
    result['expected_reasoning'] = restaurant['reasoning']
    
    # Calculate accuracy
    found_handle = result.get('instagram_handle', '').lower()
    expected_handle = restaurant['expected_handle'].lower()
    
    if expected_handle == 'not available':
        # Expected to not find anything
        result['accuracy'] = 'correct' if not found_handle else 'false_positive'
    elif expected_handle and found_handle:
        # Both have handles - check if they match
        result['accuracy'] = 'correct' if found_handle == expected_handle else 'incorrect'
    elif expected_handle and not found_handle:
        # Expected handle but didn't find it
        result['accuracy'] = 'missed'
    elif not expected_handle and found_handle:
        # Found handle but wasn't expected
        result['accuracy'] = 'unexpected_find'
    else:
        # Both empty
        result['accuracy'] = 'correct'
    
    print(f"✅ Found: {result.get('instagram_handle', 'None')}")
    print(f"📊 Accuracy: {result['accuracy']}")
    print(f"🎯 Confidence: {result.get('confidence_grade', 'Unknown')} ({result.get('confidence_score', 0):.2f})")
    
    return result

def process_golden_dataset_parallel(restaurants: List[Dict], max_workers: int = 4) -> List[Dict]:
    """Process the golden dataset to find Instagram handles using parallel processing."""
    print(f"🚀 Starting parallel processing of {len(restaurants)} restaurants with {max_workers} workers...")
    start_time = time.time()
    
    results = []
    completed_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_restaurant = {
            executor.submit(process_single_restaurant, restaurant, i+1, len(restaurants)): restaurant 
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
                print(f"⏱️  Estimated time remaining: {((time.time() - start_time) / completed_count * (len(restaurants) - completed_count)):.1f}s")
                
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
                    'expected_handle': restaurant['expected_handle'],
                    'expected_reasoning': restaurant['reasoning'],
                    'accuracy': 'error',
                    'confidence_score': 0.0,
                    'confidence_grade': 'Error'
                }
                results.append(error_result)
                completed_count += 1
    
    elapsed_time = time.time() - start_time
    print(f"\n🏁 Parallel processing completed in {elapsed_time:.1f} seconds")
    print(f"⚡ Average time per restaurant: {elapsed_time/len(restaurants):.1f}s")
    
    return results

def process_golden_dataset(restaurants: List[Dict]) -> List[Dict]:
    """Process the golden dataset - wrapper function for backward compatibility."""
    return process_golden_dataset_parallel(restaurants, max_workers=6)

def analyze_results(results: List[Dict]) -> Dict:
    """Analyze the results and generate statistics."""
    total = len(results)
    accuracy_counts = {}
    confidence_counts = {}
    
    for result in results:
        # Count accuracy types
        accuracy = result.get('accuracy', 'unknown')
        accuracy_counts[accuracy] = accuracy_counts.get(accuracy, 0) + 1
        
        # Count confidence grades
        confidence = result.get('confidence_grade', 'Unknown')
        confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
    
    # Calculate accuracy percentage
    correct = accuracy_counts.get('correct', 0)
    accuracy_percentage = (correct / total * 100) if total > 0 else 0
    
    analysis = {
        'total_restaurants': total,
        'accuracy_breakdown': accuracy_counts,
        'confidence_breakdown': confidence_counts,
        'overall_accuracy': f"{accuracy_percentage:.1f}%",
        'processing_timestamp': datetime.now().isoformat()
    }
    
    return analysis

def save_results(results: List[Dict], analysis: Dict):
    """Save results and analysis to files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save detailed results
    results_file = f"golden_results_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"💾 Detailed results saved to: {results_file}")
    
    # Save analysis summary
    analysis_file = f"golden_analysis_{timestamp}.json"
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print(f"📈 Analysis saved to: {analysis_file}")
    
    # Save results as CSV for easy viewing
    csv_file = f"golden_results_{timestamp}.csv"
    if results:
        fieldnames = list(results[0].keys())
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"📊 CSV results saved to: {csv_file}")
    
    return results_file, analysis_file, csv_file

def print_summary(analysis: Dict):
    """Print a summary of the results."""
    print(f"\n{'='*80}")
    print("📊 GOLDEN DATASET RESULTS SUMMARY")
    print(f"{'='*80}")
    
    print(f"Total Restaurants Processed: {analysis['total_restaurants']}")
    print(f"Overall Accuracy: {analysis['overall_accuracy']}")
    
    print(f"\n📈 Accuracy Breakdown:")
    for accuracy_type, count in analysis['accuracy_breakdown'].items():
        percentage = (count / analysis['total_restaurants'] * 100)
        print(f"  {accuracy_type}: {count} ({percentage:.1f}%)")
    
    print(f"\n🎯 Confidence Distribution:")
    for confidence_level, count in analysis['confidence_breakdown'].items():
        percentage = (count / analysis['total_restaurants'] * 100)
        print(f"  {confidence_level}: {count} ({percentage:.1f}%)")
    
    print(f"\n⏰ Processing completed at: {analysis['processing_timestamp']}")
    print(f"{'='*80}")

def load_existing_results(filename: str) -> List[Dict]:
    """Load existing results if available."""
    if Path(filename).exists():
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_intermediate_results(results: List[Dict], filename: str = "golden_results_intermediate.json"):
    """Save intermediate results during processing."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

def main():
    """Main function to run the golden dataset analysis."""
    print("🏆 GOLDEN DATASET PROCESSOR (PARALLELIZED)")
    print("=" * 60)
    
    try:
        # Load the dataset
        restaurants = load_golden_dataset()
        
        # Check for existing intermediate results
        intermediate_file = "golden_results_intermediate.json"
        existing_results = load_existing_results(intermediate_file)
        
        if existing_results:
            print(f"📂 Found {len(existing_results)} existing results")
            choice = input("Resume from existing results? (y/n): ").lower().strip()
            if choice == 'y':
                # Filter out already processed restaurants
                processed_names = {r.get('restaurant_name', '') for r in existing_results}
                remaining_restaurants = [r for r in restaurants if r['restaurant_name'] not in processed_names]
                
                if remaining_restaurants:
                    print(f"🔄 Processing remaining {len(remaining_restaurants)} restaurants...")
                    new_results = process_golden_dataset_parallel(remaining_restaurants, max_workers=6)
                    results = existing_results + new_results
                else:
                    print("✅ All restaurants already processed!")
                    results = existing_results
            else:
                print("🔄 Starting fresh processing...")
                results = process_golden_dataset(restaurants)
        else:
            # Process the restaurants
            results = process_golden_dataset(restaurants)
        
        # Save intermediate results
        save_intermediate_results(results, intermediate_file)
        
        # Analyze results
        analysis = analyze_results(results)
        
        # Save final results
        results_file, analysis_file, csv_file = save_results(results, analysis)
        
        # Print summary
        print_summary(analysis)
        
        # Print file locations
        print(f"\n📁 Output Files:")
        print(f"  • Detailed results: {results_file}")
        print(f"  • Analysis summary: {analysis_file}")
        print(f"  • CSV export: {csv_file}")
        
        # Clean up intermediate file
        if Path(intermediate_file).exists():
            Path(intermediate_file).unlink()
            print(f"🧹 Cleaned up intermediate file: {intermediate_file}")
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Processing interrupted by user")
        print(f"💾 Intermediate results saved to: golden_results_intermediate.json")
        print(f"🔄 Run the script again to resume processing")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
