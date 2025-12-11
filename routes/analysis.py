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
from modules.gemini_report_builder import build_gemini_report
from modules.history_store import HistoryStore
from modules.notion_client import NotionClient

logger = logging.getLogger(__name__)

# Storage for analysis jobs
analysis_jobs = {}
analysis_lock = threading.Lock()
history_store = HistoryStore()
notion_client = NotionClient(config.NOTION_API_TOKEN, config.NOTION_DATABASE_ID)


def register_analysis_routes(app, analyzer):
    """Register analysis-related routes"""
    
    @app.route("/")
    def index():
        """Serve the main HTML interface"""
        # Read HTML from template file
        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'index.html')
        with open(template_path, 'r', encoding='utf-8') as f:
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
            'gemini_error': getattr(analyzer.gemini_analyzer, 'initialization_error', None),
            'gemini_model': getattr(analyzer.gemini_analyzer, 'current_model', getattr(config, 'GEMINI_MODEL', None)),
            'available_gemini_models': getattr(config, 'GEMINI_MODEL_CHOICES', []),
            'notion_configured': notion_client.is_configured(),
        }

        if expose_model_path:
            response['local_model_path'] = local_model_path
            response['model_path'] = local_model_path  # legacy alias
        else:
            response['local_model_path'] = None
            response['model_path'] = None

        return jsonify(response)

    @app.route("/api/set_gemini_model", methods=["POST"])
    def set_gemini_model():
        """Switch the active Gemini text model at runtime."""

        payload = request.get_json(silent=True) or {}
        model = payload.get('model')

        if not model:
            return jsonify({'success': False, 'error': 'Model name is required'}), 400

        allowed_models = getattr(config, 'GEMINI_MODEL_CHOICES', [])
        if allowed_models and model not in allowed_models:
            return jsonify({'success': False, 'error': 'Model not in allowed list'}), 400

        if not analyzer.gemini_analyzer.update_model(model):
            error = getattr(analyzer.gemini_analyzer, 'initialization_error', 'Failed to initialize model')
            return jsonify({'success': False, 'error': error}), 500

        config.GEMINI_MODEL = model
        return jsonify({'success': True, 'gemini_model': model})

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

            if not results.get('success', False):
                error_message = results.get('error', 'Local detector failed to run')
                logger.error("Local analysis failed: %s", error_message)

                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)

                return jsonify({'success': False, 'error': error_message}), 400

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

            history_store.save_entry(
                job_id,
                analysis_type='local',
                original_filename=pdf_file.filename,
                results=response_data,
                pdf_path=pdf_path,
                project_name=None,
            )

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

        send_images = request.form.get('send_images', 'true').lower() == 'true'

        # Save uploaded file
        job_id = str(uuid.uuid4())
        temp_dir = tempfile.mkdtemp()
        pdf_path = os.path.join(temp_dir, 'upload.pdf')
        pdf_file.save(pdf_path)
        # Collect any additional attachments (e.g., datasheets/specs)
        additional_spec_paths = []
        additional_files = request.files.getlist('additional_files') if request.files else []
        for idx, attachment in enumerate(additional_files):
            if not attachment or not attachment.filename:
                continue

            safe_name = os.path.basename(attachment.filename)
            attachment_path = os.path.join(temp_dir, f'attachment_{idx}_{safe_name}')
            attachment.save(attachment_path)
            additional_spec_paths.append(attachment_path)
        spec_path = None
        spec_file = request.files.get('spec_pdf')
        if spec_file and spec_file.filename:
            spec_path = os.path.join(temp_dir, 'spec.pdf')
            spec_file.save(spec_path)

        try:
            logger.info(f"Starting Gemini analysis job {job_id}")

            # =================================================================
            # UPDATED CALL: Pass the pdf_path directly to the new analyzer
            # The new analyzer handles its own text extraction.
            results = analyzer.gemini_analyzer.analyze_pdf(
                pdf_path,
                include_images=send_images,
                spec_pdf_path=spec_path,
                additional_spec_paths=additional_spec_paths,
            )
            results['job_id'] = job_id
            # =================================================================

            project_name = _extract_project_name(results, pdf_file.filename)

            # Store results
            with analysis_lock:
                analysis_jobs[job_id] = {
                    'results': results,
                    'pdf_path': pdf_path,
                    'temp_dir': temp_dir,
                    'spec_pdf_path': spec_path,
                    'additional_spec_paths': additional_spec_paths,
                    'timestamp': datetime.now().isoformat(),
                    'analysis_type': 'gemini'
                }

            history_store.save_entry(
                job_id,
                analysis_type='gemini',
                original_filename=pdf_file.filename,
                results=results,
                pdf_path=pdf_path,
                project_name=project_name,
            )

            logger.info(f"Gemini analysis {job_id} completed")

            # The 'results' object from analyze_pdf already contains 'success'
            return jsonify(results)

        except Exception as e:
            logger.error(f"Error in Gemini analysis: {str(e)}", exc_info=True)
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            if spec_path and os.path.exists(spec_path):
                os.remove(spec_path)
            for path in additional_spec_paths:
                if os.path.exists(path):
                    os.remove(path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route("/api/gemini_follow_up", methods=["POST"])
    def gemini_follow_up():
        """Answer follow-up questions using prior Gemini context."""

        if not analyzer.gemini_analyzer.is_available():
            return jsonify({'success': False, 'error': 'Gemini AI not configured'}), 400

        payload = request.get_json(silent=True) or {}
        question = (payload.get('question') or '').strip()
        job_id = payload.get('job_id')

        if not question:
            return jsonify({'success': False, 'error': 'A follow-up question is required.'}), 400

        if not job_id:
            return jsonify({'success': False, 'error': 'Missing job_id for follow-up context.'}), 400

        with analysis_lock:
            job = analysis_jobs.get(job_id)

        if not job or job.get('analysis_type') != 'gemini':
            return jsonify({'success': False, 'error': 'Gemini analysis results not found for this job ID.'}), 404

        try:
            results = job.get('results') or {}
            pdf_path = job.get('pdf_path')
            spec_pdf_path = job.get('spec_pdf_path')
            additional_spec_paths = job.get('additional_spec_paths')

            follow_up = analyzer.gemini_analyzer.answer_follow_up_question(
                question,
                prior_results=results,
                pdf_path=pdf_path,
                spec_pdf_path=spec_pdf_path,
                additional_spec_paths=additional_spec_paths,
            )

            status_code = 200 if follow_up.get('success') else 400
            return jsonify(follow_up), status_code
        except Exception as exc:
            logger.error("Follow-up question failed: %s", exc, exc_info=True)
            return jsonify({'success': False, 'error': str(exc)}), 500

    @app.route("/api/notion/export", methods=["POST"])
    def export_to_notion():
        """Send the latest Gemini project snapshot to Notion."""

        if not notion_client.is_configured():
            return jsonify({'success': False, 'error': 'Notion is not configured.'}), 400

        payload = request.get_json(silent=True) or {}
        job_id = payload.get('job_id')

        if not job_id:
            return jsonify({'success': False, 'error': 'Missing job_id for Notion export.'}), 400

        with analysis_lock:
            job = analysis_jobs.get(job_id)

        if not job or job.get('analysis_type') != 'gemini':
            return jsonify({'success': False, 'error': 'Gemini results not found for this job ID.'}), 404

        results = job.get('results') or {}
        response = notion_client.create_project_page(results)
        status_code = 200 if response.get('success') else 500
        return jsonify(response), status_code
    
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

    @app.route("/api/gemini_report/<job_id>", methods=["GET"])
    def download_gemini_report(job_id):
        """Generate a DOCX report for Gemini analysis output."""
        with analysis_lock:
            job = analysis_jobs.get(job_id)

        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404

        if job.get('analysis_type') != 'gemini':
            return jsonify({'success': False, 'error': 'Gemini report unavailable for this job'}), 400

        results = job.get('results')
        if not results:
            return jsonify({'success': False, 'error': 'Analysis results missing'}), 404

        try:
            report_io = build_gemini_report(results)
        except Exception as exc:  # pragma: no cover - report generation is best-effort
            logger.error("Failed to build Gemini report: %s", exc, exc_info=True)
            return jsonify({'success': False, 'error': 'Failed to build Gemini report'}), 500

        filename = f'gemini_fire_alarm_report_{job_id}.docx'
        return send_file(
            report_io,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=filename
        )

    @app.route("/api/history", methods=["GET"])
    def list_history():
        """Return metadata for all stored analyses."""

        entries = history_store.list_entries()
        return jsonify({
            'success': True,
            'entries': entries
        })

    @app.route("/api/history/<job_id>", methods=["GET"])
    def load_history(job_id):
        """Load stored results for a previous analysis run."""

        entry = history_store.load_entry(job_id)
        if not entry:
            return jsonify({'success': False, 'error': 'History entry not found'}), 404

        # Rehydrate in-memory job cache so preview/export endpoints continue to work
        with analysis_lock:
            if job_id not in analysis_jobs:
                analysis_jobs[job_id] = {
                    'results': entry['results'],
                    'pdf_path': entry['pdf_path'],
                    'temp_dir': entry['storage_dir'],
                    'timestamp': entry.get('timestamp'),
                    'analysis_type': entry.get('analysis_type'),
                }

        payload = {**entry['results']}
        payload['job_id'] = job_id

        return jsonify({
            'success': True,
            'analysis_type': entry.get('analysis_type'),
            'project_name': entry.get('project_name'),
            'original_filename': entry.get('original_filename'),
            'timestamp': entry.get('timestamp'),
            'data': payload,
        })

    @app.route("/api/history/<job_id>/title", methods=["PATCH"])
    def update_history_title(job_id):
        """Update the saved project title for a history entry."""

        payload = request.get_json(silent=True) or {}
        project_name = (payload.get('project_name') or '').strip()

        if not project_name:
            return jsonify({'success': False, 'error': 'Project name is required'}), 400

        updated = history_store.update_project_name(job_id, project_name)
        if not updated:
            return jsonify({'success': False, 'error': 'History entry not found'}), 404

        return jsonify({'success': True, 'project_name': project_name})

    @app.route("/api/history/<job_id>", methods=["DELETE"])
    def delete_history_entry(job_id):
        """Remove a stored history entry and its assets."""

        try:
            removed = history_store.delete_entry(job_id)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to delete history entry %s: %s", job_id, exc, exc_info=True)
            return jsonify({'success': False, 'error': 'Failed to delete history entry'}), 500

        if not removed:
            return jsonify({'success': False, 'error': 'History entry not found'}), 404

        with analysis_lock:
            analysis_jobs.pop(job_id, None)

        return jsonify({'success': True})

    @app.route("/api/history/<job_id>/preview", methods=["GET"])
    def history_preview(job_id):
        """Return a PNG preview of the first page for a stored PDF."""

        entry = history_store.load_entry(job_id)
        if not entry or not entry.get('pdf_path'):
            return jsonify({'success': False, 'error': 'History entry not found'}), 404

        try:
            with fitz.open(entry['pdf_path']) as doc:
                if doc.page_count == 0:
                    raise ValueError('PDF has no pages')

                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                image_bytes = pix.tobytes("png")
        except Exception as exc:  # pragma: no cover - rendering best-effort
            logger.error("Failed to build history preview for %s: %s", job_id, exc, exc_info=True)
            return jsonify({'success': False, 'error': 'Unable to generate preview'}), 500

        return send_file(
            io.BytesIO(image_bytes),
            mimetype='image/png',
            as_attachment=False,
            download_name='preview.png'
        )


def _extract_project_name(results: dict, fallback_name: str | None = None) -> str | None:
    """Derive a project name using Gemini output, falling back to filename."""

    if not isinstance(results, dict):
        return fallback_name

    high_level = results.get('high_level_overview') or {}
    project_info = results.get('project_info') or {}

    for candidate in (
        high_level.get('project_name'),
        project_info.get('project_name'),
        project_info.get('name'),
    ):
        if candidate:
            return candidate

    return fallback_name


def _run_local_detection_analysis(analyzer, pdf_path, skip_blank, skip_edges,
                                  use_parallel, use_cache, confidence, selected_pages=None):
    """Run local model analysis on PDF"""
    if not analyzer.local_detector:
        return {'success': False, 'error': 'Local detector not initialized'}

    try:
        page_analyses = []
        total_devices = []
        pages_processed = 0

        for page_index, (page_num, image) in enumerate(
            analyzer.pdf_processor.iter_pdf_images(pdf_path, selected_pages), start=1
        ):
            pages_processed += 1
            logger.info(f"Processing page {page_num} ({page_index} processed)")

            tiles = []
            try:
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
            finally:
                # Release memory eagerly to avoid large page backlogs
                for tile in tiles:
                    tile_img = tile.get('image')
                    if hasattr(tile_img, 'close'):
                        try:
                            tile_img.close()
                        except Exception:
                            pass
                tiles.clear()

                if hasattr(image, 'close'):
                    try:
                        image.close()
                    except Exception:
                        pass

        if pages_processed == 0:
            logger.error("Failed to stream any pages from PDF: %s", pdf_path)
            return {'success': False, 'error': 'Failed to convert PDF'}

        if pages_processed == 0:
            logger.error("Failed to stream any pages from PDF: %s", pdf_path)
            return {'success': False, 'error': 'Failed to convert PDF'}

        # Compile results
        results = {
            'success': True,
            'pdf_path': pdf_path,
            'total_pages_scanned': pages_processed,
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
