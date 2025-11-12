"""Fire Alarm PDF Analyzer - Main Application"""
# --- PyTorch 2.6 Compatibility Patch (global) ---
import torch
from torch import serialization as _serialization

# Force-disable weights_only (trusted local checkpoint)
__orig_load = torch.load
def _safe_load_override(*args, **kwargs):
    kwargs["weights_only"] = False
    return __orig_load(*args, **kwargs)
torch.load = _safe_load_override
_serialization.load = _safe_load_override
# --- End Patch ---

# --- Ultralytics DFLoss shim for older checkpoints ---
import torch.nn as nn
try:
    import ultralytics.utils.loss as yloss
    if not hasattr(yloss, "DFLoss"):
        class DFLoss(nn.Module):
            def __init__(self, *args, **kwargs): super().__init__()
            def forward(self, *args, **kwargs):
                raise RuntimeError("DFLoss shim was called during inference (should not happen).")
        yloss.DFLoss = DFLoss
except Exception:
    # If ultralytics isn't imported yet, we'll set the shim later in local_yolo_detector too.
    pass
# --- End Shim ---


# --- PyTorch 2.6 Compatibility Patch ---
import torch
from torch import serialization

# Monkey-patch torch.load to force full model deserialization
_original_torch_load = torch.load

def _safe_load_override(*args, **kwargs):
    # Force-disable weights_only protection — trusted local checkpoint
    kwargs["weights_only"] = False
    return _original_torch_load(*args, **kwargs)

torch.load = _safe_load_override
serialization.load = _safe_load_override
# --- End Patch ---

import logging
import os
import sys

from flask import Flask

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from modules import (
    DetectionVisualizer,
    GeminiAnalyzer,
    LOCAL_YOLO_IMPORT_ERROR,
    LocalYOLODetector,
    PDFProcessor,
)


# =============================================================================
# LOGGING SETUP
# =============================================================================
logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


# =============================================================================
# FLASK APP INITIALIZATION
# =============================================================================
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH


class FireAlarmAnalyzer:
    """Main analyzer class that coordinates all components."""

    def __init__(self):
        self.pdf_processor = PDFProcessor(dpi=config.DPI)
        self.local_detector = None
        self.local_detector_error: str | None = None
        self.gemini_analyzer = GeminiAnalyzer()
        self.visualizer = DetectionVisualizer()

        # Initialize local detector if model available
        self._initialize_local_detector()

    def _initialize_local_detector(self) -> None:
        """Initialize local detection model if available."""

        model_path = getattr(config, 'LOCAL_MODEL_PATH', None)
        self.local_detector_error = None

        if LocalYOLODetector is None:
            base_error = "Local detector module could not be imported"
            if LOCAL_YOLO_IMPORT_ERROR:
                base_error = f"{base_error}: {LOCAL_YOLO_IMPORT_ERROR}"
            self.local_detector_error = base_error
            logger.error("❌ %s", self.local_detector_error)
            return

        if not model_path:
            self.local_detector_error = "LOCAL_MODEL_PATH is not configured"
            logger.error("❌ %s", self.local_detector_error)
            return

        if not getattr(config, 'LOCAL_MODEL_FOUND', os.path.exists(model_path)):
            self.local_detector_error = f"Local model file not found at {model_path}"
            logger.error("❌ %s", self.local_detector_error)
            search_paths = getattr(config, 'LOCAL_MODEL_SEARCH_PATHS', None)
            if search_paths:
                logger.info("🔎 Checked the following locations for the local model:")
                for candidate in search_paths:
                    status = '✅ found' if os.path.exists(candidate) else '❌ missing'
                    logger.info("    %s — %s", candidate, status)
            logger.info(
                "Set the LOCAL_MODEL_PATH environment variable to point to your model file."
            )
            return

        try:
            logger.info("Attempting to initialize local detector from %s", model_path)
            self.local_detector = LocalYOLODetector(model_path)
        except Exception as exc:  # pragma: no cover - initialization errors are logged
            self.local_detector_error = f"Failed to initialize local detector: {exc}"
            logger.error("❌ %s", self.local_detector_error, exc_info=True)
            return

        logger.info("✅ Local detector initialized successfully!")
        self.local_detector_error = None

# Create global analyzer instance
analyzer = FireAlarmAnalyzer()


# =============================================================================
# REGISTER ROUTES
# =============================================================================
from routes import register_routes  # noqa: E402

register_routes(app, analyzer)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main() -> None:
    """Main application entry point."""
    print("\n" + "=" * 70)
    print("🚨 FIRE ALARM PDF ANALYZER - v6 (NEW GEMINI MODULE)")
    print("=" * 70)

    # Validate configuration (assuming this function exists in config.py)
    try:
        config.validate_config()
    except AttributeError:
        logger.warning("config.validate_config() function not found. Skipping validation.")
    except Exception as exc:  # pragma: no cover - validation errors are logged
        logger.error("Error during config validation: %s", exc)

    logger.info("\n🤖 Analyzer Status:")
    detector_status = '✅ INITIALIZED' if analyzer.local_detector else '❌ NOT INITIALIZED'
    gemini_status = '✅ CONFIGURED' if analyzer.gemini_analyzer.is_available() else '⚪ NOT CONFIGURED'

    logger.info("  Local Detector: %s", detector_status)
    if not analyzer.local_detector and analyzer.local_detector_error:
        logger.error("  Local Detector Error: %s", analyzer.local_detector_error)

    logger.info("  Gemini AI: %s", gemini_status)

    if analyzer.local_detector:
        logger.info("\n✅ All systems ready!")
    else:
        logger.error(
            "⚠️  WARNING: Local detector is not initialized! Detection will be disabled."
        )

    print("=" * 70)
    print(f"🌐 Open your browser to: http://localhost:{config.PORT}")
    print("=" * 70 + "\n")

    # Run Flask app
    app.run(host='0.0.0.0', port=config.PORT, debug=False)


if __name__ == "__main__":
    main()
