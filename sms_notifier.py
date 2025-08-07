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
        Send SMS to restaurant requesting approval for selected videos.
        
        Args:
            restaurant_phone: Restaurant's phone number
            restaurant_name: Restaurant's name
            approved_videos: List of videos that passed quality analysis
            
        Returns:
            True if SMS sent successfully, False otherwise
        """
        try:
            if not approved_videos:
                print("No approved videos to send")
                return False
            
            message_text = self._create_approval_message(restaurant_name, approved_videos)
            
            message = self.client.messages.create(
                body=message_text,
                from_=self.from_number,
                to=restaurant_phone
            )
            
            print(f"SMS sent successfully to {restaurant_phone}. Message SID: {message.sid}")
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
    
    def _create_approval_message(self, restaurant_name: str, approved_videos: List[Dict]) -> str:
        """Create the approval request message text."""
        
        video_count = len(approved_videos)
        
        message = f"""
Hi {restaurant_name}!

We found {video_count} high-quality video{'s' if video_count > 1 else ''} from your Instagram that would be great for your DoorDash store page to help customers see your delicious food!

Video{'s' if video_count > 1 else ''}:
"""
        
        for i, video in enumerate(approved_videos[:3], 1):  # Limit to 3 videos for SMS length
            analysis = video.get('analysis', {})
            score = analysis.get('overall_score', 0)
            food_items = analysis.get('food_items', [])
            
            food_text = f" ({', '.join(food_items[:2])})" if food_items else ""
            
            # Construct Instagram URL from shortcode or use existing URL
            instagram_url = video.get('original_url', '')
            if not instagram_url and video.get('shortcode'):
                instagram_url = f"https://www.instagram.com/p/{video['shortcode']}/"
            
            message += f"\n{i}. Quality Score: {score:.1f}/10{food_text}\n   📹 {instagram_url}"
        
        if video_count > 3:
            message += f"\n...and {video_count - 3} more!"
        
        message += f"""

These videos will help customers see your food and increase orders! 

Reply YES to approve using these videos on your DoorDash store page, or NO if you prefer not to.

Questions? Contact DoorDash Merchant Support.

- DoorDash Media Team
        """.strip()
        
        return message
    
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