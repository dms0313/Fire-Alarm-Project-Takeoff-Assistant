"""Configuration settings for Fire Alarm PDF Analyzer."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable, List, Tuple

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
    print("[CONFIG] Loaded environment variables from .env file")
except ImportError:
    print("[CONFIG] python-dotenv not installed, using system environment variables")
except Exception as e:
    print(f"[CONFIG] Warning: Could not load .env file: {e}")

BASE_DIR = Path(__file__).resolve().parent


# =============================================================================
# DETECTION MODEL
# =============================================================================
_DEFAULT_MODEL_FILENAMES: Tuple[str, ...] = ("best.pt", "BESTY.pt", "weights.pt")


def _ensure_absolute(path: Path, base: Path) -> Path:
    """Return an absolute version of *path* relative to *base* if needed."""

    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return (base / expanded).resolve()


def _int_from_env(var_name: str, default: int) -> int:
    """Return an integer environment value or a default when parsing fails."""

    raw_value = os.environ.get(var_name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        logging.getLogger(__name__).warning(
            "Invalid integer for %s: %s. Using default %s.",
            var_name,
            raw_value,
            default,
        )
        return default


def _iter_env_candidates(env_path: str, cwd: Path) -> Iterable[Path]:
    """Yield candidate paths derived from the LOCAL_MODEL_PATH environment value."""

    raw_path = Path(env_path).expanduser()

    # If the provided path looks like a file (has suffix), treat it directly.
    looks_like_file = raw_path.suffix != ""
    base_candidates: List[Path] = [raw_path]

    if not looks_like_file:
        # Treat as a directory and append common filenames.
        for name in _DEFAULT_MODEL_FILENAMES:
            base_candidates.append(raw_path / name)

    for candidate in base_candidates:
        yield _ensure_absolute(candidate, BASE_DIR)
        yield _ensure_absolute(candidate, cwd)


def _collect_candidate_paths() -> Tuple[str, bool, List[str]]:
    """Determine the most appropriate local model path and search order."""

    cwd = Path.cwd()
    raw_env_path = os.environ.get("LOCAL_MODEL_PATH")
    candidates: List[Path] = []

    if raw_env_path:
        candidates.extend(_iter_env_candidates(raw_env_path, cwd))

    default_directories = [
        BASE_DIR / "models",
        BASE_DIR.parent / "models",
        cwd / "models",
        BASE_DIR / "static" / "models",
        BASE_DIR.parent / "static" / "models",
    ]

    for directory in default_directories:
        for filename in _DEFAULT_MODEL_FILENAMES:
            candidates.append((directory / filename).resolve())

    # Deduplicate while preserving order.
    seen = set()
    unique_candidates: List[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)

    for candidate in unique_candidates:
        if candidate.is_file():
            return str(candidate), True, [str(path) for path in unique_candidates]

    # No existing file found, fall back to the first candidate or a sensible default.
    if unique_candidates:
        selected = unique_candidates[0]
    else:
        selected = (BASE_DIR / "models" / "best.pt").resolve()

    return str(selected), selected.is_file(), [str(path) for path in unique_candidates or [selected]]


LOCAL_MODEL_PATH, LOCAL_MODEL_FOUND, LOCAL_MODEL_SEARCH_PATHS = _collect_candidate_paths()

# =============================================================================
# OPTIONAL SERVICES
# =============================================================================
# Support either GEMINI_API_KEY or GOOGLE_API_KEY for Gemini configuration so that
# deployments that expose the key under Google's default env var are detected.
_RAW_GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
_RAW_GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY")
GEMINI_API_KEY = _RAW_GEMINI_KEY or _RAW_GOOGLE_KEY

# Default to a broadly available model to reduce 403s from restricted previews,
# while still allowing overrides via environment variable.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_MODEL_CHOICES = [
    "gemini-2.5-pro",
    "gemini-3-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-pro-preview-03-25",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite-preview",
    "gemini-2.0-flash-exp",
]

# =============================================================================
# PROCESSING SETTINGS
# =============================================================================
TILE_SIZE = 640
DPI = 350
OVERLAP_PERCENT = 0.25
DEFAULT_CONFIDENCE = 0.55
MAX_WORKERS = 4
MAX_CACHE_SIZE = 1000
GEMINI_PROMPT_TRIM_LIMIT = _int_from_env("GEMINI_PROMPT_TRIM_LIMIT", 10000)

# =============================================================================
# FLASK SETTINGS
# =============================================================================
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
PORT = int(os.environ.get('PORT', 5003))

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
        "FOUND" if LOCAL_MODEL_FOUND else "NOT FOUND",
    )
    if LOCAL_MODEL_SEARCH_PATHS:
        logger.info("  Local Model Search Paths:")
        for candidate in LOCAL_MODEL_SEARCH_PATHS:
            status = "FOUND" if os.path.exists(candidate) else "MISSING"
            logger.info("    - %s (%s)", candidate, status)
    if GEMINI_API_KEY:
        source = "GEMINI_API_KEY" if _RAW_GEMINI_KEY else "GOOGLE_API_KEY"
        logger.info(f"  Gemini API Key: SET (source: {source})")
    else:
        logger.info("  Gemini API Key: NOT SET (optional)")
    logger.info("=" * 70)

    # Check for local model availability
    model_available = LOCAL_MODEL_FOUND
    if not model_available:
        logger.warning(
            "⚠️  Local detection model not found - detection will be disabled"
        )

    return {
        'local_model_configured': model_available,
        'local_model_filename': os.path.basename(LOCAL_MODEL_PATH) if LOCAL_MODEL_PATH else '',
        'gemini_configured': bool(GEMINI_API_KEY)
    }
