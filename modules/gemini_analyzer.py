"""
Gemini Analyzer Module
Handles AI-powered analysis of fire alarm specifications using Google's Gemini API
"""

import io
import logging
import os
import json
import re
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core import exceptions as core_exceptions
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Corrected relative import for your module structure
from .pdf_processor import PDFProcessor
from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_MODEL_CHOICES  # Assumes GEMINI_MODEL is in config


SYSTEM_INSTRUCTIONS = (
    "You are an expert Fire Alarm Sales Estimator and Code Consultant. Your goal is to review construction "
    "documents (blueprints and specifications) to extract a precise Bill of Materials (BOM) and scope of work "
    "for a commercial fire alarm system. You must filter out all non-relevant information (e.g., landscaping, "
    "civil, structural, plumbing) and focus strictly Fire Alarm requirements.\n\n"
    "You are deeply knowledgeable in:\n"
    "- NFPA 72 (National Fire Alarm and Signaling Code)\n"
    "- NFPA 101 (Life Safety Code)\n"
    "- IBC (International Building Code)\n\n"
    "When analyzing documents:\n"
    "1. Identify the applicable code versions (e.g., NFPA 72-2016, IBC 2018).\n"
    "2. Cross-check project requirements against these codes to identify potential errors or missing devices.\n"
    "3. Always check Mechanical/HVAC plans for Duct Detectors and Fire/Smoke Dampers that require FA monitoring.\n"
    "4. Look for 'Class A' vs 'Class B' wiring requirements.\n"
    "5. Verify if Voice Evacuation is required."
)

logger = logging.getLogger("fire-alarm-analyzer")


class GeminiPromptBlocked(RuntimeError):
    """Raised when Gemini blocks a prompt due to safety or policy filters."""

    def __init__(self, message: str, prompt_feedback: Any = None):
        super().__init__(message)
        self.prompt_feedback = prompt_feedback


class GeminiRequestFailed(RuntimeError):
    """Raised when Gemini consistently fails to generate a response."""

    def __init__(self, message: str, prompt_feedback: Any = None):
        super().__init__(message)
        self.prompt_feedback = prompt_feedback

