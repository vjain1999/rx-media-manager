"""Web search module to find Instagram handles for restaurants."""

import requests
import re
from typing import Optional, List
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import time
from config import settings
from concurrent.futures import ThreadPoolExecutor, as_completed
import openai

class RestaurantInstagramFinder:
    """Find Instagram handles for restaurants using web search."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def find_instagram_handle(self, restaurant_name: str, address: str, phone: str = "") -> Optional[str]:
        """
        Find Instagram handle for a restaurant using multiple search strategies.
        
        Args:
            restaurant_name: Name of the restaurant
            address: Restaurant address
            phone: Restaurant phone number
            
        Returns:
            Instagram handle (without @) if found, None otherwise
        """
        print(f"🔍 Starting Instagram search for: {restaurant_name}")
        print(f"   Address: {address}")
        print(f"   Phone: {phone}")
        
        # Try multiple search strategies
        strategies = [
            ("Google Custom Search", self._search_with_google_custom_search),
            ("GPT-4 Web Search", self._search_with_gpt4),
            ("Firecrawl + OpenAI Search", self._search_with_firecrawl),
            ("DuckDuckGo Search", self._search_with_duckduckgo),
            ("Direct Instagram Search", self._search_direct_instagram)
        ]
        
        for strategy_name, strategy_func in strategies:
            try:
                print(f"\n🔎 Trying strategy: {strategy_name}")
                handle = strategy_func(restaurant_name, address, phone)
                if handle:
                    print(f"✅ {strategy_name} found handle: @{handle}")
                    
                    # Verify the handle
                    print(f"🔍 Verifying handle @{handle}...")
                    if self._verify_instagram_handle(handle, restaurant_name):
                        print(f"✅ Handle @{handle} verified successfully")
                        return handle
                    else:
                        print(f"❌ Handle @{handle} failed verification")
                        continue
                else:
                    print(f"❌ {strategy_name} found no results")
                
                time.sleep(1)  # Rate limiting between strategies
            except Exception as e:
                print(f"❌ {strategy_name} failed: {e}")
                continue
        
        print("❌ All search strategies exhausted, no valid handle found")
        return None

    def find_instagram_handles_bulk(self, rows: List[dict]) -> List[dict]:
        """Parallel bulk search for Instagram handles with AI verification and corporate retry."""
        results: List[dict] = []
        max_workers = max(1, settings.bulk_find_max_workers)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_row = {
                executor.submit(self._process_single_row, row): row for row in rows
            }
            for future in as_completed(future_to_row):
                try:
                    results.append(future.result())
                except Exception as e:
                    row = future_to_row[future]
                    results.append({
                        'business_id': row.get('business_id', ''),
                        'restaurant_name': row.get('restaurant_name', ''),
                        'address': row.get('address', ''),
                        'phone': row.get('phone', ''),
                        'instagram_handle': '',
                        'status': 'error',
                        'message': str(e)
                    })
        return results

    def _process_single_row(self, row: dict) -> dict:
        bid = (row.get('business_id') or '').strip()
        name = (row.get('restaurant_name') or '').strip()
        address = (row.get('address') or '').strip()
        phone = (row.get('phone') or '').strip()
        try:
            handle = self.find_instagram_handle(name, address, phone)
            status = 'ok' if handle else 'not_found'
            message = '' if handle else 'No handle found'
            # Retry: try finding corporate/global if no local found
            corp_handle = ''
            if not handle:
                corp_handle = self._discover_corporate_handle_via_firecrawl(name)
                if corp_handle:
                    handle = corp_handle
                    status = 'ok'
                    message = 'Using corporate/global account'
            # AI verification (soft validation)
            if handle and settings.use_ai_verification and settings.openai_api_key:
                verified, ai_reason = self._ai_verify_handle(name, address, handle)
                if not verified:
                    status = 'probable'
                    message = f'AI low confidence: {ai_reason}'
            return {
                'business_id': bid,
                'restaurant_name': name,
                'address': address,
                'phone': phone,
                'instagram_handle': handle or '',
                'status': status,
                'message': message
            }
        except Exception as e:
            return {
                'business_id': bid,
                'restaurant_name': name,
                'address': address,
                'phone': phone,
                'instagram_handle': '',
                'status': 'error',
                'message': str(e)
            }

    def _ai_verify_handle(self, restaurant_name: str, address: str, handle: str) -> tuple[bool, str]:
        """Use OpenAI to judge if handle plausibly matches the merchant."""
        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            prompt = (
                f"Merchant: {restaurant_name}\nAddress: {address}\nCandidate IG: @{handle}\n\n"
                "Does this Instagram handle plausibly represent this merchant (local or corporate)?"
                " Consider what you know about the brand and typical naming. Return JSON: {\n"
                "  \"plausible\": true|false,\n  \"confidence\": 0.0-1.0,\n  \"reason\": \"short\"\n}"
            )
            resp = client.chat.completions.create(
                model=settings.ai_verification_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            txt = resp.choices[0].message.content or "{}"
            import json as _json
            s = txt.find('{'); e = txt.rfind('}') + 1
            data = _json.loads(txt[s:e]) if s != -1 and e != -1 else {}
            plausible = bool(data.get('plausible', False))
            conf = float(data.get('confidence', 0))
            reason = str(data.get('reason', ''))
            return plausible and conf >= settings.ai_verification_min_confidence, reason
        except Exception as e:
            return True, f"AI verify skipped: {e}"

    def _discover_corporate_handle_via_firecrawl(self, restaurant_name: str) -> Optional[str]:
        """Use Firecrawl to search for a corporate/global IG handle when local is missing."""
        try:
            from firecrawl_search import firecrawl_search_restaurant_instagram_sync
            return firecrawl_search_restaurant_instagram_sync(restaurant_name, '', '')
        except Exception:
            return None
    
    def _search_with_gpt4(self, restaurant_name: str, address: str, phone: str) -> Optional[str]:
        """Search using GPT-4 with web search capabilities."""
        if not settings.openai_api_key:
            print("   ⚠️ OpenAI API key not configured, skipping GPT-4 search")
            return None
        
        try:
            from gpt_native_search import gpt_search_restaurant_instagram
            return gpt_search_restaurant_instagram(restaurant_name, address, phone)
        except Exception as e:
            print(f"   ❌ GPT-4 native search failed: {e}")
            return None
    
    def _search_with_firecrawl(self, restaurant_name: str, address: str, phone: str) -> Optional[str]:
        """Search using Firecrawl + OpenAI analysis."""
        try:
            from firecrawl_search import firecrawl_search_restaurant_instagram_sync
            return firecrawl_search_restaurant_instagram_sync(restaurant_name, address, phone)
        except Exception as e:
            print(f"   ❌ Firecrawl search failed: {e}")
            return None
    
    def _search_with_google_custom_search(self, restaurant_name: str, address: str, phone: str) -> Optional[str]:
        """Search using Google Custom Search API."""
        if not settings.google_search_api_key or not settings.google_search_cx:
            print("   ⚠️ Google Search API not configured, skipping")
            return None
            
        query = f'"{restaurant_name}" "{address}" instagram'
        print(f"   🔍 Google query: {query}")
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': settings.google_search_api_key,
            'cx': settings.google_search_cx,
            'q': query,
            'num': 10
        }
        
        response = self.session.get(url, params=params)
        print(f"   📡 Google API response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            print(f"   📋 Found {len(items)} search results")
            
            for i, item in enumerate(items):
                link = item.get('link', '')
                title = item.get('title', '')
                print(f"   📄 Result {i+1}: {title[:50]}...")
                print(f"        URL: {link}")
                
                if 'instagram.com' in link:
                    handle = self._extract_instagram_handle_from_url(link)
                    if handle:
                        print(f"   ✅ Extracted handle: @{handle}")
                        return handle
        else:
            print(f"   ❌ Google API error: {response.status_code}")
        
        return None
    
    def _search_with_duckduckgo(self, restaurant_name: str, address: str, phone: str) -> Optional[str]:
        """Search using DuckDuckGo (no API key required)."""
        query = quote_plus(f'"{restaurant_name}" "{address}" site:instagram.com')
        url = f"https://html.duckduckgo.com/html/?q={query}"
        print(f"   🔍 DuckDuckGo query: {query}")
        print(f"   🌐 DuckDuckGo URL: {url}")
        
        response = self.session.get(url)
        print(f"   📡 DuckDuckGo response: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find Instagram links in search results
            instagram_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'instagram.com' in href:
                    instagram_links.append(href)
                    print(f"   📄 Found Instagram link: {href}")
                    
                    handle = self._extract_instagram_handle_from_url(href)
                    if handle:
                        print(f"   ✅ Extracted handle: @{handle}")
                        return handle
            
            if not instagram_links:
                print("   ❌ No Instagram links found in DuckDuckGo results")
        else:
            print(f"   ❌ DuckDuckGo request failed: {response.status_code}")
        
        return None
    
    def _search_direct_instagram(self, restaurant_name: str, address: str, phone: str) -> Optional[str]:
        """Try direct Instagram search by guessing common handle patterns."""
        # Common patterns for restaurant handles
        base_name = re.sub(r'[^a-zA-Z0-9]', '', restaurant_name.lower())
        potential_handles = [
            base_name,
            f"{base_name}restaurant",
            f"{base_name}eats",
            f"{base_name}food",
            f"{base_name}kitchen",
            f"{base_name}cafe",
            f"{base_name}bistro"
        ]
        
        print(f"   🎯 Base name: '{base_name}'")
        print(f"   🔍 Testing {len(potential_handles)} potential handles...")
        
        for i, handle in enumerate(potential_handles):
            print(f"   📝 Testing handle {i+1}/{len(potential_handles)}: @{handle}")
            if self._verify_instagram_handle(handle, restaurant_name):
                print(f"   ✅ Handle @{handle} verified!")
                return handle
            else:
                print(f"   ❌ Handle @{handle} not found or doesn't match")
        
        print("   ❌ No direct handle patterns worked")
        return None
    
    def _extract_instagram_handle_from_url(self, url: str) -> Optional[str]:
        """Extract Instagram handle from URL."""
        # Pattern to match Instagram profile URLs
        pattern = r'instagram\.com/([a-zA-Z0-9._]+)/?'
        match = re.search(pattern, url)
        
        if match:
            handle = match.group(1)
            # Filter out common non-profile paths
            if handle not in ['p', 'reel', 'tv', 'stories', 'explore', 'accounts']:
                return handle
        
        return None
    
    def _verify_instagram_handle(self, handle: str, restaurant_name: str) -> bool:
        """
        Verify if an Instagram handle likely belongs to the restaurant.
        
        This is a basic verification - in production you might want more sophisticated checks.
        """
        try:
            url = f"https://www.instagram.com/{handle}/"
            print(f"      🔍 Checking: {url}")
            
            response = self.session.get(url)
            print(f"      📡 Response: {response.status_code}")
            
            if response.status_code == 200:
                # Basic check: see if restaurant name appears in the page
                content = response.text.lower()
                name_words = restaurant_name.lower().split()
                
                print(f"      🔍 Looking for words: {name_words}")
                
                # If at least half the words from restaurant name appear, consider it a match
                matches = 0
                for word in name_words:
                    if word in content:
                        matches += 1
                        print(f"      ✅ Found word: '{word}'")
                    else:
                        print(f"      ❌ Missing word: '{word}'")
                
                required_matches = len(name_words) / 2
                print(f"      📊 Matches: {matches}/{len(name_words)} (need {required_matches:.1f})")
                
                return matches >= required_matches
            elif response.status_code == 404:
                print(f"      ❌ Handle @{handle} does not exist")
            elif response.status_code == 429:
                print(f"      ⚠️ Rate limited (429) - assuming handle exists: @{handle}")
                return True  # Accept handle when rate limited
            else:
                print(f"      ⚠️ Unexpected response code: {response.status_code}")
            
        except Exception as e:
            print(f"      ❌ Error verifying handle: {e}")
        
        return False

def find_restaurant_instagram(restaurant_name: str, address: str, phone: str = "") -> Optional[str]:
    """
    Convenience function to find Instagram handle for a restaurant.
    
    Args:
        restaurant_name: Name of the restaurant
        address: Restaurant address  
        phone: Restaurant phone number
        
    Returns:
        Instagram handle if found, None otherwise
    """
    finder = RestaurantInstagramFinder()
    return finder.find_instagram_handle(restaurant_name, address, phone)