"""Configuration management for the restaurant video analysis system."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    # Pydantic v2 settings config
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # Instagram credentials
    instagram_username: str = os.getenv("INSTAGRAM_USERNAME", "")
    instagram_password: str = os.getenv("INSTAGRAM_PASSWORD", "")
    
    # Twilio credentials
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_phone_number: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    
    # OpenAI API key
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    
    # Firecrawl API key (single source)
    firecrawl_api_key: str = os.getenv("FIRECRAWL_API_KEY", "")
    
    # Google Search API (for finding Instagram handles)
    google_search_api_key: str = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    google_search_cx: str = os.getenv("GOOGLE_SEARCH_CX", "")
    
    # Feature flags
    # Skip Instagram GraphQL (Instaloader) and discover shortcodes via web search instead
    skip_ig_graphql: bool = os.getenv("SKIP_IG_GRAPHQL", "false").lower() == "true"
    
    # File paths
    downloads_dir: Path = Path("downloads")
    videos_dir: Path = Path("downloads/videos")
    frames_dir: Path = Path("downloads/frames")
    
    # Rate limiting settings (more conservative to avoid detection)
    instagram_delay_seconds: float = 6.0  # Slightly slower pacing
    max_videos_per_restaurant: int = int(os.getenv("MAX_VIDEOS_PER_RESTAURANT", "10"))     # Target more videos per run
    max_concurrent_downloads: int = 2      # Reduced from 3
    instagram_max_posts_check: int = 30    # Limit posts to check
    instagram_retry_attempts: int = 3      # Number of retry attempts
    
    # Video analysis settings
    frames_per_second: int = 1  # Extract 1 frame per second for analysis
    max_video_duration_seconds: int = 60  # Skip videos longer than 1 minute
    
    # yt-dlp cookies (improves access to gated Instagram content)
    ig_cookies_file: str = os.getenv("IG_COOKIES_FILE", "")  # Path to Netscape cookies.txt
    ig_cookies_from_browser: str = os.getenv("IG_COOKIES_FROM_BROWSER", "")  # e.g., 'chrome', 'safari', 'firefox'
    
    # Verification fan-out limit (how many candidate shortcodes to probe)
    max_verification_candidates: int = int(os.getenv("MAX_VERIFICATION_CANDIDATES", "8"))
    # Toggle author verification for Instagram shortcodes
    verify_author: bool = os.getenv("VERIFY_AUTHOR", "false").lower() == "true"
    # Avoid using Instaloader GraphQL fallback in prod (prevents blocks)
    disable_instaloader_fallback: bool = os.getenv("DISABLE_INSTALOADER_FALLBACK", "true").lower() == "true"
    
    # Logging and debug
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Note: Pydantic v2 uses model_config; do not define inner Config

# Global settings instance
settings = Settings()

# Create necessary directories
settings.downloads_dir.mkdir(exist_ok=True)
settings.videos_dir.mkdir(exist_ok=True)
settings.frames_dir.mkdir(exist_ok=True)