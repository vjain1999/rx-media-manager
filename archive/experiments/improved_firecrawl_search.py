"""Improved Firecrawl-based web search for finding restaurant Instagram handles."""

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

class ImprovedFirecrawlInstagramFinder:
    """Enhanced Firecrawl-based Instagram handle finder with improved prompts and search strategies."""
    
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

    def _generate_optimized_search_queries(self, restaurant_name: str, address: str, phone: str) -> List[Dict[str, str]]:
        """Generate optimized search queries with specific targeting strategies."""
        
        # Parse location from address
        location_info = self._parse_location_simple(address)
        city = location_info.get('city', '')
        state = location_info.get('state', '')
        
        queries = []
        
        # Strategy 1: Direct Instagram searches with high precision
        queries.extend([
            {
                "query": f'"{restaurant_name}" site:instagram.com',
                "strategy": "direct_instagram",
                "priority": "high"
            },
            {
                "query": f'"{restaurant_name}" instagram handle social media',
                "strategy": "social_media_mention",
                "priority": "high"
            }
        ])
        
        # Strategy 2: Location-specific searches
        if city and state:
            queries.extend([
                {
                    "query": f'"{restaurant_name}" "{city}" {state} instagram',
                    "strategy": "location_specific",
                    "priority": "high"
                },
                {
                    "query": f'"{restaurant_name}" {city} site:instagram.com',
                    "strategy": "location_instagram",
                    "priority": "medium"
                }
            ])
        
        # Strategy 3: Business directory searches (often contain social links)
        queries.extend([
            {
                "query": f'"{restaurant_name}" site:yelp.com instagram social',
                "strategy": "business_directory",
                "priority": "medium"
            },
            {
                "query": f'"{restaurant_name}" site:tripadvisor.com social media',
                "strategy": "business_directory",
                "priority": "medium"
            },
            {
                "query": f'"{restaurant_name}" site:google.com/maps instagram',
                "strategy": "google_business",
                "priority": "medium"
            }
        ])
        
        # Strategy 4: Address-specific validation searches
        if address:
            queries.append({
                "query": f'"{restaurant_name}" "{address}" instagram social',
                "strategy": "address_validation",
                "priority": "low"
            })
        
        # Strategy 5: Alternative name patterns
        # Handle common restaurant name variations
        alt_names = self._generate_name_variations(restaurant_name)
        for alt_name in alt_names[:2]:  # Limit to 2 variations
            queries.append({
                "query": f'"{alt_name}" instagram {city}',
                "strategy": "name_variation",
                "priority": "low"
            })
        
        return queries
    
    def _generate_name_variations(self, restaurant_name: str) -> List[str]:
        """Generate common variations of restaurant names."""
        variations = []
        
        # Remove common suffixes/prefixes
        name_clean = restaurant_name
        
        # Remove location indicators in parentheses
        name_clean = re.sub(r'\s*\([^)]*\)\s*', ' ', name_clean).strip()
        
        # Remove common words
        common_words = ['restaurant', 'bar', 'grill', 'kitchen', 'cafe', 'bistro', 'eatery']
        for word in common_words:
            if word.lower() in name_clean.lower():
                variation = re.sub(r'\b' + word + r'\b', '', name_clean, flags=re.IGNORECASE).strip()
                if variation and variation != name_clean:
                    variations.append(variation)
        
        # Handle apostrophes and special characters
        if "'" in name_clean:
            variations.append(name_clean.replace("'", ""))
        
        # Handle "&" vs "and"
        if "&" in name_clean:
            variations.append(name_clean.replace("&", "and"))
        elif "and" in name_clean.lower():
            variations.append(re.sub(r'\band\b', '&', name_clean, flags=re.IGNORECASE))
        
        return list(set(variations))  # Remove duplicates
    
    def _parse_location_simple(self, address: str) -> Dict[str, str]:
        """Simple regex-based location parsing."""
        location = {'raw_address': address}
        
        # Extract city, state pattern: "City, State ZIP"
        city_state_match = re.search(r',\s*([^,]+),\s*([A-Z]{2})\s*\d*', address)
        if city_state_match:
            location['city'] = city_state_match.group(1).strip()
            location['state'] = city_state_match.group(2).strip()
        
        return location
    
    async def search_instagram_handle(self, restaurant_name: str, address: str, phone: str) -> Tuple[Optional[str], Dict]:
        """Enhanced search for Instagram handles with improved strategies."""
        
        if not self.app or not self.openai_client:
            return None, {"error": "Firecrawl or OpenAI not available"}
        
        print(f"🔥 Enhanced Firecrawl search for: {restaurant_name}")
        
        queries = self._generate_optimized_search_queries(restaurant_name, address, phone)
        
        # Prioritize queries by priority level
        high_priority = [q for q in queries if q['priority'] == 'high']
        medium_priority = [q for q in queries if q['priority'] == 'medium']
        low_priority = [q for q in queries if q['priority'] == 'low']
        
        all_results = []
        validation_data = {
            'queries_executed': [],
            'strategies_used': [],
            'sources_found': [],
            'location_signals': 0,
            'confidence_indicators': []
        }
        
        # Execute high priority queries first
        for query_info in high_priority[:3]:  # Limit to top 3 high priority
            result = await self._execute_search_query(query_info, validation_data)
            if result:
                all_results.extend(result)
        
        # If no strong results, try medium priority
        if not all_results or len(all_results) < 2:
            for query_info in medium_priority[:2]:  # Limit to top 2 medium priority
                result = await self._execute_search_query(query_info, validation_data)
                if result:
                    all_results.extend(result)
        
        # Analyze all results with improved prompt
        if all_results:
            handle = await self._analyze_results_with_enhanced_prompt(
                all_results, restaurant_name, address, validation_data
            )
            return handle, validation_data
        
        return None, validation_data
    
    async def _execute_search_query(self, query_info: Dict, validation_data: Dict) -> Optional[List[Dict]]:
        """Execute a single search query with enhanced scraping options."""
        
        query = query_info['query']
        strategy = query_info['strategy']
        
        print(f"   🔍 Query ({strategy}): {query}")
        
        try:
            # Enhanced scrape options based on strategy
            scrape_options = self._get_scrape_options_for_strategy(strategy)
            
            response = await self.app.search(
                query=query,
                limit=3,  # Keep limit reasonable for speed
                scrape_options=scrape_options
            )
            
            if response and response.get('success') and response.get('data'):
                results = response['data']
                print(f"   ✅ Found {len(results)} results")
                
                # Track query execution
                validation_data['queries_executed'].append(query)
                validation_data['strategies_used'].append(strategy)
                
                # Process and enrich results
                processed_results = []
                for result in results:
                    processed_result = self._process_search_result(result, strategy, validation_data)
                    if processed_result:
                        processed_results.append(processed_result)
                
                return processed_results
            else:
                print(f"   ❌ No results for query")
                return None
                
        except Exception as e:
            if '429' in str(e) or 'rate limit' in str(e).lower():
                print("   ⚠️ Rate limited, backing off...")
                await asyncio.sleep(10)
            else:
                print(f"   ❌ Query failed: {e}")
            return None
    
    def _get_scrape_options_for_strategy(self, strategy: str) -> ScrapeOptions:
        """Get optimized scrape options based on search strategy."""
        
        base_options = {
            "formats": ["markdown"],
            "onlyMainContent": True,
            "timeout": 15000,  # 15 second timeout
            "waitFor": 2000    # Wait 2 seconds for dynamic content
        }
        
        # Strategy-specific optimizations
        if strategy == "direct_instagram":
            # For Instagram pages, we want to capture social media links and bio info
            base_options.update({
                "includeTags": ["a", "div.bio", "div.header", "span.social"],
                "formats": ["markdown", "html"]  # Include HTML for link extraction
            })
        
        elif strategy == "business_directory":
            # For Yelp, TripAdvisor, etc., focus on business info and social links
            base_options.update({
                "includeTags": ["a", "div.social", "div.contact", "section.business-info"],
                "excludeTags": ["nav", "footer", "aside.ads"]
            })
        
        elif strategy == "google_business":
            # For Google My Business, focus on business details
            base_options.update({
                "includeTags": ["div.place-desc", "div.social", "a[href*='instagram']"],
                "excludeTags": ["nav", "header", "footer"]
            })
        
        return ScrapeOptions(**base_options)
    
    def _process_search_result(self, result: Dict, strategy: str, validation_data: Dict) -> Optional[Dict]:
        """Process and enrich a single search result."""
        
        url = result.get('url', '')
        title = result.get('title', '')
        description = result.get('description', '')
        markdown = result.get('markdown', '')
        html = result.get('html', '')
        
        # Track source types
        if 'instagram.com' in url:
            validation_data['sources_found'].append('instagram')
        elif 'yelp.com' in url:
            validation_data['sources_found'].append('yelp')
        elif 'tripadvisor.com' in url:
            validation_data['sources_found'].append('tripadvisor')
        elif 'google.com' in url:
            validation_data['sources_found'].append('google')
        
        # Extract potential Instagram handles from HTML if available
        instagram_links = []
        if html:
            instagram_links = re.findall(r'instagram\.com/([a-zA-Z0-9._]+)', html)
        
        # Combine all text content
        all_text = f"{title} {description} {markdown}"
        
        return {
            'url': url,
            'title': title,
            'description': description,
            'content': markdown,
            'html_content': html,
            'strategy': strategy,
            'instagram_links_found': instagram_links,
            'all_text': all_text
        }
    
    async def _analyze_results_with_enhanced_prompt(self, results: List[Dict], restaurant_name: str, address: str, validation_data: Dict) -> Optional[str]:
        """Analyze search results with an enhanced, more sophisticated prompt."""
        
        # Prepare context from results
        context_parts = []
        instagram_links_found = set()
        
        for i, result in enumerate(results, 1):
            context_parts.append(f"""
Result {i} (Strategy: {result['strategy']}):
URL: {result['url']}
Title: {result['title']}
Description: {result['description']}
Content: {result['content'][:800]}...
Instagram Links Found: {result['instagram_links_found']}
""")
            instagram_links_found.update(result['instagram_links_found'])
        
        combined_context = "\n".join(context_parts)
        
        # Enhanced prompt with few-shot examples and chain-of-thought reasoning
        enhanced_prompt = f"""You are an expert at finding official Instagram handles for restaurants from web search results.

RESTAURANT DETAILS:
Name: {restaurant_name}
Address: {address}

SEARCH RESULTS TO ANALYZE:
{combined_context}

DIRECT INSTAGRAM LINKS FOUND: {list(instagram_links_found)}

TASK: Find the official Instagram handle for this restaurant.

REASONING PROCESS:
1. First, examine any direct Instagram links found in the HTML
2. Look for official social media mentions in business directories (Yelp, Google, TripAdvisor)
3. Check if the handle matches the restaurant name and location
4. Verify the handle seems legitimate (not spam, appropriate follower count if mentioned)

EXAMPLES OF GOOD MATCHES:
- Restaurant: "Joe's Pizza" in NYC → Handle: "joespizzanyc" ✓
- Restaurant: "Mama Rosa's Italian" → Handle: "mamarosasitalian" ✓
- Restaurant: "The Blue Door Bistro" → Handle: "bluedoorbistro" ✓

EXAMPLES OF BAD MATCHES:
- Restaurant in Boston → Handle with "london" or "la" in name ✗
- Generic handles like "foodlover123" or "restaurant_pics" ✗
- Handles that don't match the business name at all ✗

CONFIDENCE INDICATORS:
- Handle appears on official business directory (Yelp, Google Business) = HIGH confidence
- Handle matches restaurant name pattern = HIGH confidence  
- Handle mentions location that matches restaurant = HIGH confidence
- Handle found on random blog or social post = LOW confidence

INSTRUCTIONS:
1. Analyze each result systematically
2. If you find a handle, explain your reasoning
3. Rate your confidence: HIGH, MEDIUM, or LOW
4. Return format: "HANDLE: [username]" or "NOT_FOUND"

Your analysis:"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",  # Use more capable model for better reasoning
                messages=[{"role": "user", "content": enhanced_prompt}],
                max_tokens=200,
                temperature=0.1  # Slight temperature for creativity in reasoning
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract handle and confidence from response
            handle_match = re.search(r'HANDLE:\s*([a-zA-Z0-9._]+)', result_text)
            confidence_match = re.search(r'confidence[:\s]+(HIGH|MEDIUM|LOW)', result_text, re.IGNORECASE)
            
            if handle_match:
                handle = handle_match.group(1)
                confidence = confidence_match.group(1).upper() if confidence_match else "UNKNOWN"
                
                validation_data['confidence_indicators'].append(f"AI_confidence: {confidence}")
                validation_data['ai_reasoning'] = result_text
                
                print(f"   🎯 Enhanced AI found: @{handle} (Confidence: {confidence})")
                return handle
            
            elif "NOT_FOUND" in result_text:
                print(f"   ❌ Enhanced AI found no handle")
                validation_data['ai_reasoning'] = result_text
                return None
            
            else:
                print(f"   ⚠️ Unclear AI response: {result_text[:100]}...")
                return None
                
        except Exception as e:
            print(f"   ❌ Enhanced AI analysis failed: {e}")
            return None

# Async context manager usage function
async def enhanced_firecrawl_search(restaurant_name: str, address: str, phone: str) -> Tuple[Optional[str], Dict]:
    """Enhanced Firecrawl search with improved prompts and strategies."""
    
    async with ImprovedFirecrawlInstagramFinder() as finder:
        return await finder.search_instagram_handle(restaurant_name, address, phone)

# Synchronous wrapper for integration with existing code
def enhanced_firecrawl_search_sync(restaurant_name: str, address: str, phone: str) -> Tuple[Optional[str], Dict]:
    """Synchronous wrapper for enhanced Firecrawl search."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(enhanced_firecrawl_search(restaurant_name, address, phone))
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
        print(f"   ❌ Enhanced Firecrawl sync wrapper failed: {e}")
        return None, {"error": str(e)}

if __name__ == "__main__":
    # Test the enhanced search
    import asyncio
    
    async def test_enhanced_search():
        test_cases = [
            ("Davio's Northern Italian Steakhouse", "75 Arlington St, Boston, MA 02116, USA", ""),
            ("Oppa Sushi", "185 Harvard Avenue, Allston, MA 02134, USA", ""),
            ("Joe's American Bar & Grill", "181 Newbury St, Boston, MA 02116, USA", "")
        ]
        
        for name, address, phone in test_cases:
            print(f"\n{'='*60}")
            print(f"Testing: {name}")
            print(f"{'='*60}")
            
            handle, data = await enhanced_firecrawl_search(name, address, phone)
            
            print(f"Result: {handle}")
            print(f"Validation data: {data}")
    
    # Run test if this file is executed directly
    # asyncio.run(test_enhanced_search())
