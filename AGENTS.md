## Gemini helper utilities

```python
"""Utilities for building a clean multimodal Gemini payload."""

from __future__ import annotations

import base64
from typing import Dict, List

import fitz


def pdf_to_page_images(pdf_path: str, dpi: int = 200) -> List[Dict[str, str | int]]:
    """Convert each page of a PDF into a base64-encoded PNG image.

    The original version leaked the `fitz.Document` handle and did not annotate
    return values, which made debugging harder.  Using a context manager ensures
    the file handle is closed promptly and makes the function safer to reuse.
    """

    images: List[Dict[str, str | int]] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            images.append(
                {
                    "mime_type": "image/png",
                    "data": base64.b64encode(img_bytes).decode("utf-8"),
                    "page": index,
                }
            )

    return images


def build_gemini_payload(pdf_path: str, user_prompt: str, *, model: str = "models/gemini-3-pro-preview") -> Dict[str, object]:
    """Build a safe multimodal payload using page images instead of raw PDF text.

    Each page is provided as inline image data so Gemini receives clean, reliably
    decoded content regardless of the PDF's text encoding quirks.
    """

    pages = pdf_to_page_images(pdf_path)

    return {
        "model": model,
        "contents": [
            {
                "parts": [{"text": user_prompt}] + [{"inline_data": p} for p in pages],
            }
        ],
    }
```

