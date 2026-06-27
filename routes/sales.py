"""Sales research dashboard routes."""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import jsonify, render_template, request

import config

DATABASE_PATH = config.BASE_DIR / "data" / "sales_research_database.json"
REAL_ESTATE_INDUSTRIES = [
    "Real estate agents",
    "Brokerages",
    "House flippers",
    "Property managers",
    "Home builders",
    "Commercial real estate",
    "Airbnb / short-term rental hosts",
    "Interior designers",
]


def _load_database() -> list[dict[str, Any]]:
    if not DATABASE_PATH.exists():
        return []
    try:
        return json.loads(DATABASE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_database(rows: list[dict[str, Any]]) -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in value).strip()
    return "-".join(cleaned.split()) or "local"


def _build_businesses(industry: str, area: str, radius: str) -> dict[str, list[dict[str, Any]]]:
    """Create structured lead rows for the dashboard.

    This is intentionally deterministic mock research data so the UI and JSON contract work
    without a paid search-provider API. Rows are marked with a research_status value so a
    future provider integration can replace them with verified contacts.
    """

    seed = f"{industry}|{area}|{radius}"
    rng = random.Random(seed)
    industry_label = industry or "Real estate photography prospects"
    area_label = area or "Local market"
    domain_slug = _safe_slug(area_label)
    vertical_tokens = ["Realty", "Homes", "Properties", "Estates", "Living", "Spaces"]
    contacts = ["Alex Morgan", "Taylor Reed", "Jordan Blake", "Casey Rivera", "Riley Stone", "Morgan Lee"]
    categories = {
        "small": ("Small Businesses", 3, ("1-5 agents", "5-15 listings/mo", "Single-city footprint")),
        "medium": ("Medium Businesses", 3, ("6-25 agents", "15-60 listings/mo", "County/regional footprint")),
        "large": ("Large Businesses", 3, ("25+ agents", "60+ listings/mo", "Multi-office footprint")),
    }
    grouped: dict[str, list[dict[str, Any]]] = {}

    for size_key, (size_label, count, footprint_options) in categories.items():
        grouped[size_key] = []
        for index in range(count):
            name = f"{area_label} {rng.choice(vertical_tokens)} {index + 1}"
            contact = contacts[(index + len(size_key)) % len(contacts)]
            phone = f"(555) {rng.randint(200, 899)}-{rng.randint(1000, 9999)}"
            email = f"hello+{_safe_slug(name)}@{domain_slug}.example"
            grouped[size_key].append(
                {
                    "id": str(uuid.uuid4()),
                    "business_name": name,
                    "point_of_contact": contact,
                    "phone": phone,
                    "email": email,
                    "industry": industry_label,
                    "estimated_size_reach_footprint": footprint_options[index % len(footprint_options)],
                    "business_size": size_label,
                    "local_area": area_label,
                    "search_radius": radius or "25 miles",
                    "research_status": "sample_unverified",
                }
            )
    return grouped


def _summarize(grouped: dict[str, list[dict[str, Any]]], industry: str, area: str, radius: str, analyzer: Any) -> str:
    counts = {key: len(value) for key, value in grouped.items()}
    fallback = (
        f"Found {sum(counts.values())} prospect records around {area or 'the target area'} within {radius or '25 miles'}. "
        "Prioritize medium and large real estate teams first because their listing volume and multi-office footprint "
        "usually create recurring real estate photography needs. Validate sample contacts before outreach."
    )
    gemini = getattr(analyzer, "gemini_analyzer", None)
    if not gemini or not gemini.is_available():
        return fallback

    prompt = (
        "Summarize these sales prospect results for a real estate photography outreach dashboard in 3 concise bullets. "
        f"Industry: {industry}. Area: {area}. Radius: {radius}. JSON: {json.dumps(grouped)[:6000]}"
    )
    try:
        result = gemini.generate_text(prompt) if hasattr(gemini, "generate_text") else None
        text = getattr(result, "text", None) or (result if isinstance(result, str) else None)
        return text.strip() if text else fallback
    except Exception:
        return fallback


def register_sales_routes(app, analyzer) -> None:
    """Register sales research dashboard and JSON endpoints."""

    @app.route("/sales", methods=["GET"])
    def sales_dashboard():
        return render_template("sales.html", industries=REAL_ESTATE_INDUSTRIES)

    @app.route("/api/sales/search", methods=["POST"])
    def sales_search():
        payload = request.get_json(silent=True) or {}
        industry = (payload.get("industry") or "Real estate agents").strip()
        area = (payload.get("area") or "Local market").strip()
        radius = (payload.get("radius") or "25 miles").strip()
        grouped = _build_businesses(industry, area, radius)
        rows = [row for group in grouped.values() for row in group]
        search_record = {
            "id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "industry": industry,
            "area": area,
            "radius": radius,
            "results": rows,
        }
        database = _load_database()
        database.append(search_record)
        _save_database(database)
        return jsonify({
            "success": True,
            "search": search_record,
            "tables": grouped,
            "summary": _summarize(grouped, industry, area, radius, analyzer),
            "json": rows,
        })

    @app.route("/api/sales/database", methods=["GET"])
    def sales_database():
        database = _load_database()
        all_rows = [row | {"search_id": search["id"], "searched_at": search["created_at"]} for search in database for row in search.get("results", [])]
        return jsonify({"success": True, "searches": database, "results": all_rows})
