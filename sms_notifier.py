"""SMS notification module using Twilio for restaurant confirmation."""

from twilio.rest import Client
from typing import List, Dict, Optional
from config import settings
import time

class RestaurantNotifier:
    """Send SMS notifications to restaurants about video approvals."""
    
    def __init__(self):
        if not all([settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_phone_number]):
            raise ValueError("Twilio credentials are required for SMS notifications")
        
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self.from_number = settings.twilio_phone_number
    
    def send_video_approval_request(self, restaurant_phone: str, restaurant_name: str, 
                                  approved_videos: List[Dict]) -> bool:
        """
        Send two SMS messages to restaurant requesting approval for selected videos.
        
        Args:
            restaurant_phone: Restaurant's phone number
            restaurant_name: Restaurant's name
            approved_videos: List of videos that passed quality analysis
            
        Returns:
            True if both SMS sent successfully, False otherwise
        """
        try:
            if not approved_videos:
                print("No approved videos to send")
                return False
            
            # Create both messages
            intro_message, links_message = self._create_two_part_message(restaurant_name, approved_videos)
            
            # Send first SMS (introduction)
            message1 = self.client.messages.create(
                body=intro_message,
                from_=self.from_number,
                to=restaurant_phone
            )
            print(f"SMS 1/2 sent successfully to {restaurant_phone}. Message SID: {message1.sid}")
            
            # Brief delay before second message
            import time
            time.sleep(2)
            
            # Send second SMS (links + confirmation)
            message2 = self.client.messages.create(
                body=links_message,
                from_=self.from_number,
                to=restaurant_phone
            )
            print(f"SMS 2/2 sent successfully to {restaurant_phone}. Message SID: {message2.sid}")
            
            return True
            
        except Exception as e:
            print(f"Failed to send SMS to {restaurant_phone}: {e}")
            return False
    
    def send_no_videos_notification(self, restaurant_phone: str, restaurant_name: str) -> bool:
        """
        Send SMS when no suitable videos were found.
        
        Args:
            restaurant_phone: Restaurant's phone number
            restaurant_name: Restaurant's name
            
        Returns:
            True if SMS sent successfully, False otherwise
        """
        try:
            message_text = f"""
Hi {restaurant_name}!

We searched your Instagram for recent food videos to feature on your DoorDash store page, but couldn't find any that met our quality standards for customer-facing content.

To get high-quality food videos featured:
- Post clear, well-lit videos of your dishes
- Focus on the food presentation
- Use good lighting and stable camera work

We'll check again in a few weeks. Thanks!

- DoorDash Media Team
            """.strip()
            
            message = self.client.messages.create(
                body=message_text,
                from_=self.from_number,
                to=restaurant_phone
            )
            
            print(f"No-videos SMS sent to {restaurant_phone}. Message SID: {message.sid}")
            return True
            
        except Exception as e:
            print(f"Failed to send no-videos SMS to {restaurant_phone}: {e}")
            return False
    
    def _create_two_part_message(self, restaurant_name: str, approved_videos: List[Dict]) -> tuple:
        """Create two-part SMS message for video approval request."""
        
        video_count = len(approved_videos)
        
        # First message: Introduction with scores (optimized for length)
        intro_parts = [f"Hi {restaurant_name}! DoorDash found {video_count} great video{'s' if video_count > 1 else ''}:"]
        
        for i, video in enumerate(approved_videos[:3], 1):  # Limit to top 3
            analysis = video.get('analysis', {})
            score = analysis.get('overall_score', 0)
            food_items = analysis.get('food_items', [])
            food_text = f" ({food_items[0]})" if food_items else ""  # Just first item
            
            intro_parts.append(f"{i}. {score:.1f}/10{food_text}")
        
        intro_message = "\n".join(intro_parts)
        
        # Second message: Links with selection options (optimized for length)
        links_parts = ["Videos:"]
        
        for i, video in enumerate(approved_videos[:3], 1):
            shortcode = video.get('shortcode', '')
            links_parts.append(f"{i}. instagram.com/p/{shortcode}")
        
        if video_count == 1:
            links_parts.append("Reply YES/NO. -DoorDash")
        else:
            links_parts.append(f"Reply with numbers (e.g. 1,3) or ALL/NONE. -DoorDash")
        
        links_message = "\n".join(links_parts)
        
        return intro_message, links_message
    
    def _create_approval_message(self, restaurant_name: str, approved_videos: List[Dict]) -> str:
        """Legacy method - now uses two-part message but returns combined for compatibility."""
        intro, links = self._create_two_part_message(restaurant_name, approved_videos)
        return f"{intro}\n\n{links}"
    
    def _create_no_videos_message(self, restaurant_name: str) -> str:
        """Create message for when no videos are approved."""
        return f"""Hi {restaurant_name}!

We searched your Instagram for recent food videos to feature on your DoorDash store page, but couldn't find any that met our quality standards for customer-facing content.

To get high-quality food videos featured:
- Post clear, well-lit videos of your dishes
- Focus on the food presentation
- Use good lighting and stable camera work

We'll check again in a few weeks. Thanks!

- DoorDash Media Team"""
    
    def send_batch_notifications(self, notifications: List[Dict]) -> Dict[str, bool]:
        """
        Send multiple SMS notifications.
        
        Args:
            notifications: List of notification dictionaries with:
                - phone: restaurant phone number
                - name: restaurant name
                - videos: list of approved videos (or empty list)
                
        Returns:
            Dictionary mapping phone numbers to success status
        """
        results = {}
        
        for notification in notifications:
            phone = notification['phone']
            name = notification['name']
            videos = notification.get('videos', [])
            
            if videos:
                success = self.send_video_approval_request(phone, name, videos)
            else:
                success = self.send_no_videos_notification(phone, name)
            
            results[phone] = success
            
            # Rate limiting between SMS sends
            time.sleep(1)
        
        return results

def notify_restaurant(restaurant_phone: str, restaurant_name: str, 
                     approved_videos: List[Dict]) -> bool:
    """
    Convenience function to send restaurant notification.
    
    Args:
        restaurant_phone: Restaurant's phone number
        restaurant_name: Restaurant's name  
        approved_videos: List of approved videos
        
    Returns:
        True if notification sent successfully
    """
    notifier = RestaurantNotifier()
    
    if approved_videos:
        return notifier.send_video_approval_request(restaurant_phone, restaurant_name, approved_videos)
    else:
        return notifier.send_no_videos_notification(restaurant_phone, restaurant_name)