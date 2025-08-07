"""Configuration management for the restaurant video analysis system."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Instagram credentials
    instagram_username: str = os.getenv("INSTAGRAM_USERNAME", "")
    instagram_password: str = os.getenv("INSTAGRAM_PASSWORD", "")
    
    # Twilio credentials
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_phone_number: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    
    # OpenAI API key
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    
    # Firecrawl API key
    firecrawl_api_key: str = os.getenv("FIRECRAWL_API_KEY", "")
    
    # Google Search API (for finding Instagram handles)
    google_search_api_key: str = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    google_search_cx: str = os.getenv("GOOGLE_SEARCH_CX", "")
    
    # Firecrawl API (for web scraping and search)
    firecrawl_api_key: str = os.getenv("FIRECRAWL_API_KEY", "")
    
    # File paths
    downloads_dir: Path = Path("downloads")
    videos_dir: Path = Path("downloads/videos")
    frames_dir: Path = Path("downloads/frames")
    
    # Rate limiting settings (more conservative to avoid detection)
    instagram_delay_seconds: float = 5.0  # Increased from 2.0
    max_videos_per_restaurant: int = 3     # Reduced from 5
    max_concurrent_downloads: int = 2      # Reduced from 3
    instagram_max_posts_check: int = 30    # Limit posts to check
    instagram_retry_attempts: int = 3      # Number of retry attempts
    
    # Video analysis settings
    frames_per_second: int = 1  # Extract 1 frame per second for analysis
    max_video_duration_seconds: int = 60  # Skip videos longer than 1 minute
    
    class Config:
        env_file = ".env"

# Global settings instance
settings = Settings()

# Create necessary directories
settings.downloads_dir.mkdir(exist_ok=True)
settings.videos_dir.mkdir(exist_ok=True)
settings.frames_dir.mkdir(exist_ok=True)