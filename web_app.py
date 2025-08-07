#!/usr/bin/env python3
"""
Modern Web UI for Restaurant Video Analyzer
Provides real-time progress updates and SMS preview
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import json
from datetime import datetime
from main import RestaurantVideoProcessor, find_restaurant_instagram, fetch_instagram_videos, analyze_restaurant_videos, notify_restaurant
from sms_notifier import RestaurantNotifier

def make_json_serializable(data):
    """Convert datetime objects to strings for JSON serialization."""
    if isinstance(data, list):
        return [make_json_serializable(item) for item in data]
    elif isinstance(data, dict):
        result = {}
        for key, value in data.items():
            result[key] = make_json_serializable(value)
        return result
    elif hasattr(data, 'isoformat'):  # datetime objects
        return data.isoformat()
    else:
        return data

app = Flask(__name__)
app.config['SECRET_KEY'] = 'restaurant-video-analyzer-2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

class WebProgressTracker:
    """Track progress and emit updates to web clients"""
    
    def __init__(self, socketio_instance):
        self.socketio = socketio_instance
        self.current_step = 0
        self.total_steps = 6
        self.progress_data = {}
        
    def update_progress(self, step, status, message, data=None):
        """Update progress and emit to all connected clients"""
        self.current_step = step
        progress_percent = int((step / self.total_steps) * 100)
        
        update = {
            'step': step,
            'total_steps': self.total_steps,
            'progress_percent': progress_percent,
            'status': status,  # 'in_progress', 'completed', 'error'
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'data': data or {}
        }
        
        self.progress_data[step] = update
        self.socketio.emit('progress_update', update)
        
    def emit_final_results(self, results):
        """Emit final processing results"""
        self.socketio.emit('processing_complete', results)

class WebRestaurantProcessor:
    """Web processor with real-time progress tracking"""
    
    def __init__(self, progress_tracker):
        self.tracker = progress_tracker
        
    def process_restaurant_with_progress(self, restaurant_name, address, phone, min_quality_score=5.0, days_back=30):
        """Process restaurant with real-time web progress updates"""
        
        try:
            # Step 1: Find Instagram handle
            self.tracker.update_progress(1, 'in_progress', f'🔍 Searching for Instagram handle for {restaurant_name}...')
            
            instagram_handle = find_restaurant_instagram(restaurant_name, address, phone)
            if not instagram_handle:
                self.tracker.update_progress(1, 'error', '❌ Could not find Instagram handle')
                return {'error': 'Instagram handle not found'}
                
            self.tracker.update_progress(1, 'completed', f'✅ Found Instagram: @{instagram_handle}', 
                                       {'instagram_handle': instagram_handle})
            
            # Step 2: Fetch videos
            self.tracker.update_progress(2, 'in_progress', f'📹 Fetching recent videos from @{instagram_handle}...')
            
            videos = fetch_instagram_videos(instagram_handle, days_back)
            if not videos:
                self.tracker.update_progress(2, 'error', '❌ No videos found')
                return {'error': 'No videos found', 'instagram_handle': instagram_handle}
                
            self.tracker.update_progress(2, 'completed', f'✅ Found {len(videos)} recent videos', 
                                       {'videos_count': len(videos), 'videos': make_json_serializable(videos)})
            
            # Step 3: Download videos
            self.tracker.update_progress(3, 'in_progress', f'📥 Downloading {len(videos)} videos...')
            
            from ytdlp_downloader import download_multiple_instagram_videos_ytdlp
            shortcodes = [video.get('shortcode') for video in videos if video.get('shortcode')]
            downloaded_videos = download_multiple_instagram_videos_ytdlp(shortcodes)
            
            if not downloaded_videos:
                self.tracker.update_progress(3, 'error', '❌ Failed to download videos')
                return {'error': 'Download failed', 'instagram_handle': instagram_handle}
                
            self.tracker.update_progress(3, 'completed', f'✅ Downloaded {len(downloaded_videos)} videos successfully', 
                                       {'downloaded_count': len(downloaded_videos)})
            
            # Step 4: Analyze videos
            self.tracker.update_progress(4, 'in_progress', '🤖 Analyzing video quality using AI...')
            
            analyzed_videos = analyze_restaurant_videos(downloaded_videos)
            
            self.tracker.update_progress(4, 'completed', '✅ Video analysis complete', 
                                       {'analyzed_videos': make_json_serializable(analyzed_videos)})
            
            # Step 5: Filter approved videos
            self.tracker.update_progress(5, 'in_progress', f'🎯 Filtering videos by quality score (min: {min_quality_score})...')
            
            approved_videos = []
            for video in analyzed_videos:
                analysis = video.get('analysis', {})
                overall_score = analysis.get('overall_score', 0)
                recommendation = analysis.get('recommendation', 'REJECT')
                
                if overall_score >= min_quality_score and recommendation == 'APPROVE':
                    approved_videos.append(video)
            
            self.tracker.update_progress(5, 'completed', f'✅ {len(approved_videos)} videos approved', 
                                       {'approved_count': len(approved_videos), 'approved_videos': make_json_serializable(approved_videos)})
            
            # Step 6: Generate SMS preview (don't send yet)
            self.tracker.update_progress(6, 'in_progress', '📱 Generating SMS preview...')
            
            notifier = RestaurantNotifier()
            if approved_videos:
                # Create two-part SMS preview
                intro_message, links_message = notifier._create_two_part_message(restaurant_name, approved_videos)
                sms_preview = {
                    'message_1': intro_message,
                    'message_2': links_message,
                    'total_messages': 2
                }
            else:
                sms_preview = {
                    'message_1': notifier._create_no_videos_message(restaurant_name),
                    'total_messages': 1
                }
                
            self.tracker.update_progress(6, 'completed', '✅ SMS preview ready')
            
            # Final results
            results = {
                'restaurant_name': restaurant_name,
                'address': address,
                'phone': phone,
                'instagram_handle': instagram_handle,
                'videos_found': len(videos),
                'videos_downloaded': len(downloaded_videos),
                'videos_approved': len(approved_videos),
                'approved_videos': make_json_serializable(approved_videos),
                'sms_preview': sms_preview,
                'processing_timestamp': datetime.now().isoformat()
            }
            
            self.tracker.emit_final_results(results)
            return results
            
        except Exception as e:
            error_msg = f'❌ Processing failed: {str(e)}'
            self.tracker.update_progress(self.tracker.current_step, 'error', error_msg)
            return {'error': str(e)}

# Create global progress tracker
progress_tracker = WebProgressTracker(socketio)

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_restaurant():
    """Start restaurant processing"""
    
    data = request.get_json()
    restaurant_name = data.get('restaurant_name', '').strip()
    address = data.get('address', '').strip()
    phone = data.get('phone', '').strip()
    min_score = float(data.get('min_score', 5.0))
    
    if not all([restaurant_name, address, phone]):
        return jsonify({'error': 'All fields are required'}), 400
    
    # Start processing in background thread
    def process_in_background():
        processor = WebRestaurantProcessor(progress_tracker)
        processor.process_restaurant_with_progress(restaurant_name, address, phone, min_score)
    
    threading.Thread(target=process_in_background, daemon=True).start()
    
    return jsonify({'status': 'processing_started'})

@app.route('/send_sms', methods=['POST'])
def send_sms():
    """Send SMS to restaurant"""
    
    data = request.get_json()
    phone = data.get('phone', '').strip()
    restaurant_name = data.get('restaurant_name', '').strip()
    approved_videos = data.get('approved_videos', [])
    
    if not all([phone, restaurant_name]):
        return jsonify({'error': 'Phone and restaurant name are required'}), 400
    
    try:
        notifier = RestaurantNotifier()
        if approved_videos:
            success = notifier.send_video_approval_request(phone, restaurant_name, approved_videos)
        else:
            success = notifier.send_no_videos_notification(phone, restaurant_name)
            
        if success:
            return jsonify({'status': 'sms_sent', 'message': 'SMS sent successfully!'})
        else:
            return jsonify({'error': 'Failed to send SMS'}), 500
            
    except Exception as e:
        return jsonify({'error': f'SMS error: {str(e)}'}), 500

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('connected', {'status': 'Connected to restaurant analyzer'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print("�� Starting Restaurant Video Analyzer Web UI...")
    print(f"📱 Open your browser to: http://localhost:{port}")
    socketio.run(app, debug=False, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)