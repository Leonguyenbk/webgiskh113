from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import import_service
from ..utils.validators import check_import_token

admin_bp = Blueprint("admin", __name__)


@admin_bp.post("/api/import-gml")
def import_gml():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Thiếu file GML"}), 400

    data, error_response = import_service.import_gml(uploaded.stream)
    if error_response:
        return error_response
    return jsonify(data)


@admin_bp.post("/api/import-ranh-thon")
def import_ranh_thon():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Thiếu file Shapefile (.zip)"}), 400

    data, error_response = import_service.import_ranh_thon(uploaded.stream)
    if error_response:
        return error_response
    return jsonify(data)


@admin_bp.post("/api/delete-ranh-thon")
def delete_ranh_thon():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    payload = request.get_json(silent=True) or {}
    ma_xa = str(payload.get("ma_xa") or "").strip()
    if not ma_xa:
        return jsonify({"error": "Thiếu mã xã cần xóa"}), 400

    data, error_response = import_service.delete_ranh_thon(ma_xa)
    if error_response:
        return error_response
    return jsonify(data)


@admin_bp.post("/api/import-dong-bo")
def import_dong_bo():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Thiếu file CSV/Excel"}), 400

    data, error_response = import_service.import_dong_bo(uploaded.filename, uploaded.read())
    if error_response:
        return error_response
    return jsonify(data)