class GeminiFireAlarmAnalyzer:
    """AI-powered fire alarm specification analyzer using Gemini"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini analyzer"""
        self.api_key = api_key or GEMINI_API_KEY
        self.model = None
        self.current_model = GEMINI_MODEL
        self.available_models = GEMINI_MODEL_CHOICES
        self.pdf_processor = PDFProcessor()
        self.initialization_error: Optional[str] = None
        self.last_prompt_feedback: Optional[Dict[str, Any]] = None
        self.max_retries = int(os.environ.get("GEMINI_MAX_RETRIES", "2"))
        self.request_timeout = int(os.environ.get("GEMINI_REQUEST_TIMEOUT_SECONDS", "240"))
        self.max_image_pages = int(os.environ.get("GEMINI_MAX_IMAGE_PAGES", "8"))
        self.tried_models: List[str] = []

        if self.api_key:
            self._initialize_model(self.current_model)
        else:
            self.initialization_error = "GEMINI_API_KEY not found. AI Analysis will be disabled."
            logger.warning(self.initialization_error)

    def _initialize_model(self, model_name: str) -> bool:
        """Configure the Gemini client with the requested model."""

        if not self.api_key:
            self.initialization_error = "GEMINI_API_KEY not found. AI Analysis will be disabled."
            logger.warning(self.initialization_error)
            return False

        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model_name)
            self.current_model = model_name
            self.initialization_error = None
            if model_name not in self.tried_models:
                self.tried_models.append(model_name)
            logger.info(f"✅ Gemini AI initialized successfully with {model_name}")
            return True
        except Exception as exc:  # pragma: no cover - depends on runtime credentials
            self.model = None
            self.initialization_error = str(exc)
            logger.error("Failed to initialize Gemini: %s", self.initialization_error)
            return False

    def update_model(self, model_name: str) -> bool:
        """Switch the active Gemini text model at runtime."""

        target = model_name or self.current_model
        return True if target == self.current_model else self._initialize_model(target)
    
    def is_available(self) -> bool:
        """Return True if Gemini model is initialized and ready."""
        return self.model is not None

    @staticmethod
    def _parse_json(raw_text: str, default: Any) -> Any:
        """Safely parse JSON from Gemini responses"""
        if not raw_text:
            return default
        
        # Clean up markdown code blocks
        cleaned = re.sub(r"^```(?:json)?", "", raw_text.strip(), flags=re.IGNORECASE | re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE)
        
        # Find the first valid JSON object or array
        match = re.search(r"\{.*\}|\[.*\]", cleaned, re.DOTALL)
        if not match:
            logger.warning(f"No JSON object or array found in Gemini response: {cleaned}")
            return default
            
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse JSON: {exc}. Raw string was: {json_str}")
            # Try to fix common issues like trailing commas
            json_str = re.sub(r",\s*([\]\}])", r"\1", json_str)
            try:
                return json.loads(json_str)
            except Exception:
                logger.error("Failed to parse JSON even after attempting fixes.")
                return default

    @staticmethod
    def _add_system_instruction(prompt: str) -> str:
        """Prefix prompts with the system instruction for SDKs without native support."""
        return f"{SYSTEM_INSTRUCTIONS}\n\n{prompt}"

    @staticmethod
    def _normalize_candidate_parts(candidate: Any) -> List[str]:
        """Return a list of text parts from a Gemini candidate payload."""

        parts = None

        if isinstance(candidate, dict):
            content = candidate.get("content")
            if isinstance(content, dict):
                parts = content.get("parts")
            parts = parts or candidate.get("parts")
        else:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) if content else getattr(candidate, "parts", None)

        if not parts:
            return []

        normalized: List[str] = []
        for part in parts:
            text_value = None
            if isinstance(part, str):
                text_value = part
            elif isinstance(part, dict):
                text_value = part.get("text")
            else:
                text_value = getattr(part, "text", None)

            if text_value and isinstance(text_value, str) and text_value.strip():
                normalized.append(text_value.strip())

        return normalized

    @classmethod
    def _extract_candidate_text(cls, response: Any) -> Optional[str]:
        """Extract the first non-empty text from Gemini response candidates."""

        candidates = getattr(response, "candidates", None)
        if not candidates:
            return None

        for candidate in candidates:
            # Some SDKs expose text directly on the candidate
            direct_text = getattr(candidate, "text", None)
            if not direct_text and isinstance(candidate, dict):
                direct_text = candidate.get("text")
            if direct_text and isinstance(direct_text, str) and direct_text.strip():
                return direct_text.strip()

            for part_text in cls._normalize_candidate_parts(candidate):
                if part_text.strip():
                    return part_text.strip()

        return None

    @staticmethod
    def _format_prompt_feedback(prompt_feedback: Any) -> Optional[Dict[str, Any]]:
        """Convert Gemini prompt feedback to a JSON-serializable dict."""

        if not prompt_feedback:
            return None

        formatted: Dict[str, Any] = {}

        block_reason = getattr(prompt_feedback, "block_reason", None)
        if block_reason is not None:
            formatted["block_reason"] = str(block_reason)

        safety_ratings = getattr(prompt_feedback, "safety_ratings", None)
        if safety_ratings:
            formatted["safety_ratings"] = [
                {
                    "category": str(getattr(rating, "category", "")),
                    "probability": getattr(rating, "probability", None),
                }
                for rating in safety_ratings
                if getattr(rating, "category", None) is not None
            ]

        feedback_detail = getattr(prompt_feedback, "block_reason_message", None)
        if feedback_detail:
            formatted["detail"] = str(feedback_detail)

        return formatted or None

    def _build_block_message(self, prompt_feedback: Any) -> str:
        """Return a user-friendly message when Gemini blocks the prompt."""

        formatted = self._format_prompt_feedback(prompt_feedback)
        if not formatted:
            return "Gemini request was blocked by safety filters."

        parts = []
        if formatted.get("block_reason"):
            parts.append(f"block_reason={formatted['block_reason']}")
        if formatted.get("detail"):
            parts.append(str(formatted["detail"]))
        if formatted.get("safety_ratings"):
            parts.append(f"safety_ratings={formatted['safety_ratings']}")

        return "Gemini request was blocked: " + "; ".join(parts)

    def _generate_model_text(
        self, prompt: str, images: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        """Call Gemini with retries and robust empty-response handling."""

        if not self.model:
            logger.error("Gemini model is not initialized.")
            return None

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                request_content = prompt if not images else [prompt, *images]
                response = self.model.generate_content(
                    request_content,
                    request_options={"timeout": self.request_timeout},
                    generation_config={
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "max_output_tokens": 1400,
                        "candidate_count": 1,
                    },
                    safety_settings={
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    }
                )

                if not response:
                    logger.error("Gemini returned no response object.")
                    return None

                prompt_feedback = getattr(response, "prompt_feedback", None)

                try:
                    response_text = response.text
                except Exception:
                    response_text = None

                if not response_text or not isinstance(response_text, str) or not response_text.strip():
                    candidate_text = self._extract_candidate_text(response)
                    if candidate_text:
                        return candidate_text

                    if prompt_feedback and getattr(prompt_feedback, "block_reason", None) is not None:
                        message = self._build_block_message(prompt_feedback)
                        raise GeminiPromptBlocked(message, prompt_feedback)

                    candidates = getattr(response, "candidates", None)
                    if candidates is not None and len(candidates) == 0:
                        logger.error("Gemini returned an empty candidates list without text.")
                        raise GeminiRequestFailed(
                            "Gemini returned an empty response without text or candidates."
                        )

                    logger.error("Gemini returned no text or candidates to parse.")
                    raise GeminiRequestFailed(
                        "Gemini returned no text or candidates to parse."
                    )

                return response_text

            except GeminiPromptBlocked as exc:
                last_error = exc
                self.last_prompt_feedback = self._format_prompt_feedback(
                    getattr(exc, "prompt_feedback", None)
                )
                logger.error("Gemini request blocked: %s", exc)
                break
            except Exception as exc:  # pragma: no cover - relies on remote API
                last_error = exc

                if isinstance(exc, (core_exceptions.PermissionDenied, core_exceptions.Forbidden)) or (
                    hasattr(exc, "code") and getattr(exc, "code") == 403
                ):
                    permission_msg = (
                        "Gemini API returned 403 (permission denied). Check your API key, "
                        "Google Cloud project access, and that the Gemini model is enabled for this project."
                    )
                    logger.error(permission_msg)
                    self.initialization_error = permission_msg

                    fallback_model = self._next_fallback_model()
                    if fallback_model:
                        logger.warning(
                            "Attempting fallback Gemini model after 403: %s -> %s",
                            self.current_model,
                            fallback_model,
                        )
                        if self._initialize_model(fallback_model):
                            logger.info("Retrying Gemini request with fallback model %s", fallback_model)
                            continue

                    self.model = None
                    last_error = permission_msg
                    break

                logger.warning(
                    "Gemini request failed (attempt %s/%s): %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(1.5 * attempt)

        if isinstance(last_error, GeminiPromptBlocked):
            raise last_error

        fallback_model = self._next_fallback_model()
        if fallback_model:
            logger.warning(
                "Switching to fallback Gemini model %s after repeated failure: %s",
                fallback_model,
                last_error,
            )
            if self._initialize_model(fallback_model):
                try:
                    return self._generate_model_text(prompt, images=images)
                except GeminiPromptBlocked:
                    raise
                except Exception as exc:  # pragma: no cover - remote API
                    last_error = exc

        logger.error(
            "Gemini request failed after %s attempts: %s", self.max_retries, last_error
        )
        raise GeminiRequestFailed(
            f"Gemini request failed after {self.max_retries} attempts: {last_error}",
            getattr(last_error, "prompt_feedback", None),
        )

    def _next_fallback_model(self) -> Optional[str]:
        """Return the next available model that has not yet been tried."""

        for model_name in self.available_models:
            if model_name not in self.tried_models:
                return model_name
        return None

    @staticmethod
    def _unique_page_order(page_numbers: List[int]) -> List[int]:
        """Return ordered, de-duplicated list of page numbers"""

        seen = set()
        ordered = []
        for page in page_numbers:
            if page not in seen:
                seen.add(page)
                ordered.append(page)
        return ordered

    @staticmethod
    def _has_fire_alarm_signals(text_lower: str) -> bool:
        """Detect whether the text contains clear fire alarm indicators."""

        keywords = [
            "fire alarm",
            "fire-alarm",
            "fa ",
            " fa-",
            "facp",
            "notification device",
            "horn strobe",
            "speaker strobe",
            "pull station",
            "annunciator",
            "riser diagram",
            "smoke detector",
            "heat detector",
            "manual station",
            "nac",
            "life safety",
            "smoke alarm",
            "duct smoke detector",
            "fac",
            "smoke control",
        ]

        return any(keyword in text_lower for keyword in keywords)

    @staticmethod
    def _is_landscaping_page(text_lower: str) -> bool:
        """Return True if the page looks like landscaping/irrigation content."""

        landscaping_keywords = [
            "landscape",
            "landscaping",
            "planting plan",
            "irrigation",
            "tree protection",
            "shrub",
            "turf",
        ]

        return any(keyword in text_lower for keyword in landscaping_keywords)

    @staticmethod
    def _is_site_work_page(text_lower: str) -> bool:
        """Return True if the page is primarily site/civil work."""

        site_keywords = [
            "site plan",
            "site work",
            "civil plan",
            "grading",
            "erosion control",
            "stormwater",
            "utility plan",
            "paving plan",
        ]

        return any(keyword in text_lower for keyword in site_keywords)

    @staticmethod
    def _is_engineering_page(text_lower: str) -> bool:
        """Return True if the page appears to be structural/engineering only."""

        engineering_keywords = [
            "structural",
            "foundation plan",
            "beam schedule",
            "column schedule",
            "truss",
            "engineering calculation",
            "structural general notes",
        ]

        return any(keyword in text_lower for keyword in engineering_keywords)

    @staticmethod
    def _is_architectural_page(text_lower: str) -> bool:
        """Return True if the page is part of the architectural set."""

        architectural_keywords = [
            "architectural",
            "floor plan",
            "reflected ceiling plan",
            "door schedule",
            "finish schedule",
            "partition schedule",
            "wall section",
            "a-",
        ]

        return any(keyword in text_lower for keyword in architectural_keywords)

    @staticmethod
    def _is_plumbing_page(text_lower: str) -> bool:
        """Return True if the page is plumbing-focused."""

        plumbing_keywords = [
            "plumbing",
            "sanitary",
            "storm drain",
            "domestic water",
            "water heater",
            "vent stack",
        ]

        return any(keyword in text_lower for keyword in plumbing_keywords)

    def _filter_pages_for_gemini(
        self, pages_text: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove non-fire-alarm sections before passing context to Gemini."""

        if not pages_text:
            return []

        filtered_pages: List[Dict[str, Any]] = []
        dropped_reasons: List[str] = []

        for page in pages_text:
            text = page.get("text", "") or ""
            text_lower = text.lower()
            page_number = page.get("page_number")

            if self._is_landscaping_page(text_lower):
                dropped_reasons.append(f"Page {page_number}: landscaping")
                continue

            if self._is_site_work_page(text_lower):
                dropped_reasons.append(f"Page {page_number}: site work")
                continue

            if self._is_engineering_page(text_lower):
                dropped_reasons.append(f"Page {page_number}: structural/engineering")
                continue

            if self._is_architectural_page(text_lower) and not self._has_fire_alarm_signals(text_lower):
                dropped_reasons.append(f"Page {page_number}: architectural without fire alarm content")
                continue

            if self._is_plumbing_page(text_lower) and not self._has_fire_alarm_signals(text_lower):
                dropped_reasons.append(f"Page {page_number}: plumbing without fire alarm content")
                continue

            filtered_pages.append(page)

        if dropped_reasons:
            logger.info(
                "Filtered %s pages before Gemini transmission: %s",
                len(dropped_reasons),
                "; ".join(dropped_reasons[:20]),
            )
            if len(dropped_reasons) > 20:
                logger.info("Additional pages filtered (not listed): %s", len(dropped_reasons) - 20)
        else:
            logger.info("No pages filtered before Gemini transmission.")

        return filtered_pages

    def _filter_spec_book_sections(
        self, spec_pages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Keep only the spec book pages that reference fire alarm scope."""

        if not spec_pages:
            return []

        division_pattern = re.compile(r"\b28\s*(?:\d{2}|\d{2}\.\d{2}|\d{2}\.\d{2}\.\d{2})")
        fire_alarm_terms = [
            "fire alarm",
            "mass notification",
            "notification appliance",
            "initiating device",
            "voice evacuation",
            "life safety",
            "smoke detector",
            "pull station",
            "alarm control",
            "fa system",
            "facp",
            "co",
            "fire smoke",
            "addressable",
            "nac",
            "duct smoke detector"
        ]

        filtered: List[Dict[str, Any]] = []

        for page in spec_pages:
            text = page.get("text", "") or ""
            lower = text.lower()
            page_number = page.get("page_number")

            if division_pattern.search(lower) or any(term in lower for term in fire_alarm_terms):
                filtered.append({
                    "page_number": page_number,
                    "text": text,
                })

        if filtered:
            logger.info(
                "Prepared %s spec book pages for Gemini (fire alarm focus): %s",
                len(filtered),
                ", ".join(str(p.get("page_number")) for p in filtered[:15]),
            )
        else:
            logger.info("No fire-alarm-related sections found in spec book; skipping upload context.")

        return filtered[:12]

    @staticmethod
    def _compile_spec_excerpt(
        spec_sections: Optional[List[Dict[str, Any]]],
        char_limit: int = 16000,
    ) -> str:
        """Create a bounded text block from relevant spec sections."""

        if not spec_sections:
            return ""

        excerpts: List[str] = []
        remaining = char_limit

        for section in spec_sections:
            text = (section.get("text") or "").strip()
            if not text or remaining <= 0:
                continue

            snippet = text if len(text) <= remaining else text[:remaining]
            header = f"[Spec Page {section.get('page_number')}]\n"
            block = f"{header}{snippet}"
            if len(block) > remaining:
                block = block[:remaining]

            excerpts.append(block)
            remaining -= len(block)

            if remaining <= 0:
                break

        return "\n\n".join(excerpts)

    @staticmethod
    def _image_guidance_text(
        image_payload: Optional[List[Dict[str, Any]]],
        image_pages: Optional[List[int]] = None,
    ) -> str:
        """Describe attached images so prompts instruct Gemini to use drawings."""

        if not image_payload:
            return ""

        if image_pages:
            mapped_pages = ", ".join(f"Page {page}" for page in image_pages)
            return (
                "\n\nIMAGE CONTEXT: The referenced PDF pages are attached as rendered "
                f"PNG images ({mapped_pages}). Rely on the drawings in these images instead "
                "of any OCR text when extracting details."
            )

        return (
            "\n\nIMAGE CONTEXT: PDF pages are attached as rendered PNG images. "
            "Use the drawings directly rather than relying on OCR text."
        )

    def _select_pages_for_image_transmission(
        self, pages_text: List[Dict[str, Any]]
    ) -> List[int]:
        """Pick a small, relevant set of pages to send as images."""

        if not pages_text:
            return []

        cover_pages = [page["page_number"] for page in pages_text[:3]]

        fire_alarm_section_pages = self._find_fire_alarm_section_pages(pages_text)

        ordered_unique = self._unique_page_order([
            *cover_pages,
            *fire_alarm_section_pages,
        ])[: self.max_image_pages]

        logger.info(
            "Attaching %s page images to Gemini (cover + fire alarm sections): %s",
            len(ordered_unique),
            ordered_unique,
        )
        return ordered_unique

    def _find_fire_alarm_section_pages(
        self, pages_text: List[Dict[str, Any]]
    ) -> List[int]:
        """Locate pages that belong to the fire alarm section for image transmission."""

        if not pages_text:
            return []

        fire_alarm_keywords = [
            "fire alarm",
            "fire-alarm",
            "fire alarm riser",
            "fire alarm notes",
            "fire alarm general notes",
            "notification device",
            "horn strobe",
            "speaker strobe",
            "pull station",
            "annunciator",
            "ann",
            "duct smoke detector",
            "smoke sensor"
        ]

        electrical_section_keywords = [
            "electrical",
            "power plan",
            "special systems",
            "one-line",
            "riser diagram",
        ]

        candidate_pages: List[int] = []

        for page in pages_text:
            page_text = page.get("text", "")
            page_number = page.get("page_number")
            if not page_text or page_number is None:
                continue

            text_lower = page_text.lower()

            has_fire_alarm_terms = any(keyword in text_lower for keyword in fire_alarm_keywords)
            has_section_context = any(keyword in text_lower for keyword in electrical_section_keywords)
            has_fa_sheet_id = bool(re.search(r"\bfa[-\s]?\d{1,3}\b", text_lower))

            if has_fire_alarm_terms or (has_section_context and has_fa_sheet_id):
                candidate_pages.append(page_number)

        return self._unique_page_order(candidate_pages)

    def _build_image_payload(self, pdf_path: str, page_numbers: List[int]) -> List[Dict[str, Any]]:
        """Render selected pages to downscaled JPEG bytes for Gemini vision context."""

        if not page_numbers:
            return []

        images = self.pdf_processor.pdf_to_images(pdf_path, selected_pages=page_numbers)
        payload: List[Dict[str, Any]] = []
        total_bytes = 0

        for image, page_number in zip(images, page_numbers):
            try:
                # Downscale to reduce upload size and speed up transmission.
                max_dimension = 1400
                image = image.convert("RGB")
                image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

                buffer = io.BytesIO()
                image.save(
                    buffer,
                    format="JPEG",
                    quality=80,
                    optimize=True,
                    progressive=True,
                )
                jpeg_bytes = buffer.getvalue()
                total_bytes += len(jpeg_bytes)
                payload.append({"inline_data": {"mime_type": "image/jpeg", "data": jpeg_bytes}})
            except Exception as exc:
                logger.warning(
                    "Skipping image for page %s due to render error: %s", page_number, exc
                )
                continue

        if payload:
            logger.info(
                "Prepared %s JPEG images for Gemini (%0.2f MB)",
                len(payload),
                total_bytes / 1_000_000,
            )

        return payload

    def analyze_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Comprehensive fire alarm analysis of construction bid set PDF
        """
        if not self.model:
            logger.error("Gemini model is not initialized.")
            return None

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.model.generate_content(
                    self._add_system_instruction(prompt)
                )

                if not response:
                    logger.error("Gemini returned no response object.")
                    return None

                prompt_feedback = getattr(response, "prompt_feedback", None)

                response_text = getattr(response, "text", None)
                if not response_text or not isinstance(response_text, str) or not response_text.strip():
                    candidate_text = self._extract_candidate_text(response)
                    if candidate_text:
                        return candidate_text

                    if prompt_feedback and getattr(prompt_feedback, "block_reason", None) is not None:
                        message = self._build_block_message(prompt_feedback)
                        raise GeminiPromptBlocked(message, prompt_feedback)

                    candidates = getattr(response, "candidates", None)
                    if candidates is not None and len(candidates) == 0:
                        logger.error("Gemini returned an empty candidates list without text.")
                        raise GeminiRequestFailed(
                            "Gemini returned an empty response without text or candidates."
                        )

                    logger.error("Gemini returned no text or candidates to parse.")
                    raise GeminiRequestFailed(
                        "Gemini returned no text or candidates to parse."
                    )

                return response_text

            except GeminiPromptBlocked as exc:
                last_error = exc
                self.last_prompt_feedback = self._format_prompt_feedback(
                    getattr(exc, "prompt_feedback", None)
                )
                logger.error("Gemini request blocked: %s", exc)
                break
            except Exception as exc:  # pragma: no cover - relies on remote API
                last_error = exc
                logger.warning(
                    "Gemini request failed (attempt %s/%s): %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(1.5 * attempt)

        if isinstance(last_error, GeminiPromptBlocked):
            raise last_error

        logger.error(
            "Gemini request failed after %s attempts: %s", self.max_retries, last_error
        )
        raise GeminiRequestFailed(
            f"Gemini request failed after {self.max_retries} attempts: {last_error}"
        )

    def _run_analysis_pipeline(
        self,
        pages_text: List[Dict[str, Any]],
        image_payload: Optional[List[Dict[str, Any]]] = None,
        image_pages: Optional[List[int]] = None,
        spec_sections: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Execute the core Gemini analysis steps once text has been extracted."""

        if not pages_text:
            return {
                'success': False,
                'error': 'Failed to extract text from PDF'
            }

        # Helper to safely run a step without crashing the pipeline
        def safe_step(func, *args, default=None):
            try:
                return func(*args)
            except (GeminiPromptBlocked, GeminiRequestFailed) as e:
                logger.warning(f"Step {func.__name__} failed/blocked: {e}")
                return default or [] if "list" in str(type(default)) else {}
            except Exception as e:
                logger.error(f"Step {func.__name__} unexpected error: {e}")
                return default

        # Step 1: Analyze cover pages for project info
        logger.info("Analyzing cover pages...")
        project_info = safe_step(
            self._analyze_cover_pages, pages_text[:5], image_payload, image_pages, default={}
        )

        # Step 2: Identify fire alarm relevant pages (Rule-based, rarely fails)
        logger.info("Identifying fire alarm pages...")
        fa_pages = self._identify_fire_alarm_pages(pages_text)

        # Step 3: Prepare a lean subset of pages to reduce token usage
        focused_pages = self._prioritize_pages_for_ai(pages_text, fa_pages)

        # Step 4: Extract fire-alarm-specific code requirements
        logger.info("Extracting fire alarm codes...")
        codes = safe_step(
            self._extract_code_requirements,
            focused_pages,
            image_payload,
            image_pages,
            default={'fire_alarm_codes': []},
        )

        # Step 5: Extract fire alarm notes from electrical pages
        logger.info("Extracting fire alarm notes...")
        fa_notes = safe_step(
            self._extract_fire_alarm_notes,
            focused_pages,
            fa_pages,
            image_payload,
            image_pages,
            default=[],
        )

        # Step 6: Extract mechanical fire alarm devices
        logger.info("Extracting mechanical FA devices...")
        mechanical_devices = safe_step(
            self._extract_mechanical_fa_devices,
            focused_pages,
            image_payload,
            image_pages,
            default={'duct_detectors': [], 'dampers': []}
        )

        # Step 7: Review device placement and CO detection
        logger.info("Reviewing device placement and CO detection needs...")
        device_layout_review = safe_step(
            self._review_device_layout,
            focused_pages,
            fa_pages,
            image_payload,
            image_pages,
            default={},
        )

        # Step 8: Extract specifications
        logger.info("Extracting specifications...")
        specifications = safe_step(
            self._extract_specifications,
            focused_pages,
            fa_pages,
            image_payload,
            image_pages,
            spec_sections,
            default={},
        )

        high_level_overview = self._build_high_level_overview(
            project_info, specifications
        )
        fire_alarm_briefing = self._build_fire_alarm_briefing(
            codes,
            specifications,
            fa_notes,
            device_layout_review,
        )

        structured_summary = self._build_structured_summary(
            project_info,
            specifications,
            codes,
            fa_notes,
            mechanical_devices,
            device_layout_review,
        )

        results = {
            'success': True,
            'project_info': project_info,
            'high_level_overview': high_level_overview,
            'fire_alarm_briefing': fire_alarm_briefing,
            'code_requirements': codes,
            'fire_alarm_pages': fa_pages,
            'fire_alarm_notes': fa_notes,
            'mechanical_devices': mechanical_devices,
            'device_layout_review': device_layout_review,
            'specifications': specifications,
            'spec_book_context': None,
            'structured_summary': structured_summary,
            'total_pages': len(pages_text),
            'analysis_timestamp': datetime.now().isoformat()
        }

        if spec_sections:
            results['spec_book_context'] = {
                'pages_considered': len(spec_sections),
                'pages_sent_to_gemini': [page.get('page_number') for page in spec_sections],
                'source': 'spec_pdf',
            }

        # Even if we had blocks, we return success=True so the UI shows what we DID get
        if self.last_prompt_feedback:
            results['prompt_feedback'] = self.last_prompt_feedback

        logger.info("Gemini analysis completed successfully (with potential partial blocks)")
        return results

    def analyze_pdf_text(self, pages_text: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run Gemini analysis when page text has already been extracted."""

        if not self.model:
            return {
                'success': False,
                'error': 'Gemini AI not initialized. Check API key.'
            }

        try:
            self.last_prompt_feedback = None
            filtered_pages = self._filter_pages_for_gemini(pages_text)

            if not filtered_pages:
                return {
                    'success': False,
                    'error': 'All pages were filtered out before Gemini analysis.'
                }

            return self._run_analysis_pipeline(filtered_pages)
        except GeminiPromptBlocked as exc:
            logger.error("Gemini analysis blocked: %s", exc)
            return {
                'success': False,
                'error': str(exc),
                'prompt_feedback': self.last_prompt_feedback
            }
        except GeminiRequestFailed as exc:
            logger.error("Gemini analysis failed after retries: %s", exc)
            return {
                'success': False,
                'error': str(exc),
                'prompt_feedback': self.last_prompt_feedback
            }
        except Exception as e:
            logger.error(f"Error during Gemini analysis: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'prompt_feedback': self.last_prompt_feedback
            }

    def answer_follow_up_question(
        self,
        question: str,
        prior_results: Optional[Dict[str, Any]] = None,
        pdf_path: Optional[str] = None,
        spec_pdf_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Use Gemini to answer follow-up questions with project context."""

        if not self.model:
            return {'success': False, 'error': 'Gemini AI not initialized. Check API key.'}

        if not question or not question.strip():
            return {'success': False, 'error': 'A follow-up question is required.'}

        context_blocks: List[str] = []

        if prior_results:
            condensed = {
                'project_info': prior_results.get('project_info'),
                'high_level_overview': prior_results.get('high_level_overview'),
                'fire_alarm_briefing': prior_results.get('fire_alarm_briefing'),
                'specifications': prior_results.get('specifications'),
                'device_layout_review': prior_results.get('device_layout_review'),
            }
            try:
                context_blocks.append(f"PRIOR GEMINI SUMMARY:\n{json.dumps(condensed, ensure_ascii=False)[:6000]}")
            except Exception:
                pass

        if pdf_path:
            try:
                pages_text = self.pdf_processor.extract_text_from_pdf(pdf_path)
                filtered_pages = self._filter_pages_for_gemini(pages_text)
                excerpt = "\n\n".join(
                    [
                        f"PAGE {page.get('page_number')}:\n{page.get('text','')[:1200]}"
                        for page in filtered_pages[:8]
                    ]
                )
                if excerpt:
                    context_blocks.append(f"PAGE EXCERPTS:\n{excerpt}")
            except Exception as exc:
                logger.error("Failed to build follow-up context from PDF: %s", exc)

        if spec_pdf_path:
            try:
                spec_pages = self.pdf_processor.extract_text_from_pdf(spec_pdf_path)
                spec_sections = self._filter_spec_book_sections(spec_pages)
                spec_excerpt = self._compile_spec_excerpt(spec_sections, char_limit=4000)
                if spec_excerpt:
                    context_blocks.append(f"SPEC EXCERPT:\n{spec_excerpt}")
            except Exception as exc:
                logger.error("Failed to build follow-up context from spec: %s", exc)

        context_text = "\n\n".join(context_blocks)

        prompt = f"""You are continuing as the fire alarm estimator AI. Answer the user's follow-up question using the project context.

FOLLOW-UP QUESTION:
{question.strip()}

CONTEXT:
{context_text[:16000]}

Expectations:
- Provide a concise, actionable answer.
- Cite specific page numbers when referencing device locations or notes.
- If device placement seems unusual, explain why it may be shown that way.
- Always state whether CO detection is required, not required, or unclear, and why.

Return JSON with keys: answer (string), referenced_pages (array of ints), co_detection (object with needed + reason), and notes (array of strings for any unusual placements or clarifications).
"""

        try:
            response_text = self._generate_model_text(self._add_system_instruction(prompt))
            if not response_text:
                return {'success': False, 'error': 'Empty response from Gemini'}

            parsed = self._parse_json(
                response_text,
                {
                    'answer': '',
                    'referenced_pages': [],
                    'co_detection': {'needed': None, 'reason': None},
                    'notes': [],
                },
            )
            return {'success': True, 'response': parsed}
        except GeminiPromptBlocked as exc:
            return {'success': False, 'error': str(exc), 'prompt_feedback': self._format_prompt_feedback(exc.prompt_feedback)}
        except GeminiRequestFailed as exc:
            return {'success': False, 'error': str(exc), 'prompt_feedback': self.last_prompt_feedback}
        except Exception as exc:
            logger.error("Follow-up question failed: %s", exc, exc_info=True)
            return {'success': False, 'error': str(exc)}

    def analyze_pdf(
        self,
        pdf_path: str,
        include_images: bool = True,
        spec_pdf_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive fire alarm analysis of construction bid set PDF
        """
        if not self.model:
            return {
                'success': False,
                'error': 'Gemini AI not initialized. Check API key.'
            }

        try:
            self.last_prompt_feedback = None
            logger.info(f"Starting Gemini analysis of PDF: {pdf_path}")

            pages_text = self.pdf_processor.extract_text_from_pdf(pdf_path)
            filtered_pages = self._filter_pages_for_gemini(pages_text)

            spec_sections: Optional[List[Dict[str, Any]]] = None
            if spec_pdf_path:
                spec_pages = self.pdf_processor.extract_text_from_pdf(spec_pdf_path)
                spec_sections = self._filter_spec_book_sections(spec_pages)

            if not filtered_pages:
                return {
                    'success': False,
                    'error': 'All pages were filtered out before Gemini analysis.'
                }

            image_pages: List[int] = []
            image_payload: Optional[List[Dict[str, Any]]] = None
            image_error: Optional[str] = None
            if include_images:
                image_pages = self._select_pages_for_image_transmission(filtered_pages)
                try:
                    image_payload = self._build_image_payload(pdf_path, image_pages)
                except Exception as exc:  # pragma: no cover - defensive guard for heavy PDFs
                    image_error = f"Failed to render images for Gemini: {exc}"
                    logger.error(image_error, exc_info=True)
                    image_payload = None

            results = self._run_analysis_pipeline(
                filtered_pages,
                image_payload,
                image_pages,
                spec_sections,
            )

            if include_images:
                results['image_pages_sent'] = image_pages
                results['images_attached_to_gemini'] = bool(image_payload)
                if image_error:
                    results['image_error'] = image_error

            return results
        except GeminiPromptBlocked as exc:
            logger.error("Gemini analysis blocked: %s", exc)
            return {
                'success': False,
                'error': str(exc),
                'prompt_feedback': self.last_prompt_feedback
            }
        except GeminiRequestFailed as exc:
            logger.error("Gemini analysis failed after retries: %s", exc)
            return {
                'success': False,
                'error': str(exc),
                'prompt_feedback': self.last_prompt_feedback
            }
        except Exception as e:
            logger.error(f"Error during Gemini analysis: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'prompt_feedback': self.last_prompt_feedback
            }
    
    def _analyze_cover_pages(
        self,
        cover_pages: List[Dict],
        image_payload: Optional[List[Dict[str, Any]]] = None,
        image_pages: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Analyze cover pages for project information"""

        cover_text = "\n\n".join([p['text'] for p in cover_pages])

        image_note = self._image_guidance_text(image_payload, image_pages)

        prompt = f"""Analyze these construction bid set cover pages and extract ONLY the high-level project details that matter to a fire alarm estimator.

COVER PAGES TEXT:
{cover_text[:15000]}

{image_note}

Extract the following information:
1. PROJECT NAME: Official name of the project
2. PROJECT ADDRESS OR LOCATION: Street address or city/state reference
3. PROJECT TYPE: (e.g., School, Hospital, Office Building, High-Rise, etc.)
4. APPLICABLE CODES: List any specific code versions mentioned (e.g., "IBC 2018", "NFPA 72-2016").
5. FIRE ALARM REQUIRED: State "Yes", "No", or "Unknown" based on the documents.
6. SPRINKLER STATUS: Indicate if the building is sprinkled and if FA must monitor it.
7. SCOPE SUMMARY: Brief summary of the overall project scope.
8. VOICE REQUIRED: State "Yes", "No", or "Unknown" based on the documents.

        Format your response as JSON with these keys: project_name, project_address, project_location, project_type, applicable_codes, fire_alarm_required, sprinkler_status, scope_summary, voice_required.
        If information is not found, use null.
        """

        try:
            response_text = self._generate_model_text(prompt, images=image_payload)
            if not response_text:
                return {}
            return self._parse_json(response_text, {})
        except GeminiPromptBlocked:
            raise
        except GeminiRequestFailed:
            raise
        except Exception as e:
            logger.error(f"Error analyzing cover pages: {str(e)}")
            return {'error': str(e)}

    def _identify_fire_alarm_pages(self, pages_text: List[Dict]) -> List[int]:
        """Identify which pages contain fire alarm information"""
        
        fa_pages = []
        fa_keywords = [
            'fire alarm', 'fa device', 'smoke detector', 'heat detector',
            'pull station', 'notification device', 'horn strobe', 'speaker strobe',
            'fire alarm control', 'facp', 'control panel', 'annunciator',
            'special systems', 'power plan', 'electrical plan',
            'life safety plan', 'fire alarm general notes', 'fire alarm riser',
            'special systems plan', 'fire protection plan', 'fa', 'nfpa', 'ann'
        ]
        
        for page in pages_text:
            page_text_lower = page['text'].lower()
            
            if any(keyword in page_text_lower for keyword in fa_keywords):
                if 'mounting height' not in page_text_lower or \
                   'fire alarm' in page_text_lower:
                    fa_pages.append(page['page_number'])
        
        return sorted(list(set(fa_pages))) # Return unique, sorted list

    def _prioritize_pages_for_ai(
        self,
        pages_text: List[Dict[str, Any]],
        fa_pages: List[int],
        max_pages: int = 30,
    ) -> List[Dict[str, Any]]:
        """Return a trimmed list of representative pages to keep prompts fast."""

        prioritized: List[Dict[str, Any]] = []
        seen_pages = set()

        def add_page(page: Dict[str, Any]):
            page_number = page.get('page_number')
            if page_number in seen_pages:
                return
            seen_pages.add(page_number)
            prioritized.append(page)

        # Always include the first few pages for project context
        for page in pages_text[:5]:
            add_page(page)

        # Bring in pages the rule-based detector tagged as fire alarm related
        for page in pages_text:
            if page.get('page_number') in fa_pages:
                add_page(page)

        # Grab mechanical/HVAC-heavy pages because they often influence FA scope
        mechanical_keywords = {'mechanical', 'hvac', 'duct', 'damper', 'air handler', 'rtu', 'ahu'}
        for page in pages_text:
            if len(prioritized) >= max_pages:
                break
            if page.get('page_number') in seen_pages:
                continue
            text = (page.get('text') or '').lower()
            if any(keyword in text for keyword in mechanical_keywords):
                add_page(page)

        # Fill remaining slots with the earliest pages to preserve document order
        for page in pages_text:
            if len(prioritized) >= max_pages:
                break
            add_page(page)

        return prioritized[:max_pages]
    
    def _extract_code_requirements(
        self,
        pages_text: List[Dict],
        image_payload: Optional[List[Dict[str, Any]]] = None,
        image_pages: Optional[List[int]] = None,
    ) -> Dict[str, List[str]]:
        """Extract fire-alarm-specific codes and standards"""

        code_pages = "\n\n".join([p['text'] for p in pages_text[:10]])  # Focus on front matter

        image_note = self._image_guidance_text(image_payload, image_pages)

        prompt = f"""Identify only the fire alarm and life-safety codes cited in this project.

DOCUMENT TEXT:
{code_pages[:10000]}

{image_note}

Extract a concise list of the exact editions referenced for:
• FIRE ALARM CODES AND STANDARDS (e.g., NFPA 72-2019, NFPA 101-2018, UL 864).
• BUILDING CODES (e.g., IBC 2018, CBC 2019) if they are relevant to Life Safety.

Also, briefly note if you detect any CONFLICTS between cited codes (e.g., citing an outdated NFPA version vs a newer IBC).

        Return JSON with:
        - fire_alarm_codes: array of strings (e.g. ["NFPA 72-2016", "IBC 2015"])
        - code_notes: string (optional, for any conflicts or observations)
        """

        try:
            response_text = self._generate_model_text(prompt, images=image_payload)
            if not response_text:
                return {'fire_alarm_codes': []}
            data = self._parse_json(response_text, {})
            if isinstance(data, dict) and 'fire_alarm_codes' not in data:
                # Backwards compatibility with older schema
                fire_alarm_codes = data.get('fire_alarm_standards') or []
                return {'fire_alarm_codes': fire_alarm_codes}
            return data
        except GeminiPromptBlocked:
            raise
        except GeminiRequestFailed:
            raise
        except Exception as e:
            logger.error(f"Error extracting codes: {str(e)}")
            return {'fire_alarm_codes': [], 'error': str(e)}
    
    def _extract_fire_alarm_notes(
        self,
        pages_text: List[Dict],
        fa_pages: List[int],
        image_payload: Optional[List[Dict[str, Any]]] = None,
        image_pages: Optional[List[int]] = None,
    ) -> List[Dict[str, str]]:
        """Extract fire alarm general notes from electrical pages"""
        
        fa_text = "\n\n".join([
            f"PAGE {p['page_number']}:\n{p['text']}" 
            for p in pages_text 
            if p['page_number'] in fa_pages
        ])
        
        if not fa_text:
            return []
        
        image_note = self._image_guidance_text(image_payload, image_pages)

        prompt = f"""Analyze these electrical/fire alarm pages and extract ONLY the PROJECT-SPECIFIC fire alarm notes.

PAGES TEXT:
{fa_text[:15000]}

{image_note}

Extract fire alarm notes that are:
✓ Panel, annunciator, or riser room locations and access instructions
✓ Critical system requirements or specialty devices (e.g., elevator recall interfaces, suppression system tie-ins, beam/aspirating detection, smoke control interfaces)
✓ Unique installation constraints that affect layout or pricing (e.g., weatherproof requirements for garage devices, conduit routing requirements, monitoring of fire pump or generator)
✓ Coordination notes with other trades that the fire alarm contractor must address
✓ Code Compliance Notes that are specific to this project (e.g., "System must meet NFPA 72-2019 spacing")

DO NOT extract:
✗ Standard NFPA mounting heights (unless non-standard)
✗ Generic "shall comply with" statements
✗ Standard distance from walls/ceilings
✗ Boilerplate code compliance text
✗ General electrical notes not related to fire alarm
✗ Locations of typical field devices (e.g., individual smoke detectors, horn/strobes) unless the note calls out a unique or critical device
✗ Any mention of fire stopping, fire sealing, or other references to construction trades outside of the fire alarm scope

Format as JSON array with objects containing:
- page: page number
- note_type: (e.g., "System Requirement", "Device Specification", "Installation Note", "Code Compliance")
- content: the actual note text

Example:
[{{"page": 5, "note_type": "System Requirement", "content": "All devices shall be addressable"}}]
"""

        try:
            response_text = self._generate_model_text(prompt, images=image_payload)
            if not response_text:
                return []
            parsed_notes = self._parse_json(response_text, [])
            if not isinstance(parsed_notes, list):
                return []

            unique_notes = []
            seen_contents = set()

            for note in parsed_notes:
                if not isinstance(note, dict):
                    continue

                content = (note.get('content') or note.get('note') or note.get('text') or '').strip()
                if not content:
                    continue

                normalized = re.sub(r"\s+", " ", content).lower()
                if normalized in seen_contents:
                    continue
                seen_contents.add(normalized)

                unique_notes.append({
                    'page': note.get('page'),
                    'note_type': note.get('note_type'),
                    'content': content,
                })

            return unique_notes
        except GeminiPromptBlocked:
            raise
        except GeminiRequestFailed:
            raise
        except Exception as e:
            logger.error(f"Error extracting FA notes: {str(e)}")
            return []
    
    def _extract_mechanical_fa_devices(
        self,
        pages_text: List[Dict],
        image_payload: Optional[List[Dict[str, Any]]] = None,
        image_pages: Optional[List[int]] = None,
    ) -> Dict[str, List[Dict]]:
        """Extract duct detectors and fire/smoke dampers from mechanical pages"""
        
        mech_pages = []
        for page in pages_text:
            page_lower = page['text'].lower()
            if any(keyword in page_lower for keyword in [
                'mechanical', 'hvac', 'duct', 'damper', 'air handler', 'rtu', 'ahu', "fsd", "smoke damper", "fire damper", "fire smoke damper"
            ]):
                mech_pages.append(page)
        
        if not mech_pages:
            return {'duct_detectors': [], 'dampers': []}
        
        mech_text = "\n\n".join([
            f"PAGE {p['page_number']}:\n{p['text']}" 
            for p in mech_pages
        ])
        
        image_note = self._image_guidance_text(image_payload, image_pages)

        prompt = f"""Analyze these mechanical pages and extract fire alarm-related devices.

Always check the HVAC schedule to see if any equipment moves more than 2000 CFM. Those units should be listed with airflow and
whether a duct detector/relay is required.
For dampers, flag only NON-FUSIBLE-LINK types that require fire alarm control; fused-link dampers do NOT need relays.

MECHANICAL PAGES TEXT:
{mech_text[:15000]}

{image_note}

Extract:
1. DUCT DETECTORS: Location, type, airflow (if given), specifications
2. FIRE/SMOKE DAMPERS: Location, type (state if non-fusible link), required fire alarm action/relay
3. HIGH AIRFLOW HVAC: Any HVAC equipment over 2000 CFM from the schedule with airflow, ID, and whether a duct detector or relay is
   required.

For each device, extract:
- page: page number
- device_type: specific type (e.g., "Duct Smoke Detector", "Fire Damper")
- location: where it's located (e.g., "RTU-1", "all transfer ducts")
- quantity: if specified
- airflow_cfm: airflow if provided (use number only)
- damper_type: state "non-fusible link" or "fusible link" when mentioned
- requires_duct_detector: Yes/No if airflow is over 2000 CFM
- fire_alarm_action/specifications: any specific requirements (e.g., "provide relay to FACP")

Format as JSON with keys:
- duct_detectors: array of duct detector objects
- dampers: array of damper objects
- high_airflow_units: array of HVAC equipment over 2000 CFM

Only return devices that require fire alarm integration. Ignore generic HVAC notes or mechanical requirements that do not involve fire alarm monitoring or control. If none found, use empty arrays.
"""

        try:
            response_text = self._generate_model_text(prompt, images=image_payload)
            if not response_text:
                return {'duct_detectors': [], 'dampers': []}
            return self._parse_json(response_text, {'duct_detectors': [], 'dampers': [], 'high_airflow_units': []})
        except GeminiPromptBlocked:
            raise
        except GeminiRequestFailed:
            raise
        except Exception as e:
            logger.error(f"Error extracting mechanical devices: {str(e)}")
            return {'duct_detectors': [], 'dampers': [], 'high_airflow_units': [], 'error': str(e)}

    def _review_device_layout(
        self,
        pages_text: List[Dict[str, Any]],
        fa_pages: List[int],
        image_payload: Optional[List[Dict[str, Any]]] = None,
        image_pages: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Review device placement, page numbers, and CO detection needs."""

        fa_text = "\n\n".join(
            [f"PAGE {p['page_number']}:\n{p['text']}" for p in pages_text if p.get('page_number') in fa_pages]
        )

        if not fa_text:
            return {}

        image_note = self._image_guidance_text(image_payload, image_pages)

        prompt = f"""Review these fire alarm/electrical pages. Identify where devices are called out and flag unusual placements.

PAGES TEXT:
{fa_text[:16000]}

{image_note}

Extract the following and ALWAYS provide page numbers where available:
1) PRIMARY DEVICE PAGE: Identify the single page/sheet where the most fire alarm devices are shown or called out. Provide the page number and a short reason (e.g., "main FA floor plan" or "device matrix"). Do NOT list each device individually.
2) UNUSUAL PLACEMENTS: If devices appear in atypical locations (e.g., notification appliance inside mechanical room, detector outdoors), capture the placement and the stated reason or probable intent.
3) CO DETECTION CHECK: State whether carbon monoxide detection is required or explicitly not required, and why (e.g., fuel-burning equipment, parking garage, or explicit note).

Return JSON with:
{{
  "primary_fa_page": {{"page": 1, "reason": "Main FA device layout"}},
  "unusual_placements": [{{"page": 2, "device_type": "Strobe", "placement": "Mechanical room", "reason": "Owner request for internal alarm"}}],
  "co_detection": {{"needed": "Yes/No/Unknown", "reason": "why"}}
}}
"""

        try:
            response_text = self._generate_model_text(prompt, images=image_payload)
            if not response_text:
                return {}
            return self._parse_json(
                response_text,
                {'primary_fa_page': {}, 'unusual_placements': [], 'co_detection': {'needed': None, 'reason': None}},
            )
        except GeminiPromptBlocked:
            raise
        except GeminiRequestFailed:
            raise
        except Exception as exc:
            logger.error("Error during device layout review: %s", exc)
            return {'primary_fa_page': {}, 'unusual_placements': [], 'co_detection': {'needed': None, 'reason': str(exc)}}

    def _extract_specifications(
        self,
        pages_text: List[Dict],
        fa_pages: List[int],
        image_payload: Optional[List[Dict[str, Any]]] = None,
        image_pages: Optional[List[int]] = None,
        spec_sections: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Extract fire alarm system specifications"""
        
        fa_text = "\n\n".join([
            f"PAGE {p['page_number']}:\n{p['text']}"
            for p in pages_text
            if p['page_number'] in fa_pages
        ])

        general_notes_text = "\n\n".join([
            f"PAGE {p['page_number']}:\n{p['text']}"
            for p in pages_text
            if 'general note' in p.get('text', '').lower()
        ])

        spec_text = self._compile_spec_excerpt(spec_sections)

        combined_text = "\n\n".join(filter(None, [
            "FIRE ALARM PAGES:\n" + fa_text if fa_text else "",
            "GENERAL NOTES (include these when checking for existing panels):\n" + general_notes_text if general_notes_text else "",
            "SPEC BOOK FIRE ALARM EXCERPTS:\n" + spec_text if spec_text else "",
        ])).strip()

        if not combined_text:
            return {}

        image_note = self._image_guidance_text(image_payload, image_pages)

        prompt = f"""Extract fire alarm system specifications from these pages and spec book excerpts. Always review fire alarm related notes AND any
general notes to see if the plans list the manufacturer/model of an existing fire alarm control panel.

SOURCE TEXT:
{combined_text[:15000]}

{image_note}

Extract:
1. CONTROL PANEL: Manufacturer, model, features.
2. DEVICES: Types of devices required (smoke, heat, pull stations, etc.).
3. NOTIFICATION DEVICES: Types (horns, strobes, speakers, low frequency sounders).
4. SYSTEM TYPE: (e.g., Addressable, Conventional, Voice Evac).
5. WIRING CLASS: (e.g., Class A, Class B, Style 4, Style 6, Style 7).
6. COMMUNICATION: How system communicates (Ethernet, phone line, cellular, radio).
7. POWER REQUIREMENTS: Backup battery (e.g. 24hr + 5min), UPS requirements.
8. MONITORING: Central station monitoring requirements.
9. INTEGRATION: Integration with other systems (access control, BMS, elevator, suppression).
10. SPRINKLER SYSTEM: State whether the building has a sprinkler system and how the fire alarm must monitor it.
11. APPROVED MANUFACTURERS: List any specific fire alarm manufacturers/brands the specifications call out (return an array).
12. AUDIO / VOICE SYSTEM: Specify if a voice evacuation or audio system is required, optional, or explicitly not required.
13. EXISTING SYSTEM PANEL MODEL: If the drawings mention an existing fire alarm panel to remain, capture the exact
    manufacturer and model number from any fire alarm notes or general notes. Return null if nothing is referenced.

Format as JSON with these keys: CONTROL_PANEL, DEVICES, NOTIFICATION_DEVICES, SYSTEM_TYPE, WIRING_CLASS, COMMUNICATION, POWER_REQUIREMENTS, MONITORING, INTEGRATION, SPRINKLER_SYSTEM, APPROVED_MANUFACTURERS, AUDIO_SYSTEM, EXISTING_SYSTEM_PANEL_MODEL.
        Use null if not found. APPROVED_MANUFACTURERS should be an array if provided.
        """

        try:
            response_text = self._generate_model_text(prompt, images=image_payload)
            if not response_text:
                return {}
            return self._parse_json(response_text, {})
        except GeminiPromptBlocked:
            raise
        except GeminiRequestFailed:
            raise
        except Exception as e:
            logger.error(f"Error extracting specifications: {str(e)}")
            return {'error': str(e)}

    # ---------------------------------------------------------------------
    # Derived summary blocks for UI consumption
    # ---------------------------------------------------------------------
    def _build_high_level_overview(self, project_info: Dict[str, Any], specifications: Dict[str, Any]) -> Dict[str, Any]:
        """Create a concise project snapshot for the estimator-focused UI."""

        sprinkler_status = project_info.get('sprinkler_status') or self._get_spec_value(specifications, 'SPRINKLER_SYSTEM')
        fire_alarm_required = project_info.get('fire_alarm_required')

        return {
            'project_name': project_info.get('project_name') or project_info.get('name'),
            'project_address': project_info.get('project_address') or project_info.get('project_location') or project_info.get('location'),
            'project_type': project_info.get('project_type'),
            'fire_alarm_required': fire_alarm_required or 'Unknown',
            'sprinkler_status': sprinkler_status,
            'scope_summary': project_info.get('scope_summary'),
            'project_number': project_info.get('project_number'),
        }

    def _build_fire_alarm_briefing(
        self,
        codes: Dict[str, Any],
        specifications: Dict[str, Any],
        fire_alarm_notes: List[Dict[str, Any]],
        device_layout_review: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compile key requirements and notes for the fire alarm scope."""

        requirement_items: List[str] = []
        for label in [
            'SYSTEM_TYPE',
            'COMMUNICATION',
            'MONITORING',
            'AUDIO_SYSTEM',
            'APPROVED_MANUFACTURERS',
            'CONTROL_PANEL',
        ]:
            value = self._get_spec_value(specifications, label)
            if value:
                pretty_label = label.replace('_', ' ').title()
                requirement_items.append(f"{pretty_label}: {value}")

        equipment_items: List[str] = []

        codes_list = []
        if isinstance(codes, dict) and isinstance(codes.get('fire_alarm_codes'), list):
            codes_list = codes['fire_alarm_codes']

        co_detection = (device_layout_review or {}).get('co_detection') or {}
        if co_detection.get('needed'):
            co_note = f"CO detection: {co_detection.get('needed')}"
            if co_detection.get('reason'):
                co_note += f" ({co_detection['reason']})"
            requirement_items.append(co_note)


        return {
            'requirements': requirement_items,
            'equipment': equipment_items,
            'codes': codes_list,
            'notes': fire_alarm_notes or [],
        }

    def _get_spec_value(self, specifications: Dict[str, Any], key: str) -> Optional[Any]:
        """Retrieve a specification value with flexible casing."""

        if not specifications or not key:
            return None

        direct = specifications.get(key)
        if direct:
            return direct

        lower = key.lower()
        if lower in specifications:
            return specifications[lower]

        upper = key.upper()
        if upper in specifications:
            return specifications[upper]

        return None

    def _build_structured_summary(
        self,
        project_info: Dict[str, Any],
        specifications: Dict[str, Any],
        codes: Dict[str, Any],
        fire_alarm_notes: List[Dict[str, Any]],
        mechanical_devices: Dict[str, List[Dict[str, Any]]],
        device_layout_review: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a structured summary with pitfalls and estimator notes."""

        section_list: List[Dict[str, Any]] = []
        pitfalls: List[str] = []
        estimating_notes: List[str] = []

        def add_pitfall(message: Optional[str]):
            if message and message.strip():
                pitfalls.append(message.strip())

        def add_estimator_note(message: Optional[str]):
            if message and message.strip():
                estimating_notes.append(message.strip())

        # Project snapshot section
        overview_bullets = []
        if project_info.get('project_type'):
            overview_bullets.append(f"Type: {project_info['project_type']}")
        if project_info.get('project_address') or project_info.get('project_location'):
            overview_bullets.append(
                f"Location: {project_info.get('project_address') or project_info.get('project_location')}"
            )
        if project_info.get('scope_summary'):
            overview_bullets.append(f"Scope: {project_info['scope_summary']}")
        if project_info.get('project_number'):
            overview_bullets.append(f"Project # {project_info['project_number']}")

        if overview_bullets:
            section_list.append(
                {
                    'title': 'Project Snapshot',
                    'bullets': overview_bullets,
                    'summary': project_info.get('scope_summary'),
                }
            )

        # Specification highlights
        spec_bullets = []
        for label in [
            'CONTROL_PANEL',
            'SYSTEM_TYPE',
            'COMMUNICATION',
            'MONITORING',
            'AUDIO_SYSTEM',
            'APPROVED_MANUFACTURERS',
        ]:
            value = self._get_spec_value(specifications, label)
            if value:
                pretty = label.replace('_', ' ').title()
                spec_bullets.append(f"{pretty}: {value}")

        if spec_bullets:
            section_list.append(
                {
                    'title': 'Specifications',
                    'bullets': spec_bullets,
                    'summary': 'Key fire alarm specification calls.',
                }
            )

        # Codes
        fire_codes = []
        if isinstance(codes, dict) and isinstance(codes.get('fire_alarm_codes'), list):
            fire_codes = codes.get('fire_alarm_codes') or []

        if fire_codes:
            section_list.append(
                {
                    'title': 'Fire Alarm Codes',
                    'bullets': fire_codes,
                    'summary': 'Codes and editions cited for the fire alarm scope.',
                }
            )

        # Fire alarm notes
        if fire_alarm_notes:
            note_bullets = []
            for note in fire_alarm_notes:
                page = note.get('page')
                content = note.get('content')
                note_type = note.get('note_type')
                if content:
                    prefix = f"Page {page}: " if page is not None else ""
                    label = f"[{note_type}] " if note_type else ""
                    note_bullets.append(f"{prefix}{label}{content}")

            if note_bullets:
                section_list.append(
                    {
                        'title': 'Fire Alarm Notes',
                        'bullets': note_bullets,
                        'summary': 'Project-specific fire alarm notes pulled from the drawings.',
                    }
                )

        # Mechanical devices
        mech_bullets = []
        for device_type, devices in (mechanical_devices or {}).items():
            if not isinstance(devices, list):
                continue
            for device in devices:
                label = device.get('device_type') or device.get('type') or device_type
                location = device.get('location') or device.get('equipment_id')
                qty = device.get('quantity')
                details = device.get('specifications') or device.get('specs')
                airflow = device.get('airflow_cfm')
                damper_type = device.get('damper_type')
                fa_action = device.get('fire_alarm_action')
                requires_dd = device.get('requires_duct_detector')

                parts = [label]
                if location:
                    parts.append(f"at {location}")
                if qty:
                    parts.append(f"qty: {qty}")
                if airflow:
                    parts.append(f"airflow: {airflow} CFM")
                if damper_type:
                    parts.append(str(damper_type))
                if requires_dd:
                    parts.append(f"duct detector: {requires_dd}")
                if details:
                    parts.append(str(details))
                if fa_action:
                    parts.append(str(fa_action))

                mech_bullets.append(" - ".join(parts))

        if mech_bullets:
            section_list.append(
                {
                    'title': 'Mechanical-Linked Devices',
                    'bullets': mech_bullets,
                    'summary': 'Duct detectors and fire/smoke dampers that need FA integration.',
                }
            )

        # Device layout review (locations, unusual placements, CO detection)
        if device_layout_review:
            layout_bullets: List[str] = []

            primary_page = device_layout_review.get('primary_fa_page') or {}
            if primary_page:
                page = primary_page.get('page')
                reason = primary_page.get('reason') or primary_page.get('note')
                text = f"Most fire alarm devices shown on page {page if page is not None else '?'}"
                if reason:
                    text += f" – {reason}"
                layout_bullets.append(text)

            for unusual in device_layout_review.get('unusual_placements', []) or []:
                page = unusual.get('page')
                device_label = unusual.get('device_type') or 'Device'
                placement = unusual.get('placement')
                reason = unusual.get('reason') or unusual.get('impact')
                prefix = f"Page {page}: " if page is not None else ""
                parts = [f"Unusual placement for {device_label}"]
                if placement:
                    parts.append(str(placement))
                if reason:
                    parts.append(str(reason))
                layout_bullets.append(prefix + " - ".join(parts))

            co_detection = device_layout_review.get('co_detection') or {}
            co_needed = co_detection.get('needed')
            co_reason = co_detection.get('reason')
            if co_needed:
                text = f"CO detection needed: {co_needed}"
                if co_reason:
                    text += f" ({co_reason})"
                layout_bullets.append(text)

            if layout_bullets:
                section_list.append(
                    {
                        'title': 'Device Placement Review',
                        'bullets': layout_bullets,
                        'summary': 'Where devices are called out, unusual placements, and CO monitoring needs.',
                    }
                )

        # Pitfalls and gaps
        add_pitfall('Fire alarm / life safety codes not cited—confirm editions with AHJ.' if not fire_codes else None)
        add_pitfall(
            'Fire alarm required status not stated—confirm with project documents.'
            if not project_info.get('fire_alarm_required')
            else None
        )
        add_pitfall(
            'Sprinkler monitoring expectations unclear—verify whether system is sprinkled.'
            if not project_info.get('sprinkler_status')
            else None
        )

        co_detection = (device_layout_review or {}).get('co_detection') or {}
        if not co_detection.get('needed'):
            add_pitfall('CO detection requirement not stated—confirm if CO monitoring is required.')
        elif str(co_detection.get('needed')).lower() in {'unknown', 'unsure'}:
            add_pitfall('CO detection need is unclear—verify with mechanical plans and code path.')

        for label, message in [
            ('SYSTEM_TYPE', 'System type (addressable vs. conventional) not specified.'),
            ('COMMUNICATION', 'Communication path not defined (cellular/phone/network).'),
            ('MONITORING', 'Central station monitoring requirements not documented.'),
            ('AUDIO_SYSTEM', 'Voice evacuation or audio requirement is unclear.'),
            (
                'APPROVED_MANUFACTURERS',
                'Approved manufacturers list missing—spec may be open or needs confirmation.',
            ),
        ]:
            if not self._get_spec_value(specifications, label):
                add_pitfall(message)

        # Control panel and existing systems
        control_panel = self._get_spec_value(specifications, 'CONTROL_PANEL')
        if not control_panel:
            add_pitfall('Control panel manufacturer/model not identified—verify if existing panel to remain.')

        if not fire_alarm_notes:
            add_estimator_note('No project-specific fire alarm notes captured—check drawings for keyed notes.')

        if mech_bullets:
            add_estimator_note('Coordinate duct detectors and dampers with mechanical contractor for relay points.')
        else:
            add_pitfall('Mechanical integration devices (duct detectors/dampers) not found—confirm if required.')

        # Aggregate estimating notes
        estimating_notes.extend(pitfalls)

        sections_obj = {'estimating_notes': estimating_notes}

        return {
            'project_summary': project_info.get('scope_summary') or project_info.get('project_type'),
            'section_list': section_list,
            'pitfalls': pitfalls,
            'sections': sections_obj,
        }

