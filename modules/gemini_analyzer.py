"""
Gemini Analyzer Module
Handles AI-powered analysis of fire alarm specifications using Google's Gemini API
"""

import logging
import os
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import google.generativeai as genai

# Corrected relative import for your module structure
from .pdf_processor import PDFProcessor
from config import GEMINI_API_KEY, GEMINI_MODEL # Assumes GEMINI_MODEL is in config

logger = logging.getLogger("fire-alarm-analyzer")

class GeminiFireAlarmAnalyzer:
    """AI-powered fire alarm specification analyzer using Gemini"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini analyzer"""
        self.api_key = api_key or GEMINI_API_KEY
        self.model = None
        self.pdf_processor = PDFProcessor()
        
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                # Use GEMINI_MODEL from config
                self.model = genai.GenerativeModel(GEMINI_MODEL) 
                logger.info(f"✅ Gemini AI initialized successfully with {GEMINI_MODEL}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {str(e)}")
        else:
            logger.warning("⚠️ GEMINI_API_KEY not found. AI Analysis will be disabled.")
    
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

    def analyze_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Comprehensive fire alarm analysis of construction bid set PDF
        """
        if not self.model:
            return {
                'success': False,
                'error': 'Gemini AI not initialized. Check API key.'
            }
        
        try:
            logger.info(f"Starting Gemini analysis of PDF: {pdf_path}")
            
            # Extract text from PDF using PDFProcessor
            pages_text = self.pdf_processor.extract_text_from_pdf(pdf_path)
            
            if not pages_text:
                return {
                    'success': False,
                    'error': 'Failed to extract text from PDF'
                }
            
            # Step 1: Analyze cover pages for project info
            logger.info("Analyzing cover pages...")
            project_info = self._analyze_cover_pages(pages_text[:5])  # First 5 pages
            
            # Step 2: Identify fire alarm relevant pages
            logger.info("Identifying fire alarm pages...")
            fa_pages = self._identify_fire_alarm_pages(pages_text)
            
            # Step 3: Extract code requirements
            logger.info("Extracting code requirements...")
            codes = self._extract_code_requirements(pages_text)
            
            # Step 4: Extract fire alarm notes from electrical pages
            logger.info("Extracting fire alarm notes...")
            fa_notes = self._extract_fire_alarm_notes(pages_text, fa_pages)
            
            # Step 5: Extract mechanical fire alarm devices
            logger.info("Extracting mechanical FA devices...")
            mechanical_devices = self._extract_mechanical_fa_devices(pages_text)
            
            # Step 6: Extract specifications
            logger.info("Extracting specifications...")
            specifications = self._extract_specifications(pages_text, fa_pages)
            
            results = {
                'success': True,
                'project_info': project_info,
                'code_requirements': codes,
                'fire_alarm_pages': fa_pages,
                'fire_alarm_notes': fa_notes,
                'mechanical_devices': mechanical_devices,
                'specifications': specifications,
                'total_pages': len(pages_text),
                'analysis_timestamp': datetime.now().isoformat()
            }
            
            logger.info("Gemini analysis completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Error during Gemini analysis: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _analyze_cover_pages(self, cover_pages: List[Dict]) -> Dict[str, Any]:
        """Analyze cover pages for project information"""
        
        cover_text = "\n\n".join([p['text'] for p in cover_pages])
        
        prompt = f"""Analyze these construction bid set cover pages and extract key project information.

COVER PAGES TEXT:
{cover_text[:15000]} 

Extract the following information:
1. PROJECT NAME: Official name of the project
2. PROJECT LOCATION: Address or location
3. PROJECT TYPE: (e.g., School, Hospital, Office Building, etc.)
4. SCOPE SUMMARY: Brief summary of the overall project scope
5. OWNER/CLIENT: Name of the project owner or client
6. ARCHITECT: Name of the architecture firm
7. ENGINEER: Name of the engineering firm(s)
8. PROJECT NUMBER: Any project reference numbers

Format your response as JSON with these keys: project_name, location, project_type, scope_summary, owner, architect, engineer, project_number.
If information is not found, use null.
"""
        
        try:
            response = self.model.generate_content(prompt)
            return self._parse_json(getattr(response, "text", ""), {})
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
            'special systems', 'power plan', 'electrical plan'
        ]
        
        for page in pages_text:
            page_text_lower = page['text'].lower()
            
            if any(keyword in page_text_lower for keyword in fa_keywords):
                if 'mounting height' not in page_text_lower or \
                   'fire alarm' in page_text_lower:
                    fa_pages.append(page['page_number'])
        
        return sorted(list(set(fa_pages))) # Return unique, sorted list
    
    def _extract_code_requirements(self, pages_text: List[Dict]) -> Dict[str, List[str]]:
        """Extract applicable codes and standards"""
        
        code_pages = "\n\n".join([p['text'] for p in pages_text[:10]]) # Look in first 10 pages
        
        prompt = f"""Analyze this construction document and identify all applicable codes and standards.

DOCUMENT TEXT:
{code_pages[:10000]}

Extract:
1. BUILDING CODES: (e.g., IBC 2021, CBC, etc.)
2. FIRE CODES: (e.g., IFC, NFPA codes specific to fire alarm)
3. ELECTRICAL CODES: (e.g., NEC 2020)
4. FIRE ALARM STANDARDS: (e.g., NFPA 72, NFPA 101)
5. LOCAL CODES: Any jurisdiction-specific requirements

