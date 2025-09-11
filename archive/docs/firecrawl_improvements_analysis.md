# Firecrawl Prompt and Search Strategy Improvements

## Overview

Based on research of the latest Firecrawl documentation and best practices, I've identified several key areas for improvement in the current Instagram handle discovery system.

## Key Improvements Implemented

### 1. **Enhanced Search Query Strategy**

**Current Approach:**
- Generic queries like `"Restaurant Name" instagram`
- Limited location context
- Fixed query order

**Improved Approach:**
```python
# Prioritized query strategies with specific targeting
queries = [
    {
        "query": f'"{restaurant_name}" site:instagram.com',
        "strategy": "direct_instagram",
        "priority": "high"
    },
    {
        "query": f'"{restaurant_name}" "{city}" {state} instagram',
        "strategy": "location_specific", 
        "priority": "high"
    },
    {
        "query": f'"{restaurant_name}" site:yelp.com instagram social',
        "strategy": "business_directory",
        "priority": "medium"
    }
]
```

**Benefits:**
- ✅ **Targeted searches** with specific site restrictions
- ✅ **Priority-based execution** (high → medium → low)
- ✅ **Strategy-specific optimization** for different source types

### 2. **Advanced Scrape Options**

**Current Approach:**
```python
scrape_options=ScrapeOptions(
    formats=["markdown"],
    only_main_content=True
)
```

**Improved Approach:**
```python
def _get_scrape_options_for_strategy(self, strategy: str) -> ScrapeOptions:
    if strategy == "direct_instagram":
        return ScrapeOptions(
            formats=["markdown", "html"],  # Include HTML for link extraction
            onlyMainContent=True,
            includeTags=["a", "div.bio", "div.header", "span.social"],
            timeout=15000,
            waitFor=2000  # Wait for dynamic content
        )
    elif strategy == "business_directory":
        return ScrapeOptions(
            formats=["markdown"],
            includeTags=["a", "div.social", "div.contact"],
            excludeTags=["nav", "footer", "aside.ads"],
            timeout=15000
        )
```

**Benefits:**
- ✅ **Strategy-specific scraping** optimized for different site types
- ✅ **Better content targeting** with includeTags/excludeTags
- ✅ **Dynamic content support** with waitFor parameter
- ✅ **Improved timeout handling**

### 3. **Significantly Enhanced AI Prompt**

**Current Prompt (Basic):**
```
You are analyzing web search results to find the Instagram handle for a restaurant.

Look for Instagram links, handles, or social media mentions. Extract ONLY the Instagram handle (username) without the @ symbol.

Rules:
- Look for patterns like "instagram.com/[handle]", "@[handle]"
- Return ONLY the handle part
- If no Instagram handle is found, return "NOT_FOUND"
```

**Improved Prompt (Advanced with Chain-of-Thought):**
```
You are an expert at finding official Instagram handles for restaurants from web search results.

REASONING PROCESS:
1. First, examine any direct Instagram links found in the HTML
2. Look for official social media mentions in business directories
3. Check if the handle matches the restaurant name and location
4. Verify the handle seems legitimate

EXAMPLES OF GOOD MATCHES:
- Restaurant: "Joe's Pizza" in NYC → Handle: "joespizzanyc" ✓
- Restaurant: "Mama Rosa's Italian" → Handle: "mamarosasitalian" ✓

EXAMPLES OF BAD MATCHES:
- Restaurant in Boston → Handle with "london" in name ✗
- Generic handles like "foodlover123" ✗

CONFIDENCE INDICATORS:
- Handle appears on official business directory = HIGH confidence
- Handle matches restaurant name pattern = HIGH confidence
- Handle mentions location that matches restaurant = HIGH confidence

INSTRUCTIONS:
1. Analyze each result systematically
2. If you find a handle, explain your reasoning
3. Rate your confidence: HIGH, MEDIUM, or LOW
```

**Benefits:**
- ✅ **Chain-of-thought reasoning** for better decision making
- ✅ **Few-shot examples** showing good vs bad matches
- ✅ **Confidence scoring** with explicit criteria
- ✅ **Location validation** logic built into prompt
- ✅ **Systematic analysis** approach

### 4. **Smart Name Variation Handling**

**New Feature:**
```python
def _generate_name_variations(self, restaurant_name: str) -> List[str]:
    variations = []
    
    # Remove location indicators: "Restaurant (Downtown)" → "Restaurant"
    name_clean = re.sub(r'\s*\([^)]*\)\s*', ' ', name_clean).strip()
    
    # Handle apostrophes: "Joe's Pizza" → "Joes Pizza"
    if "'" in name_clean:
        variations.append(name_clean.replace("'", ""))
    
    # Handle "&" vs "and": "Bar & Grill" ↔ "Bar and Grill"
    if "&" in name_clean:
        variations.append(name_clean.replace("&", "and"))
```

