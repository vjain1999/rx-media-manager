#!/usr/bin/env python3
"""
Analyze why the fixed Firecrawl version lost some handles that the original found.
This will help us understand the trade-offs and identify improvement opportunities.
"""

import json
import csv
from typing import List, Dict

def load_results_comparison():
    """Load both original and fixed results for detailed comparison."""
    
    # Load original results
    original_results = {}
    with open('golden_results_20250902_173325.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            original_results[row['restaurant_name']] = {
                'handle': row['instagram_handle'],
                'expected': row['expected_handle'],
                'accuracy': row['accuracy'],
                'confidence_score': float(row.get('confidence_score', 0)),
                'confidence_grade': row.get('confidence_grade', ''),
                'method': 'original'
            }
    
    # Load fixed results  
    fixed_results = {}
    with open('fixed_golden_results_20250902_175927.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            fixed_results[row['restaurant_name']] = {
                'handle': row['instagram_handle'],
                'expected': row['expected_handle'], 
                'accuracy': row['accuracy'],
                'processing_time': float(row.get('processing_time', 0)),
                'method': 'fixed'
            }
    
    return original_results, fixed_results

def analyze_regressions(original_results: Dict, fixed_results: Dict) -> List[Dict]:
    """Analyze cases where fixed version performed worse than original."""
    
    regressions = []
    
    for restaurant_name in original_results.keys():
        if restaurant_name not in fixed_results:
            continue
            
        orig = original_results[restaurant_name]
        fixed = fixed_results[restaurant_name]
        
        # Check if this is a regression (original found something, fixed didn't)
        orig_found = orig['handle'] and orig['handle'].strip()
        fixed_found = fixed['handle'] and fixed['handle'].strip()
        orig_correct = orig['accuracy'] == 'correct'
        fixed_correct = fixed['accuracy'] == 'correct'
        
        # Identify different types of regressions
        regression_type = None
        
        if orig_correct and not fixed_correct:
            if orig_found and not fixed_found:
                regression_type = "lost_correct_handle"
            elif orig_found and fixed_found and orig['handle'] != fixed['handle']:
                regression_type = "wrong_handle_found"
            elif not orig_found and fixed_found:
                regression_type = "false_positive_introduced"
        
        if regression_type:
            regression = {
                'restaurant_name': restaurant_name,
                'expected_handle': orig['expected'],
                'original_handle': orig['handle'],
                'fixed_handle': fixed['handle'],
                'original_accuracy': orig['accuracy'],
                'fixed_accuracy': fixed['accuracy'],
                'regression_type': regression_type,
                'original_confidence': orig.get('confidence_score', 0),
                'original_confidence_grade': orig.get('confidence_grade', ''),
                'processing_time': fixed.get('processing_time', 0)
            }
            regressions.append(regression)
    
    return regressions

def analyze_regression_patterns(regressions: List[Dict]) -> Dict:
    """Analyze patterns in the regressions to understand root causes."""
    
    patterns = {
        'by_type': {},
        'by_confidence': {'High': 0, 'Medium': 0, 'Low': 0},
        'by_name_complexity': {'simple': 0, 'complex': 0},
        'by_expected_availability': {'available': 0, 'not_available': 0},
        'common_characteristics': [],
        'potential_causes': []
    }
    
    for regression in regressions:
        # Count by regression type
        reg_type = regression['regression_type']
        patterns['by_type'][reg_type] = patterns['by_type'].get(reg_type, 0) + 1
        
        # Count by original confidence
        conf_grade = regression['original_confidence_grade']
        if conf_grade in patterns['by_confidence']:
            patterns['by_confidence'][conf_grade] += 1
        
        # Analyze name complexity
        name = regression['restaurant_name']
        if len(name.split()) > 3 or '(' in name or '&' in name:
            patterns['by_name_complexity']['complex'] += 1
        else:
            patterns['by_name_complexity']['simple'] += 1
        
        # Expected availability
        if regression['expected_handle'] == 'Not Available':
            patterns['by_expected_availability']['not_available'] += 1
        else:
            patterns['by_expected_availability']['available'] += 1
    
    return patterns

