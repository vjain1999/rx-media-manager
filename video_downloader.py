"""Video download module for Instagram videos."""

import requests
import os
from pathlib import Path
from typing import Dict, List, Optional
import concurrent.futures
from urllib.parse import urlparse
import hashlib
from config import settings
import time

class VideoDownloader:
    """Download Instagram videos with rate limiting and error handling."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Ensure download directory exists
        settings.videos_dir.mkdir(parents=True, exist_ok=True)
    
    def download_video(self, video_info: Dict) -> Optional[str]:
        """
        Download a single video.
        
        Args:
            video_info: Video metadata dictionary with 'video_url' and 'shortcode'
            
        Returns:
            Path to downloaded video file, or None if failed
        """
        try:
            video_url = video_info['video_url']
            shortcode = video_info['shortcode']
            
            # Create filename
            filename = f"{shortcode}.mp4"
            filepath = settings.videos_dir / filename
            
            # Skip if already downloaded
            if filepath.exists():
                print(f"Video {shortcode} already exists, skipping download")
                return str(filepath)
            
            print(f"Downloading video {shortcode}...")
            
            # Download with streaming to handle large files
            response = self.session.get(video_url, stream=True)
            response.raise_for_status()
            
            # Write file in chunks
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"Successfully downloaded {shortcode} to {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"Failed to download video {video_info.get('shortcode', 'unknown')}: {e}")
            return None
    
    def download_videos_batch(self, videos: List[Dict]) -> List[Dict]:
        """
        Download multiple videos with controlled concurrency.
        
        Args:
            videos: List of video metadata dictionaries
            
        Returns:
            List of video dictionaries with added 'local_path' field
        """
        downloaded_videos = []
        
        # Use ThreadPoolExecutor for concurrent downloads
        with concurrent.futures.ThreadPoolExecutor(max_workers=settings.max_concurrent_downloads) as executor:
            # Submit all download tasks
            future_to_video = {
                executor.submit(self.download_video, video): video 
                for video in videos
            }
            
            # Process completed downloads
            for future in concurrent.futures.as_completed(future_to_video):
                video = future_to_video[future]
                
                try:
                    local_path = future.result()
                    if local_path:
                        video['local_path'] = local_path
                        downloaded_videos.append(video)
                    
                    # Rate limiting between downloads
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"Error downloading video {video.get('shortcode', 'unknown')}: {e}")
        
        return downloaded_videos
    
    def verify_download(self, filepath: str) -> bool:
        """
        Verify that a downloaded video file is valid.
        
        Args:
            filepath: Path to the video file
            
        Returns:
            True if file is valid, False otherwise
        """
        try:
            # Check if file exists and has content
            if not os.path.exists(filepath):
                return False
            
            file_size = os.path.getsize(filepath)
            if file_size == 0:
                return False
            
            # Basic file type check (MP4 signature)
            with open(filepath, 'rb') as f:
                header = f.read(12)
                # Check for MP4 file signature
                if b'ftyp' in header:
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error verifying download {filepath}: {e}")
            return False
    
    def cleanup_failed_downloads(self):
        """Remove any incomplete or corrupted video files."""
        for filepath in settings.videos_dir.glob("*.mp4"):
            if not self.verify_download(str(filepath)):
                print(f"Removing corrupted file: {filepath}")
                try:
                    filepath.unlink()
                except Exception as e:
                    print(f"Failed to remove {filepath}: {e}")
    
    def get_video_info(self, filepath: str) -> Dict:
        """
        Get basic information about a downloaded video file.
        
        Args:
            filepath: Path to the video file
            
        Returns:
            Dictionary with video information
        """
        try:
            import cv2
            
            cap = cv2.VideoCapture(filepath)
            if not cap.isOpened():
                return {}
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0
            
            cap.release()
            
            return {
                'fps': fps,
                'frame_count': frame_count,
                'width': width,
                'height': height,
                'duration_seconds': duration,
                'file_size': os.path.getsize(filepath)
            }
            
        except Exception as e:
            print(f"Error getting video info for {filepath}: {e}")
            return {}

def download_instagram_videos(videos: List[Dict]) -> List[Dict]:
    """
    Convenience function to download Instagram videos.
    
    Args:
        videos: List of video metadata dictionaries
        
    Returns:
        List of video dictionaries with local file paths
    """
    downloader = VideoDownloader()
    return downloader.download_videos_batch(videos)