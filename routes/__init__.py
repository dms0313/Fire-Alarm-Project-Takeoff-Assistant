"""
Routes Module - Flask API endpoints
"""
from .auth import register_auth_routes
from .analysis import register_analysis_routes
from .preview import register_preview_routes
from .sales import register_sales_routes


def register_routes(app, analyzer):
    """Register all routes with the Flask app"""
    register_auth_routes(app)
    register_analysis_routes(app, analyzer)
    register_preview_routes(app, analyzer)
    register_sales_routes(app, analyzer)
