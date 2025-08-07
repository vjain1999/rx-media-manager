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

async def firecrawl_search_restaurant_instagram(restaurant_name: str, address: str, phone: str) -> Optional[str]:
    """
    Use Firecrawl to search for restaurant Instagram handle, then analyze with OpenAI.
    
    Args:
        restaurant_name: Name of the restaurant
        address: Restaurant address  
        phone: Restaurant phone number
        
    Returns:
        Instagram handle if found, None otherwise
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
    
    try:
        print(f"🔥 Using Firecrawl search for: {restaurant_name}")
        
        # Initialize Firecrawl
        app = AsyncFirecrawlApp(api_key=settings.firecrawl_api_key)
        
        # Create comprehensive search query targeting specific sites
        search_queries = [
            f"{restaurant_name} {address} instagram social media",
            f"{restaurant_name} {address} site:yelp.com",
            f"{restaurant_name} {address} site:tripadvisor.com",
            f"{restaurant_name} {address} site:opentable.com",
            f'"{restaurant_name}" "{address}" instagram',
            f"{restaurant_name} Mountain View instagram"  # Add city for broader search
        ]
        
        search_query = search_queries[0]  # Start with the first, most comprehensive query
        
        # Try multiple search queries until we find content with Instagram info
        all_content = []
        
        for i, query in enumerate(search_queries[:3]):  # Try first 3 queries
            print(f"   🔍 Firecrawl query {i+1}: {query}")
            
            # Search with Firecrawl
            response = await app.search(
                query=query,
                limit=3,  # Fewer results per query to try more queries
                scrape_options=ScrapeOptions(formats=['markdown'])
            )
            
            results_count = len(response.get('data', []))
            print(f"   📋 Query {i+1} found {results_count} results")
            
            # Extract content from this query
            content = _extract_content_from_response(response)
            if content:
                all_content.append(f"=== Search Query {i+1}: {query} ===\n{content}")
                
                # If we find content that mentions "instagram", we might have what we need
                if "instagram" in content.lower():
                    print(f"   ✅ Found Instagram mention in query {i+1}")
                    break
        
        # Combine all content
        combined_content = "\n\n".join(all_content)
        
        if not combined_content:
            print("   ❌ No content found in any Firecrawl results")
            return None
        
        # Use OpenAI to analyze the content and extract Instagram handle
        handle = await _analyze_content_with_openai(combined_content, restaurant_name, address, phone)
        
        if handle:
            print(f"   ✅ Firecrawl + OpenAI found handle: @{handle}")
            return handle
        else:
            print("   ❌ No Instagram handle found in Firecrawl results")
            return None
        
    except Exception as e:
        print(f"   ❌ Firecrawl search failed: {e}")
        return None

def _extract_content_from_response(response) -> str:
    """Extract relevant content from Firecrawl response."""
    try:
        content_parts = []
        
        if isinstance(response, dict) and 'data' in response:
            for item in response['data']:
                # Extract URL
                url = item.get('url', '')
                if url:
                    content_parts.append(f"URL: {url}")
                
                # Extract title
                title = item.get('title', '')
                if title:
                    content_parts.append(f"Title: {title}")
                
                # Extract content/markdown
                content = item.get('content', '') or item.get('markdown', '')
                if content:
                    # Limit content length to avoid token limits
                    content = content[:2000]  # First 2000 chars
                    content_parts.append(f"Content: {content}")
                
                content_parts.append("---")
        
        combined_content = "\n".join(content_parts)
        print(f"   📝 Extracted {len(combined_content)} characters of content")
        
        return combined_content
        
    except Exception as e:
        print(f"   ⚠️ Error extracting content: {e}")
        return ""

async def _analyze_content_with_openai(content: str, restaurant_name: str, address: str, phone: str) -> Optional[str]:
    """Use OpenAI to analyze the content and extract Instagram handle."""
    try:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        
        prompt = f"""
Extract the Instagram handle from these web search results for: {restaurant_name} at {address}

Web Search Results:
{content}

Look specifically for:
1. Instagram URLs like "instagram.com/username" or "instagram.com/@username"
2. Social media sections mentioning Instagram handles
3. "@username" mentions in social media contexts
4. Links to Instagram profiles
5. Text like "Follow us on Instagram: @username"
6. Business listings that include social media links

Return ONLY the Instagram handle (without @ symbol) if you find one that belongs to this specific restaurant.
If multiple handles are found, return the one that best matches this restaurant location.
Return "NOT_FOUND" if no Instagram handle exists for this restaurant.

Examples:
- If you see "instagram.com/crepevinerestaurants", return: crepevinerestaurants
- If you see "Follow us @bistro_sf", return: bistro_sf
- If you see multiple handles, pick the most relevant one
- If no handle found, return: NOT_FOUND

Handle only (no explanation):
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use mini for cost efficiency
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0
        )
        
        result = response.choices[0].message.content.strip()
        print(f"   🤖 OpenAI analysis result: {result}")
        
        if result and result.upper() != "NOT_FOUND":
            # Clean and validate the result
            handle = result.replace('@', '').strip()
            if handle and len(handle) >= 3 and len(handle) <= 30:
                return handle
        
        return None
        
    except Exception as e:
        print(f"   ❌ OpenAI analysis failed: {e}")
        return None

def firecrawl_search_restaurant_instagram_sync(restaurant_name: str, address: str, phone: str) -> Optional[str]:
    """Synchronous wrapper for the async Firecrawl search function."""
    try:
        # Run the async function
        return asyncio.run(firecrawl_search_restaurant_instagram(restaurant_name, address, phone))
    except Exception as e:
        print(f"   ❌ Firecrawl sync wrapper failed: {e}")
        return None