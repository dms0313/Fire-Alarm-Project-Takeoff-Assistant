"""Authentication routes and middleware."""

from __future__ import annotations

import functools
import logging
from datetime import timedelta

from flask import (
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

import config

logger = logging.getLogger(__name__)


def _public_endpoints() -> set[str]:
    return {
        "login",
        "static",
    }


def _is_request_public(path: str, endpoint: str | None) -> bool:
    if not config.REQUIRE_LOGIN:
        return True

    if endpoint in _public_endpoints():
        return True

    if path.startswith("/static/"):
        return True

    return False


def _authenticate(password: str) -> bool:
    if not config.ADMIN_PASSWORD_HASH:
        logger.error("ADMIN_PASSWORD_HASH is not configured; rejecting login attempt")
        return False

    return check_password_hash(config.ADMIN_PASSWORD_HASH, password)


def login_required(view_func):  # type: ignore[override]
    """Decorator to enforce authentication for protected endpoints."""

    @functools.wraps(view_func)
    def wrapped(*args, **kwargs):
        endpoint = request.endpoint or ""

        if _is_request_public(request.path, endpoint):
            return view_func(*args, **kwargs)

        if session.get("authenticated"):
            return view_func(*args, **kwargs)

        if request.accept_mimetypes.best == "application/json" or request.path.startswith(
            "/api/"
        ):
            return jsonify({"success": False, "error": "Authentication required"}), 401

        return redirect(url_for("login", next=request.url))

    return wrapped


def register_auth_routes(app) -> None:
    """Register authentication routes and middleware on the Flask app."""

    @app.before_request
    def _enforce_authentication():
        endpoint = request.endpoint or ""

        if _is_request_public(request.path, endpoint):
            return None

        if session.get("authenticated"):
            return None

        if request.accept_mimetypes.best == "application/json" or request.path.startswith(
            "/api/"
        ):
            return jsonify({"success": False, "error": "Authentication required"}), 401

        return redirect(url_for("login", next=request.url))

    @app.route("/login", methods=["GET"])
    def login():
        if not config.REQUIRE_LOGIN:
            return redirect(url_for("index"))

        if session.get("authenticated"):
            dest = request.args.get("next") or url_for("index")
            return redirect(dest)

        return render_template("login.html")

    @app.route("/login", methods=["POST"])
    def login_submit():
        payload = request.get_json(silent=True) or request.form
        password = (payload.get("password") or "").strip()

        if not password:
            return jsonify({"success": False, "error": "Password is required"}), 400

        if not _authenticate(password):
            return (
                jsonify({"success": False, "error": "Invalid credentials"}),
                401,
            )

        session.clear()
        session.permanent = True
        app.permanent_session_lifetime = timedelta(minutes=config.SESSION_LIFETIME_MINUTES)
        session["authenticated"] = True
        logger.info("Administrator logged in successfully")

        return jsonify({"success": True})

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return jsonify({"success": True})

    @app.route("/api/auth/status", methods=["GET"])
    def auth_status():
        return jsonify({"authenticated": bool(session.get("authenticated"))})

