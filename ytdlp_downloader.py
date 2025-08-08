"""yt-dlp based Instagram video downloader."""

import yt_dlp
import os
from pathlib import Path
from typing import Optional, Dict
import time
import random
from config import settings

def download_instagram_video_ytdlp(shortcode: str, download_path: str = "downloads/videos") -> bool:
    """
    Download Instagram video using yt-dlp.
    
    Args:
        shortcode: Instagram post shortcode
        download_path: Directory to save the video
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"📥 Downloading Instagram video {shortcode} using yt-dlp...")
        
        # Create download directory
        os.makedirs(download_path, exist_ok=True)
        
        # Construct Instagram URL
        instagram_url = f"https://www.instagram.com/p/{shortcode}/"
        
        # Configure yt-dlp options
        ydl_opts = {
            'outtmpl': os.path.join(download_path, f'{shortcode}.%(ext)s'),
            'format': 'best[ext=mp4]/best',  # Prefer mp4, fallback to best
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'writethumbnail': False,
            'writeinfojson': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }

        # Prefer cookies-based auth for Instagram (username/password not supported by yt-dlp)
        if settings.ig_cookies_file and os.path.exists(settings.ig_cookies_file):
            print(f"   🍪 Using cookies file: {settings.ig_cookies_file}")
            ydl_opts['cookiefile'] = settings.ig_cookies_file
        elif settings.ig_cookies_from_browser:
            parts = settings.ig_cookies_from_browser.split(':', 1)
            browser = parts[0].strip()
            profile = parts[1].strip() if len(parts) > 1 and parts[1] else None
            ydl_opts['cookiesfrombrowser'] = (browser,) if not profile else (browser, profile)
            print(f"   🍪 Using cookies from browser: {settings.ig_cookies_from_browser}")
        else:
            print("   ⚠️ No Instagram cookies configured (set IG_COOKIES_FILE or IG_COOKIES_FROM_BROWSER)")
        
        # Add random delay to avoid rate limiting
        delay = random.uniform(1, 3)
        print(f"   ⏳ Rate limiting: waiting {delay:.1f}s before download...")
        time.sleep(delay)
        
        # Download with yt-dlp. Try /p first, then /reel as fallback.
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([instagram_url])
            except yt_dlp.DownloadError as e:
                # Retry with reel URL variant
                reel_url = f"https://www.instagram.com/reel/{shortcode}/"
                print(f"   🔁 Retrying as reel URL: {reel_url}")
                ydl.download([reel_url])
        
        print(f"   ✅ Successfully downloaded video {shortcode}")
        return True
        
    except yt_dlp.DownloadError as e:
        print(f"   ❌ yt-dlp download error for {shortcode}: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Failed to download video {shortcode}: {e}")
        return False

def get_instagram_video_info_ytdlp(shortcode: str) -> Optional[Dict]:
    """
    Get Instagram video information using yt-dlp without downloading.
    
    Args:
        shortcode: Instagram post shortcode
        
    Returns:
        Video information dict or None if failed
    """
    try:
        print(f"🔍 Getting video info for {shortcode} using yt-dlp...")
        
        # Construct Instagram URL
        instagram_url = f"https://www.instagram.com/p/{shortcode}/"
        
        # Configure yt-dlp options for info extraction only
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,  # Only extract info, don't download
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        }
        
        # Extract info with yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(instagram_url, download=False)
            
            if info:
                return {
                    'shortcode': shortcode,
                    'title': info.get('title', ''),
                    'duration': info.get('duration'),
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                    'upload_date': info.get('upload_date'),
                    'uploader': info.get('uploader'),
                    'url': info.get('webpage_url', instagram_url),
                    'direct_url': info.get('url'),
                    'ext': info.get('ext', 'mp4')
                }
        
        return None
        
    except Exception as e:
        print(f"   ❌ Failed to get video info for {shortcode}: {e}")
        return None

def download_multiple_instagram_videos_ytdlp(shortcodes: list, download_path: str = "downloads/videos") -> list:
    """
    Download multiple Instagram videos using yt-dlp.
    
    Args:
        shortcodes: List of Instagram post shortcodes
        download_path: Directory to save the videos
        
    Returns:
        List of successfully downloaded video info dicts
    """
    downloaded_videos = []
    
    print(f"📥 Starting download of {len(shortcodes)} videos using yt-dlp...")
    
    for i, shortcode in enumerate(shortcodes, 1):
        print(f"\n🎬 Downloading video {i}/{len(shortcodes)}: {shortcode}")
        
        success = download_instagram_video_ytdlp(shortcode, download_path)
        
        if success:
            # Try to find the downloaded file
            video_file = None
            for ext in ['mp4', 'webm', 'mkv']:  # Common video extensions
                potential_file = os.path.join(download_path, f"{shortcode}.{ext}")
                if os.path.exists(potential_file):
                    video_file = potential_file
                    break
            
            if video_file:
                downloaded_videos.append({
                    'shortcode': shortcode,
                    'original_url': f"https://www.instagram.com/p/{shortcode}/",
                    'local_path': video_file,
                    'download_success': True
                })
                print(f"   📁 Video saved: {video_file}")
            else:
                print(f"   ⚠️ Download reported success but file not found for {shortcode}")
        else:
            downloaded_videos.append({
                'shortcode': shortcode,
                'original_url': f"https://www.instagram.com/p/{shortcode}/",
                'local_path': None,
                'download_success': False
            })
        
        # Rate limiting between downloads
        if i < len(shortcodes):  # Don't wait after the last download
            delay = random.uniform(2, 5)
            print(f"   ⏳ Waiting {delay:.1f}s before next download...")
            time.sleep(delay)
    
    successful_downloads = [v for v in downloaded_videos if v['download_success']]
    print(f"\n✅ Successfully downloaded {len(successful_downloads)}/{len(shortcodes)} videos")
    
    return successful_downloads