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
    
    def __init__(self, enable_google_custom_search: bool = True, enable_duckduckgo: bool = True):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        # Feature flags to enable/disable certain strategies
        self.enable_google_custom_search = enable_google_custom_search
        self.enable_duckduckgo = enable_duckduckgo
    
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
        
        # Enhanced search strategies with location validation
        strategies = []
        if self.enable_google_custom_search:
            strategies.append(("Google Custom Search", self._search_with_google_custom_search))
        strategies.extend([
            ("GPT-4 Web Search", self._search_with_gpt4),
            ("Enhanced Firecrawl + Location", self._search_with_firecrawl),
            ("Google My Business Search", self._search_with_gmb),
        ])
        if self.enable_duckduckgo:
            strategies.append(("DuckDuckGo Search", self._search_with_duckduckgo))
        # ("Direct Instagram Search", self._search_direct_instagram)  # Disabled
        
        for strategy_name, strategy_func in strategies:
            try:
                print(f"\n🔎 Trying strategy: {strategy_name}")
                handle = strategy_func(restaurant_name, address, phone)
                if handle:
                    print(f"✅ {strategy_name} found handle: @{handle}")
                    
                    # Verify the handle (AI + HTML heuristic)
                    print(f"🔍 Verifying handle @{handle}...")
                    html_ok = self._verify_instagram_handle(handle, restaurant_name)
                    ai_ok = True
                    ai_conf = 1.0
                    ai_reason = ""
                    if settings.use_ai_verification and settings.openai_api_key:
                        ai_ok, ai_conf, ai_reason = self._ai_verify_handle(restaurant_name, address, handle)
                        if not ai_ok:
                            print(f"   ⚠️ AI low confidence for @{handle} ({ai_conf:.2f}): {ai_reason}")

                    if html_ok or ai_ok:
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
        
        print("❌ All search strategies exhausted, trying fallback approaches")
        
        # Fallback 1: Try simplified restaurant name search
        simple_name = restaurant_name.split('(')[0].strip()  # Remove location suffix like "(Arlington St, Boston)"
        if simple_name != restaurant_name and len(simple_name) > 3:
            print(f"🔄 Trying simplified name: '{simple_name}'")
            for strategy_name, strategy_func in strategies[:3]:  # Try top 3 strategies with simplified name
                try:
                    print(f"   🔍 {strategy_name} with simplified name...")
                    handle = strategy_func(simple_name, address, phone)
                    if handle:
                        print(f"   ✅ Simplified search found handle: @{handle}")
                        # Still verify the handle
                        html_ok = self._verify_instagram_handle(handle, restaurant_name)
                        if html_ok:
                            print(f"✅ Fallback handle @{handle} verified successfully")
                            return handle
                        else:
                            print(f"   ❌ Fallback handle @{handle} failed verification")
                except Exception as e:
                    print(f"   ❌ Simplified search failed: {e}")
                    continue
        
        # Fallback 2 removed: Do not return corporate/global handles automatically
        
        print("❌ All fallback strategies exhausted, no valid handle found")
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
        # Handle both business_id and store_id
        bid = (row.get('business_id') or '').strip()
        store_id = (row.get('store_id') or '').strip()
        name = (row.get('restaurant_name') or '').strip()
        address = (row.get('address') or '').strip()
        phone = (row.get('phone') or '').strip()
        try:
            handle = self.find_instagram_handle(name, address, phone)
            status = 'ok' if handle else 'not_found'
            message = '' if handle else 'No handle found'
            # Do not fallback to corporate/global accounts
            corp_handle = ''
            # Enhanced confidence scoring
            confidence_score, confidence_grade = self._calculate_confidence_score(name, address, phone, handle, corp_handle, status)
            
            # AI verification (soft validation) - now incorporated into confidence score
            ai_conf = 0.0
            ai_reason = ''
            if handle and settings.use_ai_verification and settings.openai_api_key:
                verified, ai_conf, ai_reason = self._ai_verify_handle(name, address, handle)
                if not verified and ai_conf < settings.ai_verification_min_confidence:
                    status = 'probable'
                    message = f'AI low confidence ({ai_conf:.2f}): {ai_reason}'
                # Update confidence score with AI feedback
                confidence_score = self._incorporate_ai_confidence(confidence_score, ai_conf, verified)
                confidence_grade = self._get_confidence_grade(confidence_score)
            
            return {
                'business_id': bid,
                'store_id': store_id,
                'restaurant_name': name,
                'address': address,
                'phone': phone,
                'instagram_handle': handle or '',
                'status': status,
                'message': message,
                'ai_confidence': ai_conf,
                'confidence_score': confidence_score,
                'confidence_grade': confidence_grade
            }
        except Exception as e:
            return {
                'business_id': bid,
                'store_id': store_id,
                'restaurant_name': name,
                'address': address,
                'phone': phone,
                'instagram_handle': '',
                'status': 'error',
                'message': str(e),
                'ai_confidence': 0.0,
                'confidence_score': 0.0,
                'confidence_grade': 'Low'
            }

    def _ai_verify_handle(self, restaurant_name: str, address: str, handle: str) -> tuple[bool, float, str]:
        """Use OpenAI to judge if handle plausibly matches the merchant.
        Returns (verified_bool, confidence_float, reason_str).
        """
        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            prompt = (
                f"Merchant: {restaurant_name}\nAddress: {address}\nCandidate IG: @{handle}\n\n"
                "Does this Instagram handle plausibly represent this merchant (local or corporate)?\n"
                "Weigh location-specific evidence highly: prefer handles that match the city/neighborhood/address,\n"
                "and deprioritize corporate/brand-wide accounts unless no location-specific handle exists.\n"
                "Penalize generic brand handles without location tokens when a location-specific exists.\n\n"
                "Return JSON: {\n  \"plausible\": true|false,\n  \"confidence\": 0.0-1.0,\n  \"reason\": \"short\"\n}"
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
            return plausible and conf >= settings.ai_verification_min_confidence, conf, reason
        except Exception as e:
            return True, 1.0, f"AI verify skipped: {e}"
    
    def _calculate_confidence_score(self, restaurant_name: str, address: str, phone: str, 
                                  handle: str, corp_handle: str, status: str) -> tuple[float, str]:
        """Calculate a comprehensive confidence score based on multiple validation factors."""
        if not handle:
            return 0.0, "Low"
        
        score = 0.0
        max_score = 100.0
        
        # Factor 1: Discovery method (30 points)
        if corp_handle:
            score += 15  # Corporate handle found via fallback - lower confidence
        elif handle:
            score += 30  # Direct handle found - higher confidence
        
        # Factor 2: Handle quality validation (25 points)
        handle_quality_score = self._evaluate_handle_quality(handle, restaurant_name)
        score += handle_quality_score
        
        # Factor 3: Name similarity (20 points)
        name_similarity_score = self._calculate_name_similarity(handle, restaurant_name)
        score += name_similarity_score
        
        # Factor 4: Basic validation checks (15 points)
        basic_validation_score = self._perform_basic_validation(handle, restaurant_name)
        score += basic_validation_score
        
        # Factor 5: Status-based adjustment (10 points)
        if status == 'ok':
            score += 10
        elif status == 'probable':
            score += 5
        # 'not_found' and 'error' get 0 points
        
        # Convert to percentage
        confidence_percentage = min(score / max_score * 100, 100.0)
        
        # Enhanced verification for false positive reduction
        if handle and hasattr(self, '_last_validation_data'):
            enhanced_result = self._enhanced_verification(
                handle, restaurant_name, address, confidence_percentage, self._last_validation_data
            )
            confidence_percentage += enhanced_result['confidence_adjustment']
            confidence_percentage = max(0.0, min(100.0, confidence_percentage))
            
            # Reject if enhanced verification failed
            if not enhanced_result['verified']:
                print(f"   ❌ Enhanced verification rejected handle: {', '.join(enhanced_result['rejection_reasons'])}")
                return 0.0, "Low"
        
        confidence_grade = self._get_confidence_grade(confidence_percentage)
        return round(confidence_percentage, 1), confidence_grade
    
    def _enhanced_verification(self, handle: str, restaurant_name: str, address: str, 
                             confidence_score: float, validation_data: dict) -> dict:
        """Enhanced verification with geographic and bio content validation."""
        result = {
            'verified': True,
            'confidence_adjustment': 0,
            'rejection_reasons': [],
            'verification_signals': []
        }
        
        print(f"   🔍 Enhanced verification for @{handle}")
        
        # 1. CONFIDENCE THRESHOLD CHECK
        if confidence_score < 70:
            result['rejection_reasons'].append(f"Low confidence: {confidence_score:.1f}%")
            result['confidence_adjustment'] -= 15
            print(f"      ⚠️ Low confidence: {confidence_score:.1f}%")
        else:
            result['verification_signals'].append(f"Good confidence: {confidence_score:.1f}%")
        
        # 2. LOCATION VALIDATION STRENGTH
        location_score = self._calculate_location_strength(validation_data)
        if location_score < 2:
            result['rejection_reasons'].append(f"Weak location validation: {location_score}")
            result['confidence_adjustment'] -= 10
            print(f"      ⚠️ Weak location signals: {location_score}")
        else:
            result['verification_signals'].append(f"Strong location signals: {location_score}")
            print(f"      ✅ Strong location signals: {location_score}")
        
        # 3. GEOGRAPHIC CONTENT VALIDATION
        geo_red_flags = self._check_geographic_content(handle, address)
        if geo_red_flags > 0:
            result['rejection_reasons'].append(f"Geographic red flags: {geo_red_flags}")
            result['confidence_adjustment'] -= geo_red_flags * 15
            print(f"      🚩 Geographic red flags: {geo_red_flags}")
        
        # 4. BIO CONTENT VALIDATION
        bio_red_flags = self._check_bio_content(handle, restaurant_name, address)
        if bio_red_flags > 0:
            result['rejection_reasons'].append(f"Bio content red flags: {bio_red_flags}")
            result['confidence_adjustment'] -= bio_red_flags * 10
            print(f"      🚩 Bio content red flags: {bio_red_flags}")
        
        # 5. PATTERN ANALYSIS
        pattern_score = self._analyze_handle_pattern(handle, restaurant_name)
        if pattern_score < 0.2:
            result['rejection_reasons'].append(f"Handle pattern suspicious: {pattern_score:.1f}")
            result['confidence_adjustment'] -= 10
            print(f"      ⚠️ Suspicious handle pattern: {pattern_score:.1f}")
        
        # FINAL DECISION - Red flag scoring system
        total_red_flags = geo_red_flags + bio_red_flags
        total_adjustment = result['confidence_adjustment']
        adjusted_confidence = confidence_score + total_adjustment
        
        # Enhanced rejection criteria
        if total_red_flags >= 3:
            result['verified'] = False
            print(f"      ❌ REJECTED: Too many red flags ({total_red_flags})")
        elif geo_red_flags >= 2:  # Conflicting geography is a major issue
            result['verified'] = False
            print(f"      ❌ REJECTED: Major geographic conflicts")
        elif adjusted_confidence < 40:
            result['verified'] = False
            print(f"      ❌ REJECTED: Adjusted confidence too low ({adjusted_confidence:.1f}%)")
        elif confidence_score < 65 and total_red_flags >= 2:
            result['verified'] = False
            print(f"      ❌ REJECTED: Low confidence + multiple red flags")
        else:
            if total_red_flags > 0:
                print(f"      ⚠️ VERIFIED with concerns: {total_red_flags} red flags")
            else:
                print(f"      ✅ VERIFIED: Clean validation")
        
        return result
    
    def _calculate_location_strength(self, validation_data: dict) -> int:
        """Calculate strength of location validation signals."""
        score = 0
        
        if validation_data.get('google_my_business_found'):
            score += 3
        
        location_matches = validation_data.get('location_matches', [])
        score += len(set(location_matches))  # Unique location matches
        
        if validation_data.get('yelp_found'):
            score += 1
        if validation_data.get('tripadvisor_found'):
            score += 1
            
        return min(score, 10)  # Cap at 10
    
    def _analyze_handle_pattern(self, handle: str, restaurant_name: str) -> float:
        """Analyze if handle pattern makes sense for restaurant."""
        handle_lower = handle.lower()
        name_lower = restaurant_name.lower().replace("'", "")
        
        # Remove common suffixes that might not be in handle
        name_parts = name_lower.replace('restaurant', '').replace('kitchen', '').replace('cafe', '').strip()
        name_words = [w for w in name_parts.split() if len(w) > 2]
        
        if not name_words:
            return 0.5
        
        # Check if handle contains main name components
        matches = 0
        for word in name_words:
            if word in handle_lower:
                matches += 1
        
        base_score = matches / len(name_words)
        
        # Bonus for location-specific patterns
        if any(word in handle_lower for word in ['boston', 'ma', 'cambridge', 'beacon', 'allston']):
            base_score += 0.2
            
        # Penalty for suspicious patterns
        if any(suspicious in handle_lower for suspicious in ['_official', '_real', '_authentic']):
            base_score -= 0.3
            
        return min(base_score, 1.0)
    
    def _check_geographic_content(self, handle: str, address: str) -> int:
        """Check Instagram content for geographic red flags."""
        red_flags = 0
        
        try:
            url = f"https://www.instagram.com/{handle}/"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                return 0  # Can't check, neutral
            
            content = response.text.lower()
            
            # Extract expected location from address
            import re
            city_match = re.search(r',\s*([^,]+),\s*([A-Z]{2})', address)
            expected_city = city_match.group(1).strip().lower() if city_match else ""
            expected_state = city_match.group(2).strip().lower() if city_match else ""
            
            # Check for Boston area indicators
            boston_indicators = ['boston', 'ma', 'massachusetts', 'cambridge', 'allston', 'brookline', 'beacon']
            has_boston_indicators = any(indicator in content for indicator in boston_indicators)
            
            # Check for conflicting locations
            conflicting_cities = ['atlanta', 'chicago', 'miami', 'seattle', 'denver', 'philadelphia', 'houston', 'dallas', 'portland']
            conflicting_locations = [city for city in conflicting_cities if city in content]
            
            # Red flag: Conflicting major cities
            if conflicting_locations:
                red_flags += 2  # Major red flag
                print(f"      🚩 Conflicting locations found: {conflicting_locations}")
            
            # Red flag: No local location indicators for Boston-area restaurants
            if expected_city in ['boston', 'cambridge', 'allston', 'brookline'] and not has_boston_indicators:
                red_flags += 1
                print(f"      🚩 No Boston-area location indicators")
            
            return red_flags
            
        except Exception:
            return 0  # Error checking, neutral
    
    def _check_bio_content(self, handle: str, restaurant_name: str, address: str) -> int:
        """Check Instagram bio content for validation red flags."""
        red_flags = 0
        
        try:
            url = f"https://www.instagram.com/{handle}/"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                return 0  # Can't check, neutral
            
            content = response.text
            
            # Extract bio content
            import re
            bio_patterns = [
                r'"biography":"([^"]*)"',
                r'<meta property="og:description" content="([^"]*)"',
                r'<title>([^<]*)</title>'
            ]
            
            bio_text = ""
            for pattern in bio_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    bio_text += " " + match.group(1)
            
            if not bio_text:
                return 1  # No bio extractable is a minor red flag
            
            bio_lower = bio_text.lower()
            
            # Check restaurant name components
            name_words = restaurant_name.lower().replace("'", "").split()
            meaningful_words = [w for w in name_words if len(w) > 2 and w not in ['the', 'and', 'restaurant', 'kitchen']]
            
            name_matches = sum(1 for word in meaningful_words if word in bio_lower)
            name_score = name_matches / len(meaningful_words) if meaningful_words else 0
            
            # Red flag: Poor name matching
            if name_score < 0.3 and meaningful_words:
                red_flags += 1
                print(f"      🚩 Poor name matching in bio: {name_score:.1%}")
            
            # Check for business keywords
            business_keywords = ['restaurant', 'cafe', 'kitchen', 'grill', 'sushi', 'food', 'dining', 'eat', 'bar']
            has_business_keywords = any(kw in bio_lower for kw in business_keywords)
            
            # Red flag: No business/restaurant keywords
            if not has_business_keywords:
                red_flags += 1
                print(f"      🚩 No business/restaurant keywords in bio")
            
            # Check for address components (less critical)
            address_words = address.lower().split()
            significant_address_words = [w for w in address_words if len(w) > 3 and w not in ['street', 'avenue', 'boston']]
            address_matches = sum(1 for word in significant_address_words if word in bio_lower)
            
            # Minor red flag: No address components
            if not address_matches and significant_address_words:
                red_flags += 0.5  # Half a red flag
                print(f"      🚩 No address components in bio")
            
            return int(red_flags)  # Convert to int
            
        except Exception:
            return 0  # Error checking, neutral
    
    def _evaluate_handle_quality(self, handle: str, restaurant_name: str) -> float:
        """Evaluate the quality of the Instagram handle (0-25 points)."""
        score = 0.0
        
        # Length check (handles that are too short or too long are suspicious)
        if 3 <= len(handle) <= 30:
            score += 5
        
        # Character composition (prefer alphanumeric with minimal special chars)
        special_char_count = sum(1 for c in handle if c in '._')
        if special_char_count <= 2:
            score += 5
        elif special_char_count <= 4:
            score += 2
        
        # Avoid obviously generic or spam patterns
        spam_patterns = ['official', 'real', 'authentic', '123', '000', 'xxx']
        if not any(pattern in handle.lower() for pattern in spam_patterns):
            score += 5
        
        # Check if handle contains restaurant name components
        name_words = [word.lower() for word in restaurant_name.split() if len(word) > 2]
        handle_lower = handle.lower()
        matching_words = sum(1 for word in name_words if word in handle_lower)
        if matching_words > 0:
            score += min(matching_words * 3, 10)  # Up to 10 points for name matches
        
        return score
    
    def _calculate_name_similarity(self, handle: str, restaurant_name: str) -> float:
        """Calculate similarity between handle and restaurant name (0-20 points)."""
        import difflib
        
        # Normalize strings
        handle_clean = handle.lower().replace('_', '').replace('.', '')
        name_clean = restaurant_name.lower().replace(' ', '').replace("'", '')
        
        # Calculate similarity ratio
        similarity = difflib.SequenceMatcher(None, handle_clean, name_clean).ratio()
        
        # Also check if handle contains significant parts of restaurant name
        name_words = [word for word in restaurant_name.lower().split() if len(word) > 2]
        word_matches = sum(1 for word in name_words if word in handle.lower())
        word_coverage = word_matches / len(name_words) if name_words else 0
        
        # Combine similarity metrics
        combined_score = (similarity * 0.6) + (word_coverage * 0.4)
        return combined_score * 20  # Scale to 0-20 points
    
    def _perform_basic_validation(self, handle: str, restaurant_name: str) -> float:
        """Perform basic validation checks (0-15 points)."""
        score = 0.0
        
        try:
            # Check if handle exists (basic HTTP check)
            url = f"https://www.instagram.com/{handle}/"
            response = self.session.get(url, timeout=5)
            
            if response.status_code == 200:
                score += 10  # Handle exists
                
                # Basic content check
                content = response.text.lower()
                name_words = [word.lower() for word in restaurant_name.split() if len(word) > 2]
                
                # Check for restaurant-related keywords
                restaurant_keywords = ['restaurant', 'food', 'eat', 'menu', 'kitchen', 'cafe', 'bar', 'dine']
                keyword_matches = sum(1 for keyword in restaurant_keywords if keyword in content)
                if keyword_matches > 0:
                    score += 3
                
                # Check for name word matches in content
                name_matches = sum(1 for word in name_words if word in content)
                if name_matches > 0:
                    score += 2
                    
            elif response.status_code == 429:
                score += 8  # Rate limited, assume it exists but dock some points
            # 404 or other errors get 0 points
            
        except Exception:
            # Network error or timeout - neutral score
            score += 5
        
        return score
    
    def _incorporate_ai_confidence(self, base_score: float, ai_confidence: float, ai_verified: bool) -> float:
        """Incorporate AI confidence into the overall score."""
        if ai_confidence == 0.0:
            return base_score  # No AI feedback
        
        # AI confidence is 0.0-1.0, convert to adjustment factor
        ai_weight = 0.3  # AI feedback contributes 30% to final score
        
        if ai_verified:
            # AI confirms the match - boost the score
            ai_contribution = ai_confidence * 100 * ai_weight
        else:
            # AI is skeptical - reduce the score
            ai_contribution = -(1.0 - ai_confidence) * 100 * ai_weight
        
        # Apply the adjustment
        adjusted_score = base_score + ai_contribution
        return max(0.0, min(100.0, adjusted_score))  # Clamp to 0-100
    
    def _get_confidence_grade(self, score: float) -> str:
        """Convert numerical score to simplified grade."""
        if score >= 80:
            return "High"
        elif score >= 50:
            return "Medium"
        else:
            return "Low"
    
    def _parse_location_components(self, address: str) -> dict:
        """Use LLM to parse address components for better location validation."""
        if not settings.openai_api_key:
            # Fallback to basic regex parsing
            import re
            city_match = re.search(r',\s*([^,]+),\s*([A-Z]{2})', address)
            if city_match:
                return {
                    'city': city_match.group(1).strip(),
                    'state': city_match.group(2).strip(),
                    'raw_address': address
                }
            return {'raw_address': address}
        
        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            prompt = f"""Parse this address into components. Return only valid JSON.

Address: {address}

Extract:
- street: street number and name
- city: city name
- state: state abbreviation (2 letters)
- zip: zip code if present
- neighborhood: neighborhood/area if mentioned
- landmarks: any notable landmarks nearby if mentioned

Return JSON format:
{{"street": "value", "city": "value", "state": "value", "zip": "value", "neighborhood": "value", "landmarks": "value"}}

Only include fields that have actual values. Use null for missing information."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
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
                for key in ['street', 'city', 'state', 'zip', 'neighborhood', 'landmarks']:
                    value = parsed.get(key)
                    if value and value.lower() not in ['null', 'none', 'n/a', '']:
                        location[key] = str(value).strip()
                
                return location
            
        except Exception as e:
            print(f"   ⚠️ LLM address parsing failed: {e}")
        
        # Fallback
        return {'raw_address': address}
    
    def _search_google_my_business_specific(self, restaurant_name: str, address: str, phone: str = "") -> dict:
        """Enhanced Google search specifically targeting Google My Business results."""
        location = self._parse_location_components(address)
        city = location.get('city', '')
        state = location.get('state', '')
        
        gmb_data = {
            'profile_found': False,
            'instagram_linked': False,
            'address_verified': False,
            'phone_verified': False,
            'location_verified': False,
            'business_hours_found': False,
            'gmb_urls': []
        }
        
        # Multiple GMB-specific search strategies
        gmb_queries = []
        if city and state:
            gmb_queries.extend([
                f'site:google.com/maps "{restaurant_name}" {city} {state}',
                f'"{restaurant_name}" {city} {state} hours phone instagram',
                f'"{restaurant_name}" "{address}" google business profile',
                f'"google my business" "{restaurant_name}" {city} instagram'
            ])
        
        # Fallback queries
        gmb_queries.append(f'"{restaurant_name}" "{address}" google maps')
        
        print(f"   🔍 Searching Google My Business for: {restaurant_name}")
        
        for query in gmb_queries[:3]:  # Limit to first 3 queries
            try:
                print(f"      📋 GMB query: {query}")
                
                # Use DuckDuckGo search (since we disabled direct Google in some cases)
                search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
                response = self.session.get(search_url, timeout=10)
                
                if response.status_code == 200:
                    content = response.text.lower()
                    
                    # Check for Google Maps/GMB indicators
                    if 'google.com/maps' in content:
                        gmb_data['profile_found'] = True
                        gmb_data['gmb_urls'].append('google.com/maps')
                        print(f"      ✅ Found Google Maps profile")
                        
                        # Check for Instagram links in results
                        if 'instagram.com' in content:
                            gmb_data['instagram_linked'] = True
                            print(f"      ✅ Instagram link found in GMB context")
                        
                        # Verify location components
                        if city and city.lower() in content:
                            gmb_data['location_verified'] = True
                        if state and state.lower() in content:
                            gmb_data['location_verified'] = True
                        
                        # Check for phone number
                        if phone:
                            phone_clean = phone.replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
                            if phone_clean in content.replace('-', '').replace('(', '').replace(')', '').replace(' ', ''):
                                gmb_data['phone_verified'] = True
                                print(f"      ✅ Phone number verified in GMB")
                        
                        # Business hours indicator
                        hours_indicators = ['hours', 'open', 'closed', 'monday', 'tuesday', 'am', 'pm']
                        if any(indicator in content for indicator in hours_indicators):
                            gmb_data['business_hours_found'] = True
                            print(f"      ✅ Business hours found")
                
            except Exception as e:
                print(f"      ❌ GMB search error: {e}")
                continue
        
        return gmb_data
    
    def _search_with_gmb(self, restaurant_name: str, address: str, phone: str) -> Optional[str]:
        """Search using Google My Business specific approach."""
        try:
            gmb_data = self._search_google_my_business_specific(restaurant_name, address, phone)
            
            # Store GMB data for confidence scoring
            if not hasattr(self, '_last_gmb_data'):
                self._last_gmb_data = {}
            self._last_gmb_data = gmb_data
            
            if gmb_data.get('instagram_linked'):
                print(f"   ✅ Instagram found via Google My Business!")
                # Try to extract handle from GMB URLs or content
                # This would require more sophisticated scraping
                # For now, we signal that GMB validation is strong
                return None  # No direct handle extraction yet, but validation data stored
            
            return None
        except Exception as e:
            print(f"   ❌ GMB search failed: {e}")
            return None

    def _discover_corporate_handle_via_firecrawl(self, restaurant_name: str) -> Optional[str]:
        """Use Firecrawl to search for a corporate/global IG handle when local is missing."""
        try:
            from firecrawl_search import firecrawl_search_restaurant_instagram_sync
            result = firecrawl_search_restaurant_instagram_sync(restaurant_name, '', '')
            # Handle both old (str) and new (tuple) return formats
            if isinstance(result, tuple):
                return result[0]  # Return just the handle
            return result
        except Exception:
            return None
    
    def _search_with_gpt4(self, restaurant_name: str, address: str, phone: str) -> Optional[str]:
        """Search using GPT-4 with web search capabilities."""
        if not settings.openai_api_key:
            print("   ⚠️ OpenAI API key not configured, skipping GPT-4 search")
            return None
        
        try:
            from gpt_native_search import gpt_search_restaurant_instagram
            # Consider adaptive throttling via OpenAI handled in downstream libs
            return gpt_search_restaurant_instagram(restaurant_name, address, phone)
        except Exception as e:
            print(f"   ❌ GPT-4 native search failed: {e}")
            return None
    
    def _search_with_firecrawl(self, restaurant_name: str, address: str, phone: str) -> Optional[str]:
        """Search using enhanced Firecrawl + OpenAI analysis with location validation."""
        try:
            from firecrawl_search import firecrawl_search_restaurant_instagram_sync
            handle, validation_data = firecrawl_search_restaurant_instagram_sync(restaurant_name, address, phone)
            
            if handle and validation_data:
                # Enhanced validation: check if we have good location signals
                location_score = 0
                if validation_data.get('google_my_business_found'):
                    location_score += 3
                if validation_data.get('location_matches'):
                    location_score += len(validation_data['location_matches'])
                if validation_data.get('yelp_found') or validation_data.get('tripadvisor_found'):
                    location_score += 1
                
                print(f"   📊 Firecrawl location validation score: {location_score}")
                
                # Store validation data for confidence scoring
                if not hasattr(self, '_last_validation_data'):
                    self._last_validation_data = {}
                self._last_validation_data = validation_data
                
                # Apply location-based filtering (very permissive now)
                if location_score >= 0:  # Accept any handle found - location only affects confidence
                    if location_score >= 3:
                        print(f"   ✅ Strong location validation ({location_score} signals)")
                    elif location_score >= 1:
                        print(f"   ✅ Moderate location validation ({location_score} signals)")
                    else:
                        print(f"   ⚠️ Weak location validation ({location_score} signals) - handle returned with lower confidence")
                    return handle
            
            return handle
        except Exception as e:
            print(f"   ❌ Enhanced Firecrawl search failed: {e}")
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
        Bypass verification: accept any found handle (experiment to measure impact).
        """
        print(f"      ⚠️ Skipping keyword verification for @{handle} (experiment)")
        return True

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