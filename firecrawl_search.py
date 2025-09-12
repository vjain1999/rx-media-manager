"""Firecrawl-based web search for finding restaurant Instagram handles."""

import asyncio
import time
from typing import Optional
import contextlib
import openai
import re
from config import settings
from openai_client import make_openai_client

try:
    from firecrawl import AsyncFirecrawlApp, ScrapeOptions
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    print("⚠️ Firecrawl not available. Install with: pip install firecrawl-py")

_last_fc_call_sync: float = 0.0
# Adaptive throttling state (based on server rate-limit headers / 429s)
_OPENAI_COOLDOWN_UNTIL: float = 0.0
_FIRECRAWL_COOLDOWN_UNTIL: float = 0.0
_fc_thread_lock = None
def _get_fc_thread_lock():
    import threading
    global _fc_thread_lock
    if _fc_thread_lock is None:
        _fc_thread_lock = threading.Lock()
    return _fc_thread_lock

async def _parse_location_components_async(address: str) -> dict:
    """Async version of LLM-based address parsing."""
    try:
        client = make_openai_client(async_client=True)
        prompt = f"""Parse this address into components. Return only valid JSON.

Address: {address}

Extract:
- street: street number and name
- city: city name
- state: state abbreviation (2 letters)
- zip: zip code if present
- neighborhood: neighborhood/area if mentioned

Return JSON format:
{{"street": "value", "city": "value", "state": "value", "zip": "value", "neighborhood": "value"}}

Only include fields that have actual values. Use null for missing information."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Extract JSON from response
        import json
        start = result_text.find('{')
        end = result_text.rfind('}') + 1
        
        if start != -1 and end != -1:
            json_str = result_text[start:end]
            parsed = json.loads(json_str)
            
            # Clean and validate the parsed data
            location = {'raw_address': address}
            for key in ['street', 'city', 'state', 'zip', 'neighborhood']:
                value = parsed.get(key)
                if value and value.lower() not in ['null', 'none', 'n/a', '']:
                    location[key] = str(value).strip()
            
            return location
        
    except Exception as e:
        print(f"   ⚠️ Async address parsing failed: {e}")
    
    # Fallback to regex
    city_match = re.search(r',\s*([^,]+),\s*([A-Z]{2})', address)
    if city_match:
        return {
            'city': city_match.group(1).strip(),
            'state': city_match.group(2).strip(),
            'raw_address': address
        }
    return {'raw_address': address}

async def firecrawl_search_restaurant_instagram(restaurant_name: str, address: str, phone: str) -> tuple[Optional[str], dict]:
    """
    Enhanced Firecrawl search with location context and validation data.
    
    Args:
        restaurant_name: Name of the restaurant
        address: Restaurant address  
        phone: Restaurant phone number
        
    Returns:
        Tuple of (Instagram handle, validation_data dict)
    """
    
    if not FIRECRAWL_AVAILABLE:
        print("   ⚠️ Firecrawl not available, skipping")
        return None, {}
        
    if not settings.firecrawl_api_key:
        print("   ⚠️ Firecrawl API key not configured, skipping")
        return None, {}
    
    if not settings.openai_api_key:
        print("   ⚠️ OpenAI API key not configured, skipping")
        return None, {}
    
    # Parse location components using LLM
    location = await _parse_location_components_async(address)
    city = location.get('city', '')
    state = location.get('state', '')
    neighborhood = location.get('neighborhood', '')
    
    try:
        print(f"🔥 Using Firecrawl search for: {restaurant_name}")
        
        # Initialize Firecrawl
        app = AsyncFirecrawlApp(api_key=settings.firecrawl_api_key)
        
        # Balanced search queries - mix of general and location-specific
        search_queries = []
        
        # Start with direct Instagram searches (most likely to find handles)
        search_queries.extend([
            f'"{restaurant_name}" instagram',
            f'"{restaurant_name}" site:instagram.com',
            f'{restaurant_name} instagram handle'
        ])
        
        # Location-specific Instagram searches
        if city and state:
            search_queries.extend([
                f'"{restaurant_name}" {city} instagram',
                f'"{restaurant_name}" "{city}" {state} instagram social media'
            ])
        
        # Business directory searches (often have social media links)
        search_queries.extend([
            f'"{restaurant_name}" site:yelp.com',
            f'"{restaurant_name}" site:tripadvisor.com'
        ])
        
        # Address-specific searches (for verification)
        if address:
            search_queries.extend([
                f'"{restaurant_name}" "{address}" instagram',
                f'"{restaurant_name}" "{address}" social media'
            ])
        
        # Google My Business (for validation)
        if city and state:
            search_queries.append(f'site:google.com/maps "{restaurant_name}" {city} {state}')
        
        # Fallback if no location parsed
        if not city and not state:
            search_queries = [
                f'"{restaurant_name}" instagram',
                f'"{restaurant_name}" site:instagram.com',
                f'"{restaurant_name}" site:yelp.com',
                f'{restaurant_name} instagram handle'
            ]
        
        all_content = []
        validation_data = {
            'sources_checked': [],
            'location_matches': [],
            'google_my_business_found': False,
            'yelp_found': False,
            'tripadvisor_found': False,
            'queries_used': []
        }
        
        for i, query in enumerate(search_queries[:5]):  # Try first 5 queries
            print(f"   🔍 Firecrawl query {i+1}: {query}")
            
            try:
                # Search with Firecrawl using the search endpoint (rate limited in sync wrapper)
                response = await app.search(
                    query=query,
                    limit=3,  # Fewer results per query to try more queries
                    scrape_options=ScrapeOptions(
                        formats=["markdown"],
                        only_main_content=True
                    )
                )
                
                if response and response.get('success') and response.get('data'):
                    results_count = len(response['data'])
                    print(f"   📋 Query {i+1} found {results_count} results")
                    # Verbose: list result URLs and titles
                    for idx, item in enumerate(response['data']):
                        title = (item.get('title') or '')[:120]
                        url = item.get('url') or ''
                        print(f"      {i+1}.{idx+1} • {title} | {url}")
                    
                    # Track validation data
                    validation_data['queries_used'].append(query)
                    
                    # Extract content and track sources
                    content = _extract_content_from_response(response, validation_data, city, state)
                    if content:
                        all_content.append(content)
                else:
                    print(f"   ❌ Query {i+1} returned no results")
                    
            except Exception as query_error:
                msg = str(query_error)
                if '429' in msg or 'rate limit' in msg.lower():
                    # Backoff on rate limit using Retry-After header if available
                    retry_after = _extract_retry_after_seconds(query_error) or 12
                    global _FIRECRAWL_COOLDOWN_UNTIL
                    _FIRECRAWL_COOLDOWN_UNTIL = time.time() + retry_after
                    print(f"   ⚠️ Firecrawl rate-limited. Backing off {retry_after}s...")
                    await asyncio.sleep(retry_after)
                else:
                    print(f"   ❌ Query {i+1} failed: {query_error}")
                continue
        
        if not all_content:
            print("   ❌ No content found in any Firecrawl results")
            return None, validation_data
        
        # Combine all content and analyze with OpenAI
        combined_content = "\n\n".join(all_content)
        # Verbose: list candidate handles seen in combined content
        candidates = _extract_candidate_handles(combined_content)
        if candidates:
            print(f"   🔎 Candidate handles (regex): {sorted(list(candidates))[:12]}")
        handle = await _analyze_content_with_openai(combined_content, restaurant_name, address)
        
        if handle:
            print(f"   ✅ Firecrawl + OpenAI found handle: @{handle}")
            return handle, validation_data
        else:
            print("   ❌ No Instagram handle found in Firecrawl results")
            return None, validation_data
            
    except Exception as e:
        print(f"   ❌ Firecrawl search failed: {e}")
        return None, {}
    finally:
        # Ensure Firecrawl client closes its async resources before loop closes
        try:
            if 'app' in locals() and hasattr(app, 'aclose'):
                await app.aclose()  # type: ignore
        except Exception:
            pass

def _extract_content_from_response(response, validation_data: dict = None, city: str = "", state: str = "") -> Optional[str]:
    """Extract relevant content from Firecrawl search response."""
    try:
        if not response or not response.get('success'):
            return None
            
        data = response.get('data', [])
        if not data:
            return None
        
        content_parts = []
        for item in data:
            # Get title and description from search result
            title = item.get('title', '')
            description = item.get('description', '')
            url = item.get('url', '')
            markdown = item.get('markdown', '')
            
            # Track validation data if provided
            if validation_data is not None:
                validation_data['sources_checked'].append(url)
                
                # Check for Google My Business
                if 'google.com/maps' in url or 'google.com/search' in url:
                    validation_data['google_my_business_found'] = True
                
                # Check for other important sources
                if 'yelp.com' in url:
                    validation_data['yelp_found'] = True
                if 'tripadvisor.com' in url:
                    validation_data['tripadvisor_found'] = True
                
                # Check for location matches in content
                all_text = f"{title} {description} {markdown}".lower()
                if city and city.lower() in all_text:
                    validation_data['location_matches'].append(f"city:{city}")
                if state and state.lower() in all_text:
                    validation_data['location_matches'].append(f"state:{state}")
            
            # Combine all available text
            item_content = []
            if title:
                item_content.append(f"Title: {title}")
            if description:
                item_content.append(f"Description: {description}")
            if url:
                item_content.append(f"URL: {url}")
            if markdown and len(markdown) > 50:  # Only include if substantial
                item_content.append(f"Content: {markdown[:1000]}")  # Limit content length
            
            if item_content:
                content_parts.append("\n".join(item_content))
        
        return "\n\n---\n\n".join(content_parts) if content_parts else None
        
    except Exception as e:
        print(f"   ❌ Content extraction failed: {e}")
        return None

async def _analyze_content_with_openai(content: str, restaurant_name: str, address: str) -> Optional[str]:
    """Analyze search content with OpenAI to find Instagram handle."""
    try:
        client = make_openai_client(async_client=True)
        
        # Truncate content if too long (keep first 4000 chars)
        if len(content) > 4000:
            content = content[:4000] + "..."
        
        prompt = f"""You are analyzing web search results to find the Instagram handle for a restaurant.

