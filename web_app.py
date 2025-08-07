#!/usr/bin/env python3
"""
Modern Web UI for Restaurant Video Analyzer
Provides real-time progress updates and SMS preview
"""

import logging
import sys
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import json
import os
from main import RestaurantVideoProcessor, find_restaurant_instagram, fetch_instagram_videos, analyze_restaurant_videos, notify_restaurant
from sms_notifier import RestaurantNotifier

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)

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
    """Tracks processing progress and emits updates via WebSocket"""
    
    def __init__(self, socketio, session_id=None):
        self.socketio = socketio
        self.session_id = session_id
    """Tracks processing progress and emits updates via WebSocket"""
    
    def __init__(self, socketio):
        self.socketio = socketio
        self.current_step = 0
        self.steps = [
            "Finding Instagram Handle",
            "Fetching Recent Videos", 
            "Downloading Videos",
            "Analyzing Video Quality",
            "Filtering by Quality Score",
            "Generating SMS Preview"
        ]
        logger.info(f"🎯 WebProgressTracker initialized with {len(self.steps)} steps")
    
    def update_progress(self, step, status, message, data=None):
        """Update progress and emit to connected clients"""
        self.current_step = step
        progress_data = {
            'step': step,
            'status': status,
            'message': message,
            'total_steps': len(self.steps),
            'step_name': self.steps[step-1] if 1 <= step <= len(self.steps) else "Unknown",
            'timestamp': datetime.now().isoformat(),
            'data': data or {}
        }
        
        logger.info(f"📊 Step {step}/{len(self.steps)} - {status.upper()}: {message}")
        if data:
            logger.debug(f"📋 Step {step} data: {json.dumps(data, indent=2, default=str)}")
        
        self.socketio.emit('progress_update', progress_data)
    
    def emit_final_results(self, results):
        """Emit final processing results"""
        logger.info("🎉 Processing completed successfully")
        logger.info(f"📈 Final results: {results['videos_found']} found, {results['videos_approved']} approved")
        self.socketio.emit('processing_complete', results)

