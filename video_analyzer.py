"""Video analysis module using LLM for quality assessment."""

import cv2
import base64
import os
from typing import Dict, List, Optional
from pathlib import Path
import openai
from config import settings
import json
import time

class VideoQualityAnalyzer:
    """Analyze video quality for restaurant marketing using LLM."""
    
    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key is required for video analysis")
        
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        
        # Ensure frames directory exists
        settings.frames_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_frames(self, video_path: str, max_frames: int = 5) -> List[str]:
        """
        Extract representative frames from video for analysis.
        
        Args:
            video_path: Path to the video file
            max_frames: Maximum number of frames to extract
            
        Returns:
            List of paths to extracted frame images
        """
        frame_paths = []
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Failed to open video: {video_path}")
                return []
            
            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            
            # Skip very long videos
            if duration > settings.max_video_duration_seconds:
                print(f"Video too long ({duration:.1f}s), skipping frame extraction")
                cap.release()
                return []
            
            # Calculate frame intervals
            if total_frames <= max_frames:
                frame_indices = list(range(0, total_frames, max(1, total_frames // max_frames)))
            else:
                frame_indices = [int(i * total_frames / max_frames) for i in range(max_frames)]
            
            video_name = Path(video_path).stem
            
            for i, frame_idx in enumerate(frame_indices):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                
                if ret:
                    frame_filename = f"{video_name}_frame_{i:02d}.jpg"
                    frame_path = settings.frames_dir / frame_filename
                    
                    # Save frame
                    cv2.imwrite(str(frame_path), frame)
                    frame_paths.append(str(frame_path))
                else:
                    print(f"Failed to read frame {frame_idx}")
            
            cap.release()
            print(f"Extracted {len(frame_paths)} frames from {video_path}")
            
        except Exception as e:
            print(f"Error extracting frames from {video_path}: {e}")
        
        return frame_paths
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """Encode image to base64 for OpenAI API."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def analyze_video_quality(self, video_info: Dict) -> Dict:
        """
        Analyze video quality using LLM on extracted frames.
        
        Args:
            video_info: Video metadata with 'local_path'
            
        Returns:
            Analysis results dictionary
        """
        if 'local_path' not in video_info:
            return {'error': 'No local video path provided'}
        
        video_path = video_info['local_path']
        if not os.path.exists(video_path):
            return {'error': f'Video file not found: {video_path}'}
        
        # Extract frames for analysis
        frame_paths = self.extract_frames(video_path)
        if not frame_paths:
            return {'error': 'Failed to extract frames from video'}
        
        try:
            # Prepare images for API
            image_data = []
            for frame_path in frame_paths[:3]:  # Limit to 3 frames for cost efficiency
                base64_image = self.encode_image_to_base64(frame_path)
                image_data.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                        "detail": "high"
                    }
                })
            
            # Create analysis prompt
            prompt = self._create_analysis_prompt(video_info)
            
            # Prepare messages for API
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        *image_data
                    ]
                }
            ]
            
            print(f"Analyzing video quality for {Path(video_path).stem}...")
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Updated to current vision model
                messages=messages,
                max_tokens=1000,
                temperature=0.1
            )
            
            # Parse response
            analysis_text = response.choices[0].message.content
            analysis_result = self._parse_analysis_response(analysis_text)
            
            # Add metadata
            analysis_result.update({
                'video_shortcode': video_info.get('shortcode', ''),
                'video_url': video_info.get('url', ''),
                'analysis_timestamp': time.time(),
                'frames_analyzed': len(image_data)
            })
            
            # Clean up frame files
            self._cleanup_frames(frame_paths)
            
            return analysis_result
            
        except Exception as e:
            print(f"Error analyzing video quality: {e}")
            return {'error': f'Analysis failed: {str(e)}'}
    
    def _create_analysis_prompt(self, video_info: Dict) -> str:
        """Create analysis prompt for the LLM."""
        caption = video_info.get('caption', 'No caption')
        
        prompt = f"""
Analyze these video frames from a restaurant's Instagram post for use on a DoorDash store page.

Video Caption: "{caption}"

Please evaluate the video on these criteria and provide a JSON response:

1. FOOD_QUALITY (1-10): How appetizing and high-quality does the food look?
2. VISUAL_APPEAL (1-10): Overall visual aesthetics, lighting, composition
3. PROFESSIONALISM (1-10): Does it look professionally shot or at least well-made?
4. BRAND_SAFETY (1-10): Is the content appropriate for a food delivery platform?
5. MARKETING_VALUE (1-10): How effective would this be for attracting customers?

Also provide:
- RECOMMENDATION: "APPROVE" or "REJECT" for DoorDash store page
- REASONING: Brief explanation of your decision
- HIGHLIGHTS: What makes this video good/bad
- FOOD_ITEMS: List any specific food items you can identify

Respond in valid JSON format only:
{{
    "food_quality": 8,
    "visual_appeal": 7,
    "professionalism": 6,
    "brand_safety": 9,
    "marketing_value": 8,
    "overall_score": 7.6,
    "recommendation": "APPROVE",
    "reasoning": "Your explanation here",
    "highlights": ["Good point 1", "Good point 2"],
    "food_items": ["Pizza", "Burger"]
}}
"""
        return prompt
    
    def _parse_analysis_response(self, response_text: str) -> Dict:
        """Parse LLM response into structured data."""
        try:
            # Try to extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_text = response_text[json_start:json_end]
                analysis = json.loads(json_text)
                
                # Ensure required fields
                required_fields = ['food_quality', 'visual_appeal', 'professionalism', 
                                 'brand_safety', 'marketing_value', 'recommendation']
                
                for field in required_fields:
                    if field not in analysis:
                        analysis[field] = 0 if field != 'recommendation' else 'REJECT'
                
                # Calculate overall score if not provided
                if 'overall_score' not in analysis:
                    scores = [analysis.get(field, 0) for field in required_fields[:-1]]
                    analysis['overall_score'] = sum(scores) / len(scores)
                
                return analysis
            else:
                raise ValueError("No valid JSON found in response")
                
        except Exception as e:
            print(f"Error parsing analysis response: {e}")
            return {
                'food_quality': 0,
                'visual_appeal': 0,
                'professionalism': 0,
                'brand_safety': 0,
                'marketing_value': 0,
                'overall_score': 0,
                'recommendation': 'REJECT',
                'reasoning': f'Failed to parse analysis: {str(e)}',
                'highlights': [],
                'food_items': []
            }
    
    def _cleanup_frames(self, frame_paths: List[str]):
        """Clean up extracted frame files."""
        for frame_path in frame_paths:
            try:
                os.remove(frame_path)
            except Exception as e:
                print(f"Failed to remove frame {frame_path}: {e}")
    
    def analyze_videos_batch(self, videos: List[Dict]) -> List[Dict]:
        """
        Analyze multiple videos for quality.
        
        Args:
            videos: List of video dictionaries with 'local_path'
            
        Returns:
            List of videos with added 'analysis' field
        """
        analyzed_videos = []
        
        for video in videos:
            print(f"Analyzing video: {video.get('shortcode', 'unknown')}")
            
            analysis = self.analyze_video_quality(video)
            video['analysis'] = analysis
            
            analyzed_videos.append(video)
            
            # Rate limiting for API calls
            time.sleep(2)
        
        return analyzed_videos

def analyze_restaurant_videos(videos: List[Dict]) -> List[Dict]:
    """
    Convenience function to analyze restaurant videos.
    
    Args:
        videos: List of video dictionaries with local paths
        
    Returns:
        List of videos with analysis results
    """
    analyzer = VideoQualityAnalyzer()
    return analyzer.analyze_videos_batch(videos)