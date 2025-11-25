# agents.py
import fitz
import base64

def pdf_to_page_images(pdf_path):
    """Convert every page of a PDF into a PNG image in base64 format."""
    doc = fitz.open(pdf_path)
    images = []

    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode("utf-8")

        images.append({
            "mime_type": "image/png",
            "data": b64
        })

    return images


def build_gemini_payload(pdf_path, user_prompt):
    """
    Build a clean, safe multimodal prompt for Gemini.
    Sends page images instead of corrupt PDF text.
    """
    pages = pdf_to_page_images(pdf_path)

    return {
        "model": "models/gemini-3-pro-preview",
        "contents": [
            {
                "parts": (
                    [{"text": user_prompt}] +
                    [{"inline_data": p} for p in pages]
                )
            }
        ]
    }

