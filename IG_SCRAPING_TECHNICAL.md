# Instagram Scraping Architecture and Implementation Guide

This document explains exactly how the Instagram discovery, shortcode verification, and download pipeline works in this repository. It includes prompts, APIs/tools, configuration flags, rate‑limit protections, and recommended production settings.

## Scope and goals

- Input: merchant name and address (optionally phone)
- Output: recent Instagram video shortcodes and locally downloaded video files ready for quality analysis
- Constraints: minimize rate‑limit risk, avoid breaking ToS, use public information; prefer cookie‑based access over credentials

## End‑to‑end data flow

1) Handle discovery (web) → 2) Shortcode discovery/verification (IG URLs) → 3) Download (yt‑dlp) → 4) Quality analysis (LLM)

Core modules:
- Handle discovery: `web_search.py`, `firecrawl_search.py`, `gpt_native_search.py`
- Shortcode discovery and IG probing: `instagram_client.py`
- Video downloading: `ytdlp_downloader.py`
- Orchestration: `main.py`, `web_app.py`, `run_full_system_*.py`

## Components and internals

### 1) Handle discovery strategies (`web_search.py`)

Strategies (in order, feature‑flagged):
- Google Custom Search API (optional; requires GOOGLE_SEARCH_API_KEY/GOOGLE_SEARCH_CX)
- GPT‑4o “Responses API with web_search” helper (`gpt_native_search.py`)
- Firecrawl search + OpenAI extraction with location weighting (`firecrawl_search.py`)
- Google‑My‑Business heuristics (detect maps listings, social links)
- DuckDuckGo HTML scraping (no API key)

Verification and scoring:
- Soft AI verification `_ai_verify_handle(...)` using `gpt-4o-mini` with JSON verdict: plausible, confidence, reason
- Confidence grade composed from: discovery method, handle pattern quality, name similarity, minimal HTML checks, AI verdict
- Location weighting: prefers handles matching city/neighborhood; deprioritizes corporate if location‑specific exists

Rate‑limit protections:
- Small sleeps between strategies
- Firecrawl/OpenAI adaptive cooldowns on 429 via `get_rate_cooldowns()`

Key prompt (OpenAI extraction in Firecrawl path):
```
You are analyzing web search results to find the Instagram handle…
Rules: … Return ONLY the handle …
Location weighting (very important): …
```

Address parsing prompt (LLM, async):
```
Parse this address into components. Return only valid JSON …
```

### 2) Shortcode discovery and verification (`instagram_client.py`)

Default path (recommended in production):
- If `SKIP_IG_GRAPHQL=true`, skip Instaloader GraphQL entirely
- Use Firecrawl search to find recent `/p/<sc>` or `/reel/<sc>` URLs
- Verify each candidate shortcode without download using yt‑dlp metadata probe:
  - Headers set to modern desktop UA, `skip_download=True`, retries, socket timeouts
  - Prefer Instagram cookies via:
    - `IG_COOKIES_FILE` (Netscape format)
    - or `IG_COOKIES_FROM_BROWSER` (e.g., `chrome[:Profile]`)
  - Optional `VERIFY_AUTHOR=true` checks uploader fields (`uploader`, `uploader_id`, `uploader_url`) match handle
- Cap verification fan‑out via `MAX_VERIFICATION_CANDIDATES`

Fallback (disabled by default): Instaloader GraphQL
- Controlled by `DISABLE_INSTALOADER_FALLBACK` (default true)
- When enabled, uses `instaloader.Instaloader` with:
  - Custom UA, sleeps enabled, request timeouts, limited connection attempts
  - Session reuse via `session_{INSTAGRAM_USERNAME}` file
  - Per‑request pacing (3–7s jitter), hourly cap, exponential backoff on 429
  - Iterates `profile.get_posts()` with cut‑off by `days_back` and max posts
  - Video/reel detection via `is_video` and typename heuristics

### 3) Downloading videos (`ytdlp_downloader.py`)

