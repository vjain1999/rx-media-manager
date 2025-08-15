"""Firecrawl-based web search for finding restaurant Instagram handles."""

import asyncio
from typing import Optional
import openai
import re
from config import settings

try:
    from firecrawl import AsyncFirecrawlApp, ScrapeOptions
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    print("⚠️ Firecrawl not available. Install with: pip install firecrawl-py")

_fc_lock: Optional[asyncio.Lock] = None
_last_fc_call: float = 0.0

def _get_fc_lock() -> asyncio.Lock:
    global _fc_lock
    if _fc_lock is None:
        _fc_lock = asyncio.Lock()
    return _fc_lock

async def _fc_rate_limited_sleep():
    import time, random
    global _last_fc_call
    now = time.time()
    elapsed = now - _last_fc_call
    if elapsed < 1.0:
        await asyncio.sleep(1.0 - elapsed + random.uniform(0.05, 0.25))
    _last_fc_call = time.time()

async def firecrawl_search_restaurant_instagram(restaurant_name: str, address: str, phone: str) -> Optional[str]:
    """
    Use Firecrawl search to find restaurant Instagram handle, then analyze with OpenAI.
    
    Args:
        restaurant_name: Name of the restaurant
        address: Restaurant address  
        phone: Restaurant phone number
        
    Returns:
        Instagram handle (without @) if found, None otherwise
    """
    
    if not FIRECRAWL_AVAILABLE:
        print("   ⚠️ Firecrawl not available, skipping")
        return None
        
    if not settings.firecrawl_api_key:
        print("   ⚠️ Firecrawl API key not configured, skipping")
        return None
    
    if not settings.openai_api_key:
        print("   ⚠️ OpenAI API key not configured, skipping")
        return None
    
    # Extract city/location from address for better search
    city_match = re.search(r',\s*([^,]+),\s*[A-Z]{2}', address)
    city = city_match.group(1) if city_match else ""
    
    try:
        print(f"🔥 Using Firecrawl search for: {restaurant_name}")
        
        # Initialize Firecrawl
        app = AsyncFirecrawlApp(api_key=settings.firecrawl_api_key)
        
        # Create comprehensive search queries targeting specific sites
        search_queries = [
            f"{restaurant_name} {address} instagram social media",
            f"{restaurant_name} {address} site:yelp.com",
            f"{restaurant_name} {address} site:tripadvisor.com",
            f"{restaurant_name} {city} instagram handle",
            f"{restaurant_name} {city} social media profiles",
        ]
        
        all_content = []
        
        for i, query in enumerate(search_queries[:3]):  # Try first 3 queries
            print(f"   🔍 Firecrawl query {i+1}: {query}")
            
            try:
                # Global semaphore & rate limit ≤ 1 rps
                async with _get_fc_lock():
                    await _fc_rate_limited_sleep()
                    # Search with Firecrawl using the search endpoint
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
                    
                    # Extract content from this query
                    content = _extract_content_from_response(response)
                    if content:
                        all_content.append(content)
                else:
                    print(f"   ❌ Query {i+1} returned no results")
                    
            except Exception as query_error:
                msg = str(query_error)
                if '429' in msg or 'rate limit' in msg.lower():
                    # Backoff on rate limit
                    print("   ⚠️ Firecrawl rate-limited. Backing off 12s...")
                    await asyncio.sleep(12)
                else:
                    print(f"   ❌ Query {i+1} failed: {query_error}")
                continue
        
        if not all_content:
            print("   ❌ No content found in any Firecrawl results")
            return None
        
        # Combine all content and analyze with OpenAI
        combined_content = "\n\n".join(all_content)
        handle = await _analyze_content_with_openai(combined_content, restaurant_name, address)
        
        if handle:
            print(f"   ✅ Firecrawl + OpenAI found handle: @{handle}")
            return handle
        else:
            print("   ❌ No Instagram handle found in Firecrawl results")
            return None
            
    except Exception as e:
        print(f"   ❌ Firecrawl search failed: {e}")
        return None

def _extract_content_from_response(response) -> Optional[str]:
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
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        
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
                return handle
        
        print(f"   🔍 Handle extraction: NOT_FOUND")
        return None
        
    except Exception as e:
        print(f"   ❌ OpenAI analysis failed: {e}")
        return None

def firecrawl_search_restaurant_instagram_sync(restaurant_name: str, address: str, phone: str) -> Optional[str]:
    """Synchronous wrapper for the async Firecrawl search function."""
    try:
        # Use a persistent event loop to avoid 'event loop is closed' warnings
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if loop.is_running():
            # In case called from a running loop, create a new task and gather
            return loop.run_until_complete(firecrawl_search_restaurant_instagram(restaurant_name, address, phone))  # type: ignore
        else:
            return loop.run_until_complete(firecrawl_search_restaurant_instagram(restaurant_name, address, phone))
    except Exception as e:
        print(f"   ❌ Firecrawl sync wrapper failed: {e}")
        return None