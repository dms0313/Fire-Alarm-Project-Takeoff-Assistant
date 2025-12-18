"""Vercel entrypoint that exposes the Flask WSGI app."""

from app import app as application

# Vercel's Python runtime looks for a top-level ``app`` callable.
app = application
