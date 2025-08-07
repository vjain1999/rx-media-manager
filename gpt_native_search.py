"""GPT-4 web search using OpenAI Responses API for finding restaurant Instagram handles."""

import openai
from typing import Optional
from config import settings
import re

def gpt_search_restaurant_instagram(restaurant_name: str, address: str, phone: str) -> Optional[str]:
    """
    Use GPT-4's Responses API with web search to find restaurant Instagram handle.
    
    Args:
        restaurant_name: Name of the restaurant
        address: Restaurant address  
        phone: Restaurant phone number
        
    Returns:
        Instagram handle if found, None otherwise
    """
    if not settings.openai_api_key:
        print("   ⚠️ OpenAI API key not configured, skipping GPT-4 web search")
        return None
    
    try:
        print(f"🌐 Using GPT-4 Responses API with web search for: {restaurant_name}")
        
        client = openai.OpenAI(api_key=settings.openai_api_key)
        
        search_query = f"""
Find the Instagram handle for this restaurant by searching these specific sources:

Restaurant: {restaurant_name}
Address: {address}
Phone: {phone}

Search these sites for social media links, specifically Instagram:
1. Official restaurant website - look for social media icons/links
2. Yelp.com - check business profile for social media section
3. TripAdvisor.com - look for social media links in restaurant listing
4. Google Business/Maps listing - check for social media links
5. OpenTable.com - restaurant profile may include social media
6. Restaurant's Facebook page - often links to Instagram
7. Local business directories that include social media info

Look for patterns like:
- Instagram icons or links
- @username mentions
- instagram.com/username URLs
- Social media sections on business profiles

Return the exact Instagram handle (without @) if found, or "NOT_FOUND" if no Instagram account exists for this specific restaurant location.
"""

        # Use the Responses API with web search
        response = client.responses.create(
            model="gpt-4o",  # Use the latest model
            tools=[{"type": "web_search_preview"}],
            input=search_query
        )
        
        # Extract the result from the response
        result = _extract_text_from_response(response)
        
        print(f"   🎯 GPT-4 web search result: {result}")
        
        if result:
            # Use another LLM call to extract just the handle cleanly
            handle = _extract_handle_with_llm(client, result)
            if handle and handle.upper() != "NOT_FOUND":
                print(f"   ✅ Found handle: @{handle}")
                return handle
        
        print("   ❌ No Instagram handle found")
        return None
        
    except Exception as e:
        print(f"   ❌ GPT-4 web search failed: {e}")
        return None

def _extract_text_from_response(response) -> str:
    """Extract text content from the Responses API response."""
    try:
        # The response structure might be different, let's handle various formats
        if hasattr(response, 'output_text'):
            return response.output_text
        elif hasattr(response, 'output') and response.output:
            # Handle array of outputs
            for output in response.output:
                if hasattr(output, 'content') and output.content:
                    for content in output.content:
                        if hasattr(content, 'text'):
                            return content.text
                        elif hasattr(content, 'content'):
                            return content.content
        elif hasattr(response, 'choices') and response.choices:
            # Fallback to chat completion format
            return response.choices[0].message.content
        
        # If we can't extract, convert to string and try to parse
        response_str = str(response)
        return response_str
        
    except Exception as e:
        print(f"   ⚠️ Error extracting response text: {e}")
        return ""

def _extract_handle_with_llm(client, search_result: str) -> Optional[str]:
    """Use LLM to extract just the Instagram handle from search results."""
    try:
        extraction_prompt = f"""
The following is a web search result about a restaurant's Instagram handle:

{search_result}

Extract ONLY the Instagram handle from this text. Return just the handle without @ symbol.

Examples:
- If the text mentions "CrepevineRestaurants", return: CrepevineRestaurants  
- If the text mentions "@bistro_sf", return: bistro_sf
- If no handle is found, return: NOT_FOUND

Handle only (no explanation):
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use mini for cost efficiency
            messages=[
                {"role": "user", "content": extraction_prompt}
            ],
            max_tokens=50,
            temperature=0
        )
        
        result = response.choices[0].message.content.strip()
        print(f"   🔍 Handle extraction: {result}")
        
        if result and result.upper() != "NOT_FOUND":
            # Clean the result (remove @ if present, strip whitespace)
            handle = result.replace('@', '').strip()
            if handle and len(handle) >= 3 and len(handle) <= 30:
                return handle
        
        return None
        
    except Exception as e:
        print(f"   ❌ Handle extraction failed: {e}")
        return None