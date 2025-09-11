"""GPT-4 enhanced web search module for finding restaurant Instagram handles."""

import json
import time
from typing import List, Dict, Optional, Any
import requests
from bs4 import BeautifulSoup
import openai
from config import settings
import concurrent.futures
from urllib.parse import quote_plus
import re

class GPTWebSearcher:
    """Enhanced web search using GPT-4 with function calling capabilities."""
    
    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key is required for GPT web search")
        
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def search_restaurant_instagram(self, restaurant_name: str, address: str, phone: str) -> Optional[str]:
        """
        Use GPT-4 with web search to find the correct Instagram handle for a restaurant.
        
        Args:
            restaurant_name: Name of the restaurant
            address: Restaurant address
            phone: Restaurant phone number
            
        Returns:
            Instagram handle if found, None otherwise
        """
        print(f"🤖 Using GPT-4 web search for: {restaurant_name}")
        print(f"   Address: {address}")
        print(f"   Phone: {phone}")
        
        # Define the search function for GPT to use
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for information about restaurants and their Instagram handles",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query to perform"
                            },
                            "focus": {
                                "type": "string", 
                                "description": "What to focus on: 'instagram', 'social_media', 'general'"
                            }
                        },
                        "required": ["query", "focus"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "verify_instagram_handle",
                    "description": "Verify if an Instagram handle belongs to the specific restaurant",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "handle": {
                                "type": "string",
                                "description": "Instagram handle to verify (without @)"
                            },
                            "restaurant_name": {
                                "type": "string",
                                "description": "Restaurant name to verify against"
                            },
                            "address": {
                                "type": "string", 
                                "description": "Restaurant address to verify against"
                            }
                        },
                        "required": ["handle", "restaurant_name", "address"]
                    }
                }
            }
        ]
        
        # Create the prompt for GPT-4
        prompt = f"""
You are an expert at finding Instagram handles for restaurants. I need you to find the correct Instagram handle for this restaurant:

Restaurant: {restaurant_name}
Address: {address}
Phone: {phone}

Please use the web search function to find the Instagram handle for this specific restaurant location. 

IMPORTANT: Make sure the Instagram handle belongs to THIS SPECIFIC restaurant location, not just any restaurant with the same name. Pay attention to:
- The exact address/location
- Phone number if mentioned
- Profile photos and content that match the restaurant
- Bio information that confirms the location

Use multiple search strategies:
1. Search for the restaurant name + address + Instagram
2. Search for the restaurant name + city + Instagram  
3. Search for the restaurant name + phone number
4. Verify any potential handles you find

Return the verified Instagram handle (without @) or "NOT_FOUND" if no valid handle exists.
"""
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that can search the web and verify Instagram handles for restaurants."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # Call GPT-4 with function calling
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Use mini version for cost efficiency
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=1500,
                temperature=0.1
            )
            
            # Process the response and handle function calls
            return self._process_gpt_response(response, messages, restaurant_name, address, phone)
            
        except Exception as e:
            print(f"❌ GPT web search failed: {e}")
            return None
    
    def _process_gpt_response(self, response, messages, restaurant_name: str, address: str, phone: str) -> Optional[str]:
        """Process GPT response and handle function calls."""
        
        # Define tools for subsequent calls
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for information about restaurants and their Instagram handles",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query to perform"
                            },
                            "focus": {
                                "type": "string", 
                                "description": "What to focus on: 'instagram', 'social_media', 'general'"
                            }
                        },
                        "required": ["query", "focus"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "verify_instagram_handle",
                    "description": "Verify if an Instagram handle belongs to the specific restaurant",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "handle": {
                                "type": "string",
                                "description": "Instagram handle to verify (without @)"
                            },
                            "restaurant_name": {
                                "type": "string",
                                "description": "Restaurant name to verify against"
                            },
                            "address": {
                                "type": "string", 
                                "description": "Restaurant address to verify against"
                            }
                        },
                        "required": ["handle", "restaurant_name", "address"]
                    }
                }
            }
        ]
        
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            message = response.choices[0].message
            tool_calls = message.tool_calls
            
            if tool_calls:
                print(f"🔧 GPT is calling {len(tool_calls)} function(s)")
                
                # Add the assistant's message to conversation
                messages.append(message)
                
                # Execute function calls
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    print(f"   📞 Calling {function_name} with args: {function_args}")
                    
                    if function_name == "web_search":
                        result = self._web_search(**function_args)
                    elif function_name == "verify_instagram_handle":
                        result = self._verify_instagram_handle(**function_args)
                    else:
                        result = "Function not found"
                    
                    # Add function result to messages
                    messages.append({
                        "role": "tool",
                        "content": str(result),
                        "tool_call_id": tool_call.id
                    })
                
                # Get next response from GPT
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    max_tokens=1500,
                    temperature=0.1
                )
                
                iteration += 1
            else:
                # No more function calls, extract the final answer
                final_answer = message.content
                print(f"🎯 GPT final answer: {final_answer}")
                
                # Extract Instagram handle from the response
                handle = self._extract_handle_from_response(final_answer)
                return handle if handle != "NOT_FOUND" else None
        
        print("❌ Max iterations reached, no final answer")
        return None
    
    def _web_search(self, query: str, focus: str = "general") -> Dict[str, Any]:
        """Perform web search and return results."""
        print(f"   🔍 Web searching: {query} (focus: {focus})")
        
        try:
            # Use DuckDuckGo for web search (no API key required)
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            
            response = self.session.get(search_url)
            if response.status_code != 200:
                return {"error": f"Search failed with status {response.status_code}"}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Extract search results - try multiple selectors for DuckDuckGo
            result_links = (soup.find_all('a', class_='result__a') or 
                          soup.find_all('a', {'data-testid': 'result-extras-url-link'}) or
                          soup.find_all('h2', class_='result__title'))
            
            for result in result_links[:10]:  # Top 10 results
                title = result.get_text(strip=True) if result else ""
                link = ""
                
                # Extract link based on element type
                if result.name == 'a':
                    link = result.get('href', '')
                elif result.name == 'h2':
                    # For h2 elements, find the link inside
                    link_elem = result.find('a')
                    if link_elem:
                        link = link_elem.get('href', '')
                
                # Get snippet from nearby elements
                snippet = ""
                if result:
                    parent_div = result.find_parent('div')
                    if parent_div:
                        snippet_elem = parent_div.find(class_='result__snippet') or parent_div.find('span')
                        if snippet_elem:
                            snippet = snippet_elem.get_text(strip=True)
                
                if link and title and len(title) > 5:  # Basic validation
                    results.append({
                        "title": title,
                        "link": link,
                        "snippet": snippet
                    })
            
            # Filter results based on focus
            if focus == "instagram":
                results = [r for r in results if 'instagram.com' in r['link'].lower()]
            elif focus == "social_media":
                social_keywords = ['instagram', 'facebook', 'twitter', 'social']
                results = [r for r in results if any(keyword in r['title'].lower() or keyword in r['snippet'].lower() for keyword in social_keywords)]
            
            print(f"   📋 Found {len(results)} results")
            return {"results": results, "query": query, "focus": focus}
            
        except Exception as e:
            print(f"   ❌ Search error: {e}")
            return {"error": str(e)}
    
    def _verify_instagram_handle(self, handle: str, restaurant_name: str, address: str) -> Dict[str, Any]:
        """Verify if an Instagram handle belongs to the restaurant."""
        print(f"   🔍 Verifying Instagram handle: @{handle}")
        
        try:
            url = f"https://www.instagram.com/{handle}/"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 404:
                return {
                    "valid": False,
                    "reason": "Instagram handle does not exist",
                    "handle": handle
                }
            elif response.status_code != 200:
                return {
                    "valid": False,
                    "reason": f"HTTP error {response.status_code}",
                    "handle": handle
                }
            
            # Parse the page content
            content = response.text.lower()
            
            # Extract information from the page
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for restaurant name in various places
            name_words = restaurant_name.lower().split()
            address_parts = address.lower().split()
            
            # Count matches in content
            name_matches = sum(1 for word in name_words if len(word) > 2 and word in content)
            address_matches = sum(1 for part in address_parts if len(part) > 3 and part in content)
            
            # Additional verification signals
            signals = []
            if "restaurant" in content: signals.append("restaurant")
            if "food" in content: signals.append("food")
            if "menu" in content: signals.append("menu")
            if "location" in content: signals.append("location")
            if any(city in content for city in ["mountain view", "mountainview", "mv"]): signals.append("mountain_view")
            
            verification_score = (name_matches * 2) + address_matches + len(signals)
            
            print(f"   📊 Verification score: {verification_score}")
            print(f"   📝 Name matches: {name_matches}/{len(name_words)}")
            print(f"   📍 Address matches: {address_matches}/{len(address_parts)}")
            print(f"   🔍 Signals: {signals}")
            
            # Consider valid if good score or strong signals
            is_valid = verification_score >= 3 or (name_matches >= len(name_words) / 2 and len(signals) >= 1)
            
            return {
                "valid": is_valid,
                "verification_score": verification_score,
                "name_matches": f"{name_matches}/{len(name_words)}",
                "address_matches": f"{address_matches}/{len(address_parts)}",
                "signals": signals,
                "handle": handle,
                "reason": "Verified successfully" if is_valid else "Insufficient verification signals"
            }
            
        except Exception as e:
            print(f"   ❌ Verification error: {e}")
            return {
                "valid": False,
                "reason": f"Verification failed: {str(e)}",
                "handle": handle
            }
    
    def _extract_handle_from_response(self, response: str) -> Optional[str]:
        """Extract Instagram handle from GPT response."""
        if "NOT_FOUND" in response.upper():
            return "NOT_FOUND"
        
        # Look for Instagram handles in the response
        # More specific patterns to avoid false matches
        patterns = [
            r'\*\*([a-zA-Z0-9._]+)\*\*',  # **handle** (markdown bold)
            r'@([a-zA-Z0-9._]{3,})',      # @handle (minimum 3 chars)
            r'instagram\.com/([a-zA-Z0-9._]{3,})',  # instagram.com/handle
            r'handle[:\s]+([a-zA-Z0-9._]{3,})',     # handle: something
            r'is[:\s]+([a-zA-Z0-9._]{3,})',         # is: handle
            r'found[:\s]+([a-zA-Z0-9._]{3,})',      # found: handle
            r'\b([a-zA-Z0-9._]{6,})\b(?=\.?\s*$)',  # Long word at end of sentence
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            for match in matches:
                # Filter out common non-profile paths and common words
                excluded = ['p', 'reel', 'tv', 'stories', 'explore', 'accounts', 
                           'for', 'the', 'and', 'with', 'this', 'that', 'instagram',
                           'located', 'restaurant', 'address', 'phone']
                
                if (match.lower() not in excluded and 
                    len(match) >= 3 and 
                    not match.isdigit()):
                    print(f"   ✅ Extracted handle: {match}")
                    return match
        
        # Fallback: look for any Instagram-like handles in the response
        fallback_pattern = r'\b([a-zA-Z0-9._]{5,30})\b'
        matches = re.findall(fallback_pattern, response, re.IGNORECASE)
        for match in matches:
            if (match.lower() not in excluded and 
                not match.isdigit() and
                len(match) >= 5):
                print(f"   ✅ Extracted handle (fallback): {match}")
                return match
        
        return None

def gpt_search_restaurant_instagram(restaurant_name: str, address: str, phone: str) -> Optional[str]:
    """
    Convenience function to search for restaurant Instagram using GPT-4.
    
    Args:
        restaurant_name: Name of the restaurant
        address: Restaurant address
        phone: Restaurant phone number
        
    Returns:
        Instagram handle if found, None otherwise
    """
    try:
        searcher = GPTWebSearcher()
        return searcher.search_restaurant_instagram(restaurant_name, address, phone)
    except Exception as e:
        print(f"❌ GPT search failed: {e}")
        return None