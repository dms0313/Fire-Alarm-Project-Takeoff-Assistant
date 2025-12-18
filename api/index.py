"""Vercel entrypoint that exposes the Flask WSGI app."""

import os
import sys

# Ensure the project root is on sys.path when Vercel executes this file from
# the ``api`` directory. Without this, ``import app`` fails with
# ``ModuleNotFoundError`` and the serverless function returns 500.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app as application

# Vercel's Python runtime looks for a top-level ``app`` callable.