**Benefits:**
- ✅ **Handles common name variations** automatically
- ✅ **Removes location suffixes** that might confuse search
- ✅ **Normalizes punctuation** differences

### 5. **Enhanced Result Processing**

**New Features:**
- **HTML link extraction**: Direct Instagram URL parsing from HTML content
- **Source type tracking**: Knows if result came from Yelp, Google, Instagram, etc.
- **Strategy-based processing**: Different handling for different source types
- **Validation data collection**: Tracks confidence indicators throughout process

## Performance Comparison

### Current System Results (Golden Dataset)
- **Overall Accuracy**: 63.2%
- **False Positives**: 21.1% (4/19)
- **Common Issues**:
  - Found handles with wrong locations (e.g., "halifax" for Boston restaurant)
  - Generic corporate handles instead of location-specific ones
  - Poor location validation

### Expected Improvements with Enhanced System
- **Better Location Validation**: Enhanced prompt explicitly checks location matching
- **Reduced False Positives**: Chain-of-thought reasoning should catch location mismatches
- **Higher Confidence Accuracy**: Explicit confidence scoring with reasoning
- **Better Source Prioritization**: Direct Instagram and business directory results prioritized

## Integration Instructions

### Option 1: Replace Existing Function
```python
# In web_search.py, replace the _search_with_firecrawl method:
def _search_with_firecrawl(self, restaurant_name: str, address: str, phone: str) -> Optional[str]:
    from improved_firecrawl_search import enhanced_firecrawl_search_sync
    handle, validation_data = enhanced_firecrawl_search_sync(restaurant_name, address, phone)
    return handle
```

### Option 2: A/B Testing Setup
```python
# Add as new strategy in web_search.py:
strategies = [
    ("Google Custom Search", self._search_with_google_custom_search),
    ("Enhanced Firecrawl", self._search_with_enhanced_firecrawl),  # NEW
    ("Original Firecrawl", self._search_with_firecrawl),  # Keep for comparison
    ("GPT-4 Web Search", self._search_with_gpt4),
]
```

### Option 3: Gradual Rollout
```python
# Use enhanced version for specific cases:
def _search_with_firecrawl(self, restaurant_name: str, address: str, phone: str) -> Optional[str]:
    # Use enhanced version for restaurants that had issues
    problematic_cases = ['Umai Sushi', 'Green House Kitchen']
    if any(case.lower() in restaurant_name.lower() for case in problematic_cases):
        return enhanced_firecrawl_search_sync(restaurant_name, address, phone)[0]
    else:
        return original_firecrawl_search(restaurant_name, address, phone)
```

## Testing Recommendations

### 1. **Run Enhanced Version on Golden Dataset**
```bash
# Test with problematic cases from golden dataset
python -c "
from improved_firecrawl_search import enhanced_firecrawl_search_sync
test_cases = [
    ('Green House Kitchen', '435 Faneuil St, Boston, MA 02135, USA'),
    ('Umai Sushi', '224 Newbury Street, Boston, MA 02116, USA'),
    ('Joe\'s American Bar & Grill', '181 Newbury St, Boston, MA 02116, USA')
]
for name, addr in test_cases:
    handle, data = enhanced_firecrawl_search_sync(name, addr, '')
    print(f'{name}: {handle} | Confidence: {data.get(\"confidence_indicators\", [])}')
"
```

### 2. **Compare Results Side-by-Side**
Create a comparison script that runs both old and new versions on the same dataset to measure improvement.

### 3. **Monitor Rate Limiting**
The enhanced version makes more strategic queries but should be more efficient overall due to better prioritization.

## Expected Impact

### Immediate Benefits
- **🎯 Higher Accuracy**: Better location validation should reduce false positives
- **🧠 Smarter Reasoning**: Chain-of-thought prompting should catch edge cases
- **📊 Better Confidence**: Explicit confidence scoring with reasoning
- **⚡ More Efficient**: Priority-based query execution

### Measurable Improvements Expected
- **Accuracy**: 63.2% → 75%+ (estimated)
- **False Positive Rate**: 21.1% → <10% (estimated)
- **Confidence Reliability**: Better correlation between confidence scores and actual accuracy

## Next Steps

1. **🧪 Test Enhanced Version**: Run on golden dataset subset
2. **📊 Compare Results**: Measure accuracy improvements
3. **🔧 Fine-tune**: Adjust based on test results
4. **🚀 Deploy**: Integrate into main system
5. **📈 Monitor**: Track performance in production

---

*This analysis is based on the latest Firecrawl documentation and prompt engineering best practices as of September 2024.*