Restaurant: {restaurant_name}
Address: {address}

Search results to analyze:
{content}

Look for Instagram links, handles, or social media mentions. Extract ONLY the Instagram handle (username) without the @ symbol.

Rules:
- Look for patterns like "instagram.com/[handle]", "@[handle]", or "Follow us @[handle]"
- Return ONLY the handle part (e.g., if you see "instagram.com/johndoe", return "johndoe")
- If you find multiple handles, choose the one most likely to be the restaurant's official account
- If no Instagram handle is found, return "NOT_FOUND"
- Do not include @, instagram.com, or any other text - just the handle

 Location weighting (very important):
 - Strongly prefer handles that clearly match the provided address/city/neighborhood in their profile or page context.
 - If there is a location-specific handle (e.g., antonios_of_beacon_hill_) and a corporate/brand-wide handle (e.g., antoniosrestaurants), choose the location-specific handle.
 - Prefer usernames that include the restaurant name plus city/neighborhood tokens when available.
 - Only choose a corporate or brand-wide account if no location-specific handle exists and the brand clearly maps to this merchant.

 Use each result's Description field:
 - The content contains entries with Title, Description, and URL per result. Treat Description as a strong source of location evidence.
 - If a Description includes the exact street address or the correct city/neighborhood, prefer the associated handle over others.
 - Deprioritize handles tied to Descriptions mentioning a different city/state or unrelated location.