class WebRestaurantProcessor:
    """Handles restaurant processing with web progress tracking"""
    
    def __init__(self, tracker):
        self.tracker = tracker
        logger.info("🏗️ WebRestaurantProcessor initialized")
    
    def process_restaurant(self, restaurant_name, address, phone, min_quality_score=7.0, days_back=30):
        """Process restaurant with real-time progress updates"""
        logger.info(f"🚀 Starting restaurant processing: {restaurant_name}")
        logger.info(f"📍 Address: {address}")
        logger.info(f"📱 Phone: {phone}")
        logger.info(f"⭐ Min quality score: {min_quality_score}")
        logger.info(f"📅 Days back: {days_back}")
        
        try:
            # Step 1: Find Instagram handle
            self.tracker.update_progress(1, 'in_progress', f'🔍 Searching for Instagram handle...')
            
            instagram_handle = find_restaurant_instagram(restaurant_name, address)
            if not instagram_handle:
                error_msg = '❌ No Instagram handle found'
                logger.error(f"Instagram search failed for {restaurant_name}")
                self.tracker.update_progress(1, 'error', error_msg)
                return {'error': 'No Instagram handle found', 'restaurant_name': restaurant_name}
            
            logger.info(f"✅ Found Instagram handle: {instagram_handle}")
            self.tracker.update_progress(1, 'completed', f'✅ Found Instagram: {instagram_handle}', 
                                       {'instagram_handle': instagram_handle})
            
            # Step 2: Fetch videos
            self.tracker.update_progress(2, 'in_progress', f'📹 Fetching recent videos from {instagram_handle}...')
            logger.info(f"🔍 Fetching videos from {instagram_handle} (last {days_back} days)")
            
            videos = fetch_instagram_videos(instagram_handle, days_back)
            if not videos:
                error_msg = '❌ No videos found'
                logger.warning(f"No videos found for {instagram_handle}")
                self.tracker.update_progress(2, 'error', error_msg)
                return {'error': 'No videos found', 'instagram_handle': instagram_handle}
                
            logger.info(f"✅ Found {len(videos)} videos")
            self.tracker.update_progress(2, 'completed', f'✅ Found {len(videos)} recent videos', 
                                       {'videos_count': len(videos), 'videos': make_json_serializable(videos)})
            
            # Step 3: Download videos
            self.tracker.update_progress(3, 'in_progress', f'📥 Downloading {len(videos)} videos...')
            logger.info(f"📥 Starting download of {len(videos)} videos")
            
            from ytdlp_downloader import download_multiple_instagram_videos_ytdlp
            shortcodes = [video.get('shortcode') for video in videos if video.get('shortcode')]
            logger.info(f"🎬 Video shortcodes to download: {shortcodes}")
            
            downloaded_videos = download_multiple_instagram_videos_ytdlp(shortcodes)
            if not downloaded_videos:
                error_msg = '❌ Failed to download videos'
                logger.error("Video download failed")
                self.tracker.update_progress(3, 'error', error_msg)
                return {'error': 'Failed to download videos', 'instagram_handle': instagram_handle}
            
            logger.info(f"✅ Downloaded {len(downloaded_videos)} videos successfully")
            self.tracker.update_progress(3, 'completed', f'✅ Downloaded {len(downloaded_videos)} videos')
            
            # Step 4: Analyze videos
            self.tracker.update_progress(4, 'in_progress', '�� Analyzing video quality using AI...')
            logger.info("🤖 Starting AI video analysis")
            
            analyzed_videos = analyze_restaurant_videos(downloaded_videos)
            
            logger.info(f"🔍 Analysis complete for {len(analyzed_videos)} videos")
            for i, video in enumerate(analyzed_videos):
                analysis = video.get('analysis', {})
                score = analysis.get('overall_score', 0)
                recommendation = analysis.get('recommendation', 'UNKNOWN')
                logger.info(f"  Video {i+1}: Score {score:.1f}/10, Recommendation: {recommendation}")
            
            self.tracker.update_progress(4, 'completed', '✅ Video analysis complete', 
                                       {'analyzed_videos': make_json_serializable(analyzed_videos)})
            
            # Step 5: Filter approved videos
            self.tracker.update_progress(5, 'in_progress', f'🎯 Filtering videos by quality score (min: {min_quality_score})...')
            logger.info(f"🎯 Filtering videos with min score: {min_quality_score}")
            
            approved_videos = []
            for video in analyzed_videos:
                analysis = video.get('analysis', {})
                overall_score = analysis.get('overall_score', 0)
                recommendation = analysis.get('recommendation', 'REJECT')
                
                if overall_score >= min_quality_score and recommendation == 'APPROVE':
                    approved_videos.append(video)
                    logger.info(f"✅ Approved video: {video.get('shortcode')} (score: {overall_score:.1f})")
                else:
                    logger.info(f"❌ Rejected video: {video.get('shortcode')} (score: {overall_score:.1f}, rec: {recommendation})")
            
            logger.info(f"🎉 Approved {len(approved_videos)}/{len(analyzed_videos)} videos")
            self.tracker.update_progress(5, 'completed', f'✅ {len(approved_videos)} videos approved', 
                                       {'approved_count': len(approved_videos), 'approved_videos': make_json_serializable(approved_videos)})
            
            # Step 6: Generate SMS preview (don't send yet)
            self.tracker.update_progress(6, 'in_progress', '📱 Generating SMS preview...')
            logger.info("📱 Generating SMS preview")
            
            notifier = RestaurantNotifier()
            if approved_videos:
                # Create two-part SMS preview
                intro_message, links_message = notifier._create_two_part_message(restaurant_name, approved_videos)
                sms_preview = {
                    'message_1': intro_message,
                    'message_2': links_message,
                    'total_messages': 2
                }
                logger.info(f"📨 SMS preview generated: {len(intro_message)} + {len(links_message)} chars")
            else:
                sms_preview = {
                    'message_1': notifier._create_no_videos_message(restaurant_name),
                    'total_messages': 1
                }
                logger.info("📨 No-videos SMS preview generated")
                
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
            
            logger.info("🎊 Restaurant processing completed successfully")
            self.tracker.emit_final_results(results)
            return results
            
        except Exception as e:
            error_msg = f'❌ Processing failed: {str(e)}'
            logger.error(f"Processing failed for {restaurant_name}: {str(e)}", exc_info=True)
            self.tracker.update_progress(self.tracker.current_step, 'error', error_msg)
            return {'error': str(e), 'restaurant_name': restaurant_name}

# Create global progress tracker
progress_tracker = WebProgressTracker(socketio)

@app.route('/')
def index():
    """Serve the main web interface"""
    logger.info("🌐 Serving main web interface")
    return render_template('index.html')

