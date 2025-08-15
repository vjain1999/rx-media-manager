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
from video_analyzer import VideoQualityAnalyzer
from config import settings
import csv
import io
from web_search import RestaurantInstagramFinder
import uuid
import time as _time
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
            "step": step,
            "status": status,
            "message": message,
            "total_steps": len(self.steps),
            "step_name": self.steps[step-1] if 1 <= step <= len(self.steps) else "Unknown",
            "timestamp": datetime.now().isoformat(),
            "data": data or {}
        }
        
        logger.info(f"📊 Step {step}/{len(self.steps)} - {status.upper()}: {message}")
        if data:
            logger.debug(f"📋 Step {step} data: {json.dumps(data, indent=2, default=str)}")
        
        if self.session_id:
            self.socketio.emit("progress_update", progress_data, room=self.session_id)
        else:
            self.socketio.emit("progress_update", progress_data)
    
    def emit_final_results(self, results):
        """Emit final processing results"""
        logger.info("🎉 Processing completed successfully")
        logger.info("📈 Final results: %s found, %s approved", results.get("videos_found", 0), results.get("videos_approved", 0))
        if self.session_id:
            self.socketio.emit("processing_complete", results, room=self.session_id)
        else:
            self.socketio.emit("processing_complete", results)

class WebRestaurantProcessor:
    """Handles restaurant processing with web progress tracking"""
    
    def __init__(self, tracker):
        self.tracker = tracker
        logger.info("🏗️ WebRestaurantProcessor initialized")
    
    def process_restaurant(self, restaurant_name, address, phone, min_quality_score=5.0, days_back=30):
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

@app.route('/api/find_instagram', methods=['POST'])
def api_find_instagram():
    try:
        data = request.get_json()
        restaurant_name = (data.get('restaurant_name') or '').strip()
        address = (data.get('address') or '').strip()
        phone = (data.get('phone') or '').strip()
        if not restaurant_name or not address:
            return jsonify({'error': 'Missing restaurant_name or address'}), 400
        handle = find_restaurant_instagram(restaurant_name, address, phone)
        if not handle:
            return jsonify({'instagram_handle': None, 'message': 'No handle found'}), 200
        return jsonify({'instagram_handle': handle})
    except Exception as e:
        logger.exception('find_instagram API failed')
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze_frames', methods=['POST'])
def api_analyze_frames():
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'No video file uploaded'}), 400
        file = request.files['video']
        caption = request.form.get('caption', '')
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400

        # Save to temp path in configured videos dir
        save_dir = settings.videos_dir
        save_dir.mkdir(parents=True, exist_ok=True)
        temp_path = os.path.join(str(save_dir), file.filename)
        file.save(temp_path)

        analyzer = VideoQualityAnalyzer()
        analysis = analyzer.analyze_video_quality({'local_path': temp_path, 'caption': caption})

        # Optionally remove uploaded file after analysis
        try:
            os.remove(temp_path)
        except Exception:
            pass

        return jsonify(analysis)
    except Exception as e:
        logger.exception('analyze_frames API failed')
        return jsonify({'error': str(e)}), 500

@app.route('/api/bulk_find_instagram', methods=['POST'])
def api_bulk_find_instagram():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        file = request.files['file']
        if not file.filename.lower().endswith('.csv'):
            return jsonify({'error': 'Please upload a .csv file'}), 400

        # Read CSV
        stream = io.StringIO(file.stream.read().decode('utf-8', errors='ignore'))
        reader = csv.DictReader(stream)
        required_cols = {'business_id', 'restaurant_name', 'address'}
        if not required_cols.issubset({c.strip() for c in reader.fieldnames or []}):
            return jsonify({'error': 'CSV must include columns: business_id, restaurant_name, address'}), 400

        rows = list(reader)

        # Create a bulk job and process in background with progress
        job_id = str(uuid.uuid4())
        if not hasattr(app, 'bulk_jobs'):
            app.bulk_jobs = {}
        app.bulk_jobs[job_id] = {
            'status': 'running',
            'created_at': _time.time(),
            'total': len(rows),
            'completed': 0,
            'results': []
        }

        def process_bulk_job(job_id_local: str, rows_local):
            try:
                finder = RestaurantInstagramFinder()
                from concurrent.futures import ThreadPoolExecutor, as_completed
                max_workers = max(1, settings.bulk_find_max_workers)
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(finder._process_single_row, row): row for row in rows_local}
                    for future in as_completed(futures):
                        try:
                            result = future.result()
                        except Exception as e:  # pragma: no cover
                            row = futures[future]
                            result = {
                                'business_id': row.get('business_id', ''),
                                'restaurant_name': row.get('restaurant_name', ''),
                                'address': row.get('address', ''),
                                'phone': row.get('phone', ''),
                                'instagram_handle': '',
                                'status': 'error',
                                'message': str(e)
                            }
                        # Deduplicate by business_id, choose the most likely/common handle
                        job = app.bulk_jobs.get(job_id_local)
                        if not job:
                            continue
                        existing = job['results']
                        bid = (result.get('business_id') or '').strip()
                        if bid:
                            # gather all results so far for this business_id including new one
                            candidates = [r for r in existing if (r.get('business_id') or '').strip() == bid]
                            candidates.append(result)
                            # score: prefer explicit ok over probable over not_found/error; then higher AI confidence if present
                            def score(r):
                                status = r.get('status', '')
                                s = 2 if status == 'ok' else 1 if status == 'probable' else 0
                                conf = r.get('ai_confidence', 0.0)
                                return (s, conf)
                            best = sorted(candidates, key=score, reverse=True)[0]
                            # remove previous entries for this business_id
                            job['results'] = [r for r in existing if (r.get('business_id') or '').strip() != bid]
                            job['results'].append(best)
                        else:
                            job['results'].append(result)
                        job['completed'] += 1
                # Done
                job = app.bulk_jobs.get(job_id_local)
                if job:
                    job['status'] = 'done'
            except Exception as e:  # pragma: no cover
                job = app.bulk_jobs.get(job_id_local)
                if job:
                    job['status'] = f'error: {e}'

        t = threading.Thread(target=process_bulk_job, args=(job_id, rows))
        t.daemon = True
        t.start()

        return jsonify({'job_id': job_id})
    except Exception as e:
        logger.exception('bulk_find_instagram API failed')
        return jsonify({'error': str(e)}), 500

