
"""
Unified Gemini Analyzer for Fire Alarm Analyzer v6
--------------------------------------------------
• Uses PDFProcessor for text extraction
• Uses Gemini 2.0 Flash Experimental for text analysis
• Integrates legacy FA-specific methods (page identification, mechanical extraction, cover analysis)
• Maintains improved JSON parsing and error handling
"""

import os
import json
import re
import logging
from typing import List, Dict, Any

import google.generativeai as genai
from modules.pdf_processor import PDFProcessor
from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)


class GeminiAnalyzer:
    """Unified Gemini Analyzer combining old and new features"""

    def __init__(self):
        self.model = None
        if GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                self.model = genai.GenerativeModel(GEMINI_MODEL)
                logger.info(f"✅ Gemini Analyzer initialized with model: {GEMINI_MODEL}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
        else:
            logger.warning("⚠️ GEMINI_API_KEY not set; Gemini analysis disabled.")

        self.pdf_processor = PDFProcessor()

    # -------------------------------------------------------------------------
    # Utility: Robust JSON parser
    # -------------------------------------------------------------------------
    @staticmethod
    def _parse_json(raw_text: str, default: Any) -> Any:
        """Safely parse JSON from Gemini responses"""
        if not raw_text:
            return default
        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        match = re.search(r"\{.*\}|\[.*\]", cleaned, flags=re.DOTALL)
        json_str = match.group(0) if match else cleaned
        try:
            return json.loads(json_str)
        except Exception as exc:
            logger.error(f"Failed to parse JSON: {exc}")
            return default

    # -------------------------------------------------------------------------
    # Text extraction pipeline
    # -------------------------------------------------------------------------
    def extract_pdf_text(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Extracts text content from PDF pages"""
        try:
            return self.pdf_processor.extract_text_from_pdf(pdf_path)
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return []

    # -------------------------------------------------------------------------
    # Fire Alarm Page Identification
    # -------------------------------------------------------------------------
    def _identify_fire_alarm_pages(self, pages: List[Dict[str, Any]]) -> List[int]:
        """Identify fire alarm-related pages based on keywords"""
        fa_keywords = [
            "fire alarm", "special systems", "power plan", "smoke detector",
            "heat detector", "pull station", "notification", "speaker strobe",
            "horn strobe", "facp", "annunciator", "relay", "duct detector",
            "module", "smoke control", "mechanical"
        ]
        fa_pages = []
        for p in pages:
            txt = p.get("text", "").lower()
            if any(k in txt for k in fa_keywords):
                fa_pages.append(p.get("page_number"))
        return fa_pages

    # -------------------------------------------------------------------------
    # Gemini Analysis Orchestration
    # -------------------------------------------------------------------------
    def analyze_pdf_text(self, pdf_path: str) -> Dict[str, Any]:
        """Main orchestrator combining extraction + Gemini AI analysis"""
        if not self.model:
            return {"success": False, "error": "Gemini model not configured"}

        pages = self.extract_pdf_text(pdf_path)
        if not pages:
            return {"success": False, "error": "No text extracted"}

        try:
            fa_pages = self._identify_fire_alarm_pages(pages)
            cover_data = self._analyze_cover_pages(pages[:3])
            fa_notes = self._extract_fa_notes(pages, fa_pages)
            mechanical = self._extract_mechanical_devices(pages)

            return {
                "success": True,
                "project_info": cover_data,
                "fire_alarm_pages": fa_pages,
                "fire_alarm_notes": fa_notes,
                "mechanical_devices": mechanical
            }
        except Exception as e:
            logger.error(f"Error in Gemini analysis: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------------------
    # Cover Page Extraction
    # -------------------------------------------------------------------------
    def _analyze_cover_pages(self, pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract high-level project info from cover pages"""
        text = "\n".join([p.get("text", "") for p in pages])[:15000]
        prompt = f"""
You are analyzing the cover pages of a construction PDF.
Extract the following details and return JSON only:
{{
  "project_name": string,
  "project_location": string,
  "project_type": string,
  "owner": string,
  "engineer": string,
  "architect": string,
  "scope_summary": string
}}

COVER PAGE TEXT:
{text}
"""
        try:
            response = self.model.generate_content(prompt)
            return self._parse_json(getattr(response, "text", ""), {})
        except Exception as e:
            logger.error(f"Error extracting project info: {e}")
            return {}

    # -------------------------------------------------------------------------
    # FA Notes Extraction
    # -------------------------------------------------------------------------
    def _extract_fa_notes(self, pages: List[Dict[str, Any]], fa_pages: List[int]) -> List[str]:
        """Extract relevant FA notes from identified pages"""
        joined = "\n".join(
            [pages[i - 1]["text"] for i in fa_pages if i - 1 < len(pages)]
        )[:30000]
        prompt = f"""
Extract concise bullet points summarizing all fire alarm related notes.
Return JSON array of strings only.
TEXT:
{joined}
"""
        try:
            response = self.model.generate_content(prompt)
            return self._parse_json(getattr(response, "text", ""), [])
        except Exception as e:
            logger.error(f"Error extracting FA notes: {e}")
            return []

    # -------------------------------------------------------------------------
    # Mechanical / FA Device Extraction
    # -------------------------------------------------------------------------
    def _extract_mechanical_devices(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract mechanical system references related to FA integration"""
        mech_text = "\n".join([p["text"] for p in pages if "mech" in p.get("text", "").lower()])
        prompt = f"""
Identify any mechanical or HVAC devices that interface with the fire alarm system.
Return a JSON array of objects each like:
[
  {{"device": "smoke damper", "location": "RTU-3", "action": "supervised"}}
]

TEXT:
{mech_text}
"""
        try:
            response = self.model.generate_content(prompt)
            return self._parse_json(getattr(response, "text", ""), [])
        except Exception as e:
            logger.error(f"Error extracting mechanical devices: {e}")
            return []

