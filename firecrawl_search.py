"""Firecrawl-based web scraping for finding restaurant Instagram handles."""

import asyncio
from typing import Optional
import openai
import re
from config import settings

try:
    from firecrawl import FirecrawlApp
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    print("⚠️ Firecrawl not available. Install with: pip install firecrawl-py")

def firecrawl_search_restaurant_instagram_sync(restaurant_name: str, address: str, phone: str) -> Optional[str]:
    """
    Use Firecrawl to scrape relevant websites for restaurant Instagram handle, then analyze with OpenAI.
    
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
        print(f"🔥 Using Firecrawl scraping for: {restaurant_name}")
        
        # Initialize Firecrawl (sync version)
        app = FirecrawlApp(api_key=settings.firecrawl_api_key)
        
        # Create URLs to scrape for Instagram handles
        # We'll scrape some known restaurant directory sites
        scrape_urls = []
        
        # Add restaurant's potential website
        restaurant_search = f"{restaurant_name} {city}".replace(" ", "+")
        restaurant_domain = restaurant_name.lower().replace(" ", "").replace("'", "")
        
        # Common restaurant website patterns
        potential_websites = [
            f"https://www.{restaurant_domain}.com",
            f"https://{restaurant_domain}.com",
        ]
        
        # Try to scrape the restaurant's main website first
        scrape_urls.extend(potential_websites[:1])  # Try the first one
        
        all_content = []
        
        for i, url in enumerate(scrape_urls):
            print(f"   🔍 Firecrawl scraping URL {i+1}: {url}")
            
            try:
                # Scrape with Firecrawl
                response = app.scrape_url(
                    url=url,
                    formats=['markdown']
                )
                
                if response and 'content' in response:
                    content = response['content']
                    if content and len(content.strip()) > 100:  # Only include substantial content
                        all_content.append(content)
                        print(f"   📋 URL {i+1} scraped successfully ({len(content)} chars)")
                    else:
                        print(f"   ⚠️ URL {i+1} returned minimal content")
                else:
                    print(f"   ❌ URL {i+1} scraping failed - no content")
                    
            except Exception as url_error:
                print(f"   ❌ URL {i+1} scraping failed: {url_error}")
                continue
        
        if not all_content:
            print("   ❌ No content found from any Firecrawl scraping")
            return None
        
        # Combine all content and analyze with OpenAI
        combined_content = "\n\n".join(all_content)
        handle = _analyze_content_with_openai_sync(combined_content, restaurant_name, address)
        
        if handle:
            print(f"   ✅ Firecrawl + OpenAI found handle: @{handle}")
            return handle
        else:
            print("   ❌ No Instagram handle found in Firecrawl results")
            return None
            
    except Exception as e:
        print(f"   ❌ Firecrawl scraping failed: {e}")
        return None

def _analyze_content_with_openai_sync(content: str, restaurant_name: str, address: str) -> Optional[str]:
    """Analyze scraped content with OpenAI to find Instagram handle."""
    try:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        
        # Truncate content if too long (keep first 4000 chars)
        if len(content) > 4000:
            content = content[:4000] + "..."
        
        prompt = f"""You are analyzing web content to find the Instagram handle for a restaurant.

Restaurant: {restaurant_name}
Address: {address}

Content to analyze:
{content}

Look for Instagram links, handles, or social media mentions. Extract ONLY the Instagram handle (username) without the @ symbol.

Rules:
- Look for patterns like "instagram.com/[handle]", "@[handle]", or "Follow us @[handle]"
- Return ONLY the handle part (e.g., if you see "instagram.com/johndoe", return "johndoe")
- If you find multiple handles, choose the one most likely to be the restaurant's official account
- If no Instagram handle is found, return "NOT_FOUND"
- Do not include @, instagram.com, or any other text - just the handle

Restaurant Instagram handle:"""

        response = client.chat.completions.create(
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