@app.route('/api/bulk_status', methods=['GET'])
def api_bulk_status():
    job_id = request.args.get('job_id', '').strip()
    job = getattr(app, 'bulk_jobs', {}).get(job_id)
    if not job:
        return jsonify({'error': 'job not found'}), 404
    total = max(1, job.get('total', 1))
    completed = job.get('completed', 0)
    percent = int((completed / total) * 100)
    # Support cursor-based pagination using 'from' index to avoid duplicates client-side
    results = job.get('results', [])
    from_index_raw = request.args.get('from', '').strip()
    try:
        from_index = int(from_index_raw) if from_index_raw != '' else None
    except Exception:
        from_index = None
    if from_index is not None and 0 <= from_index <= len(results):
        latest = results[from_index:]
    else:
        # default: last 50
        latest = results[-50:] if len(results) > 50 else results
    return jsonify({
        'status': job.get('status'),
        'total': total,
        'completed': completed,
        'percent': percent,
        'latest': latest,
        'next_index': len(results)
    })

@app.route('/api/bulk_download', methods=['GET'])
def api_bulk_download():
    job_id = request.args.get('job_id', '').strip()
    job = getattr(app, 'bulk_jobs', {}).get(job_id)
    if not job:
        return jsonify({'error': 'job not found'}), 404
    results = job.get('results', [])
    headers = ['business_id','restaurant_name','address','phone','instagram_handle','status','message']
    import csv as _csv
    from io import StringIO
    buf = StringIO()
    writer = _csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    for r in results:
        writer.writerow({h: (r.get(h, '') if r.get(h, '') is not None else '') for h in headers})
    csv_data = buf.getvalue()
    from flask import Response
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=ig_handles_{job_id}.csv'}
    )

@socketio.on('start_processing')
@socketio.on("start_processing")
def handle_start_processing(data):
    """Handle restaurant processing request via WebSocket"""
    logger.info(f"🎬 Received processing request: {data}")
    
    try:
        restaurant_name = data.get("restaurant_name", "").strip()
        address = data.get("address", "").strip()
        phone = data.get("phone", "").strip()
        min_quality_score = float(data.get("min_score", 5.0))
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
                    logger.error("Processing error: %s", result.get("error", "Unknown error"))
                    socketio.emit("processing_error", result, room=session_id)
                else:
                    logger.info("✅ Background processing completed successfully")
            except Exception as e:
                logger.error(f"Background thread error: {str(e)}", exc_info=True)
                socketio.emit("processing_error", {"error": f"Processing failed: {str(e)}"}, room=session_id)
        
        thread = threading.Thread(target=process_in_thread)
        thread.daemon = True
        thread.start()
        logger.info("�� Background processing thread started")
        
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
    
    # Decode cookies from base64 env if provided (IG_COOKIES_B64 or chunked IG_COOKIES_B64_1..N)
    try:
        import base64, os
        cookies_b64 = os.environ.get('IG_COOKIES_B64', '')
        # Support chunked variables to bypass platform length limits
        if not cookies_b64:
            parts = []
            for i in range(1, 11):  # up to 10 parts
                part = os.environ.get(f'IG_COOKIES_B64_{i}', '')
                if not part:
                    break
                parts.append(part.strip())
            if parts:
                cookies_b64 = ''.join(parts)
        cookies_path = os.environ.get('IG_COOKIES_FILE', '') or '/app/secrets/insta_cookies.txt'
        if cookies_b64 and cookies_path:
            os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
            decoded = base64.b64decode(cookies_b64)
            with open(cookies_path, 'wb') as f:
                f.write(decoded)
            logger.info(
                "🍪 Wrote Instagram cookies to %s (%d base64 chars, %d bytes decoded)%s",
                cookies_path,
                len(cookies_b64),
                len(decoded),
                " from chunked vars" if os.environ.get('IG_COOKIES_B64_1') else ""
            )
        else:
            logger.info("🍪 IG_COOKIES_B64 not provided; skipping cookie file write. Using existing path: %s", cookies_path)
    except Exception:
        logger.exception("Failed to decode IG_COOKIES_B64")
    
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


