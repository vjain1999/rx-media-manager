# Restaurant Video Analysis System - Setup Guide

## System Overview

This system automatically:
1. **Finds Instagram handles** from restaurant name/address
2. **Fetches recent videos** using Instagram credentials  
3. **Downloads videos** efficiently
4. **Analyzes quality** using GPT-4 Vision
5. **Sends SMS** to restaurants for approval

## Quick Start

### 1. Environment Setup

The virtual environment and dependencies are already installed. To activate:

```bash
source venv/bin/activate
```

### 2. Configure API Keys

Create a `.env` file with your credentials:

```env
# Instagram credentials (required)
INSTAGRAM_USERNAME=your_instagram_username
INSTAGRAM_PASSWORD=your_instagram_password

# Twilio credentials (required for SMS)
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# OpenAI API key (required for video analysis)
OPENAI_API_KEY=sk-your-openai-api-key

# Google Search (optional but recommended)
GOOGLE_SEARCH_API_KEY=your_google_api_key
GOOGLE_SEARCH_CX=your_custom_search_engine_id
```

### 3. Test Setup

```bash
source venv/bin/activate
python test_setup.py
```

## Usage Examples

### Command Line

**Single restaurant:**
```bash
python cli.py single \
  --name "Joe's Pizza" \
  --address "123 Main St, New York, NY" \
  --phone "+1234567890" \
  --days-back 30 \
  --min-score 7.0
```

**Batch processing:**
```bash
python cli.py batch --file example_restaurants.json --min-score 7.0
```

### Python API

```python
from main import RestaurantVideoProcessor

processor = RestaurantVideoProcessor()

# Single restaurant
result = processor.process_restaurant(
    restaurant_name="Test Restaurant",
    address="123 Test St, Test City, TC",
    phone="+1234567890"
)

# Multiple restaurants
restaurants = [
    {"name": "Restaurant 1", "address": "Address 1", "phone": "Phone 1"},
    {"name": "Restaurant 2", "address": "Address 2", "phone": "Phone 2"}
]
results = processor.process_restaurants_batch(restaurants)
```

## Rate Limiting & Anti-Detection

- **Instagram**: Authenticated requests with 2-second delays
- **Downloads**: Maximum 3 concurrent downloads
- **API Calls**: 2-second delays between LLM requests
- **SMS**: 1-second delays between messages

## Output Files

- **Individual results**: `results/{restaurant_name}_{timestamp}.json`
- **Batch results**: `results/batch_results_{timestamp}.json`
- **Videos**: `downloads/videos/{shortcode}.mp4`

## Quality Scoring

Videos are scored 1-10 on:
- **Food Quality**: How appetizing the food looks
- **Visual Appeal**: Lighting, composition, aesthetics  
- **Professionalism**: Production quality
- **Brand Safety**: Appropriate for delivery platform
- **Marketing Value**: Customer attraction effectiveness

## Troubleshooting

**Instagram Issues:**
- Verify credentials in `.env`
- Instagram may require app passwords for 2FA accounts
- Private profiles require following relationship

**Video Download Issues:**
- Check network connectivity
- Instagram video URLs may expire
- Reduce concurrent download limit if failing

**LLM Analysis Issues:**
- Verify OpenAI API key and account credits
- Videos over 60 seconds are skipped
- Large videos may hit token limits

**SMS Issues:**
- Phone numbers must include country code (+1 for US)
- Verify Twilio account has sufficient credits
- Check Twilio phone number is SMS-enabled

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Search    │───▶│ Instagram Client│───▶│ Video Downloader│
│ Find Instagram  │    │ Fetch Videos    │    │ Download Files  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌─────────────────┐             │
│  SMS Notifier   │◀───│ Video Analyzer  │◀────────────┘
│ Restaurant SMS  │    │ LLM Quality     │
└─────────────────┘    └─────────────────┘
```

## Security Notes

- All API keys stored in environment variables
- No credentials in source code
- Rate limiting respects service terms
- User-agent rotation for web requests

## Next Steps

1. **Configure `.env`** with your API credentials
2. **Test with a real restaurant** using the CLI
3. **Adjust quality thresholds** based on results
4. **Scale to batch processing** for multiple restaurants

The system is designed to be production-ready with proper error handling, rate limiting, and modular architecture.