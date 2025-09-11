"""Demo script showing the restaurant video analysis system without real API calls."""

import json
import time
from pathlib import Path

def demo_web_search():
    """Demo the web search functionality."""
    print("🔍 DEMO: Web Search for Instagram Handle")
    print("-" * 40)
    
    restaurant_name = "Joe's Pizza Palace"
    address = "123 Broadway, New York, NY 10001"
    phone = "+12125551234"
    
    print(f"Restaurant: {restaurant_name}")
    print(f"Address: {address}")
    print(f"Phone: {phone}")
    print()
    
    # Simulate search process
    print("Searching web for Instagram handle...")
    time.sleep(1)
    print("✅ Found Instagram: @joespizzapalace")
    print()
    
    return "@joespizzapalace"

def demo_instagram_fetch():
    """Demo the Instagram video fetching."""
    print("📱 DEMO: Instagram Video Fetching")
    print("-" * 40)
    
    handle = "@joespizzapalace"
    print(f"Fetching recent videos from {handle}...")
    time.sleep(1)
    
    # Simulate found videos
    mock_videos = [
        {
            'shortcode': 'ABC123',
            'url': 'https://www.instagram.com/p/ABC123/',
            'video_url': 'https://scontent.cdninstagram.com/v/t50.2886-16/...',
            'caption': 'Fresh pizza straight from the oven! 🍕',
            'likes': 145,
            'views': 1200,
            'date': '2024-01-15T18:30:00Z',
            'duration': 15
        },
        {
            'shortcode': 'DEF456',
            'url': 'https://www.instagram.com/p/DEF456/',
            'video_url': 'https://scontent.cdninstagram.com/v/t50.2886-16/...',
            'caption': 'Making dough the traditional way',
            'likes': 89,
            'views': 650,
            'date': '2024-01-10T12:15:00Z',
            'duration': 22
        }
    ]
    
    for video in mock_videos:
        print(f"✅ Found video: {video['shortcode']} - {video['caption'][:30]}...")
    
    print(f"\nTotal: {len(mock_videos)} videos found")
    print()
    
    return mock_videos

def demo_video_download():
    """Demo the video download process."""
    print("⬇️ DEMO: Video Download")
    print("-" * 40)
    
    videos = [
        {'shortcode': 'ABC123', 'video_url': 'https://example.com/video1.mp4'},
        {'shortcode': 'DEF456', 'video_url': 'https://example.com/video2.mp4'}
    ]
    
    for video in videos:
        print(f"Downloading {video['shortcode']}...")
        time.sleep(0.5)
        video['local_path'] = f"downloads/videos/{video['shortcode']}.mp4"
        print(f"✅ Downloaded to {video['local_path']}")
    
    print(f"\nAll {len(videos)} videos downloaded successfully")
    print()
    
    return videos

def demo_video_analysis():
    """Demo the LLM video analysis."""
    print("🤖 DEMO: LLM Video Quality Analysis")
    print("-" * 40)
    
    videos = [
        {'shortcode': 'ABC123', 'local_path': 'downloads/videos/ABC123.mp4', 'caption': 'Fresh pizza straight from the oven! 🍕'},
        {'shortcode': 'DEF456', 'local_path': 'downloads/videos/DEF456.mp4', 'caption': 'Making dough the traditional way'}
    ]
    
    for video in videos:
        print(f"Analyzing {video['shortcode']}...")
        time.sleep(1)
        
        # Mock analysis results
        if video['shortcode'] == 'ABC123':
            analysis = {
                'food_quality': 9,
                'visual_appeal': 8,
                'professionalism': 7,
                'brand_safety': 10,
                'marketing_value': 9,
                'overall_score': 8.6,
                'recommendation': 'APPROVE',
                'reasoning': 'High-quality food presentation with excellent visual appeal',
                'highlights': ['Great food close-ups', 'Good lighting', 'Appetizing presentation'],
                'food_items': ['pizza', 'cheese', 'pepperoni']
            }
        else:
            analysis = {
                'food_quality': 6,
                'visual_appeal': 5,
                'professionalism': 4,
                'brand_safety': 8,
                'marketing_value': 5,
                'overall_score': 5.6,
                'recommendation': 'REJECT',
                'reasoning': 'Poor lighting and shaky camera work affects quality',
                'highlights': ['Shows process but poor quality'],
                'food_items': ['dough', 'flour']
            }
        
        video['analysis'] = analysis
        
        print(f"✅ Analysis complete:")
        print(f"   Overall Score: {analysis['overall_score']}/10")
        print(f"   Recommendation: {analysis['recommendation']}")
        print(f"   Reasoning: {analysis['reasoning']}")
        print()
    
    return videos

