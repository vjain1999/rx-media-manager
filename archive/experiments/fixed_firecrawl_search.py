#!/usr/bin/env python3
"""
Fixed Firecrawl search - Learning from the enhanced version's failures.
Key fixes: Simplified prompt, proven query patterns, better response parsing.
"""

import asyncio
from typing import Optional, List, Dict, Tuple
import openai
import re
from config import settings

try:
    from firecrawl import AsyncFirecrawlApp, ScrapeOptions
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    print("⚠️ Firecrawl not available. Install with: pip install firecrawl-py")

class FixedFirecrawlInstagramFinder:
    """Fixed Firecrawl finder that combines original system's reliability with speed improvements."""
    
    def __init__(self):
        self.app = None
        self.openai_client = None
    
    async def __aenter__(self):
        if FIRECRAWL_AVAILABLE and settings.firecrawl_api_key:
            self.app = AsyncFirecrawlApp(api_key=settings.firecrawl_api_key)
        if settings.openai_api_key:
            self.openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.app and hasattr(self.app, 'aclose'):
            try:
                await self.app.aclose()
            except Exception:
                pass
        if self.openai_client:
            try:
                await self.openai_client.close()
            except Exception:
                pass

    def _generate_proven_queries(self, restaurant_name: str, address: str) -> List[str]:
        """Generate queries using patterns proven to work in the original system."""
        
        # Parse location simply
        city_state_match = re.search(r',\s*([^,]+),\s*([A-Z]{2})', address)
        city = city_state_match.group(1).strip() if city_state_match else ""
        state = city_state_match.group(2).strip() if city_state_match else ""
        
        queries = []
        
        # PROVEN PATTERNS from original system (in order of effectiveness)
        queries.extend([
            f'"{restaurant_name}" instagram',  # Most effective from original
            f'{restaurant_name} instagram handle',  # Second most effective
        ])
        
        # Add site-specific searches (but keep them simple)
        queries.extend([
            f'site:instagram.com "{restaurant_name}"',
            f'"{restaurant_name}" site:yelp.com instagram',
        ])
        
        # Location-based searches (only if we have location)
        if city and state:
            queries.extend([
                f'"{restaurant_name}" {city} instagram',
                f'"{restaurant_name}" {city} {state} social media',
            ])
        
        # Address-specific (last resort)
        if address:
            queries.append(f'"{restaurant_name}" "{address}" instagram')
        
        return queries[:5]  # Limit to 5 most promising queries

    async def search_instagram_handle(self, restaurant_name: str, address: str, phone: str) -> Tuple[Optional[str], Dict]:
        """Search for Instagram handle using fixed approach."""
        
        if not self.app or not self.openai_client:
            return None, {"error": "Services not available"}
        
        print(f"🔧 Fixed Firecrawl search for: {restaurant_name}")
        
        queries = self._generate_proven_queries(restaurant_name, address)
        
        all_content = []
        validation_data = {
            'queries_used': [],
            'sources_found': [],
            'content_length': 0
        }
        
        # Execute queries sequentially with simple error handling
        for i, query in enumerate(queries, 1):
            print(f"   🔍 Query {i}: {query}")
            
            try:
                # Use SIMPLE scrape options (like original)
                response = await self.app.search(
                    query=query,
                    limit=3,
                    scrape_options=ScrapeOptions(
                        formats=["markdown"],
                        onlyMainContent=True,
                        timeout=15000
                    )
                )
                
                if response and response.get('success') and response.get('data'):
                    results = response['data']
                    print(f"   ✅ Found {len(results)} results")
                    
                    validation_data['queries_used'].append(query)
                    
                    # Extract content simply
                    for result in results:
                        content = self._extract_content_simple(result, validation_data)
                        if content:
                            all_content.append(content)
                else:
                    print(f"   ❌ No results")
                
                # Don't continue if we have enough content
                if len(all_content) >= 5:
                    break
                    
            except Exception as e:
                if '429' in str(e) or 'rate limit' in str(e).lower():
                    print("   ⚠️ Rate limited, backing off...")
                    await asyncio.sleep(8)
                else:
                    print(f"   ❌ Query failed: {e}")
                continue
        
        if not all_content:
            print("   ❌ No content found")
            return None, validation_data
        
        # Combine content and analyze with SIMPLE prompt
        combined_content = "\n\n".join(all_content)
        validation_data['content_length'] = len(combined_content)
        
        handle = await self._analyze_with_simple_prompt(combined_content, restaurant_name, address)
        
        if handle:
            print(f"   ✅ Fixed search found: @{handle}")
        else:
            print(f"   ❌ No handle extracted")
            
        return handle, validation_data
    
    def _extract_content_simple(self, result: Dict, validation_data: Dict) -> Optional[str]:
        """Simple content extraction like the original system."""
        
        url = result.get('url', '')
        title = result.get('title', '')
        description = result.get('description', '')
        markdown = result.get('markdown', '')
        
        # Track source types
        if 'instagram.com' in url:
            validation_data['sources_found'].append('instagram')
        elif 'yelp.com' in url:
            validation_data['sources_found'].append('yelp')
        elif 'google.com' in url:
            validation_data['sources_found'].append('google')
        
        # Simple content combination
        content_parts = []
        if title:
            content_parts.append(f"Title: {title}")
        if description:
            content_parts.append(f"Description: {description}")
        if url:
            content_parts.append(f"URL: {url}")
        if markdown:
            # Limit markdown content to prevent overload
            content_parts.append(f"Content: {markdown[:800]}")
        
        return "\n".join(content_parts) if content_parts else None
    
    async def _analyze_with_simple_prompt(self, content: str, restaurant_name: str, address: str) -> Optional[str]:
        """Analyze content with a SIMPLE, proven prompt design."""
        
        try:
            # Truncate content if too long
            if len(content) > 4000:
                content = content[:4000] + "..."
            
            # SIMPLE prompt based on what worked in original system
            simple_prompt = f"""Find the Instagram handle for this restaurant from the search results.

Restaurant: {restaurant_name}
Location: {address}

Search Results:
{content}

Look for:
- instagram.com/[handle] links
- @[handle] mentions  
- Social media sections mentioning Instagram

IMPORTANT: Return ONLY the handle (username without @) or "NOT_FOUND"
Examples: "joespizza" or "daviosrestaurant" or "NOT_FOUND"

Instagram handle:"""

            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Use same model as original for consistency
                messages=[{"role": "user", "content": simple_prompt}],
                max_tokens=50,  # Keep it short
                temperature=0   # Deterministic
            )
            
            result = response.choices[0].message.content.strip()
            
            # Simple parsing (like original)
            if result and result != "NOT_FOUND" and len(result) > 0:
                # Clean the result
                handle = re.sub(r'[^a-zA-Z0-9._]', '', result)
                if handle and len(handle) > 0:
                    print(f"   🔍 Extracted: {handle}")
                    return handle
            
            print(f"   🔍 Result: NOT_FOUND")
            return None
            
        except Exception as e:
            print(f"   ❌ Analysis failed: {e}")
            return None