Format response as JSON with keys: building_codes, fire_codes, electrical_codes, fire_alarm_standards, local_codes.
Each should be a list of strings. If none found, use empty list.
"""
        
        try:
            response = self.model.generate_content(prompt)
            return self._parse_json(getattr(response, "text", ""), {})
        except Exception as e:
            logger.error(f"Error extracting codes: {str(e)}")
            return {'error': str(e)}
    
    def _extract_fire_alarm_notes(self, pages_text: List[Dict], fa_pages: List[int]) -> List[Dict[str, str]]:
        """Extract fire alarm general notes from electrical pages"""
        
        fa_text = "\n\n".join([
            f"PAGE {p['page_number']}:\n{p['text']}" 
            for p in pages_text 
            if p['page_number'] in fa_pages
        ])
        
        if not fa_text:
            return []
        
        prompt = f"""Analyze these electrical/fire alarm pages and extract ONLY the PROJECT-SPECIFIC fire alarm notes.

PAGES TEXT:
{fa_text[:15000]}

Extract fire alarm notes that are:
✓ Project-specific requirements
✓ Device quantities or locations
✓ System specifications
✓ Special installation requirements
✓ Coordination notes with other trades

DO NOT extract:
✗ Standard NFPA mounting heights
✗ Generic "shall comply with" statements
✗ Standard distance from walls/ceilings
✗ Boilerplate code compliance text
✗ General electrical notes not related to fire alarm

Format as JSON array with objects containing:
- page: page number
- note_type: (e.g., "System Requirement", "Device Specification", "Installation Note")
- content: the actual note text

Example:
[{{"page": 5, "note_type": "System Requirement", "content": "All devices shall be addressable"}}]
"""
        
        try:
            response = self.model.generate_content(prompt)
            return self._parse_json(getattr(response, "text", ""), [])
        except Exception as e:
            logger.error(f"Error extracting FA notes: {str(e)}")
            return []
    
    def _extract_mechanical_fa_devices(self, pages_text: List[Dict]) -> Dict[str, List[Dict]]:
        """Extract duct detectors and fire/smoke dampers from mechanical pages"""
        
        mech_pages = []
        for page in pages_text:
            page_lower = page['text'].lower()
            if any(keyword in page_lower for keyword in [
                'mechanical', 'hvac', 'duct', 'damper', 'air handler', 'rtu', 'ahu'
            ]):
                mech_pages.append(page)
        
        if not mech_pages:
            return {'duct_detectors': [], 'dampers': []}
        
        mech_text = "\n\n".join([
            f"PAGE {p['page_number']}:\n{p['text']}" 
            for p in mech_pages
        ])
        
        prompt = f"""Analyze these mechanical pages and extract fire alarm-related devices.

MECHANICAL PAGES TEXT:
{mech_text[:15000]}

Extract:
1. DUCT DETECTORS: Location, type, specifications
2. FIRE/SMOKE DAMPERS: Location, type, specifications

For each device, extract:
- page: page number
- device_type: specific type (e.g., "Duct Smoke Detector", "Fire Damper")
- location: where it's located (e.g., "RTU-1", "all transfer ducts")
- quantity: if specified
- specifications: any specific requirements (e.g., "provide relay to FACP")

Format as JSON with keys:
- duct_detectors: array of duct detector objects
- dampers: array of damper objects

If none found, use empty arrays.
"""
        
        try:
            response = self.model.generate_content(prompt)
            return self._parse_json(getattr(response, "text", ""), {'duct_detectors': [], 'dampers': []})
        except Exception as e:
            logger.error(f"Error extracting mechanical devices: {str(e)}")
            return {'duct_detectors': [], 'dampers': [], 'error': str(e)}
    
    def _extract_specifications(self, pages_text: List[Dict], fa_pages: List[int]) -> Dict[str, Any]:
        """Extract fire alarm system specifications"""
        
        fa_text = "\n\n".join([
            f"PAGE {p['page_number']}:\n{p['text']}" 
            for p in pages_text 
            if p['page_number'] in fa_pages
        ])
        
        if not fa_text:
            return {}
        
        prompt = f"""Extract fire alarm system specifications from these pages.

FIRE ALARM PAGES:
{fa_text[:15000]}

Extract:
1. CONTROL PANEL: Manufacturer, model, features
2. DEVICES: Types of devices required (smoke, heat, pull stations, etc.)
3. NOTIFICATION DEVICES: Types (horns, strobes, speakers)
4. SYSTEM TYPE: (e.g., addressable, conventional, hybrid)
5. COMMUNICATION: How system communicates (Ethernet, phone line, cellular)
6. POWER REQUIREMENTS: Backup battery, UPS requirements
7. MONITORING: Central station monitoring requirements
8. INTEGRATION: Integration with other systems (access control, BMS, etc.)

Format as JSON with these keys: CONTROL_PANEL, DEVICES, NOTIFICATION_DEVICES, SYSTEM_TYPE, COMMUNICATION, POWER_REQUIREMENTS, MONITORING, INTEGRATION.
Use null if not found.
"""
        
        try:
            response = self.model.generate_content(prompt)
            return self._parse_json(getattr(response, "text", ""), {})
        except Exception as e:
            logger.error(f"Error extracting specifications: {str(e)}")
            return {'error': str(e)}