Restaurant Instagram handle:"""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Using faster, cheaper model for this task
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0
        )
        
        result = response.choices[0].message.content.strip()
        
        if result and result != "NOT_FOUND" and len(result) > 0:
            # Clean the result
            handle = re.sub(r'[^a-zA-Z0-9._]', '', result)
            if handle and len(handle) > 0:
                print(f"   🔍 Handle extraction: {handle}")
                # If LLM picked something not present in regex candidates, note it
                cands = _extract_candidate_handles(content)
                if handle.lower() not in cands:
                    print(f"   ⚠️ LLM-picked handle not in regex candidates: {handle}")
                return handle
        
        print(f"   🔍 Handle extraction: NOT_FOUND")
        return None
        
    except Exception as e:
        # Adaptive backoff on OpenAI rate limit / connection issues
        msg = str(e)
        if any(k in msg.lower() for k in ['429', 'rate limit', 'retry-after']):
            retry_after = _extract_retry_after_seconds(e) or 15
            global _OPENAI_COOLDOWN_UNTIL
            _OPENAI_COOLDOWN_UNTIL = time.time() + retry_after
            print(f"   ⚠️ OpenAI rate-limited. Backing off {retry_after}s...")
        elif any(k in msg.lower() for k in ['connection error', 'connect timeout', 'read timeout', 'service unavailable', 'bad gateway']):
            print("   ⚠️ OpenAI connection issue. Backing off 5s...")
            _OPENAI_COOLDOWN_UNTIL = time.time() + 5
        else:
            print(f"   ❌ OpenAI analysis failed: {e}")
        return None
    finally:
        # Ensure HTTPX async client is closed before event loop ends
        try:
            if 'client' in locals() and hasattr(client, 'close'):
                with contextlib.suppress(Exception):
                    await client.close()
        except Exception:
            pass

def _extract_candidate_handles(text: str) -> set[str]:
    """Extract possible IG handles via regex from text (urls and mentions)."""
    candidates: set[str] = set()
    try:
        # instagram.com/<handle>
        for m in re.findall(r"instagram\.com/([A-Za-z0-9._]+)", text, flags=re.I):
            candidates.add(m.lower())
        # @handle mentions
        for m in re.findall(r"@([A-Za-z0-9._]{2,})", text):
            candidates.add(m.lower())
    except Exception:
        pass
    return candidates

def firecrawl_search_restaurant_instagram_sync(restaurant_name: str, address: str, phone: str) -> tuple[Optional[str], dict]:
    """Synchronous wrapper for the async Firecrawl search function.

    Prefer asyncio.run for proper loop lifecycle; fall back to manual loop only if needed.
    """
    try:
        # Simple global rate limit ≤ 1 rps using thread lock
        import time, random
        lock = _get_fc_thread_lock()
        with lock:
            global _last_fc_call_sync
            now = time.time()
            elapsed = now - _last_fc_call_sync
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed + random.uniform(0.05, 0.25))
            _last_fc_call_sync = time.time()

        # Preferred: asyncio.run handles setup/teardown safely
        try:
            return asyncio.run(firecrawl_search_restaurant_instagram(restaurant_name, address, phone))
        except RuntimeError as re:
            # If already within a running loop (rare in threadpool), fallback
            if 'asyncio.run() cannot be called from a running event loop' in str(re).lower():
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(firecrawl_search_restaurant_instagram(restaurant_name, address, phone))
                finally:
                    try:
                        pending = asyncio.all_tasks(loop)
                        if pending:
                            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                        loop.close()
                    except Exception:
                        pass
            else:
                raise
    except Exception as e:
        print(f"   ❌ Firecrawl sync wrapper failed: {e}")
        return None, {}

# ===== Adaptive throttling helpers =====
def _parse_retry_after_header(value: str) -> float:
    try:
        # Numeric seconds
        secs = float(value)
        if secs >= 0:
            return secs
    except Exception:
        pass
    # HTTP-date not handled; fallback
    return 0.0

def _extract_retry_after_seconds(exc: Exception) -> float:
    """Attempt to extract Retry-After seconds from exceptions with response headers."""
    try:
        # httpx / requests style
        resp = getattr(exc, 'response', None)
        headers = getattr(resp, 'headers', None)
        if headers and isinstance(headers, dict):
            ra = headers.get('Retry-After') or headers.get('retry-after')
            if ra:
                secs = _parse_retry_after_header(ra)
                if secs > 0:
                    return secs
        # OpenAI SDK may attach metadata
        hdrs = getattr(exc, 'headers', None)
        if hdrs and isinstance(hdrs, dict):
            ra = hdrs.get('Retry-After') or hdrs.get('retry-after')
            if ra:
                secs = _parse_retry_after_header(ra)
                if secs > 0:
                    return secs
    except Exception:
        pass
    return 0.0

def get_rate_cooldowns() -> tuple[float, float]:
    """Return remaining cooldown seconds for (openai, firecrawl)."""
    now = time.time()
    openai_rem = max(0.0, _OPENAI_COOLDOWN_UNTIL - now)
    firecrawl_rem = max(0.0, _FIRECRAWL_COOLDOWN_UNTIL - now)
    return openai_rem, firecrawl_rem