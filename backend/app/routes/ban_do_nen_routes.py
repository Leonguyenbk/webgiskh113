from __future__ import annotations

import base64

from flask import Blueprint, Response, jsonify, request, send_from_directory

from ..services import ban_do_nen_service
from ..utils.validators import check_import_token

ban_do_nen_bp = Blueprint("ban_do_nen", __name__)

# URL tile có v<version> (tải lại tờ => version tăng => URL đổi) nên cho
# trình duyệt + Cloudflare cache hẳn 1 ngày. Trước đây send_from_directory
# trả "no-cache" => mỗi lần kéo/zoom bản đồ lại hỏi server toàn bộ tile.
TILE_CACHE_CONTROL = "public, max-age=86400"

# Tool cắt tile bỏ qua ô trong suốt (không ghi file) nên phần lớn ô trong
# ranh tờ không có file — trả 404 thì không được cache, Leaflet xin lại mãi
# (từng ~1.000 request 404/phút cho 1 tờ). Trả PNG 1x1 trong suốt thay thế.
_EMPTY_TILE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABpfZFQAAAAABJRU5ErkJggg=="
)


@ban_do_nen_bp.get("/tiles/ban-do-nen/<ma_xa>/<so_to>/v<int:version>/<int:z>/<int:x>/<int:y>.png")
def get_ban_do_nen_tile(ma_xa: str, so_to: str, version: int, z: int, x: int, y: int):
    directory = ban_do_nen_service.tile_dir(
        ma_xa, so_to, version, z, x, ban_do_nen_service.current_loai()
    )
    if (directory / f"{y}.png").is_file():
        response = send_from_directory(directory, f"{y}.png")
    elif directory.parent.parent.is_dir():
        # Tờ/version có thật, chỉ ô này trống.
        response = Response(_EMPTY_TILE_PNG, mimetype="image/png")
    else:
        return jsonify({"error": "Không có tile"}), 404
    response.headers["Cache-Control"] = TILE_CACHE_CONTROL
    return response


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