def demo_sms_notification():
    """Demo the SMS notification process."""
    print("📱 DEMO: SMS Restaurant Notification")
    print("-" * 40)
    
    restaurant_name = "Joe's Pizza Palace"
    phone = "+12125551234"
    
    # Mock approved videos
    approved_videos = [
        {
            'shortcode': 'ABC123',
            'url': 'https://www.instagram.com/p/ABC123/',
            'analysis': {
                'overall_score': 8.6,
                'food_items': ['pizza', 'cheese', 'pepperoni']
            }
        }
    ]
    
    print(f"Sending SMS to {restaurant_name} at {phone}...")
    time.sleep(1)
    
    # Mock SMS content
    sms_content = f"""
Hi {restaurant_name}!

We found 1 high-quality video from your Instagram that would be great for your DoorDash store page!

Video:
1. Quality Score: 8.6/10 (pizza, cheese, pepperoni)
   https://www.instagram.com/p/ABC123/

This video will help customers see your food and increase orders!

Reply YES to approve using this video on your DoorDash store page, or NO if you prefer not to.

- DoorDash Media Team
    """.strip()
    
    print("✅ SMS sent successfully!")
    print("\nSMS Content:")
    print("-" * 20)
    print(sms_content)
    print("-" * 20)
    print()

def demo_full_pipeline():
    """Demo the complete pipeline for a restaurant."""
    print("🚀 FULL PIPELINE DEMO")
    print("=" * 50)
    print("Processing: Joe's Pizza Palace")
    print("=" * 50)
    print()
    
    # Step 1: Find Instagram
    instagram_handle = demo_web_search()
    
    # Step 2: Fetch videos
    videos = demo_instagram_fetch()
    
    # Step 3: Download videos
    videos_with_files = demo_video_download()
    
    # Step 4: Analyze videos
    analyzed_videos = demo_video_analysis()
    
    # Step 5: Filter approved videos
    print("🎯 DEMO: Filtering Approved Videos")
    print("-" * 40)
    
    approved_videos = []
    min_score = 7.0
    
    for video in analyzed_videos:
        analysis = video['analysis']
        if analysis['overall_score'] >= min_score and analysis['recommendation'] == 'APPROVE':
            approved_videos.append(video)
            print(f"✅ Approved: {video['shortcode']} (Score: {analysis['overall_score']})")
        else:
            print(f"❌ Rejected: {video['shortcode']} (Score: {analysis['overall_score']})")
    
    print(f"\nResult: {len(approved_videos)}/{len(analyzed_videos)} videos approved")
    print()
    
    # Step 6: Send SMS
    if approved_videos:
        demo_sms_notification()
    
    # Summary
    print("📊 DEMO RESULTS SUMMARY")
    print("=" * 50)
    print(f"Restaurant: Joe's Pizza Palace")
    print(f"Instagram: {instagram_handle}")
    print(f"Videos found: {len(videos)}")
    print(f"Videos downloaded: {len(videos_with_files)}")
    print(f"Videos approved: {len(approved_videos)}")
    print(f"SMS sent: {'Yes' if approved_videos else 'No'}")
    print("=" * 50)

def main():
    """Run the demo."""
    print("Restaurant Video Analysis System - DEMO MODE")
    print("=" * 60)
    print("This demo simulates the complete pipeline without real API calls")
    print("=" * 60)
    print()
    
    demo_full_pipeline()
    
    print("\n🎉 Demo completed!")
    print("\nTo run with real data:")
    print("1. Configure your .env file with API credentials")
    print("2. Run: python cli.py single --name 'Restaurant Name' --address 'Address' --phone '+1234567890'")

if __name__ == "__main__":
    main()