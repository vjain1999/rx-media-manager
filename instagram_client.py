"""Instagram client module to fetch videos without getting rate limited."""

import instaloader
import time
import random
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from config import settings
import os
import requests
import re
from yt_dlp import YoutubeDL

class InstagramVideoFetcher:
    """Fetch Instagram videos using instaloader with rate limiting protection."""
    
    def __init__(self):
        # Enhanced instaloader configuration for anti-detection
        self.loader = instaloader.Instaloader(
            download_videos=False,  # We'll handle downloads separately
            download_pictures=False,
            download_video_thumbnails=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            sleep=True,  # Enable sleep between requests
            request_timeout=30.0,  # Increase timeout
            max_connection_attempts=3  # Retry failed connections
        )
        
        # Session management
        self.session_file = f"session_{settings.instagram_username}" if settings.instagram_username else None
        self.last_request_time = 0
        self.request_count = 0
        self.max_requests_per_hour = 50  # Conservative limit
        
        # Login if credentials are provided
        if settings.instagram_username and settings.instagram_password:
            try:
                self._login_with_session_management()
                print("Successfully logged into Instagram")
            except Exception as e:
                print(f"Failed to login to Instagram: {e}")
                print("Proceeding without login (limited functionality)")
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Ensure minimum 3-7 seconds between requests
        min_delay = 3
        if time_since_last < min_delay:
            additional_wait = min_delay - time_since_last + random.uniform(0, 4)
            print(f"   ⏳ Rate limiting: waiting {additional_wait:.1f}s...")
            time.sleep(additional_wait)
        
        self.last_request_time = time.time()
        self.request_count += 1
        
        # Check hourly limit
        if self.request_count >= self.max_requests_per_hour:
            print("   ⚠️ Hourly request limit reached, taking extended break")
            time.sleep(3600)  # 1 hour break
            self.request_count = 0
    
    def _login_with_session_management(self):
        """Login with session persistence and better error handling."""
        try:
            # Try to load existing session
            if self.session_file and os.path.exists(self.session_file):
                print("   🔄 Loading existing Instagram session...")
                self.loader.load_session_from_file(settings.instagram_username, self.session_file)
                
                # Test if session is still valid
                try:
                    # Try a simple request to validate session
                    profile = instaloader.Profile.from_username(self.loader.context, settings.instagram_username)
                    print("   ✅ Existing session is valid")
                    return
                except Exception as e:
                    print(f"   ❌ Existing session invalid: {e}")
                    # Continue to fresh login
            
            # Fresh login with enhanced anti-detection
            print("   🔐 Performing fresh Instagram login...")
            
            # Add some randomness to login timing
            time.sleep(random.uniform(2, 5))
            
            self.loader.login(settings.instagram_username, settings.instagram_password)
            
            # Save session for future use
            if self.session_file:
                self.loader.save_session_to_file(self.session_file)
                print("   💾 Session saved for future use")
                
        except instaloader.exceptions.ConnectionException as e:
            if "rate limit" in str(e).lower():
                print("   ⚠️ Rate limited during login, waiting...")
                time.sleep(random.uniform(300, 600))  # 5-10 minute wait
                raise e
            else:
                raise e
    
    def get_recent_videos(self, username: str, days_back: int = 30) -> List[Dict]:
        """
        Get recent videos from an Instagram profile with enhanced error handling.
        
        Args:
            username: Instagram username (without @)
            days_back: How many days back to look for videos
            
        Returns:
            List of video metadata dictionaries
        """
        videos = []
        
        try:
            print(f"Fetching recent videos from @{username}...")
            
            # Get profile with retry logic
            profile = self._get_profile_with_retry(username)
            if not profile:
                return videos
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            count = 0
            posts_checked = 0
            max_posts_to_check = 50  # Limit to avoid infinite loops
            
            for post in profile.get_posts():
                posts_checked += 1
                
                # Apply our custom rate limiting
                self._enforce_rate_limit()
                print(f"   🔍 Checking post {posts_checked}...")
                
                # Stop if we've reached the date limit
                if post.date < cutoff_date:
                    print(f"   📅 Reached date cutoff, stopping")
                    break
                
                # Stop if we've checked too many posts
                if posts_checked >= max_posts_to_check:
                    print(f"   🛑 Reached max posts limit ({max_posts_to_check}), stopping")
                    break
                
                # Only process videos
                if self._is_video_post(post):
                    try:
                        video_info = self._extract_basic_video_info(post)
                        if video_info:
                            videos.append(video_info)
                            count += 1
                            
                            print(f"   ✅ Found video {count}: {video_info['shortcode']}")
                            
                            # Limit number of videos per restaurant
                            if count >= settings.max_videos_per_restaurant:
                                print(f"   🎯 Reached video limit ({settings.max_videos_per_restaurant}), stopping")
                                break
                            
                    except Exception as e:
                        print(f"   ❌ Error processing video for {getattr(post, 'shortcode', 'unknown')}: {e}")
                        continue
            
            print(f"✅ Retrieved {len(videos)} videos from @{username} (checked {posts_checked} posts)")
            
        except instaloader.exceptions.ProfileNotExistsException:
            print(f"❌ Instagram profile @{username} does not exist")
        except instaloader.exceptions.PrivateProfileNotFollowedException:
            print(f"❌ Instagram profile @{username} is private and not followed")
        except instaloader.exceptions.ConnectionException as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                print(f"❌ Rate limited while fetching @{username}: {e}")
                print("   ⏰ Consider waiting before trying again")
            else:
                print(f"❌ Connection error for @{username}: {e}")
        except Exception as e:
            print(f"❌ Unexpected error fetching videos from @{username}: {e}")
        
        return videos
    
    def _get_profile_with_retry(self, username: str, max_retries: int = 3):
        """Get profile with retry logic for rate limiting."""
        for attempt in range(max_retries):
            try:
                profile = instaloader.Profile.from_username(self.loader.context, username)
                return profile
            except instaloader.exceptions.ConnectionException as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    wait_time = (2 ** attempt) * 60  # Exponential backoff: 1, 2, 4 minutes
                    print(f"   ⚠️ Rate limited (attempt {attempt + 1}/{max_retries}), waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise e
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                print(f"   ⚠️ Error getting profile (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(30)  # Wait 30 seconds before retry
        
        return None
    
    def _is_video_post(self, post) -> bool:
        """Check if a post is a video with safe attribute access."""
        try:
            return getattr(post, 'is_video', False)
        except Exception:
            return False
    
    def _extract_basic_video_info(self, post) -> Dict:
        """Extract only essential video information without triggering API calls."""
        try:
            # Get basic info that doesn't require additional API calls
            shortcode = getattr(post, 'shortcode', 'unknown')
            post_date = getattr(post, 'date', datetime.now())
            
            print(f"      ✅ Video shortcode: {shortcode}")
            
            return {
                'shortcode': shortcode,
                'url': f"https://www.instagram.com/p/{shortcode}/",
                'date': post_date,
                'is_video': True,
                'typename': getattr(post, 'typename', 'video')
            }
        except Exception as e:
            print(f"      ❌ Error extracting basic video info: {e}")
            return None
    
    def get_reel_videos(self, username: str, days_back: int = 30) -> List[Dict]:
        """
        Get recent Instagram Reels from a profile with enhanced error handling.
        
        Args:
            username: Instagram username (without @)
            days_back: How many days back to look for reels
            
        Returns:
            List of reel metadata dictionaries
        """
        reels = []
        
        try:
            print(f"Fetching recent reels from @{username}...")
            
            # Get profile with retry logic
            profile = self._get_profile_with_retry(username)
            if not profile:
                return reels
            
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            count = 0
            posts_checked = 0
            max_posts_to_check = 30  # Limit for reels
            
            for post in profile.get_posts():
                posts_checked += 1
                
                # Apply our custom rate limiting  
                self._enforce_rate_limit()
                print(f"   🔍 Checking reel {posts_checked}...")
                
                if post.date < cutoff_date:
                    print(f"   📅 Reached date cutoff for reels")
                    break
                
                if posts_checked >= max_posts_to_check:
                    print(f"   🛑 Reached max posts limit for reels ({max_posts_to_check})")
                    break
                
                # Check if it's a reel with better detection
                if self._is_reel_post(post):
                    try:
                        reel_info = self._extract_basic_video_info(post)
                        if reel_info:
                            reels.append(reel_info)
                            count += 1
                            
                            print(f"   ✅ Found reel {count}: {reel_info['shortcode']}")
                            
                            if count >= settings.max_videos_per_restaurant:
                                print(f"   🎯 Reached reel limit ({settings.max_videos_per_restaurant})")
                                break
                            
                    except Exception as e:
                        print(f"   ❌ Error processing reel for {getattr(post, 'shortcode', 'unknown')}: {e}")
                        continue
            
            print(f"✅ Retrieved {len(reels)} reels from @{username} (checked {posts_checked} posts)")
            
        except instaloader.exceptions.ConnectionException as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                print(f"❌ Rate limited while fetching reels from @{username}: {e}")
            else:
                print(f"❌ Connection error fetching reels from @{username}: {e}")
        except Exception as e:
            print(f"❌ Error fetching reels from @{username}: {e}")
        
        return reels
    
    def _is_reel_post(self, post) -> bool:
        """Check if a post is a reel with safe attribute access."""
        try:
            # Multiple ways to detect reels
            is_video = getattr(post, 'is_video', False)
            typename = getattr(post, 'typename', '')
            
            # Reels are typically GraphVideo or video posts
            return is_video and (typename == 'GraphVideo' or 'reel' in typename.lower())
        except Exception:
            return False
    
    def get_all_videos(self, username: str, days_back: int = 30) -> List[Dict]:
        """
        Get all videos (posts + reels) from an Instagram profile.
        
        Args:
            username: Instagram username (without @)
            days_back: How many days back to look for videos
            
        Returns:
            Combined list of all video metadata
        """
        all_videos = []
        
        # Get regular video posts
        videos = self.get_recent_videos(username, days_back)
        all_videos.extend(videos)
        
        # Get reels
        reels = self.get_reel_videos(username, days_back)
        all_videos.extend(reels)
        
        # Remove duplicates based on shortcode
        seen_shortcodes = set()
        unique_videos = []
        
        for video in all_videos:
            if video['shortcode'] not in seen_shortcodes:
                seen_shortcodes.add(video['shortcode'])
                unique_videos.append(video)
        
        # Sort by date (newest first)
        unique_videos.sort(key=lambda x: x['date'], reverse=True)
        
        return unique_videos[:settings.max_videos_per_restaurant]

def fetch_instagram_videos(username: str, days_back: int = 30) -> List[Dict]:
    """
    Convenience function to fetch Instagram videos.
    
    Args:
        username: Instagram username (without @)
        days_back: How many days back to look for videos
        
    Returns:
        List of video metadata dictionaries
    """
    # Optional fast path: skip Instagram GraphQL and discover shortcodes via web search
    if settings.skip_ig_graphql:
        print("⚙️ SKIP_IG_GRAPHQL enabled – using web search for shortcodes")
        videos = _discover_shortcodes_via_search(username, days_back)
        if videos:
            return videos
        print("   ⚠️ Web search returned no shortcodes, falling back to Instaloader")

    fetcher = InstagramVideoFetcher()
    videos = fetcher.get_all_videos(username, days_back)
    if not videos:
        # Fallback: try web search-based discovery if GraphQL path yielded nothing
        print("   ⚠️ No videos from GraphQL; attempting web search for shortcodes")
        return _discover_shortcodes_via_search(username, days_back)
    return videos

def _discover_shortcodes_via_search(username: str, days_back: int = 30) -> List[Dict]:
    """Discover recent Instagram post shortcodes for a user via web search (Firecrawl).

    Returns minimal video dicts: shortcode, url, approximate date, flags.
    """
    try:
        from firecrawl import FirecrawlApp
    except Exception:
        print("   ⚠️ Firecrawl not available for shortcode discovery")
        return []

    if not settings.firecrawl_api_key:
        print("   ⚠️ FIRECRAWL_API_KEY not set")
        return []

    print(f"🔎 Discovering shortcodes via web search for @{username} (skip GraphQL)")
    app = FirecrawlApp(api_key=settings.firecrawl_api_key)

    queries = [
        f"site:instagram.com/p {username}",
        f"site:instagram.com/reel {username}",
        f"{username} instagram"
    ]

    found: List[Dict] = []
    seen: set = set()
    for q in queries:
        try:
            resp = app.search(query=q, limit=5)

            # Firecrawl SDK may return a Pydantic model (e.g., SearchResponse) or a dict
            if resp is None:
                items = []
            elif hasattr(resp, "data"):
                items = getattr(resp, "data", [])
            elif isinstance(resp, dict):
                items = resp.get("data", [])
            else:
                items = []

            for item in items:
                # item may be dict or model; support both
                url = item.get("url", "") if isinstance(item, dict) else getattr(item, "url", "")
                m = re.search(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)/?", url)
                if not m:
                    continue
                shortcode = m.group(1)
                if shortcode in seen:
                    continue
                seen.add(shortcode)
                found.append({
                    "shortcode": shortcode,
                    "url": f"https://www.instagram.com/p/{shortcode}/",
                    "date": datetime.now(),  # approximate recency
                })
        except Exception as e:
            print(f"   ❌ Firecrawl search failed: {e}")

    # Vet shortcodes to ensure they are actually videos using yt-dlp metadata (no download)
    # Reduce fan-out: limit number of candidates to verify
    max_cands = max(1, settings.max_verification_candidates)
    candidates = found[:max_cands]
    print(f"   🔎 Verifying {len(candidates)} shortcodes are videos (limited to {max_cands})...")
    verified: List[Dict] = []
    for item in candidates:
        sc = item["shortcode"]
        is_video = _is_shortcode_video(sc)
        is_author_ok = True if not settings.verify_author else _is_shortcode_by_author(sc, username)
        if is_video and is_author_ok:
            item.update({
                "is_video": True,
                "typename": "video",
                "url": f"https://www.instagram.com/p/{sc}/",
            })
            verified.append(item)
            if settings.verify_author:
                print(f"      ✅ Video confirmed from @{username}: {sc}")
            else:
                print(f"      ✅ Video confirmed (author unchecked): {sc}")
        else:
            print(f"      ❌ Skipped (not video or not by @{username}): {sc}")

    # Sort newest first and limit
    verified.sort(key=lambda x: x["date"], reverse=True)
    return verified[: settings.max_videos_per_restaurant]

def _is_shortcode_video(shortcode: str) -> bool:
    """Return True if shortcode URL resolves to a video according to yt-dlp formats metadata."""
    try:
        urls = [
            f"https://www.instagram.com/p/{shortcode}/",
            f"https://www.instagram.com/reel/{shortcode}/",
        ]
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            # Modern desktop UA helps Instagram serve full responses
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        }
        # Attach cookies if available (prefer explicit env; fallback to default path used in prod)
        default_cookies_path = "/app/secrets/insta_cookies.txt"
        if settings.ig_cookies_file and os.path.exists(settings.ig_cookies_file):
            ydl_opts["cookiefile"] = settings.ig_cookies_file
        elif os.path.exists("/app/secrets/insta_cookies.txt"):
            ydl_opts["cookiefile"] = "/app/secrets/insta_cookies.txt"
        elif settings.ig_cookies_from_browser:
            # Support formats like "chrome" or "chrome:Default"
            parts = settings.ig_cookies_from_browser.split(":", 1)
            browser = parts[0].strip()
            profile = parts[1].strip() if len(parts) > 1 and parts[1] else None
            # yt-dlp accepts variable-length tuple: (browser[, profile[, keyring[, browserdir]]])
            ydl_opts["cookiesfrombrowser"] = (browser,) if not profile else (browser, profile)
        ydl = YoutubeDL(ydl_opts)
        for u in urls:
            try:
                info = ydl.extract_info(u, download=False)
                if not info:
                    continue
                # Direct video
                if info.get("formats"):
                    return True
                # Carousel/playlist: check entries for any video
                entries = info.get("entries") or []
                for entry in entries:
                    if entry and entry.get("formats"):
                        return True
            except Exception:
                continue
    except Exception:
        pass
    return False

def _is_shortcode_by_author(shortcode: str, username: str) -> bool:
    """Return True if yt-dlp reports the uploader as the given username."""
    try:
        urls = [
            f"https://www.instagram.com/p/{shortcode}/",
            f"https://www.instagram.com/reel/{shortcode}/",
        ]
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        }
        if settings.ig_cookies_file and os.path.exists(settings.ig_cookies_file):
            ydl_opts["cookiefile"] = settings.ig_cookies_file
        elif os.path.exists("/app/secrets/insta_cookies.txt"):
            ydl_opts["cookiefile"] = "/app/secrets/insta_cookies.txt"
        elif settings.ig_cookies_from_browser:
            parts = settings.ig_cookies_from_browser.split(":", 1)
            browser = parts[0].strip()
            profile = parts[1].strip() if len(parts) > 1 and parts[1] else None
            ydl_opts["cookiesfrombrowser"] = (browser,) if not profile else (browser, profile)
        ydl = YoutubeDL(ydl_opts)
        target = username.strip().lstrip('@').lower()
        for u in urls:
            try:
                info = ydl.extract_info(u, download=False)
                if not info:
                    continue
                # Check top-level
                uploader = (info.get("uploader") or info.get("creator") or "").strip().lower()
                uploader_id = (info.get("uploader_id") or info.get("channel_id") or "").strip().lower()
                uploader_url = (info.get("uploader_url") or info.get("channel_url") or "").strip().lower()
                def matches(u, uid, url):
                    return (
                        (u == target) or
                        (uid == target) or
                        (target and url and target in url)
                    )
                if matches(uploader, uploader_id, uploader_url):
                    return True
                # Check entries for carousels
                entries = info.get("entries") or []
                for entry in entries:
                    eu = (entry.get("uploader") or entry.get("creator") or "").strip().lower() if isinstance(entry, dict) else ""
                    euid = (entry.get("uploader_id") or entry.get("channel_id") or "").strip().lower() if isinstance(entry, dict) else ""
                    eurl = (entry.get("uploader_url") or entry.get("channel_url") or "").strip().lower() if isinstance(entry, dict) else ""
                    if matches(eu, euid, eurl):
                        return True
            except Exception:
                continue
    except Exception:
        pass
    return False

def download_instagram_video(shortcode: str, download_path: str = "downloads/videos") -> bool:
    """
    Convenience function to download a video by shortcode.
    
    Args:
        shortcode: Instagram post shortcode
        download_path: Directory to save the video
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"📥 Downloading Instagram video {shortcode}...")
        
        # Create download directory
        os.makedirs(download_path, exist_ok=True)
        
        # Create a simple loader just for downloading
        loader = instaloader.Instaloader(
            download_videos=True,
            download_pictures=False,
            download_video_thumbnails=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False
        )
        
        # Get the post and download it
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        loader.download_post(post, target=download_path)
        
        print(f"✅ Successfully downloaded video {shortcode}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to download video {shortcode}: {e}")
        return False