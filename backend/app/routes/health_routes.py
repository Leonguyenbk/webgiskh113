from __future__ import annotations

from flask import Blueprint, current_app

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "webgis-api",
        "environment": current_app.config.get("RENDER_ENV", "local"),
    }
