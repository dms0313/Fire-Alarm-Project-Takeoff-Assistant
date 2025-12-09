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


DEVICE_NAME_MAP = {
    "cm": "Control Module",
    "co": "CO Detector",
    "dd": "Duct Detector",
    "dh": "Door Holder",
    "ecap": "Emergency Communications Access Panel",
    "ecps": "Emergency Communications Power Supply",
    "ecs": "Emergency Communication Station",
    "faap": "Remote Annunciator",
    "facp": "Fire Alarm Control Panel",
    "fsd": "Fire/Smoke Damper",
    "h_w": "Horn, Wall Mounted",
    "heat": "Heat Detector",
    "hs_c": "Horn/Strobe, Ceiling Mounted",
    "hs_w": "Horn/Strobe, Wall Mounted",
    "hs_w_wp": "Horn/Strobe, Wall Mounted, Weatherproof",
    "loc": "Local Operating Console",
    "mm": "Monitor Module",
    "nac": "NAC Panel",
    "pull": "Pull Station",
    "relay": "Relay Module",
    "rts": "Remote Test Switch",
    "s_w": "Strobe, Wall Mounted",
    "s_w_wp": "Strobe, Wall Mounted, Weatherproof",
    "sc": "Strobe, Ceiling Mounted",
    "smoke": "Smoke Detector",
    "smoke-co": "Smoke/CO Combo",
    "smoke-sb": "Smoke w/ Sounder Base",
    "sp_c": "Speaker, Ceiling Mounted",
    "ss_c": "Speaker/Strobe, Ceiling Mounted",
    "ss_w": "Speaker/Strobe, Wall Mounted",
    "ts": "Tamper Switch",
    "wf": "Waterflow Switch",
}


def get_device_display_name(device_code: str) -> str:
    """Return the human-readable device name for a symbol code."""
    if not device_code:
        return "Unknown Device"
    return DEVICE_NAME_MAP.get(device_code.lower(), device_code)

