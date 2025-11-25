
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
from datetime import datetime
from typing import List, Dict, Any

import google.generativeai as genai
from modules.pdf_processor import PDFProcessor
from config import GEMINI_API_KEY, GEMINI_MODEL
from .gemini_analyzer import SYSTEM_INSTRUCTIONS

logger = logging.getLogger(__name__)


class GeminiAnalyzer:
    """Unified Gemini Analyzer combining old and new features"""

    def __init__(self):
        self.model = None
        if GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                # SDK version pinned in requirements lacks system_instruction support,
                # so prepend instructions manually to prompts.
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

    @staticmethod
    def _add_system_instruction(prompt: str) -> str:
        """Prefix prompts with the system instruction for SDKs without native support."""
        return f"{SYSTEM_INSTRUCTIONS}\n\n{prompt}"

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
            structured_sections = self._analyze_report_sections(pages, fa_pages)
            report = self._build_report_object(
                cover_data=cover_data,
                fa_pages=fa_pages,
                ai_sections=structured_sections,
                pages=pages,
            )

            return {
                "success": True,
                "project_info": cover_data,
                "fire_alarm_pages": fa_pages,
                "fire_alarm_notes": fa_notes,
                "mechanical_devices": mechanical,
                "report": report,
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
            response = self.model.generate_content(self._add_system_instruction(prompt))
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
            response = self.model.generate_content(self._add_system_instruction(prompt))
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
            response = self.model.generate_content(self._add_system_instruction(prompt))
            return self._parse_json(getattr(response, "text", ""), [])
        except Exception as e:
            logger.error(f"Error extracting mechanical devices: {e}")
            return []

    # -------------------------------------------------------------------------
    # Comprehensive Report Extraction
    # -------------------------------------------------------------------------
    def _analyze_report_sections(
        self, pages: List[Dict[str, Any]], fa_pages: List[int]
    ) -> Dict[str, Any]:
        """Gather all report sections with a single, structured Gemini prompt."""

        # Prioritize identified FA pages and always include general notes for context
        relevant_pages = [
            p for p in pages if not fa_pages or p.get("page_number") in fa_pages
        ] or pages

        general_note_pages = [
            p for p in pages if "general note" in p.get("text", "").lower()
        ]

        for p in general_note_pages:
            if p not in relevant_pages:
                relevant_pages.append(p)

        joined = "\n\n".join(
            f"Page {p.get('page_number')}:\n{p.get('text', '')}" for p in relevant_pages
        )
        trimmed_text = joined[:60000]  # Protect against overly long prompts

        prompt = f"""
Review the following construction drawing text and extract structured fire alarm details.
Return JSON ONLY with the exact schema below. Use concise evidence snippets or direct quotes
from the plans for every bullet-level item. Always review fire alarm related notes and any
general notes to confirm whether the plans list the manufacturer/model of any existing
fire alarm control panel; capture that in the panels array with clear notes and evidence.

Expected JSON shape:
{{
  "system_architecture": {{
    "system_type": string,
    "panels": [{{"name": string, "location": string, "page": int|null, "notes": string, "evidence": string}}],
    "network_topology": string,
    "power_requirements": string,
    "evidence": [string]
  }},
  "unique_area_notes": [
    {{"area": string, "note": string, "page": int|null, "priority": string, "evidence": string}}
  ],
  "initiation_devices": {{
    "devices": [
      {{"device_type": string, "location": string, "quantity": int, "page": int|null, "notes": string, "evidence": string}}
    ],
    "totals": {{"<device_type>": int}}
  }},
  "notification_appliances": {{
    "appliances": [
      {{"type": string, "location": string, "quantity": int, "page": int|null, "output": string, "evidence": string}}
    ],
    "totals": {{"<type>": int}}
  }},
  "interfaces_modules": {{
    "items": [
      {{"type": string, "location": string, "quantity": int, "page": int|null, "purpose": string, "evidence": string}}
    ],
    "totals": {{"<type>": int}}
  }},
  "rfis": [
    {{"question": string, "reason": string, "page": int|null, "evidence": string}}
  ],
  "takeoff_counts": {{
    "overall_totals": {{
      "initiation": {{"<device_type>": int}},
      "notification": {{"<type>": int}},
      "interfaces": {{"<type>": int}}
    }},
    "per_page": [
      {{"page": int, "initiation": {{"<device_type>": int}}, "notification": {{"<type>": int}}, "interfaces": {{"<type>": int}}, "notes": string}}
    ]
  }}
}}

Rules:
- Return valid JSON only (no markdown or commentary).
- Use integers for quantities; default to 1 when not stated.
- Prefer pages identified as fire alarm/special systems; include page numbers when known.
- Evidence snippets should be short quotes that support the extracted data.

SOURCE TEXT (trimmed):
{trimmed_text}
"""

        try:
            response = self.model.generate_content(self._add_system_instruction(prompt))
            response_text = getattr(response, "text", "")
            if not isinstance(response_text, str) or not response_text.strip():
                logger.error("Model response is empty or not a valid string.")
                return {}

            return self._parse_json(response_text, {})
        except Exception as e:
            logger.error(f"Error extracting structured report sections: {e}")
            return {}

    def _aggregate_totals(self, items: List[Dict[str, Any]], existing: Dict[str, int] | None) -> Dict[str, int]:
        """Roll up quantity totals by device type, preserving any AI-provided totals."""

        totals: Dict[str, int] = (existing or {}).copy()
        for item in items or []:
            device_type = next(
                (str(item.get(key)).strip() for key in ("device_type", "type", "name", "category") if item.get(key)),
                "unspecified",
            )
            raw_qty = item.get("quantity") or item.get("qty") or 1
            try:
                quantity = int(raw_qty)
            except (TypeError, ValueError):
                quantity = 1
            totals[device_type] = totals.get(device_type, 0) + quantity
        return totals

    def _build_takeoff_counts(
        self,
        initiation_devices: List[Dict[str, Any]],
        initiation_totals: Dict[str, int],
        notification_appliances: List[Dict[str, Any]],
        notification_totals: Dict[str, int],
        interfaces: List[Dict[str, Any]],
        interface_totals: Dict[str, int],
        ai_takeoff: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        """Combine AI-provided takeoff counts with deterministic rollups."""

        takeoff = (ai_takeoff or {}).copy()
        takeoff.setdefault(
            "overall_totals",
            {
                "initiation": initiation_totals,
                "notification": notification_totals,
                "interfaces": interface_totals,
            },
        )

        per_page_map: Dict[Any, Dict[str, Any]] = {}

        def _rollup(items: List[Dict[str, Any]], bucket: str) -> None:
            for item in items or []:
                page = item.get("page") or item.get("page_number")
                if page in (None, ""):
                    continue
                device_type = next(
                    (str(item.get(key)).strip() for key in ("device_type", "type", "name", "category") if item.get(key)),
                    "unspecified",
                )
                raw_qty = item.get("quantity") or item.get("qty") or 1
                try:
                    quantity = int(raw_qty)
                except (TypeError, ValueError):
                    quantity = 1

                bucket_row = per_page_map.setdefault(
                    page, {"page": page, "initiation": {}, "notification": {}, "interfaces": {}}
                )
                bucket_totals = bucket_row[bucket]
                bucket_totals[device_type] = bucket_totals.get(device_type, 0) + quantity

        _rollup(initiation_devices, "initiation")
        _rollup(notification_appliances, "notification")
        _rollup(interfaces, "interfaces")

        if per_page_map and not takeoff.get("per_page"):
            takeoff["per_page"] = sorted(
                per_page_map.values(), key=lambda row: row.get("page") or 0
            )

        return takeoff

    def _build_report_object(
        self,
        cover_data: Dict[str, Any],
        fa_pages: List[int],
        ai_sections: Dict[str, Any],
        pages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Normalize AI sections into a comprehensive report object."""

        system_architecture = ai_sections.get("system_architecture") or {}
        unique_area_notes = ai_sections.get("unique_area_notes") or []

        initiation_section = ai_sections.get("initiation_devices") or {}
        initiation_devices = initiation_section.get("devices") or []
        initiation_totals = self._aggregate_totals(
            initiation_devices, initiation_section.get("totals")
        )

        notification_section = ai_sections.get("notification_appliances") or {}
        notification_appliances = notification_section.get("appliances") or []
        notification_totals = self._aggregate_totals(
            notification_appliances, notification_section.get("totals")
        )

        interfaces_section = ai_sections.get("interfaces_modules") or {}
        interface_items = interfaces_section.get("items") or []
        interface_totals = self._aggregate_totals(
            interface_items, interfaces_section.get("totals")
        )

        takeoff_counts = self._build_takeoff_counts(
            initiation_devices,
            initiation_totals,
            notification_appliances,
            notification_totals,
            interface_items,
            interface_totals,
            ai_sections.get("takeoff_counts"),
        )

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "total_pages": len(pages),
            "fire_alarm_pages": fa_pages,
            "project_info": cover_data,
            "system_architecture": system_architecture,
            "unique_area_notes": unique_area_notes,
            "initiation_devices": {
                "devices": initiation_devices,
                "totals": initiation_totals,
            },
            "notification_appliances": {
                "appliances": notification_appliances,
                "totals": notification_totals,
            },
            "interfaces_modules": {
                "items": interface_items,
                "totals": interface_totals,
            },
            "rfis": ai_sections.get("rfis") or [],
            "takeoff_counts": takeoff_counts,
        }

