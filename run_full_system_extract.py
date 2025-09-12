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
from typing import List, Dict, Union, Optional
import contextlib
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

from web_search import RestaurantInstagramFinder
from firecrawl_search import get_rate_cooldowns


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


def process_single_restaurant_extract(restaurant: Dict, index: int, total: int, enable_google: bool, enable_ddg: bool, terse: bool = False) -> Dict:
    """Process a single restaurant and return extraction-only result."""
    print(f"Processing {index}/{total}: {restaurant['restaurant_name']}")
    start_time = time.time()

    try:
        finder = RestaurantInstagramFinder(enable_google_custom_search=enable_google, enable_duckduckgo=enable_ddg)
        with (contextlib.redirect_stdout(io.StringIO()) if terse else contextlib.nullcontext()):
            with (contextlib.redirect_stderr(io.StringIO()) if terse else contextlib.nullcontext()):
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


def process_dataset_extract(
    restaurants: List[Dict],
    max_workers: int = 6,
    starts_per_sec: float = 1.5,
    shuffle: bool = True,
    enable_google: bool = True,
    enable_ddg: bool = True,
    save_every: int = 0,
    jsonl_path: str = "",
    latest_json_path: str = "",
    latest_csv_path: str = "",
    progress_csv_path: str = "",
    terse: bool = False,
    progress_every: int = 100,
) -> List[Dict]:
    """Run extraction-only flow with optional start-rate throttling and shuffling.

    If save_every > 0, results are streamed to JSONL and periodic snapshots are written.
    """
    print(f"🚀 Starting extraction for {len(restaurants)} rows with {max_workers} workers...")
    if shuffle:
        print("🔀 Shuffling input order")
        random.shuffle(restaurants)

    start_time = time.time()
    results: List[Dict] = []
    jsonl_file = None
    found_counter = 0
    error_counter = 0

    def _write_latest_snapshot():
        try:
            if not results:
                return
            if latest_json_path:
                with open(latest_json_path, "w", encoding="utf-8") as jf:
                    json.dump(results, jf, indent=2, ensure_ascii=False)
            if latest_csv_path:
                fieldnames = list(results[0].keys())
                with open(latest_csv_path, "w", newline="", encoding="utf-8") as cf:
                    writer = csv.DictWriter(cf, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(results)
            if latest_json_path or latest_csv_path:
                print(f"💾 Snapshot saved: {latest_json_path or '[json disabled]'} | {latest_csv_path or '[csv disabled]'}")
        except Exception as snapshot_err:
            print(f"⚠️ Failed to write snapshot: {snapshot_err}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_restaurant = {}
        last_start_ts = 0.0
        min_interval = (1.0 / starts_per_sec) if starts_per_sec and starts_per_sec > 0 else 0.0
        total = len(restaurants)

        # Prepare JSONL stream file if requested
        if jsonl_path:
            try:
                jsonl_file = open(jsonl_path, "a", encoding="utf-8")
            except Exception as e:
                print(f"⚠️ Could not open JSONL stream file '{jsonl_path}': {e}")
                jsonl_file = None

        for i, restaurant in enumerate(restaurants):
            if min_interval > 0:
                now = time.time()
                elapsed = now - last_start_ts
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                last_start_ts = time.time()
            # Global adaptive cooldowns based on prior 429s
            try:
                openai_wait, firecrawl_wait = get_rate_cooldowns()
                adaptive_sleep = max(openai_wait, firecrawl_wait)
                if adaptive_sleep > 0:
                    print(f"⏳ Backing off {adaptive_sleep:.1f}s due to upstream rate limits...")
                    time.sleep(adaptive_sleep)
            except Exception:
                pass

            fut = executor.submit(process_single_restaurant_extract, restaurant, i + 1, total, enable_google, enable_ddg, terse)
            future_to_restaurant[fut] = restaurant

        completed = 0
        try:
            for future in as_completed(future_to_restaurant):
                try:
                    result = future.result()
                    results.append(result)
                    if (result.get('instagram_handle') or '').strip():
                        found_counter += 1
                    if (result.get('status') or '') == 'error':
                        error_counter += 1
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
                    error_counter += 1

                # Stream to JSONL if enabled
                if jsonl_file is not None:
                    try:
                        jsonl_file.write(json.dumps(results[-1], ensure_ascii=False) + "\n")
                        jsonl_file.flush()
                    except Exception as stream_err:
                        print(f"⚠️ Failed to append to JSONL stream: {stream_err}")

                completed += 1
                if completed % max(1, progress_every) == 0 or completed == total:
                    elapsed = max(1e-6, time.time() - start_time)
                    rps = completed / elapsed
                    remaining = max(0, total - completed)
                    eta_s = int(remaining / rps) if rps > 0 else 0
                    print(f"🧭 Progress: {completed}/{total} | found={found_counter} errors={error_counter} | rps={rps:.2f} | eta~{eta_s//3600:02d}:{(eta_s%3600)//60:02d}:{eta_s%60:02d}")

                    # Append a row to progress CSV
                    if progress_csv_path:
                        try:
                            p = Path(progress_csv_path)
                            write_header = not p.exists()
                            with open(progress_csv_path, 'a', newline='', encoding='utf-8') as pf:
                                writer = csv.writer(pf)
                                if write_header:
                                    writer.writerow(["timestamp", "completed", "total", "found", "errors", "rps", "eta_seconds"])
                                writer.writerow([
                                    datetime.now().isoformat(timespec='seconds'),
                                    completed,
                                    total,
                                    found_counter,
                                    error_counter,
                                    f"{rps:.3f}",
                                    eta_s,
                                ])
                        except Exception as e:
                            print(f"⚠️ Failed to write progress CSV: {e}")

                # Periodic snapshot
                if save_every > 0 and (completed % save_every == 0):
                    _write_latest_snapshot()
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user. Writing last snapshot before exit...")
            _write_latest_snapshot()
            raise
        finally:
            try:
                if jsonl_file is not None:
                    jsonl_file.close()
            except Exception:
                pass

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

def save_extract_results(results: List[Dict], output_basename: Optional[str] = None) -> Dict[str, str]:
    """Save extraction results to JSON and CSV with improved naming.

    If output_basename is provided, files are named:
      results/{output_basename}_final.json
      results/{output_basename}_final.csv
    Otherwise, fall back to legacy timestamped naming.
    """
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    if output_basename:
        json_file = str(results_dir / f"{output_basename}_final.json")
        csv_file = str(results_dir / f"{output_basename}_final.csv")
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
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
    parser.add_argument("--save-every", dest="save_every", type=int, default=100, help="Write snapshot every N completed rows (0 to disable)")
    parser.add_argument("--output-prefix", dest="output_prefix", default="", help="Custom output prefix for results naming")
    parser.add_argument("--terse", dest="terse", action="store_true", help="Reduce per-item logs and show compact progress heartbeats")
    parser.add_argument("--progress-every", dest="progress_every", type=int, default=100, help="Print heartbeat and append progress CSV every N rows")
    args = parser.parse_args()

    print("🔧 FULL INSTAGRAM DISCOVERY SYSTEM: EXTRACTION-ONLY RUN")
    print("=" * 80)

    restaurants = load_input_dataset(args.csv_path)

    # Derive output naming and streaming paths
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_stem = Path(args.csv_path).stem.replace(" ", "_")
    base_name = (args.output_prefix.strip() or f"full_extract_{input_stem}_{ts}")
    jsonl_path = str(results_dir / f"{base_name}.jsonl")
    latest_json = str(results_dir / f"{base_name}_latest.json")
    latest_csv = str(results_dir / f"{base_name}_latest.csv")
    progress_csv = str(results_dir / f"{base_name}_progress.csv")

    results = process_dataset_extract(
        restaurants,
        max_workers=max(1, args.workers),
        starts_per_sec=max(0.0, args.starts_per_sec),
        shuffle=bool(args.shuffle),
        enable_google=bool(args.enable_google),
        enable_ddg=bool(args.enable_ddg),
        save_every=max(0, int(args.save_every)),
        jsonl_path=jsonl_path,
        latest_json_path=latest_json,
        latest_csv_path=latest_csv,
        progress_csv_path=progress_csv,
        terse=bool(args.terse),
        progress_every=max(1, int(args.progress_every)),
    )
    results = add_review_flags(results)
    files = save_extract_results(results, output_basename=base_name)

    print("\n📁 Output Files:")
    print(f"  • JSON: {files['json']}")
    print(f"  • CSV:  {files['csv']}")
    print(f"  • JSONL stream: {jsonl_path}")
    print(f"  • Progress CSV: {progress_csv}")


if __name__ == "__main__":
    main()