- Downloads by shortcode; tries `/p/<sc>` then falls back to `/reel/<sc>` on error
- Strongly prefer cookie‑based access (`IG_COOKIES_FILE` or `IG_COOKIES_FROM_BROWSER`)
- Random jitter (≈2.5–6s) before downloads; retries minimal; modern UA headers
- Output template: `downloads/videos/<shortcode>.<ext>`

### 4) Video quality analysis (`video_analyzer.py`)

- Extracts a few frames with OpenCV (skips long videos > `max_video_duration_seconds`)
- Sends up to 3 frames to `gpt-4o` with structured JSON scoring prompt
- Returns scores, recommendation, highlights, identified food items

## Tools, APIs, and SDKs

- Firecrawl (`firecrawl-py`): async search and optional content scrape
- OpenAI via `openai` SDK, optionally routed through Portkey (`openai_client.py`)
- yt‑dlp (`yt_dlp`): metadata probes and downloads; supports cookies and browser extraction
- instaloader: GraphQL browsing with session reuse (fallback only)
- OpenCV (`cv2`): frame extraction

## Configuration and flags (`config.py`)

Environment highlights:
- OpenAI/Portkey: `OPENAI_API_KEY`, `USE_PORTKEY`, `PORTKEY_*`
- Firecrawl: `FIRECRAWL_API_KEY`
- Google CSE: `GOOGLE_SEARCH_API_KEY`, `GOOGLE_SEARCH_CX`
- IG cookies: `IG_COOKIES_FILE` or `IG_COOKIES_FROM_BROWSER`
- GraphQL path: `SKIP_IG_GRAPHQL=true`, `DISABLE_INSTALOADER_FALLBACK=true`
- Verification: `MAX_VERIFICATION_CANDIDATES`, `VERIFY_AUTHOR`
- Download/analysis paths: `downloads/`, `results/`

The web app also supports `IG_COOKIES_B64` (or chunked `IG_COOKIES_B64_1..N`) and decodes to `/app/secrets/insta_cookies.txt` on startup.

## Rate‑limit and anti‑detection measures

- Randomized delays and conservative request pacing
- Limited concurrency and starts‑per‑sec throttles in batch scripts
- Exponential backoff on 429 for Firecrawl/Instaloader
- Prefer metadata probes over full downloads to reduce fan‑out
- Session reuse for Instaloader

## Error handling patterns

- Distinguish network errors vs. rate limiting; adaptive cooldowns
- Strict bounding on posts scanned and candidates verified
- Gracefully degrade: if Firecrawl path yields nothing, optional fallback to Instaloader

## Prompts (verbatim excerpts)

OpenAI extraction in Firecrawl path (`_analyze_content_with_openai`):
```
… Look for Instagram links … Extract ONLY the Instagram handle (username) …
Location weighting (very important): … prefer location‑specific …
```

Async address parsing (`_parse_location_components_async`):
```
Parse this address into components. Return only valid JSON …
```

GPT Responses API (native search):
```
Find the Instagram handle for this restaurant by searching these specific sources: …
Return the exact Instagram handle … or NOT_FOUND
```

## Production recommendations

- Prefer cookie‑based access; avoid username/password flows
- Set `SKIP_IG_GRAPHQL=true` and `DISABLE_INSTALOADER_FALLBACK=true` in production
- Provide cookies via `IG_COOKIES_FILE` or chunked `IG_COOKIES_B64[_i]`
- Limit verification fan‑out: `MAX_VERIFICATION_CANDIDATES=6–8`
- Keep `starts-per-sec` ≤ 1.5 in dataset runs; cap workers based on upstream limits
- Monitor logs for 429s; honor cooldown hints

Security and compliance:
- Never commit cookies or keys; use env/volumes/secrets
- Scrape only publicly available content; respect platform policies

## Testing and validation

- Dry run handle extraction on a small CSV via `run_full_system_extract.py --terse`
- Use `run_full_system_golden.py` for precision/recall evaluation against a labeled dataset
- Verify downloads exist and pass basic file validation before analysis
