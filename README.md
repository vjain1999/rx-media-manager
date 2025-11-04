## Restaurant Video Analysis System

Automates discovery of restaurant Instagram accounts, collects recent videos, scores quality with AI, and prepares SMS outreach for approvals.

### High-level pipeline

Restaurant row → Find Instagram handle → Discover recent IG shortcodes → Download videos → LLM video quality review → Approved set → SMS preview/sending

## Components and data flow

- Instagram handle discovery: `web_search.py`, `firecrawl_search.py`, `gpt_native_search.py`
  - Multi-strategy: Google Custom Search (optional), DuckDuckGo HTML, Firecrawl+OpenAI, GPT-4o with web_search tool, and GMB heuristics
  - AI verification and confidence scoring, location-weighting, optional enhanced checks
- Shortcode discovery and verification: `instagram_client.py`
  - Default path: Firecrawl web search → extract shortcodes → verify with yt-dlp metadata (no download). Optional author check
  - Optional fallback: Instaloader GraphQL with conservative pacing and session reuse
- Download: `ytdlp_downloader.py`
  - Cookies-based access preferred; randomized delays; retry `/p` then `/reel`
- Analysis: `video_analyzer.py`
  - Extract frames (OpenCV), send to OpenAI Vision (gpt-4o), produce JSON scores and recommendation
- Orchestration: `main.py` (single restaurant), `run_full_system_extract.py` (handles-only), `run_full_system_golden.py` (evaluation)
- Web UI: `web_app.py` (Flask + Socket.IO) with progress and SMS preview

Outputs live under `results/` and downloads under `downloads/`.

## Setup

1) Install dependencies

```bash
pip install -r requirements.txt
```

2) Configure environment (.env)

```env
# OpenAI / Portkey
OPENAI_API_KEY=...
USE_PORTKEY=false
PORTKEY_BASE_URL=https://api.portkey.ai/v1
PORTKEY_VIRTUAL_KEY=
PORTKEY_API_KEY=

# Instagram scraping
SKIP_IG_GRAPHQL=true
DISABLE_INSTALOADER_FALLBACK=true
IG_COOKIES_FILE=/app/secrets/insta_cookies.txt
# or: IG_COOKIES_FROM_BROWSER=chrome[:Profile]
MAX_VERIFICATION_CANDIDATES=8
VERIFY_AUTHOR=false

# Handle discovery (optional)
GOOGLE_SEARCH_API_KEY=
GOOGLE_SEARCH_CX=
FIRECRAWL_API_KEY=

# SMS / misc
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
LOG_LEVEL=INFO
```

Cookie setup (production):
- Export Instagram cookies (Netscape format) and mount to `/app/secrets/insta_cookies.txt`, or pass base64 via `IG_COOKIES_B64[_i]` (web_app decodes on boot).

## Running

- Web UI with realtime progress and SMS preview:

```bash
python web_app.py
# open http://localhost:5000
```

- Extract handles only over a CSV (see script help for flags):

```bash
python run_full_system_extract.py --csv data/your_dataset.csv --workers 6 --starts-per-sec 1.5 --shuffle
```

- Extract handles with inline API keys (no .env):

```bash
# Edit keys at the top of run_full_system_extract_with_keys.py, then run:
python run_full_system_extract_with_keys.py \
  --csv data/your_dataset.csv \
  --workers 6 --starts-per-sec 1.5 --shuffle --enable-ddg \
  --output-prefix your_prefix
```

Notes:
- This runner sets keys inline and configures clients before imports (no os.environ).
- For networks blocking api.openai.com, set USE_PORTKEY=True in the file and add Portkey keys.

- Full golden-dataset evaluation:

```bash
python run_full_system_golden.py --csv data/golden_dataset.csv --workers 6 --starts-per-sec 1.5
```

- Programmatic single-restaurant run:

```python
from main import RestaurantVideoProcessor

processor = RestaurantVideoProcessor()
result = processor.process_restaurant(
    restaurant_name="Test Restaurant",
    address="123 Test St, Test City, TC 12345",
    phone="+1234567890",
    days_back=30,
    min_quality_score=7.0,
)
```

## Key implementation details

- Portkey routing for OpenAI supported via `USE_PORTKEY=true` (see `openai_client.py`).
- IG discovery prefers Firecrawl+OpenAI; strategies are throttled with adaptive cooldowns.
- Shortcode verification uses `yt-dlp` metadata only (no download) with modern UA and optional cookies.
- Instaloader path is hardened (session reuse, backoff) and disabled in prod by default.
- Video analysis uses gpt-4o with up to 3 frames per video and a structured JSON prompt.

## Rate limits and safety

- Starts-per-second throttles, exponential backoff on 429s, random jitters before downloads, and candidate-verification caps.
- Cookies are preferred over username/password for IG; avoid storing credentials; never commit secrets.

## Where to learn more

- Technical IG scraping deep dive: `IG_SCRAPING_TECHNICAL.md`
- Non-technical IG overview: `IG_SCRAPING_NON_TECHNICAL.md`