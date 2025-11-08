"""
Routes Module - Flask API endpoints
"""
from .analysis import register_analysis_routes
from .preview import register_preview_routes


def register_routes(app, analyzer):
    """Register all routes with the Flask app"""
    register_analysis_routes(app, analyzer)
    register_preview_routes(app, analyzer)
