import logging
logger = logging.getLogger(__name__)
"""Main orchestrator for the restaurant video analysis system."""

import json
import time
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from config import settings
from web_search import find_restaurant_instagram
from instagram_client import fetch_instagram_videos
from video_downloader import download_instagram_videos
from video_analyzer import analyze_restaurant_videos
from sms_notifier import notify_restaurant

class RestaurantVideoProcessor:
    """Main processor that orchestrates the entire video analysis pipeline."""
    
    def __init__(self):
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
    
    def process_restaurant(self, restaurant_name: str, address: str, phone: str, 
                          days_back: int = 30, min_quality_score: float = 7.0) -> Dict:
        """
        Process a single restaurant through the entire pipeline.
        
        Args:
            restaurant_name: Name of the restaurant
            address: Restaurant address
            phone: Restaurant phone number
            days_back: How many days back to search for videos
            min_quality_score: Minimum quality score for approval
            
        Returns:
            Processing results dictionary
        """
        print(f"\n{'='*60}")
        print(f"Processing: {restaurant_name}")
        print(f"Address: {address}")
        print(f"Phone: {phone}")
        print(f"{'='*60}")
        
        results = {
            'restaurant_name': restaurant_name,
            'address': address,
            'phone': phone,
            'timestamp': datetime.now().isoformat(),
            'instagram_handle': None,
            'videos_found': 0,
            'videos_downloaded': 0,
            'videos_approved': 0,
            'sms_sent': False,
            'approved_videos': [],
            'errors': []
        }
        
        try:
            # Step 1: Find Instagram handle
            print("\n1. Searching for Instagram handle...")
            instagram_handle = find_restaurant_instagram(restaurant_name, address, phone)
            
            if not instagram_handle:
                error_msg = "Could not find Instagram handle for restaurant"
                print(f"❌ {error_msg}")
                results['errors'].append(error_msg)
                return results
            
            results['instagram_handle'] = instagram_handle
            print(f"✅ Found Instagram: @{instagram_handle}")
            
            # Step 2: Fetch recent videos
            print(f"\n2. Fetching recent videos from @{instagram_handle}...")
            videos = fetch_instagram_videos(instagram_handle, days_back)
            
            if not videos:
                error_msg = f"No recent videos found on @{instagram_handle}"
                print(f"❌ {error_msg}")
                results['errors'].append(error_msg)
                return results
            
            results['videos_found'] = len(videos)
            print(f"✅ Found {len(videos)} recent videos")
            
            # Step 3: Download videos using yt-dlp
            print(f"\n3. Downloading {len(videos)} videos...")
            
            from ytdlp_downloader import download_multiple_instagram_videos_ytdlp
            
            # Extract shortcodes from video list
            shortcodes = [video.get('shortcode') for video in videos if video.get('shortcode')]
            
            if not shortcodes:
                error_msg = "No valid shortcodes found in videos"
                print(f"❌ {error_msg}")
                results['errors'].append(error_msg)
                return results
            
            # Download using yt-dlp
            downloaded_videos = download_multiple_instagram_videos_ytdlp(shortcodes)
            
            if not downloaded_videos:
                error_msg = "Failed to download any videos"
                print(f"❌ {error_msg}")
                results['errors'].append(error_msg)
                return results
            
            results['videos_downloaded'] = len(downloaded_videos)
            print(f"✅ Downloaded {len(downloaded_videos)} videos successfully")
            
            # Step 4: Analyze video quality
            print(f"\n4. Analyzing video quality using LLM...")
            analyzed_videos = analyze_restaurant_videos(downloaded_videos)
            
            # Step 5: Filter approved videos
            print(f"\n5. Filtering videos by quality score (min: {min_quality_score})...")
            approved_videos = []
            
            for video in analyzed_videos:
                analysis = video.get('analysis', {})
                overall_score = analysis.get('overall_score', 0)
                recommendation = analysis.get('recommendation', 'REJECT')
                
                if overall_score >= min_quality_score and recommendation == 'APPROVE':
                    approved_videos.append(video)
                    print(f"✅ Approved: {video['shortcode']} (Score: {overall_score:.1f})")
                else:
                    print(f"❌ Rejected: {video['shortcode']} (Score: {overall_score:.1f})")
            
            results['videos_approved'] = len(approved_videos)
            results['approved_videos'] = approved_videos
            
            # Step 6: Send SMS notification
            print(f"\n6. Sending SMS notification to {phone}...")
            sms_success = notify_restaurant(phone, restaurant_name, approved_videos)
            results['sms_sent'] = sms_success
            
            if sms_success:
                if approved_videos:
                    print(f"✅ SMS sent with {len(approved_videos)} approved videos")
                else:
                    print("✅ SMS sent (no videos met quality standards)")
            else:
                print("❌ Failed to send SMS")
                results['errors'].append("Failed to send SMS notification")
            
            # Save results
            self._save_results(restaurant_name, results)
            
            print(f"\n{'='*60}")
            print(f"PROCESSING COMPLETE: {restaurant_name}")
            print(f"Instagram: @{instagram_handle}")
            print(f"Videos found: {results['videos_found']}")
            print(f"Videos downloaded: {results['videos_downloaded']}")
            print(f"Videos approved: {results['videos_approved']}")
            print(f"SMS sent: {'Yes' if results['sms_sent'] else 'No'}")
            print(f"{'='*60}")
            
        except Exception as e:
            error_msg = f"Unexpected error processing {restaurant_name}: {str(e)}"
            print(f"❌ {error_msg}")
            results['errors'].append(error_msg)
        
        return results
    
    def process_restaurants_batch(self, restaurants: List[Dict], **kwargs) -> List[Dict]:
        """
        Process multiple restaurants in batch.
        
        Args:
            restaurants: List of restaurant dictionaries with 'name', 'address', 'phone'
            **kwargs: Additional arguments passed to process_restaurant
            
        Returns:
            List of processing results
        """
        all_results = []
        
        for i, restaurant in enumerate(restaurants, 1):
            print(f"\n\n🔄 Processing restaurant {i}/{len(restaurants)}")
            
            result = self.process_restaurant(
                restaurant['name'],
                restaurant['address'], 
                restaurant['phone'],
                **kwargs
            )
            
            all_results.append(result)
            
            # Delay between restaurants to avoid rate limiting
            if i < len(restaurants):
                print(f"\n⏳ Waiting before next restaurant...")
                time.sleep(5)
        
        # Save batch results
        self._save_batch_results(all_results)
        
        return all_results
    
    def _save_results(self, restaurant_name: str, results: Dict):
        """Save individual restaurant results to file."""
        safe_name = "".join(c for c in restaurant_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_name}_{int(time.time())}.json"
        filepath = self.results_dir / filename
        
        try:
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"📄 Results saved to {filepath}")
        except Exception as e:
            print(f"Failed to save results: {e}")
    
    def _save_batch_results(self, results: List[Dict]):
        """Save batch results summary."""
        batch_summary = {
            'batch_timestamp': datetime.now().isoformat(),
            'total_restaurants': len(results),
            'successful_processing': sum(1 for r in results if not r['errors']),
            'total_videos_found': sum(r['videos_found'] for r in results),
            'total_videos_approved': sum(r['videos_approved'] for r in results),
            'sms_success_rate': sum(1 for r in results if r['sms_sent']) / len(results) if results else 0,
            'restaurants': results
        }
        
        filename = f"batch_results_{int(time.time())}.json"
        filepath = self.results_dir / filename
        
        try:
            with open(filepath, 'w') as f:
                json.dump(batch_summary, f, indent=2, default=str)
            print(f"\n📊 Batch results saved to {filepath}")
            
            # Print summary
            print(f"\n{'='*60}")
            print("BATCH PROCESSING SUMMARY")
            print(f"{'='*60}")
            print(f"Total restaurants processed: {batch_summary['total_restaurants']}")
            print(f"Successful processing: {batch_summary['successful_processing']}")
            print(f"Total videos found: {batch_summary['total_videos_found']}")
            print(f"Total videos approved: {batch_summary['total_videos_approved']}")
            print(f"SMS success rate: {batch_summary['sms_success_rate']:.1%}")
            print(f"{'='*60}")
            
        except Exception as e:
            print(f"Failed to save batch results: {e}")

def main():
    """Example usage of the restaurant video processor."""
    
    # Example restaurant data
    example_restaurants = [
        {
            'name': 'Mama Rosa\'s Pizza',
            'address': '123 Main St, New York, NY 10001',
            'phone': '+1234567890'
        },
        {
            'name': 'Tokyo Sushi Bar',
            'address': '456 Oak Ave, Los Angeles, CA 90210', 
            'phone': '+1234567891'
        }
    ]
    
    # Initialize processor
    processor = RestaurantVideoProcessor()
    
    # Process single restaurant
    print("Processing single restaurant...")
    result = processor.process_restaurant(
        restaurant_name="Test Restaurant",
        address="123 Test St, Test City, TC 12345",
        phone="+1234567890",
        days_back=30,
        min_quality_score=7.0
    )
    
    # Process multiple restaurants
    # results = processor.process_restaurants_batch(example_restaurants)

if __name__ == "__main__":
    main()