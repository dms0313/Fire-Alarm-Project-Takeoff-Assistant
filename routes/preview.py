"""
Preview Routes - PDF page preview and download endpoints
"""
import os
import io
import base64
import tempfile
import logging

import fitz
from PIL import Image
from flask import request, jsonify, send_file

logger = logging.getLogger(__name__)


def register_preview_routes(app, analyzer):
    """Register preview-related routes"""

    # ---------------------------------------------------------------------
    # PREVIEW PAGES
    # ---------------------------------------------------------------------
    @app.route("/api/preview_pages", methods=["POST"])
    def preview_pages():
        """Generate low-res thumbnails for PDF pages"""
        if 'pdf' not in request.files:
            return jsonify({'success': False, 'error': 'No PDF file provided'}), 400

        pdf_file = request.files['pdf']
        if pdf_file.filename == '':
            return jsonify({'success': False, 'error': 'Empty filename'}), 400

        try:
            logger.info(f"Processing PDF preview request for: {pdf_file.filename}")

            temp_dir = tempfile.mkdtemp()
            pdf_path = os.path.join(temp_dir, 'upload.pdf')
            pdf_file.save(pdf_path)

            doc = fitz.open(pdf_path)
            pages = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                mat = fitz.Matrix(150 / 72, 150 / 72)
                pix = page.get_pixmap(matrix=mat)

                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.thumbnail((300, 300))

                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=85)
                img_str = base64.b64encode(buffered.getvalue()).decode()

                pages.append({
                    'thumbnail': f'data:image/jpeg;base64,{img_str}',
                    'page_number': page_num + 1
                })

            doc.close()
            os.remove(pdf_path)
            os.rmdir(temp_dir)

            return jsonify({'success': True, 'pages': pages, 'total_pages': len(pages)})

        except Exception as e:
            logger.error(f"Error generating previews: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    # ---------------------------------------------------------------------
    # DOWNLOAD ANNOTATED PAGE AS PDF
    # ---------------------------------------------------------------------
    @app.route("/api/download_annotated_pdf/<job_id>/<int:page_num>", methods=["GET"])
    def download_annotated_pdf(job_id, page_num):
        """Download annotated page as PDF"""
        from routes.analysis import analysis_jobs, analysis_lock

        with analysis_lock:
            if job_id not in analysis_jobs:
                return jsonify({'success': False, 'error': 'Job not found'}), 404

            job = analysis_jobs[job_id]
            results = job.get('results', {})
            if not results or 'page_analyses' not in results:
                return jsonify({'success': False, 'error': 'No analysis results'}), 404

        try:
            logger.info(f"Requested annotated download for job {job_id}, page {page_num}")

            # Open source PDF
            doc = fitz.open(job['pdf_path'])
            if page_num > len(doc):
                doc.close()
                return jsonify({'success': False, 'error': 'Invalid page number'}), 404

            # Locate analysis for this page
            page_analysis = next(
                (p for p in results['page_analyses'] if int(p['page_number']) == int(page_num)),
                None
            )
            if not page_analysis:
                doc.close()
                return jsonify({'success': False, 'error': f'No analysis for page {page_num}'}), 404

            devices = page_analysis.get('devices', [])
            logger.info(f"Found analysis with {len(devices)} devices")

            # -----------------------------------------------------------------
            # Render PDF page and compute proper DPI scaling
            # -----------------------------------------------------------------
            render_dpi = 180
            training_dpi = 350

            page = doc[page_num - 1]
            mat = fitz.Matrix(render_dpi / 72, render_dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Compute page size in inches (PDF units are 1/72 inch)
            page_rect = page.rect
            pdf_width_inch = page_rect.width / 72.0
            pdf_height_inch = page_rect.height / 72.0

            # Determine scale factors between training and render DPI
            training_width_px = pdf_width_inch * training_dpi
            training_height_px = pdf_height_inch * training_dpi
            scale_x = (pdf_width_inch * render_dpi) / training_width_px
            scale_y = (pdf_height_inch * render_dpi) / training_height_px

            # -----------------------------------------------------------------
            # Draw annotations (YOLO/Roboflow center-based boxes)
            # -----------------------------------------------------------------
            from PIL import ImageDraw, ImageFont
            annotated_image = image.copy()
            draw = ImageDraw.Draw(annotated_image)
            try:
                # Try to load a slightly larger font if possible
                font = ImageFont.truetype("arial.ttf", 12)
            except IOError:
                font = ImageFont.load_default()

            render_dpi = 180
            training_dpi = 350
            
            # This is the scale factor for render DPI vs training DPI
            # Calculate a single scaling factor between the model’s DPI (350) and the
            # rendered preview DPI (180).  See conversion notes here:contentReference[oaicite:0]{index=0}.
            render_scale = render_dpi / training_dpi  # e.g. 180 / 350

            for device in devices:
                # Class/type and confidence
                d_type = device.get('device_type') or device.get('class', 'unknown')
                conf = float(device.get('confidence', 0))

                # Detector outputs are in pixels at training DPI (350)
                x_center_350 = float(device.get('x', 0))
                y_center_350 = float(device.get('y', 0))
                w_350 = float(device.get('width', 0))
                h_350 = float(device.get('height', 0))

                # Scale everything to 180 DPI
                x_center_180 = x_center_350 * render_scale
                y_center_180 = y_center_350 * render_scale
                w_180 = w_350 * render_scale
                h_180 = h_350 * render_scale

                # Skip tiny boxes
                if w_180 < 5 or h_180 < 5:
                    continue

                # Convert centre to corner coordinates
                x1 = x_center_180 - (w_180 / 2)
                y1 = y_center_180 - (h_180 / 2)
                x2 = x_center_180 + (w_180 / 2)
                y2 = y_center_180 + (h_180 / 2)

                draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
                label = f"{d_type} ({conf*100:.1f}%)"
                draw.text((x1, y1 - 10), label, fill="red", font=font)

            # -----------------------------------------------------------------
            # Convert annotated image → single-page PDF
            # -----------------------------------------------------------------
            img_buffer = io.BytesIO()
            annotated_image.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            pdf_output = fitz.open()
            rect = fitz.Rect(0, 0, annotated_image.width, annotated_image.height)
            pdf_page = pdf_output.new_page(width=rect.width, height=rect.height)
            pdf_page.insert_image(rect, stream=img_buffer.getvalue())

            pdf_bytes = pdf_output.tobytes()
            pdf_output.close()
            doc.close()

            # -----------------------------------------------------------------
            # Send file to client
            # -----------------------------------------------------------------
            pdf_io = io.BytesIO(pdf_bytes)
            pdf_io.seek(0)
            return send_file(
                pdf_io,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'annotated_page_{page_num}.pdf'
            )
            if devices:
                sample = devices[0]
                logger.debug(f"Sample device: {sample}")
            else:
                logger.debug("No devices detected on this page")

        except Exception as e:
            logger.error(f"Error creating annotated PDF: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
