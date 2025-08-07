"""Test script to verify system setup and configuration."""

import os
import sys
from pathlib import Path
import importlib

def test_dependencies():
    """Test if all required dependencies are installed."""
    required_packages = [
        'requests', 'instaloader', 'openai', 'twilio', 
        'dotenv', 'bs4', 'selenium',
        'cv2', 'PIL', 'moviepy', 'pydantic'
    ]
    
    print("Testing dependencies...")
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'cv2':
                import cv2
            elif package == 'PIL':
                import PIL
            elif package == 'dotenv':
                import dotenv
            elif package == 'bs4':
                import bs4
            else:
                importlib.import_module(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    print("All dependencies installed!")
    return True

def test_environment():
    """Test environment variable configuration."""
    print("\nTesting environment variables...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = {
        'INSTAGRAM_USERNAME': 'Instagram username',
        'INSTAGRAM_PASSWORD': 'Instagram password', 
        'TWILIO_ACCOUNT_SID': 'Twilio Account SID',
        'TWILIO_AUTH_TOKEN': 'Twilio Auth Token',
        'TWILIO_PHONE_NUMBER': 'Twilio Phone Number',
        'OPENAI_API_KEY': 'OpenAI API Key'
    }
    
    optional_vars = {
        'GOOGLE_SEARCH_API_KEY': 'Google Search API Key',
        'GOOGLE_SEARCH_CX': 'Google Custom Search Engine ID'
    }
    
    missing_required = []
    
    for var, description in required_vars.items():
        if os.getenv(var):
            print(f"✅ {var} ({description})")
        else:
            print(f"❌ {var} ({description})")
            missing_required.append(var)
    
    for var, description in optional_vars.items():
        if os.getenv(var):
            print(f"✅ {var} ({description}) - Optional")
        else:
            print(f"⚠️ {var} ({description}) - Optional, but recommended")
    
    if missing_required:
        print(f"\nMissing required environment variables: {', '.join(missing_required)}")
        print("Create a .env file with these variables.")
        return False
    
    print("Required environment variables configured!")
    return True

def test_directories():
    """Test if required directories can be created."""
    print("\nTesting directory creation...")
    
    try:
        from config import settings
        
        # Test directory creation
        test_dirs = [
            settings.downloads_dir,
            settings.videos_dir,
            settings.frames_dir
        ]
        
        for directory in test_dirs:
            if directory.exists():
                print(f"✅ {directory} exists")
            else:
                directory.mkdir(parents=True, exist_ok=True)
                print(f"✅ {directory} created")
        
        # Test write permissions
        test_file = settings.downloads_dir / "test_write.txt"
        test_file.write_text("test")
        test_file.unlink()
        print("✅ Write permissions OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Directory test failed: {e}")
        return False

def test_modules():
    """Test if custom modules can be imported."""
    print("\nTesting custom modules...")
    
    modules = [
        'config', 'web_search', 'instagram_client', 
        'video_downloader', 'video_analyzer', 'sms_notifier', 'main'
    ]
    
    failed_modules = []
    
    for module in modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module}")
        except Exception as e:
            print(f"❌ {module}: {e}")
            failed_modules.append(module)
    
    if failed_modules:
        print(f"\nFailed to import: {', '.join(failed_modules)}")
        return False
    
    print("All modules imported successfully!")
    return True

def test_api_connections():
    """Test API connections (optional - requires valid credentials)."""
    print("\nTesting API connections (optional)...")
    
    try:
        # Test OpenAI
        from config import settings
        if settings.openai_api_key:
            import openai
            client = openai.OpenAI(api_key=settings.openai_api_key)
            # Just test client creation, not actual API call
            print("✅ OpenAI client created")
        else:
            print("⚠️ OpenAI API key not set")
        
        # Test Twilio
        if all([settings.twilio_account_sid, settings.twilio_auth_token]):
            from twilio.rest import Client
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            print("✅ Twilio client created")
        else:
            print("⚠️ Twilio credentials not set")
        
        return True
        
    except Exception as e:
        print(f"⚠️ API connection test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Restaurant Video Analysis System - Setup Test")
    print("=" * 50)
    
    tests = [
        ("Dependencies", test_dependencies),
        ("Environment Variables", test_environment), 
        ("Directories", test_directories),
        ("Custom Modules", test_modules),
        ("API Connections", test_api_connections)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 30)
        
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"SETUP TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ System is ready to use!")
        print("\nNext steps:")
        print("1. Configure your .env file with API credentials")
        print("2. Test with a single restaurant: python cli.py single --name 'Test Restaurant' --address '123 Test St' --phone '+1234567890'")
    else:
        print("❌ Setup incomplete. Please fix the issues above.")
    
    print("=" * 50)

if __name__ == "__main__":
    main()