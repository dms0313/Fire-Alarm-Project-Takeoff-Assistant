"""Configuration settings for Fire Alarm PDF Analyzer."""

import logging
import os

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
    print("[CONFIG] Loaded environment variables from .env file")
except ImportError:
    print("[CONFIG] python-dotenv not installed, using system environment variables")
except Exception as e:
    print(f"[CONFIG] Warning: Could not load .env file: {e}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =============================================================================
# DETECTION MODEL
# =============================================================================
LOCAL_MODEL_PATH = os.environ.get(
    "LOCAL_MODEL_PATH",
    os.path.join(BASE_DIR, "models", "best.pt"),
)

# =============================================================================
# OPTIONAL SERVICES
# =============================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"

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
PORT = int(os.environ.get('PORT', 5005))

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
    logger.info(f"  Local Model Path: {LOCAL_MODEL_PATH}")
    logger.info(
        "  Local Model Status: %s",
        "FOUND" if os.path.exists(LOCAL_MODEL_PATH) else "NOT FOUND",
    )
    logger.info(f"  Gemini API Key: {'SET' if GEMINI_API_KEY else 'NOT SET (optional)'}")
    logger.info("=" * 70)

    # Check for local model availability
    model_available = os.path.exists(LOCAL_MODEL_PATH)
    if not model_available:
        logger.warning(
            "⚠️  Local detection model not found - detection will be disabled"
        )

    return {
        'local_model_configured': model_available,
        'local_model_filename': os.path.basename(LOCAL_MODEL_PATH) if LOCAL_MODEL_PATH else '',
        'gemini_configured': bool(GEMINI_API_KEY)
    }
