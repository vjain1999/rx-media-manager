#!/usr/bin/env python3
"""
Run the complete Instagram handle discovery system to extract handles only.
No evaluation/accuracy metrics. Outputs JSON and CSV with found handles.

Usage example:
  python run_full_system_extract.py --csv "Expanded Golden Dataset - Sheet1.csv" --workers 6 --starts-per-sec 1.5 --shuffle
"""

import csv
import json
import time
import argparse
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

from web_search import RestaurantInstagramFinder


def load_input_dataset(csv_path: Union[str, Path]) -> List[Dict]:
    """Load input dataset rows. Requires minimal columns used by the pipeline.

    Expected columns:
    - BUSINESS_ID
    - STORE_ID
    - RESTAURANT NAME
    - ADDRESS
    Extra columns are ignored.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    rows: List[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "business_id": (row.get("BUSINESS_ID") or "").strip(),
                "store_id": (row.get("STORE_ID") or "").strip(),
                "restaurant_name": (row.get("RESTAURANT NAME") or "").strip(),
                "address": (row.get("ADDRESS") or "").strip(),
            })

    print(f"📦 Loaded {len(rows)} rows from {path}")
    return rows


def process_single_restaurant_extract(restaurant: Dict, index: int, total: int, enable_google: bool, enable_ddg: bool) -> Dict:
    """Process a single restaurant and return extraction-only result."""
    print(f"Processing {index}/{total}: {restaurant['restaurant_name']}")
    start_time = time.time()

    try:
        finder = RestaurantInstagramFinder(enable_google_custom_search=enable_google, enable_duckduckgo=enable_ddg)
        result = finder._process_single_row({
            'business_id': restaurant['business_id'],
            'store_id': restaurant['store_id'],
            'restaurant_name': restaurant['restaurant_name'],
            'address': restaurant['address'],
            'phone': ''
        })

        processing_time = time.time() - start_time

        # Build lean output
        output = {
            'business_id': restaurant['business_id'],
            'store_id': restaurant['store_id'],
            'restaurant_name': restaurant['restaurant_name'],
            'address': restaurant['address'],
            'instagram_handle': result.get('instagram_handle', ''),
            'confidence_score': result.get('confidence_score', 0.0),
            'confidence_grade': result.get('confidence_grade', 'Unknown'),
            'discovery_method': result.get('discovery_method', ''),
            'status': result.get('status', 'ok'),
            'message': result.get('message', ''),
            'processing_time': processing_time,
        }

        print(f"  → Found: {output['instagram_handle'] or 'None'}  [{output['confidence_grade']}]  {processing_time:.1f}s")
        return output

    except Exception as e:
        processing_time = time.time() - start_time
        print(f"  ✖ Error: {e}")
        return {
            'business_id': restaurant['business_id'],
            'store_id': restaurant['store_id'],
            'restaurant_name': restaurant['restaurant_name'],
            'address': restaurant['address'],
            'instagram_handle': '',
            'confidence_score': 0.0,
            'confidence_grade': 'Error',
            'discovery_method': '',
            'status': 'error',
            'message': str(e),
            'processing_time': processing_time,
        }


def process_dataset_extract(restaurants: List[Dict], max_workers: int = 6, starts_per_sec: float = 1.5, shuffle: bool = True, enable_google: bool = True, enable_ddg: bool = True) -> List[Dict]:
    """Run extraction-only flow with optional start-rate throttling and shuffling."""
    print(f"🚀 Starting extraction for {len(restaurants)} rows with {max_workers} workers...")
    if shuffle:
        print("🔀 Shuffling input order")
        random.shuffle(restaurants)

    start_time = time.time()
    results: List[Dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
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

            fut = executor.submit(process_single_restaurant_extract, restaurant, i + 1, total, enable_google, enable_ddg)
            future_to_restaurant[fut] = restaurant

        completed = 0
        for future in as_completed(future_to_restaurant):
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                r = future_to_restaurant[future]
                results.append({
                    'business_id': r.get('business_id', ''),
                    'store_id': r.get('store_id', ''),
                    'restaurant_name': r.get('restaurant_name', ''),
                    'address': r.get('address', ''),
                    'instagram_handle': '',
                    'confidence_score': 0.0,
                    'confidence_grade': 'Error',
                    'discovery_method': '',
                    'status': 'error',
                    'message': str(exc),
                    'processing_time': 0.0,
                })
            completed += 1
            if completed % 10 == 0 or completed == total:
                print(f"🧭 Progress: {completed}/{total}")

    elapsed = time.time() - start_time
    found_count = sum(1 for r in results if (r.get('instagram_handle') or '').strip())
    print(f"🏁 Done in {elapsed:.1f}s  |  Found handles: {found_count}/{len(results)}")
    return results


def add_review_flags(results: List[Dict]) -> List[Dict]:
    """Add 'review' flag when the same business_id has multiple distinct non-empty handles."""
    by_biz: Dict[str, set] = {}
    for r in results:
        bid = (r.get('business_id') or '').strip()
        handle = (r.get('instagram_handle') or '').strip().lower()
        if bid:
            if bid not in by_biz:
                by_biz[bid] = set()
            if handle:
                by_biz[bid].add(handle)

    flagged = {bid for bid, handles in by_biz.items() if len(handles) > 1}
    for r in results:
        bid = (r.get('business_id') or '').strip()
        r['review'] = 'FLAG' if bid in flagged else ''
    return results

def save_extract_results(results: List[Dict]) -> Dict[str, str]:
    """Save extraction results to timestamped JSON and CSV.

    Returns a dict with file paths.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    json_file = str(results_dir / f"full_system_extract_results_{ts}.json")
    csv_file = str(results_dir / f"full_system_extract_results_{ts}.csv")

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"💾 Saved JSON: {json_file}")

    if results:
        fieldnames = list(results[0].keys())
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"📊 Saved CSV: {csv_file}")

    return {"json": json_file, "csv": csv_file}


def main():
    parser = argparse.ArgumentParser(description="Extract Instagram handles (no evaluation)")
    parser.add_argument("--csv", dest="csv_path", required=True, help="Path to input CSV")
    parser.add_argument("--workers", dest="workers", type=int, default=6, help="Max workers")
    parser.add_argument("--starts-per-sec", dest="starts_per_sec", type=float, default=1.5, help="Throttle task starts per second (0 to disable)")
    parser.add_argument("--shuffle", dest="shuffle", action="store_true", help="Shuffle input rows before processing")
    parser.add_argument("--enable-google", dest="enable_google", action="store_true", help="Enable Google Custom Search strategy")
    parser.add_argument("--enable-ddg", dest="enable_ddg", action="store_true", help="Enable DuckDuckGo strategy")
    args = parser.parse_args()

    print("🔧 FULL INSTAGRAM DISCOVERY SYSTEM: EXTRACTION-ONLY RUN")
    print("=" * 80)

    restaurants = load_input_dataset(args.csv_path)
    results = process_dataset_extract(
        restaurants,
        max_workers=max(1, args.workers),
        starts_per_sec=max(0.0, args.starts_per_sec),
        shuffle=bool(args.shuffle),
        enable_google=bool(args.enable_google),
        enable_ddg=bool(args.enable_ddg),
    )
    results = add_review_flags(results)
    files = save_extract_results(results)

    print("\n📁 Output Files:")
    print(f"  • JSON: {files['json']}")
    print(f"  • CSV:  {files['csv']}")


if __name__ == "__main__":
    main()


