"""
Analysis Routes - PDF analysis and detection endpoints
"""
import os
import io
import uuid
import json
import tempfile
import threading
import logging
from datetime import datetime
from collections import Counter

import fitz
from flask import request, jsonify, send_file, render_template_string

import config
from models import FireAlarmDevice, PageAnalysis

logger = logging.getLogger(__name__)

# Storage for analysis jobs
analysis_jobs = {}
analysis_lock = threading.Lock()


def register_analysis_routes(app, analyzer):
    """Register analysis-related routes"""
    
    @app.route("/")
    def index():
        """Serve the main HTML interface"""
        # Read HTML from template file
        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'index.html')
        with open(template_path, 'r') as f:
            html_content = f.read()
        return render_template_string(html_content)
    

    @app.route("/api/check_status", methods=["GET"])
    def check_status():
        """Check API status and configuration"""
        local_model_path = getattr(config, 'LOCAL_MODEL_PATH', '') or ''
        model_filename = os.path.basename(local_model_path) if local_model_path else ''
        model_name = os.path.splitext(model_filename)[0] if model_filename else ''
        expose_model_path = os.environ.get('EXPOSE_MODEL_PATH', '').lower() in {"1", "true", "yes"}

        response = {
            'local_model_configured': analyzer.local_detector is not None,
            'gemini_configured': analyzer.gemini_analyzer.is_available(),
            'local_model_name': model_name,
            'local_model_filename': model_filename,
            'local_detector_error': analyzer.local_detector_error,
        }

        if expose_model_path:
            response['local_model_path'] = local_model_path
            response['model_path'] = local_model_path  # legacy alias
        else:
            response['local_model_path'] = None
            response['model_path'] = None

        return jsonify(response)

    @app.route("/api/analyze", methods=["POST"])
    def analyze_pdf():
        """Analyze uploaded PDF with local detection"""
        if 'pdf' not in request.files:
            return jsonify({'success': False, 'error': 'No PDF file provided'}), 400
        
        pdf_file = request.files['pdf']
        if pdf_file.filename == '':
            return jsonify({'success': False, 'error': 'Empty filename'}), 400
        
        # Get options from request
        skip_blank = request.form.get('skip_blank', 'true').lower() == 'true'
        skip_edges = request.form.get('skip_edges', 'false').lower() == 'true'
        use_parallel = request.form.get('use_parallel', 'true').lower() == 'true'
        use_cache = request.form.get('use_cache', 'true').lower() == 'true'
        confidence = float(request.form.get('confidence', config.DEFAULT_CONFIDENCE))
        
        # Handle page selection
        selected_pages_str = request.form.get('selected_pages')
        selected_pages = None
        if selected_pages_str:
            try:
                selected_pages = [int(p) for p in selected_pages_str.split(',')]
                logger.info(f"Will analyze pages: {selected_pages}")
                if not selected_pages:
                    return jsonify({'success': False, 'error': 'No valid pages selected'}), 400
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid page numbers'}), 400
        
        # Save uploaded file
        job_id = str(uuid.uuid4())
        temp_dir = tempfile.mkdtemp()
        pdf_path = os.path.join(temp_dir, 'upload.pdf')
        pdf_file.save(pdf_path)
        
        try:
            logger.info(f"Starting analysis job {job_id}")
            
            # Run analysis
            results = _run_local_detection_analysis(
                analyzer,
                pdf_path,
                skip_blank,
                skip_edges,
                use_parallel,
                use_cache,
                confidence,
                selected_pages
            )
            
            if selected_pages:
                results['selected_pages'] = selected_pages
            
            # Store results
            with analysis_lock:
                analysis_jobs[job_id] = {
                    'results': results,
                    'pdf_path': pdf_path,
                    'temp_dir': temp_dir,
                    'timestamp': datetime.now().isoformat()
                }
            
            logger.info(f"Analysis job {job_id} completed")
            
            response_data = {
                'success': True,
                'job_id': job_id,
                'total_devices': sum(len(page.get('devices', [])) for page in results.get('page_analyses', [])),
                'pages_with_devices': sum(1 for page in results.get('page_analyses', []) if page.get('devices')),
                'total_pages': len(results.get('page_analyses', [])),
                'page_analyses': results.get('page_analyses', [])
            }
            
            return jsonify(response_data)
            
        except Exception as e:
            logger.error(f"Error in analysis: {str(e)}", exc_info=True)
            # Cleanup on error
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route("/api/analyze_gemini", methods=["POST"])
    def analyze_gemini():
        """Analyze PDF using Gemini AI"""
        if not analyzer.gemini_analyzer.is_available():
            return jsonify({'success': False, 'error': 'Gemini AI not configured'}), 400
        
        if 'pdf' not in request.files:
            return jsonify({'success': False, 'error': 'No PDF file provided'}), 400
        
        pdf_file = request.files['pdf']
        if pdf_file.filename == '':
            return jsonify({'success': False, 'error': 'Empty filename'}), 400
        
        # Save uploaded file
        job_id = str(uuid.uuid4())
        temp_dir = tempfile.mkdtemp()
        pdf_path = os.path.join(temp_dir, 'upload.pdf')
        pdf_file.save(pdf_path)
        
        try:
            logger.info(f"Starting Gemini analysis job {job_id}")
            
            # =================================================================
            # UPDATED CALL: Pass the pdf_path directly to the new analyzer
            # The new analyzer handles its own text extraction.
            results = analyzer.gemini_analyzer.analyze_pdf(pdf_path)
            # =================================================================
            
            # Store results
            with analysis_lock:
                analysis_jobs[job_id] = {
                    'results': results,
                    'pdf_path': pdf_path,
                    'temp_dir': temp_dir,
                    'timestamp': datetime.now().isoformat(),
                    'analysis_type': 'gemini'
                }
            
            logger.info(f"Gemini analysis {job_id} completed")
            
            # The 'results' object from analyze_pdf already contains 'success'
            return jsonify(results)
            
        except Exception as e:
            logger.error(f"Error in Gemini analysis: {str(e)}", exc_info=True)
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route("/api/visualize/<job_id>/<int:page_num>", methods=["GET"])
    def visualize_page(job_id, page_num):
        """Get visualized page with detections"""
        with analysis_lock:
            if job_id not in analysis_jobs:
                return jsonify({'success': False, 'error': 'Job not found'}), 404
            job = analysis_jobs[job_id]
        
        try:
            # Convert PDF page to image
            # Pass page_num as a single-item list
            images = analyzer.pdf_processor.pdf_to_images(job['pdf_path'], selected_pages=[page_num])
            if not images:
                return jsonify({'success': False, 'error': 'Invalid page number'}), 404
            
            image = images[0] # We only requested one image
            
            # Create and process tiles
            tiles, _ = analyzer.pdf_processor.create_tiles(
                image,
                skip_blank=True,
                skip_edges=False,
                prioritize_complex=True
            )
            
            if not tiles:
                # Return original image if no tiles
                img_io = io.BytesIO()
                image.save(img_io, 'JPEG', quality=95)
                img_io.seek(0)
                return send_file(img_io, mimetype='image/jpeg')
            
            # Run detection
            detections, _ = analyzer.local_detector.process_all_tiles_parallel(
                tiles, config.DEFAULT_CONFIDENCE, config.MAX_WORKERS, use_cache=True
            )
            
            # Remove overlaps
            filtered_detections = analyzer.visualizer.remove_overlapping_detections(detections)
            
            # Draw detections
            annotated_image = analyzer.visualizer.draw_detections(image, filtered_detections)
            
            # Convert to bytes
            img_io = io.BytesIO()
            annotated_image.save(img_io, 'JPEG', quality=95)
            img_io.seek(0)
            
            return send_file(img_io, mimetype='image/jpeg')
            
        except Exception as e:
            logger.error(f"Error visualizing page: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route("/api/export/<job_id>", methods=["GET"])
    def export_results(job_id):
        """Export analysis results as JSON"""
        with analysis_lock:
            if job_id not in analysis_jobs:
                return jsonify({'success': False, 'error': 'Job not found'}), 404
            job = analysis_jobs[job_id]
        
        # Create JSON file
        json_str = json.dumps(job['results'], indent=2)
        json_io = io.BytesIO(json_str.encode())
        
        return send_file(
            json_io,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'fire_alarm_analysis_{job_id}.json'
        )


def _run_local_detection_analysis(analyzer, pdf_path, skip_blank, skip_edges,
                                  use_parallel, use_cache, confidence, selected_pages=None):
    """Run local model analysis on PDF"""
    if not analyzer.local_detector:
        return {'success': False, 'error': 'Local detector not initialized'}
    
    try:
        # Convert PDF to images
        images = analyzer.pdf_processor.pdf_to_images(pdf_path, selected_pages)
        if not images:
            return {'success': False, 'error': 'Failed to convert PDF'}
        
        logger.info(f"Converted {len(images)} pages")
        
        # Analyze each page
        page_analyses = []
        total_devices = []
        
        # Use the correct page numbers if a selection was made
        page_numbers_to_process = selected_pages if selected_pages else range(1, len(images) + 1)

        for i, image in enumerate(images):
            page_num = page_numbers_to_process[i] # Get the original page number
            logger.info(f"Processing page {page_num} ({i+1}/{len(images)} selected)")
            
            # Create tiles
            tiles, tile_stats = analyzer.pdf_processor.create_tiles(
                image,
                tile_size=config.TILE_SIZE,
                overlap=config.OVERLAP_PERCENT,
                skip_blank=skip_blank,
                skip_edges=skip_edges,
                prioritize_complex=True
            )
            
            logger.info(f"Page {page_num} - Created {tile_stats['kept']} tiles")
            
            if not tiles:
                page_analyses.append(PageAnalysis(
                    page_number=page_num,
                    is_fire_alarm_page=False,
                    page_type='other',
                    devices=[],
                    keyed_notes=[],
                    specifications=[]
                ).to_dict())
                continue
            
            # Run detection
            if use_parallel:
                detections, proc_stats = analyzer.local_detector.process_all_tiles_parallel(
                    tiles, confidence, config.MAX_WORKERS, use_cache
                )
            else:
                detections, proc_stats = analyzer.local_detector.process_all_tiles_sequential(
                    tiles, confidence, use_cache
                )
            
            logger.info(f"Page {page_num} - Found {len(detections)} raw detections")
            
            # Remove overlaps
            filtered_detections = analyzer.visualizer.remove_overlapping_detections(detections)
            
            logger.info(f"Page {page_num} - {len(filtered_detections)} unique detections after NMS")
            
            # Convert to FireAlarmDevice objects
            devices = []
            for det in filtered_detections:
                device = FireAlarmDevice(
                    device_type=det['class'],
                    location=f"Page {page_num}",
                    page_number=page_num,
                    confidence=det['confidence'],
                    x=int(det['x']),
                    y=int(det['y']),
                    width=int(det['width']),
                    height=int(det['height'])
                )
                devices.append(device)
                total_devices.append(device)
            
            # Create page analysis
            page_analysis = PageAnalysis(
                page_number=page_num,
                is_fire_alarm_page=len(devices) > 0,
                page_type=_classify_page_type(page_num, devices),
                devices=devices,
                keyed_notes=[],
                specifications=[]
            )
            
            page_analyses.append(page_analysis.to_dict())
        
        # Compile results
        results = {
            'success': True,
            'pdf_path': pdf_path,
            'total_pages_scanned': len(images),
            'pages_with_devices': sum(1 for p in page_analyses if p['devices']),
            'total_devices': len(total_devices),
            'device_summary': _summarize_devices(total_devices),
            'page_analyses': page_analyses,
            'processing_stats': {
                'cache_stats': analyzer.local_detector.cache.get_stats(),
                'optimizations_used': {
                    'skip_blank_tiles': skip_blank,
                    'skip_edge_tiles': skip_edges,
                    'parallel_processing': use_parallel,
                    'caching': use_cache
                }
            }
        }
        
        return results
        
    except Exception as e:
        logger.error(f"Error in local model analysis: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}


def _classify_page_type(page_num, devices):
    """Classify page type based on devices"""
    if not devices:
        return "other"
    
    device_types = [d.device_type.lower() for d in devices]
    
    if any('mechanical' in dt or 'duct' in dt or 'damper' in dt for dt in device_types):
        return "mechanical"
    elif len(devices) > 5:
        return "special_systems"
    else:
        return "power_plan"


def _summarize_devices(devices):
    """Create summary count of device types"""
    device_types = [d.device_type for d in devices]
    return dict(Counter(device_types))
