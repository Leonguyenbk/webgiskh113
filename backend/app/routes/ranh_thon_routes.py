from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import ranh_thon_service

ranh_thon_bp = Blueprint("ranh_thon", __name__)


@ranh_thon_bp.get("/api/ranh-thon")
def get_ranh_thon():
    ma_xa = request.args.get("ma_xa", "")
    data, error_response = ranh_thon_service.get_ranh_gioi_thon(ma_xa)
    if error_response:
        return error_response
    return jsonify(data)
