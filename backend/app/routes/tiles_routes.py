from __future__ import annotations

from flask import Blueprint, Response, jsonify

from ..services.tiles_service import TileFetchError, fetch_tile

tiles_bp = Blueprint("tiles", __name__)


@tiles_bp.get("/api/tiles/<int:z>/<int:x>/<int:y>")
def vietbando_tile(z: int, x: int, y: int):
    if not 0 <= z <= 18:
        return jsonify({"error": "Mức zoom không hợp lệ"}), 400

    try:
        content, content_type = fetch_tile(z, x, y)
    except TileFetchError as exc:
        return jsonify(exc.payload), exc.status

    return Response(
        content,
        status=200,
        content_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
