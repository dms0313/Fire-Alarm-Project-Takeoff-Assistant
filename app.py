"""Fire Alarm PDF Analyzer - Main Application"""
import logging
import os
import sys

from flask import Flask

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from modules.pdf_processor import PDFProcessor
from modules.local_yolo_detector import LocalYOLODetector
from modules.visualizer import DetectionVisualizer
from modules.gemini_analyzer import GeminiFireAlarmAnalyzer


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
        self.gemini_analyzer = GeminiFireAlarmAnalyzer()
        self.visualizer = DetectionVisualizer()

        # Initialize local detector if model available
        self._initialize_local_detector()

    def _initialize_local_detector(self) -> None:
        """Initialize local detection model if available."""
        logger.info("Checking local detection model...")

        model_path = getattr(config, 'LOCAL_MODEL_PATH', None)
        if not model_path:
            logger.error("❌ LOCAL_MODEL_PATH is not configured")
            return

        if not os.path.exists(model_path):
            logger.error("❌ Local model file not found at %s", model_path)
            return

        try:
            logger.info("Attempting to initialize local detector from %s", model_path)
            self.local_detector = LocalYOLODetector(model_path)
            logger.info("✅ Local detector initialized successfully!")
        except Exception as exc:  # pragma: no cover - initialization errors are logged
            logger.error("❌ Failed to initialize local detector: %s", exc, exc_info=True)


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
    logger.info(
        "  Local Detector: %s",
        '✅ INITIALIZED' if analyzer.local_detector else '❌ NOT INITIALIZED',
    )
    logger.info(
        "  Gemini AI: %s",
        '✅ CONFIGURED' if analyzer.gemini_analyzer.is_available() else '⚪ NOT CONFIGURED',
    )

    if not analyzer.local_detector:
        logger.error("\n⚠️  WARNING: Local detector is not initialized!")
        logger.error("The application will start but detection will not work.")
        logger.error("Please verify the LOCAL_MODEL_PATH setting and restart.")
    else:
        logger.info("\n✅ All systems ready!")

    print("=" * 70)
    print(f"🌐 Open your browser to: http://localhost:{config.PORT}")
    print("=" * 70 + "\n")

    # Run Flask app
    app.run(host='0.0.0.0', port=config.PORT, debug=False)


if __name__ == "__main__":
    main()