def identify_root_causes(regressions: List[Dict], patterns: Dict) -> List[str]:
    """Identify likely root causes for the regressions."""
    
    root_causes = []
    
    # Analyze the specific cases
    lost_handles = [r for r in regressions if r['regression_type'] == 'lost_correct_handle']
    
    if lost_handles:
        root_causes.append("SIMPLIFIED QUERIES: Fixed version uses fewer, simpler queries which may miss some handles")
        
        # Check for complex restaurant names
        complex_names = [r for r in lost_handles if len(r['restaurant_name'].split()) > 3]
        if complex_names:
            root_causes.append("COMPLEX NAMES: Restaurants with long/complex names may need more diverse query strategies")
        
        # Check for high-confidence losses
        high_conf_losses = [r for r in lost_handles if r['original_confidence_grade'] == 'High']
        if high_conf_losses:
            root_causes.append("HIGH-CONFIDENCE LOSSES: Lost some handles that original system was very confident about")
        
        # Check for generic terms
        generic_terms = [r for r in lost_handles if any(term in r['restaurant_name'].lower() 
                        for term in ['grotto', 'paramount', 'toro', 'alexandria'])]
        if generic_terms:
            root_causes.append("GENERIC TERMS: Restaurants with generic/common names need more specific search strategies")
    
    return root_causes

def generate_improvement_suggestions(regressions: List[Dict], root_causes: List[str]) -> List[str]:
    """Generate specific suggestions to recover lost handles."""
    
    suggestions = []
    
    # Analyze lost handles for patterns
    lost_handles = [r for r in regressions if r['regression_type'] == 'lost_correct_handle']
    
    if lost_handles:
        suggestions.extend([
            "ADD FALLBACK QUERIES: Include more diverse query patterns for complex restaurant names",
            "IMPLEMENT HYBRID APPROACH: Use original system's query diversity with fixed system's speed",
            "ADD LOCATION-SPECIFIC QUERIES: Include more city/neighborhood specific searches",
            "INCREASE QUERY LIMIT: Try 3-4 queries instead of 2 for difficult cases",
            "ADD BUSINESS DIRECTORY SEARCHES: Include more Yelp/Google Business specific queries"
        ])
    
    # Specific suggestions based on the actual lost cases
    restaurant_names = [r['restaurant_name'] for r in lost_handles]
    
    if 'Grotto' in restaurant_names:
        suggestions.append("GENERIC NAME HANDLING: Add disambiguation for generic restaurant names")
    
    if any('(' in name for name in restaurant_names):
        suggestions.append("PARENTHETICAL HANDLING: Better processing of location indicators in names")
    
    if any('&' in name for name in restaurant_names):
        suggestions.append("SPECIAL CHARACTER HANDLING: Improve handling of ampersands and special characters")
    
    return suggestions

