#!/usr/bin/env python3
"""
Deep-dive runner for specific restaurants with additional logging.
Re-runs handle discovery for selected cases and prints detailed diagnostics:
- Strategy that produced the handle
- Verification details (name/location matches)
- Firecrawl validation breakdown
- Confidence scoring and AI verification
"""

import csv
import time
from typing import Dict, List

from web_search import RestaurantInstagramFinder
from config import settings

TARGET_RESTAURANTS = {
    "Rocco's Tavern Express",
    "Anna's Taqueria (MGH)",
    "Antonio's Cucina Italiana",
}


def load_golden_rows() -> List[Dict]:
    rows: List[Dict] = []
    with open("golden_dataset.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("RESTAURANT NAME", "").strip()
            if name in TARGET_RESTAURANTS:
                rows.append({
                    'business_id': row.get('BUSINESS_ID', '').strip(),
                    'store_id': row.get('STORE_ID', '').strip(),
                    'restaurant_name': name,
                    'address': row.get('ADDRESS', '').strip(),
                    'expected_handle': (row.get('INSTAGRAM HANDLE') or '').strip(),
                    'reasoning': (row.get('REASONING') or '').strip(),
                    'phone': ''
                })
    return rows


def summarize_validation(finder: RestaurantInstagramFinder):
    vd = getattr(finder, '_last_validation_data', None) or {}
    gmb = getattr(finder, '_last_gmb_data', None) or {}
    print("\n🔎 Validation summary:")
    if vd:
        lm = vd.get('location_matches') or []
        print(f"   • google_my_business_found: {vd.get('google_my_business_found', False)}")
        print(f"   • yelp_found: {vd.get('yelp_found', False)} | tripadvisor_found: {vd.get('tripadvisor_found', False)}")
        print(f"   • location_matches ({len(lm)}): {lm[:8]}")
        print(f"   • sources: {sorted([k for k,v in vd.items() if isinstance(v,bool) and v])}")
    else:
        print("   • No Firecrawl validation data captured")
    if gmb:
        print(f"   • GMB: instagram_linked={gmb.get('instagram_linked', False)}, address_match={gmb.get('address_match', False)}")
    else:
        print("   • No GMB data captured")


def run_case(row: Dict):
    print("\n" + "="*90)
    print(f"🔬 Deep dive: {row['restaurant_name']}")
    print(f"   Address: {row['address']}")
    print(f"   Expected: {row['expected_handle']}")
    print("="*90)

    finder = RestaurantInstagramFinder()
    start = time.time()
    result = finder._process_single_row(row)
    elapsed = time.time() - start

    print(f"\n✅ Result handle: {result.get('instagram_handle') or 'None'}")
    print(f"📊 Status: {result.get('status')} | Conf: {result.get('confidence_grade')} ({result.get('confidence_score'):.2f}) | AI: {result.get('ai_confidence'):.2f}")
    print(f"⏱️  Time: {elapsed:.1f}s")

    summarize_validation(finder)

    # Extra verification pass to print internals already logged by finder
    handle = result.get('instagram_handle')
    if handle:
        print("\n🔁 Re-verify to emit matcher details:")
        finder._verify_instagram_handle(handle, row['restaurant_name'])


def main():
    # Disable AI verification to speed up deep-dive and avoid external latency
    settings.use_ai_verification = False
    rows = load_golden_rows()
    if not rows:
        print("No target rows found.")
        return
    for row in rows:
        run_case(row)


if __name__ == "__main__":
    main()


