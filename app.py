"""
Fire Alarm PDF Analyzer - Main Application
Version 5 - Modularized Architecture
"""
import os
import sys
import logging
from flask import Flask

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
# Corrected imports based on your file structure
from modules.pdf_processor import PDFProcessor
from modules.local_yolo_detector import LocalYOLODetector
from modules.visualizer import DetectionVisualizer
# Updated to import the new Gemini Analyzer class
from modules.gemini_analyzer import GeminiFireAlarmAnalyzer 

# =============================================================================
# LOGGING SETUP
# =============================================================================
logging.basicConfig(
    level=config.LOG_LEVEL,
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# =============================================================================
# FLASK APP INITIALIZATION
# =============================================================================
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# =============================================================================
# ANALYZER INITIALIZATION
# =============================================================================
class FireAlarmAnalyzer:
    """Main analyzer class that coordinates all components"""
    
    def __init__(self):
        self.pdf_processor = PDFProcessor(dpi=config.DPI)
        self.local_detector = None
        # Updated to initialize the new GeminiFireAlarmAnalyzer
        self.gemini_analyzer = GeminiFireAlarmAnalyzer() 
        self.visualizer = DetectionVisualizer()
        
        # Initialize local detector if model available
        self._initialize_local_detector()

    def _initialize_local_detector(self):
        """Initialize local detection model."""
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
        except Exception as e:
            logger.error(f"❌ Failed to initialize local detector: {str(e)}", exc_info=True)

# Create global analyzer instance
analyzer = FireAlarmAnalyzer()

# =============================================================================
# REGISTER ROUTES
# =============================================================================
# Assuming routes/__init__.py has a register_routes function
from routes import register_routes
register_routes(app, analyzer)

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main():
    """Main application entry point"""
    print("\n" + "=" * 70)
    print("🚨 FIRE ALARM PDF ANALYZER - v6 (NEW GEMINI MODULE)")
    print("=" * 70)
    
    # Validate configuration (assuming this function exists in config.py)
    try:
        config.validate_config()
    except AttributeError:
        logger.warning("config.validate_config() function not found. Skipping validation.")
    except Exception as e:
        logger.error(f"Error during config validation: {e}")

    
    logger.info("\n🤖 Analyzer Status:")
    logger.info(f"  Local Detector: {'✅ INITIALIZED' if analyzer.local_detector else '❌ NOT INITIALIZED'}")
    logger.info(f"  Gemini AI: {'✅ CONFIGURED' if analyzer.gemini_analyzer.is_available() else '⚪ NOT CONFIGURED'}")
    
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