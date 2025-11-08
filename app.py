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
from modules.roboflow_detector import RoboflowDetector
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
        self.roboflow_detector = None
        # Updated to initialize the new GeminiFireAlarmAnalyzer
        self.gemini_analyzer = GeminiFireAlarmAnalyzer() 
        self.visualizer = DetectionVisualizer()
        
        # Initialize Roboflow if credentials available
        self._initialize_roboflow()
    
    def _initialize_roboflow(self):
        """Initialize Roboflow detector"""
        logger.info("Checking Roboflow credentials...")
        
        if all([config.ROBOFLOW_API_KEY, config.ROBOFLOW_WORKSPACE, config.ROBOFLOW_PROJECT]):
            try:
                logger.info("Attempting to initialize Roboflow detector...")
                self.roboflow_detector = RoboflowDetector(
                    config.ROBOFLOW_API_KEY,
                    config.ROBOFLOW_WORKSPACE,
                    config.ROBOFLOW_PROJECT,
                    int(config.ROBOFLOW_VERSION)
                )
                logger.info("✅ Roboflow detector initialized successfully!")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Roboflow: {str(e)}", exc_info=True)
        else:
            logger.warning("❌ Roboflow credentials incomplete")
            if not config.ROBOFLOW_API_KEY:
                logger.warning("  - ROBOFLOW_API_KEY is missing")
            if not config.ROBOFLOW_WORKSPACE:
                logger.warning("  - ROBOFLOW_WORKSPACE is missing")
            if not config.ROBOFLOW_PROJECT:
                logger.warning("  - ROBOFLOW_PROJECT is missing")

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
    logger.info(f"  Roboflow Detector: {'✅ INITIALIZED' if analyzer.roboflow_detector else '❌ NOT INITIALIZED'}")
    logger.info(f"  Gemini AI: {'✅ CONFIGURED' if analyzer.gemini_analyzer.is_available() else '⚪ NOT CONFIGURED'}")
    
    if not analyzer.roboflow_detector:
        logger.error("\n⚠️  WARNING: Roboflow detector is not initialized!")
        logger.error("The application will start but detection will not work.")
        logger.error("Please check your credentials and restart.")
    else:
        logger.info("\n✅ All systems ready!")
    
    print("=" * 70)
    print(f"🌐 Open your browser to: http://localhost:{config.PORT}")
    print("=" * 70 + "\n")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=config.PORT, debug=False)


if __name__ == "__main__":
    main()