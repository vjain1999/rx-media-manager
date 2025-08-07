# Restaurant Video Analysis System

An automated system that finds, analyzes, and approves restaurant Instagram videos for DoorDash store pages.

## Features

1. **Web Search**: Automatically finds Instagram handles from restaurant name and address
2. **Instagram Integration**: Fetches recent videos using Instagram credentials (rate-limited)
3. **Video Download**: Downloads videos efficiently with concurrent processing
4. **AI Analysis**: Uses LLM (GPT-4 Vision) to analyze video quality for marketing use
5. **SMS Notifications**: Sends Twilio SMS to restaurants for video approval
6. **Modular Design**: Each component can be used independently

## Pipeline Overview

```
Restaurant Info → Find Instagram → Fetch Videos → Download → Analyze Quality → SMS Approval
```

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**: Create a `.env` file with:
   ```env
   # Instagram credentials
   INSTAGRAM_USERNAME=your_instagram_username
   INSTAGRAM_PASSWORD=your_instagram_password

   # Twilio credentials
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TWILIO_PHONE_NUMBER=your_twilio_phone_number

   # OpenAI API key for video analysis
   OPENAI_API_KEY=your_openai_api_key

   # Google Custom Search (optional, for better Instagram discovery)
   GOOGLE_SEARCH_API_KEY=your_google_search_api_key
   GOOGLE_SEARCH_CX=your_custom_search_engine_id
   ```

## Usage

### Command Line Interface

**Process a single restaurant:**
```bash
python cli.py single \
  --name "Joe's Pizza" \
  --address "123 Main St, New York, NY" \
  --phone "+1234567890" \
  --days-back 30 \
  --min-score 7.0
```

**Process multiple restaurants from file:**
```bash
python cli.py batch \
  --file example_restaurants.json \
  --days-back 30 \
  --min-score 7.0 \
  --output results.json
```

### Python API

```python
from main import RestaurantVideoProcessor

processor = RestaurantVideoProcessor()

# Process single restaurant
result = processor.process_restaurant(
    restaurant_name="Mama Rosa's Pizza",
    address="123 Main St, New York, NY 10001", 
    phone="+1234567890",
    days_back=30,
    min_quality_score=7.0
)

# Process multiple restaurants
restaurants = [
    {"name": "Restaurant 1", "address": "Address 1", "phone": "Phone 1"},
    {"name": "Restaurant 2", "address": "Address 2", "phone": "Phone 2"}
]
results = processor.process_restaurants_batch(restaurants)
```

## Module Documentation

### `web_search.py`
- Finds Instagram handles using Google Custom Search and DuckDuckGo
- Verifies handles by checking if restaurant name appears on the profile
- Fallback strategies for robust discovery

### `instagram_client.py`
- Uses `instaloader` library for Instagram API access
- Rate-limited requests to avoid getting blocked
- Fetches both regular posts and Reels
- Handles private profiles and authentication

### `video_downloader.py`
- Concurrent video downloads with configurable limits
- Verifies downloaded files for corruption
- Cleanup utilities for failed downloads

### `video_analyzer.py`
- Extracts representative frames from videos
- Uses GPT-4 Vision for quality analysis
- Scores videos on multiple criteria:
  - Food quality (1-10)
  - Visual appeal (1-10)
  - Professionalism (1-10)
  - Brand safety (1-10)
  - Marketing value (1-10)

### `sms_notifier.py`
- Sends SMS via Twilio to restaurant phone numbers
- Includes video URLs and quality scores
- Handles both approval requests and "no videos found" notifications

### `config.py`
- Centralized configuration management
- Environment variable loading
- Directory creation and path management

## Rate Limiting & Anti-Detection

- **Instagram**: Uses authenticated requests with delays between calls
- **Web Search**: Rotates between search engines and includes delays
- **API Calls**: Rate-limited OpenAI and Twilio requests
- **Downloads**: Concurrent but limited simultaneous downloads

## Output Files

- **Individual Results**: `results/{restaurant_name}_{timestamp}.json`
- **Batch Results**: `results/batch_results_{timestamp}.json`
- **Downloaded Videos**: `downloads/videos/`
- **Extracted Frames**: `downloads/frames/` (temporary)

## Quality Scoring

Videos are scored on 5 criteria (1-10 scale):
1. **Food Quality**: How appetizing the food looks
2. **Visual Appeal**: Lighting, composition, aesthetics
3. **Professionalism**: Production quality
4. **Brand Safety**: Appropriate for food delivery platform
5. **Marketing Value**: Effectiveness for attracting customers

Videos need both a high overall score AND "APPROVE" recommendation to be selected.

## Error Handling

- Graceful handling of private/non-existent Instagram profiles
- Retry logic for failed downloads
- Comprehensive error logging and reporting
- Continues processing other restaurants if one fails

## Security Considerations

- API keys stored in environment variables
- No hardcoded credentials in source code
- Rate limiting to respect service limits
- User-agent rotation for web scraping

## Troubleshooting

**Instagram Login Issues**:
- Verify credentials in `.env` file
- Instagram may require 2FA - use app passwords
- Consider using Instagram Basic Display API for production

**Video Download Failures**:
- Check internet connection
- Instagram may block direct video URLs after time
- Try reducing concurrent download limit

**LLM Analysis Errors**:
- Verify OpenAI API key and credits
- Check video file integrity
- Reduce frame extraction rate if hitting token limits

**SMS Delivery Issues**:
- Verify Twilio credentials and phone number format
- Check that restaurant phone numbers include country code
- Ensure Twilio account has sufficient credits