COLOR_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
    "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#fb8072", "#80b1d3",
    "#fdb462", "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd", "#ccebc5",
    "#ffed6f", "#a6cee3", "#1b9e77", "#d95f02", "#7570b3", "#e7298a",
    "#66a61e", "#e6ab02", "#a6761d", "#666666", "#8dd3c7", "#bebada",
    "#ffffb3",
]


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

                # Generate a higher resolution preview for hover/zoom
                mat = fitz.Matrix(220 / 72, 220 / 72)
                pix = page.get_pixmap(matrix=mat, alpha=False)

                base_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                thumbnail_image = base_image.copy()
                thumbnail_image.thumbnail((320, 320))

                preview_image = base_image.copy()
                preview_image.thumbnail((900, 900))

                thumb_buffer = io.BytesIO()
                thumbnail_image.save(thumb_buffer, format="JPEG", quality=88)
                thumbnail_b64 = base64.b64encode(thumb_buffer.getvalue()).decode()

                preview_buffer = io.BytesIO()
                preview_image.save(preview_buffer, format="JPEG", quality=92)
                preview_b64 = base64.b64encode(preview_buffer.getvalue()).decode()

                pages.append({
                    'thumbnail': f'data:image/jpeg;base64,{thumbnail_b64}',
                    'preview': f'data:image/jpeg;base64,{preview_b64}',
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
            #
            # NOTE: We intentionally render at a lower DPI than the model's
            # training resolution to keep the exported PDFs lightweight. The
            # output is meant for reference, not pixel-perfect CAD fidelity.
            # -----------------------------------------------------------------
            render_dpi = 140
            training_dpi = 350

            page = doc[page_num - 1]
            mat = fitz.Matrix(render_dpi / 72, render_dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
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
            annotated_image = annotated_image.convert("RGB")
            draw = ImageDraw.Draw(annotated_image)
            legend_scale = 3
            font_size = 12 * legend_scale
            font = None
            for font_path in ("arial.ttf", "DejaVuSans.ttf"):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except IOError:
                    continue

            if font is None:
                font = ImageFont.load_default()

            # This is the scale factor for render DPI vs training DPI
            # Calculate a single scaling factor between the model’s DPI (350) and the
            # rendered preview DPI (140).  See conversion notes here:contentReference[oaicite:0]{index=0}.
            render_scale = render_dpi / training_dpi  # e.g. 140 / 350

            class_colors = {}
            color_idx = 0

            device_counts = {}

            for device in devices:
                # Class/type and confidence
                d_type_raw = device.get('device_type') or device.get('class', 'unknown')
                d_type = str(d_type_raw).lower()

                # Track counts per device type
                device_counts[d_type] = device_counts.get(d_type, 0) + 1

                # Assign color for this device type
                if d_type not in class_colors:
                    class_colors[d_type] = COLOR_PALETTE[color_idx % len(COLOR_PALETTE)]
                    color_idx += 1
                color = class_colors[d_type]

                # Detector outputs are in pixels at training DPI (350)
                x_center_350 = float(device.get('x', 0))
                y_center_350 = float(device.get('y', 0))
                w_350 = float(device.get('width', 0))
                h_350 = float(device.get('height', 0))

                # Scale everything to the rendered DPI
                x_center_render = x_center_350 * render_scale
                y_center_render = y_center_350 * render_scale
                w_render = w_350 * render_scale
                h_render = h_350 * render_scale

                # Skip tiny boxes
                if w_render < 5 or h_render < 5:
                    continue

                # Convert centre to corner coordinates
                x1 = x_center_render - (w_render / 2)
                y1 = y_center_render - (h_render / 2)
                x2 = x_center_render + (w_render / 2)
                y2 = y_center_render + (h_render / 2)

                draw.rectangle([x1, y1, x2, y2], outline=color, width=4)

            # Build legend with full device names
            legend_entries = []
            for dtype, color in class_colors.items():
                full_name = get_device_display_name(dtype)
                count = device_counts.get(dtype, 0)
                label = f"{full_name}: {count}"
                legend_entries.append((color, label))

            if legend_entries:
                swatch_size = 16 * legend_scale
                text_spacing = 8 * legend_scale
                row_spacing = 6 * legend_scale
                padding = 10 * legend_scale
                margin = 20

                legend_width = 0
                legend_height = 0
                text_sizes = {}

                for color, name in legend_entries:
                    bbox = draw.textbbox((0, 0), name, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    text_sizes[name] = (text_width, text_height)
                    entry_width = swatch_size + text_spacing + text_width
                    entry_height = max(swatch_size, text_height)
                    legend_width = max(legend_width, entry_width)
                    legend_height += entry_height + row_spacing

                legend_height = legend_height - row_spacing if legend_entries else 0

                legend_x = margin + padding
                legend_y = annotated_image.height - legend_height - (padding * 2) - margin

                bg_x1 = legend_x - padding
                bg_y1 = legend_y - padding
                bg_x2 = legend_x + legend_width + padding
                bg_y2 = legend_y + legend_height + padding
                draw.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill="#FFFFFF", outline="#CCCCCC")

                current_y = legend_y
                for color, name in sorted(legend_entries, key=lambda item: item[1]):
                    text_width, text_height = text_sizes[name]
                    entry_height = max(swatch_size, text_height)

                    draw.rectangle(
                        [legend_x, current_y, legend_x + swatch_size, current_y + swatch_size],
                        fill=color,
                        outline=color,
                    )

                    text_y = current_y + (entry_height - text_height) / 2
                    draw.text(
                        (legend_x + swatch_size + text_spacing, text_y),
                        name,
                        fill="black",
                        font=font,
                    )

                    current_y += entry_height + row_spacing

            # -----------------------------------------------------------------
            # Convert annotated image → single-page PDF
            # -----------------------------------------------------------------
            img_buffer = io.BytesIO()
            annotated_image.save(
                img_buffer,
                format="JPEG",
                quality=70,
                optimize=True,
                subsampling="4:2:0",
            )
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
