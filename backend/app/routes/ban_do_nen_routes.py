from __future__ import annotations

from flask import Blueprint, jsonify, request, send_from_directory

from ..services import ban_do_nen_service
from ..utils.validators import check_import_token

ban_do_nen_bp = Blueprint("ban_do_nen", __name__)


@ban_do_nen_bp.get("/tiles/ban-do-nen/<ma_xa>/<so_to>/v<int:version>/<int:z>/<int:x>/<int:y>.png")
def get_ban_do_nen_tile(ma_xa: str, so_to: str, version: int, z: int, x: int, y: int):
    directory = ban_do_nen_service.tile_dir(ma_xa, so_to, version, z, x)
    return send_from_directory(directory, f"{y}.png")


@ban_do_nen_bp.post("/api/ban-do-nen/upload-tiles")
def upload_ban_do_nen_tiles():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    ma_xa = request.form.get("ma_xa", "").strip()
    so_to = request.form.get("so_to", "").strip()
    tile_version = request.form.get("tile_version", "").strip()
    tiles_zip = request.files.get("tiles_zip")

    data, error_response = ban_do_nen_service.save_tiles_zip(
        ma_xa, so_to, tile_version, tiles_zip
    )
    if error_response:
        return error_response
    return jsonify(data)


@ban_do_nen_bp.get("/api/ban-do-nen")
def list_ban_do_nen():
    data, error_response = ban_do_nen_service.list_sheets()
    if error_response:
        return error_response
    return jsonify(data)


@ban_do_nen_bp.get("/api/ban-do-nen/in-view")
def get_ban_do_nen_in_view():
    try:
        west = float(request.args["west"])
        south = float(request.args["south"])
        east = float(request.args["east"])
        north = float(request.args["north"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai tham số khung bản đồ: west, south, east, north"}), 400

    data, error_response = ban_do_nen_service.get_in_view(west, south, east, north)
    if error_response:
        return error_response
    return jsonify(data)


@ban_do_nen_bp.get("/api/ban-do-nen/search")
def search_ban_do_nen():
    ma_xa = request.args.get("ma_xa", "").strip()
    so_to_raw = request.args.get("so_to", "").strip()
    so_to = so_to_raw or None

    data, error_response = ban_do_nen_service.search(ma_xa, so_to)
    if error_response:
        return error_response
    return jsonify(data)


@ban_do_nen_bp.get("/api/ban-do-nen/<int:id_>")
def get_ban_do_nen(id_: int):
    data, error_response = ban_do_nen_service.get_sheet(id_)
    if error_response:
        return error_response
    return jsonify(data)


@ban_do_nen_bp.post("/api/ban-do-nen/register")
def register_ban_do_nen():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    body = request.get_json(silent=True) or {}
    data, error_response = ban_do_nen_service.register(body)
    if error_response:
        return error_response
    return jsonify(data)


@ban_do_nen_bp.patch("/api/ban-do-nen/<int:id_>")
def update_ban_do_nen(id_: int):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    body = request.get_json(silent=True) or {}
    data, error_response = ban_do_nen_service.update_sheet(id_, body)
    if error_response:
        return error_response
    return jsonify(data)


@ban_do_nen_bp.delete("/api/ban-do-nen/<int:id_>")
def delete_ban_do_nen(id_: int):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    data, error_response = ban_do_nen_service.delete_sheet(id_)
    if error_response:
        return error_response
    return jsonify(data)
