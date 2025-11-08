"""
Configuration settings for Fire Alarm PDF Analyzer
"""
import os
import logging

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[CONFIG] Loaded environment variables from .env file")
except ImportError:
    print("[CONFIG] python-dotenv not installed, using system environment variables")
except Exception as e:
    print(f"[CONFIG] Warning: Could not load .env file: {e}")

# =============================================================================
# API KEYS AND CREDENTIALS
# =============================================================================
ROBOFLOW_API_KEY = os.environ.get('ROBOFLOW_API_KEY')
ROBOFLOW_WORKSPACE = os.environ.get('ROBOFLOW_WORKSPACE', '')
ROBOFLOW_PROJECT = os.environ.get('ROBOFLOW_PROJECT', '')
ROBOFLOW_VERSION = os.environ.get('ROBOFLOW_VERSION', '1')

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI_MODEL = 'gemini-2.5-flash'

# =============================================================================
# PROCESSING SETTINGS
# =============================================================================
TILE_SIZE = 640
DPI = 350
OVERLAP_PERCENT = 0.25
DEFAULT_CONFIDENCE = 0.40
MAX_WORKERS = 4
MAX_CACHE_SIZE = 1000

# =============================================================================
# FLASK SETTINGS
# =============================================================================
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size
PORT = int(os.environ.get('PORT', 5000))

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

# =============================================================================
# VALIDATION
# =============================================================================
def validate_config():
    """Validate configuration and log status"""
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 70)
    logger.info("CONFIGURATION CHECK:")
    logger.info(f"  Roboflow API Key: {'SET (' + ROBOFLOW_API_KEY[:10] + '...)' if ROBOFLOW_API_KEY else 'NOT SET'}")
    logger.info(f"  Roboflow Workspace: {ROBOFLOW_WORKSPACE if ROBOFLOW_WORKSPACE else 'NOT SET'}")
    logger.info(f"  Roboflow Project: {ROBOFLOW_PROJECT if ROBOFLOW_PROJECT else 'NOT SET'}")
    logger.info(f"  Roboflow Version: {ROBOFLOW_VERSION if ROBOFLOW_VERSION else 'NOT SET'}")
    logger.info(f"  Gemini API Key: {'SET' if GEMINI_API_KEY else 'NOT SET (optional)'}")
    logger.info("=" * 70)
    
    # Check for required Roboflow credentials
    roboflow_configured = all([ROBOFLOW_API_KEY, ROBOFLOW_WORKSPACE, ROBOFLOW_PROJECT])
    if not roboflow_configured:
        logger.warning("⚠️  Roboflow credentials incomplete - detection will be disabled")
    
    return {
        'roboflow_configured': roboflow_configured,
        'gemini_configured': bool(GEMINI_API_KEY)
    }