# Async wrapper
async def fixed_firecrawl_search(restaurant_name: str, address: str, phone: str) -> Tuple[Optional[str], Dict]:
    """Fixed Firecrawl search that should work reliably."""
    async with FixedFirecrawlInstagramFinder() as finder:
        return await finder.search_instagram_handle(restaurant_name, address, phone)

# Sync wrapper for integration
def fixed_firecrawl_search_sync(restaurant_name: str, address: str, phone: str) -> Tuple[Optional[str], Dict]:
    """Synchronous wrapper for fixed Firecrawl search."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(fixed_firecrawl_search(restaurant_name, address, phone))
        finally:
            try:
                # Clean shutdown
                pending = asyncio.all_tasks(loop)
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
            except Exception:
                pass
    except Exception as e:
        print(f"   ❌ Fixed Firecrawl sync wrapper failed: {e}")
        return None, {"error": str(e)}

if __name__ == "__main__":
    # Quick test
    async def test():
        test_cases = [
            ("Davio's Northern Italian Steakhouse", "75 Arlington St, Boston, MA 02116, USA"),
            ("Joe's American Bar & Grill", "181 Newbury St, Boston, MA 02116, USA")
        ]
        
        for name, address in test_cases:
            print(f"\n{'='*50}")
            print(f"Testing: {name}")
            handle, data = await fixed_firecrawl_search(name, address, "")
            print(f"Result: {handle}")
            print(f"Data: {data}")
    
    # Uncomment to test:
    # asyncio.run(test())
