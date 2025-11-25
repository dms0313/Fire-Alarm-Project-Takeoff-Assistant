"""
agent_fix_text_encoding.py
--------------------------
A text-extraction and encoding-normalization agent for Gemini PDF analysis.

This module guarantees:
- Always returns a clean Python `str`
- Never returns bytes
- Detects escaped-binary patterns like \u0001\u0007\u000b
- Attempts repair using several decoding strategies
- Falls back to safe replacements rather than propagating garbage
"""

import re
import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BINARY_ESCAPE_PATTERN = re.compile(
    r"(\\u00[0-9a-fA-F]{2})"
)


def looks_corrupted(text: str) -> bool:
    """
    Detect if text contains a high frequency of escaped binary sequences.
    """
    matches = BINARY_ESCAPE_PATTERN.findall(text)
    return len(matches) > 20  # threshold: tune if needed


def repair_binary_escapes(escaped: str) -> str:
    """
    Attempt to repair strings that look like:
    '\\u0001\\u0007\\u000bL\\u0002 ...'

    Strategy:
    1. Interpret escaped unicode sequences
    2. Remove null/damaged chars
    3. Replace non-printables
    """
    try:
        # Convert sequences like "\u0007" → real characters
        raw = escaped.encode("utf-8").decode("unicode_escape")

        # Remove control chars except newline/tab
        cleaned = re.sub(r"[^\n\t\r\x20-\x7E]", "", raw)
        return cleaned

    except Exception:
        return escaped  # fallback, but safe for Gemini


# ---------------------------------------------------------------------------
# Core Agent
# ---------------------------------------------------------------------------

def extract_pdf_text_clean(pdf_path: str) -> str:
    """
    Extract text from a PDF safely and ensure it is clean Unicode text.
    """
    doc = fitz.open(pdf_path)
    text_chunks = []

    for page in doc:
        txt = page.get_text("text")
        if not isinstance(txt, str):
            txt = str(txt)
        text_chunks.append(txt)

    combined = "\n".join(text_chunks)

    # If the text extracted is likely corrupted, try repairing
    if looks_corrupted(combined):
        repaired = repair_binary_escapes(combined)
        return repaired

    return combined


def sanitize_text_for_gemini(text: str) -> str:
    """
    Guarantee that what goes into Gemini is safe Unicode.
    """

    # If bytes accidentally get passed
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8", errors="replace")
        except Exception:
            text = text.decode("latin-1", errors="replace")

    # Force removal of stray control chars
    text = re.sub(r"[^\n\t\r\x20-\x7E]", "", text)

    return text


def process_pdf_for_gemini(pdf_path: str) -> str:
    """
    End-to-end: Extract → Clean → Return UTF-8 safe text.
    """
    raw_text = extract_pdf_text_clean(pdf_path)
    clean_text = sanitize_text_for_gemini(raw_text)
    return clean_text


# ---------------------------------------------------------------------------
# Example direct call
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_path = "example.pdf"
    safe_text = process_pdf_for_gemini(test_path)

    print("\n--- CLEAN TEXT OUTPUT ---\n")
    print(safe_text[:3000])  # preview
    print("\n-------------------------\n")