def print_detailed_analysis(regressions: List[Dict], patterns: Dict, root_causes: List[str], suggestions: List[str]):
    """Print comprehensive regression analysis."""
    
    print("🔍 REGRESSION ANALYSIS: Why Fixed Version Lost Some Handles")
    print("=" * 80)
    
    print(f"\n📊 REGRESSION SUMMARY:")
    print(f"   Total Regressions: {len(regressions)}")
    print(f"   Lost Correct Handles: {patterns['by_type'].get('lost_correct_handle', 0)}")
    print(f"   Wrong Handles Found: {patterns['by_type'].get('wrong_handle_found', 0)}")
    print(f"   False Positives Introduced: {patterns['by_type'].get('false_positive_introduced', 0)}")
    
    print(f"\n🎯 DETAILED REGRESSION CASES:")
    print(f"{'Restaurant':<35} {'Expected':<15} {'Original':<15} {'Fixed':<15} {'Type'}")
    print("-" * 95)
    
    for reg in regressions:
        name = reg['restaurant_name'][:34]
        expected = reg['expected_handle'][:14] if reg['expected_handle'] != 'Not Available' else 'None'
        original = reg['original_handle'][:14] if reg['original_handle'] else 'None'
        fixed = reg['fixed_handle'][:14] if reg['fixed_handle'] else 'None'
        reg_type = reg['regression_type']
        
        print(f"{name:<35} {expected:<15} {original:<15} {fixed:<15} {reg_type}")
    
    print(f"\n🔍 REGRESSION PATTERNS:")
    print(f"   By Original Confidence:")
    for conf, count in patterns['by_confidence'].items():
        if count > 0:
            print(f"     {conf}: {count} cases")
    
    print(f"   By Name Complexity:")
    print(f"     Simple names: {patterns['by_name_complexity']['simple']} cases")
    print(f"     Complex names: {patterns['by_name_complexity']['complex']} cases")
    
    print(f"\n🚨 IDENTIFIED ROOT CAUSES:")
    for i, cause in enumerate(root_causes, 1):
        print(f"   {i}. {cause}")
    
    print(f"\n💡 IMPROVEMENT SUGGESTIONS:")
    for i, suggestion in enumerate(suggestions, 1):
        print(f"   {i}. {suggestion}")
    
    # Specific case analysis
    print(f"\n🔬 CASE-BY-CASE ROOT CAUSE ANALYSIS:")
    
    for reg in regressions:
        print(f"\n   📍 {reg['restaurant_name']}:")
        print(f"      Expected: {reg['expected_handle']}")
        print(f"      Original found: {reg['original_handle']} (confidence: {reg['original_confidence_grade']})")
        print(f"      Fixed found: {reg['fixed_handle'] or 'None'}")
        
        # Analyze why this specific case failed
        name = reg['restaurant_name']
        likely_causes = []
        
        if len(name.split()) > 3:
            likely_causes.append("Complex name with multiple words")
        if '(' in name:
            likely_causes.append("Location indicator in parentheses")
        if any(term in name.lower() for term in ['grotto', 'paramount', 'toro']):
            likely_causes.append("Generic/common restaurant name")
        if '&' in name:
            likely_causes.append("Special characters (ampersand)")
        if reg['original_confidence_grade'] == 'High':
            likely_causes.append("High-confidence handle from original system")
        
        if likely_causes:
            print(f"      Likely causes: {', '.join(likely_causes)}")
        else:
            print(f"      Likely causes: Unclear - needs further investigation")

def main():
    """Main analysis function."""
    try:
        # Load results
        original_results, fixed_results = load_results_comparison()
        
        # Analyze regressions
        regressions = analyze_regressions(original_results, fixed_results)
        
        # Analyze patterns
        patterns = analyze_regression_patterns(regressions)
        
        # Identify root causes
        root_causes = identify_root_causes(regressions, patterns)
        
        # Generate suggestions
        suggestions = generate_improvement_suggestions(regressions, root_causes)
        
        # Print analysis
        print_detailed_analysis(regressions, patterns, root_causes, suggestions)
        
        # Save analysis
        analysis_data = {
            'regressions': regressions,
            'patterns': patterns,
            'root_causes': root_causes,
            'suggestions': suggestions,
            'summary': {
                'total_regressions': len(regressions),
                'lost_handles': len([r for r in regressions if r['regression_type'] == 'lost_correct_handle']),
                'analysis_timestamp': '2025-09-02T18:00:00'
            }
        }
        
        with open('regression_analysis.json', 'w') as f:
            json.dump(analysis_data, f, indent=2)
        
        print(f"\n💾 Detailed analysis saved to: regression_analysis.json")
        
    except Exception as e:
        print(f"❌ Error in regression analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