@socketio.on('start_processing')
@socketio.on("start_processing")
def handle_start_processing(data):
    """Handle restaurant processing request via WebSocket"""
    logger.info(f"🎬 Received processing request: {data}")
    
    try:
        restaurant_name = data.get("restaurant_name", "").strip()
        address = data.get("address", "").strip()
        phone = data.get("phone", "").strip()
        min_quality_score = float(data.get("min_quality_score", 7.0))
        days_back = int(data.get("days_back", 30))
        
        if not all([restaurant_name, address, phone]):
            error_msg = "Missing required fields"
            logger.error(f"Validation failed: {error_msg}")
            emit("processing_error", {"error": error_msg})
            return
        
        # Get the current session ID for background thread communication
        session_id = request.sid
        
        # Process in background thread
        # Create session-specific progress tracker
        session_tracker = WebProgressTracker(socketio, session_id)
        processor = WebRestaurantProcessor(session_tracker)
        
        def process_in_thread():
            try:
                logger.info(f"🧵 Starting background processing thread")
                result = processor.process_restaurant(restaurant_name, address, phone, min_quality_score, days_back)
                if "error" in result:
                    logger.error(f"Processing error: {result["error"]}")
                    socketio.emit("processing_error", result, room=session_id)
                else:
                    logger.info("✅ Background processing completed successfully")
            except Exception as e:
                logger.error(f"Background thread error: {str(e)}", exc_info=True)
                socketio.emit("processing_error", {"error": f"Processing failed: {str(e)}"}, room=session_id)
        
        thread = threading.Thread(target=process_in_thread)
        thread.daemon = True
        thread.start()
        logger.info("🚀 Background processing thread started")        logger.info("🚀 Background processing thread started")
        
    except Exception as e:
        error_msg = f'Request handling failed: {str(e)}'
        logger.error(error_msg, exc_info=True)
        emit('processing_error', {'error': error_msg})

@socketio.on('send_sms')
def handle_send_sms(data):
    """Handle SMS sending request"""
    logger.info(f"📱 SMS send request: {data}")
    
    try:
        phone = data.get('phone', '').strip()
        restaurant_name = data.get('restaurant_name', '').strip()
        approved_videos = data.get('approved_videos', [])
        
        if not all([phone, restaurant_name]):
            error_msg = "Missing phone or restaurant name"
            logger.error(f"SMS validation failed: {error_msg}")
            emit('sms_error', {'error': error_msg})
            return
        
        logger.info(f"📤 Sending SMS to {phone} for {restaurant_name} with {len(approved_videos)} videos")
        
        notifier = RestaurantNotifier()
        success = notifier.send_video_approval_request(phone, restaurant_name, approved_videos)
        
        if success:
            logger.info("✅ SMS sent successfully")
            emit('sms_success', {'message': 'SMS sent successfully!'})
        else:
            logger.error("❌ SMS sending failed")
            emit('sms_error', {'error': 'Failed to send SMS'})
            
    except Exception as e:
        error_msg = f'SMS error: {str(e)}'
        logger.error(error_msg, exc_info=True)
        emit('sms_error', {'error': error_msg})

@app.route('/send_sms', methods=['POST'])
def send_sms_route():
    """REST endpoint for sending SMS"""
    logger.info(f"📱 REST SMS request received")
    
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        restaurant_name = data.get('restaurant_name', '').strip()
        approved_videos = data.get('approved_videos', [])
        
        logger.info(f"📤 Sending SMS via REST to {phone} for {restaurant_name}")
        
        notifier = RestaurantNotifier()
        success = notifier.send_video_approval_request(phone, restaurant_name, approved_videos)
        
        if success:
            logger.info("✅ REST SMS sent successfully")
            return jsonify({'success': True, 'message': 'SMS sent successfully!'})
        else:
            logger.error("❌ REST SMS sending failed")
            return jsonify({'error': 'Failed to send SMS'}), 500
            
    except Exception as e:
        error_msg = f'SMS error: {str(e)}'
        logger.error(error_msg, exc_info=True)
        return jsonify({'error': error_msg}), 500

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info('👤 Client connected to WebSocket')
    emit('connected', {'status': 'Connected to restaurant analyzer'})

@app.route("/logs")
def view_logs():
    """Simple endpoint to view recent logs (for debugging)"""
    try:
        log_info = {
            "message": "Detailed logs are available in Railway dashboard under Deploy Logs tab",
            "log_level": os.environ.get("LOG_LEVEL", "INFO"),
            "debug_mode": os.environ.get("DEBUG", "false"),
            "timestamp": datetime.now().isoformat()
        }
        return jsonify(log_info)
    except Exception as e:
        logger.error(f"Error accessing logs: {str(e)}")
        return jsonify({"error": "Could not access logs"}), 500

@app.route("/health")
def health_check():
    """Health check endpoint"""
    logger.info("🏥 Health check requested")
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })
@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info('👋 Client disconnected from WebSocket')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    logger.info("🚀 Starting Restaurant Video Analyzer Web UI...")
    logger.info(f"🌍 Environment: {'Development' if debug_mode else 'Production'}")
    logger.info(f"📱 Server will run on port: {port}")
    logger.info(f"🔧 Debug mode: {debug_mode}")
    
    # Set logging level based on environment
    if debug_mode:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🐛 Debug logging enabled")
    
    logger.info(f"🌐 Open your browser to: http://localhost:{port}")
    socketio.run(app, debug=debug_mode, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)


