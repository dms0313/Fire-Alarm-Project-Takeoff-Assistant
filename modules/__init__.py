"""Modules Package"""
import logging

logger = logging.getLogger(__name__)

# Public interface exposed when importing from ``modules``.
__all__ = [
    "PDFProcessor",
    "LocalYOLODetector",
    "DetectionVisualizer",
    "GeminiAnalyzer",
]

try:
    from .pdf_processor import PDFProcessor
    from .local_yolo_detector import LocalYOLODetector
    from .visualizer import DetectionVisualizer
    from .gemini_analyzer import GeminiFireAlarmAnalyzer as GeminiAnalyzer
except ImportError as exc:
    logger.error("Error importing core modules: %s", exc, exc_info=True)
    raise

UnifiedGeminiAnalyzer = None  # Backwards compatibility placeholder
