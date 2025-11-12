"""Modules Package"""
import logging

logger = logging.getLogger(__name__)


# Public interface exposed when importing from ``modules``.
__all__ = []


LOCAL_YOLO_IMPORT_ERROR: str | None = None
__all__.append("LOCAL_YOLO_IMPORT_ERROR")


def _import_required(module_name: str, symbol: str):
    """Import a symbol from the modules package, logging on failure."""

    try:
        module = __import__(module_name, globals(), locals(), [symbol], 1)
        return getattr(module, symbol)
    except ImportError as exc:  # pragma: no cover - defensive logging
        logger.error("Error importing %s: %s", symbol, exc, exc_info=True)
        raise


PDFProcessor = _import_required("pdf_processor", "PDFProcessor")
__all__.append("PDFProcessor")

try:
    from .local_yolo_detector import LocalYOLODetector
except ImportError as exc:  # pragma: no cover - optional dependency
    LOCAL_YOLO_IMPORT_ERROR = str(exc)
    logger.error("Local YOLO detector unavailable: %s", exc, exc_info=True)
    LocalYOLODetector = None
else:
    __all__.append("LocalYOLODetector")

DetectionVisualizer = _import_required("visualizer", "DetectionVisualizer")
__all__.append("DetectionVisualizer")

GeminiAnalyzer = _import_required("gemini_analyzer", "GeminiFireAlarmAnalyzer")
__all__.append("GeminiAnalyzer")


try:
    from .roboflow_detector import RoboflowDetector  # type: ignore[attr-defined]
except ImportError as exc:  # pragma: no cover - optional dependency
    logger.warning("Roboflow detector unavailable: %s", exc)
    RoboflowDetector = None
else:
    __all__.append("RoboflowDetector")

try:
    from .gemini_analyzer_unified import GeminiAnalyzer as UnifiedGeminiAnalyzer
except ImportError as exc:  # pragma: no cover - optional dependency
    logger.warning("Unified Gemini analyzer unavailable: %s", exc)
    UnifiedGeminiAnalyzer = None
else:
    __all__.append("UnifiedGeminiAnalyzer")

