"""Legacy compatibility wrapper for local YOLO detector."""
import logging

from .local_yolo_detector import LocalYOLODetector

logger = logging.getLogger(__name__)


class RoboflowDetector(LocalYOLODetector):
    """Deprecated wrapper retaining the old import path.

    The project now uses a local YOLO model instead of the Roboflow API. This
    class simply extends :class:`LocalYOLODetector` so existing imports
    (`from modules.roboflow_detector import RoboflowDetector`) continue to work.
    A deprecation warning is emitted to remind developers to migrate to the new
    `LocalYOLODetector` name.
    """

    def __init__(self, *args, **kwargs):
        logger.warning(
            "RoboflowDetector is deprecated. Use LocalYOLODetector instead.")
        super().__init__(*args, **kwargs)
