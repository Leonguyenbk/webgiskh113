from __future__ import annotations

import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from flask import jsonify, request

from ..repositories import ban_do_nen_repository

LIST_FILTER_FIELDS = ("ma_xa", "so_to", "trang_thai")

# Tile raster (bản đồ nền) chạy local — trước đây file .png nằm trên
# Supabase Storage, giờ lưu thẳng trên đĩa, Flask tự serve qua route
# GET /tiles/ban-do-nen/... (xem app/routes/ban_do_nen_routes.py). Giữ
# đúng cấu trúc cũ {ma_xa}/{so_to}/v{version}/{z}/{x}/{y}.png để chỉ cần
# đổi domain/gốc đường dẫn trong tile_url, không đổi gì khác.
TILES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "ban_do_nen_tiles"

# Tên entry hợp lệ trong file zip tile: "{z}/{x}/{y}.png" (chỉ số nguyên) —
# chặn zip-slip (đường dẫn "../", tuyệt đối, ký tự lạ).
_TILE_ENTRY_RE = re.compile(r"^(\d{1,2})/(\d{1,10})/(\d{1,10})\.png$")


def list_sheets():
    params = {}
    for field_name in LIST_FILTER_FIELDS:
        value = request.args.get(field_name, "").strip()
        if value:
            params[field_name] = f"eq.{value}"

    result, error_response = ban_do_nen_repository.list_all(params)
    if error_response:
        return None, error_response
    return {"items": result}, None


def get_sheet(id_: int):
    result, error_response = ban_do_nen_repository.get_by_id(id_)
    if error_response:
        return None, error_response
    if not result:
        return None, (jsonify({"error": "Không tìm thấy tờ bản đồ"}), 404)
    return result, None


def _validate_geom(geom) -> str | None:
    if not isinstance(geom, dict):
        return "geom phải là 1 object GeoJSON"
    if geom.get("type") != "Polygon":
        return "geom phải là GeoJSON Polygon"
    coordinates = geom.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates or len(coordinates[0]) < 4:
        return "geom.coordinates không hợp lệ (cần vành ngoài tối thiểu 4 điểm)"
    return None


def register(body: dict):
    ma_xa = str(body.get("ma_xa", "")).strip()
    # so_to là text (không bắt buộc số nguyên) — một số tờ bản đồ cũ đánh
    # số kèm tên địa phương cũ (VD "ttmdrak12").
    so_to = str(body.get("so_to", "")).strip()
    tile_url = str(body.get("tile_url", "")).strip()
    geom = body.get("geom")

    if not ma_xa or not so_to or not tile_url or not geom:
        return None, (jsonify({"error": "Thiếu ma_xa, so_to, geom hoặc tile_url"}), 400)

    geom_error = _validate_geom(geom)
    if geom_error:
        return None, (jsonify({"error": geom_error}), 400)

    try:
        tile_version = int(body.get("tile_version", 1))
    except (TypeError, ValueError):
        return None, (jsonify({"error": "tile_version phải là số nguyên"}), 400)

    def _optional_int(name: str):
        value = body.get(name)
        if value in (None, ""):
            return None, None
        try:
            return int(value), None
        except (TypeError, ValueError):
            return None, f"{name} phải là số nguyên"

    min_zoom, error = _optional_int("min_zoom")
    if error:
        return None, (jsonify({"error": error}), 400)
    max_zoom, error = _optional_int("max_zoom")
    if error:
        return None, (jsonify({"error": error}), 400)

    payload = {
        "p_ma_xa": ma_xa,
        "p_so_to": so_to,
        "p_geom_geojson": geom,
        "p_tile_url": tile_url,
        "p_tile_version": tile_version,
        "p_min_zoom": min_zoom,
        "p_max_zoom": max_zoom,
        "p_ghi_chu": (body.get("ghi_chu") or "").strip() or None,
    }

    result, error_response = ban_do_nen_repository.register(payload)
    if error_response:
        return None, error_response
    return {"ok": True, "id": result}, None


def update_sheet(id_: int, body: dict):
    updates: dict = {}
    if "kich_hoat" in body:
        updates["kich_hoat"] = bool(body["kich_hoat"])
    if "ghi_chu" in body:
        updates["ghi_chu"] = (body["ghi_chu"] or "").strip() or None

    if not updates:
        return None, (jsonify({"error": "Không có trường nào để cập nhật"}), 400)

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    result, error_response = ban_do_nen_repository.update(id_, updates)
    if error_response:
        return None, error_response
    if not result:
        return None, (jsonify({"error": "Không tìm thấy tờ bản đồ"}), 404)
    return {"ok": True, "item": result[0]}, None


def delete_sheet(id_: int):
    _, error_response = ban_do_nen_repository.delete(id_)
    if error_response:
        return None, error_response
    return {"ok": True}, None


def get_in_view(west, south, east, north):
    result, error_response = ban_do_nen_repository.get_in_view(west, south, east, north)
    if error_response:
        return None, error_response
    return result, None


def search(ma_xa: str, so_to=None):
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã xã"}), 400)
    result, error_response = ban_do_nen_repository.search(ma_xa, so_to)
    if error_response:
        return None, error_response
    return result, None


# Chỉ cho phép ma_xa/so_to là chữ/số/gạch dưới/gạch ngang — dùng trực tiếp
# làm tên thư mục trên đĩa (xem save_tiles_zip/tile_dir bên dưới), phải
# chặn "../" và ký tự đường dẫn khác ngay từ đây.
_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def tile_dir(ma_xa: str, so_to: str, version: int, z: int, x: int) -> Path:
    return TILES_DIR / ma_xa / so_to / f"v{version}" / str(z) / str(x)


def save_tiles_zip(ma_xa: str, so_to: str, tile_version_raw: str, tiles_zip):
    if not ma_xa or not so_to:
        return None, (jsonify({"error": "Thiếu ma_xa hoặc so_to"}), 400)
    if not _PATH_SEGMENT_RE.match(ma_xa) or not _PATH_SEGMENT_RE.match(so_to):
        return None, (
            jsonify({"error": "ma_xa/so_to chỉ được chứa chữ, số, gạch dưới, gạch ngang"}),
            400,
        )

    try:
        tile_version = int(tile_version_raw)
        if tile_version < 1:
            raise ValueError
    except (TypeError, ValueError):
        return None, (jsonify({"error": "tile_version phải là số nguyên >= 1"}), 400)

    if tiles_zip is None:
        return None, (jsonify({"error": "Thiếu file tiles_zip"}), 400)

    try:
        archive = zipfile.ZipFile(tiles_zip)
    except zipfile.BadZipFile:
        return None, (jsonify({"error": "tiles_zip không phải file .zip hợp lệ"}), 400)

    target_dir = TILES_DIR / ma_xa / so_to / f"v{tile_version}"
    saved = 0
    skipped = 0
    with archive:
        for name in archive.namelist():
            match = _TILE_ENTRY_RE.match(name.replace("\\", "/"))
            if not match:
                skipped += 1
                continue
            z, x, y = match.groups()
            out_path = target_dir / z / x / f"{y}.png"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as src, open(out_path, "wb") as dst:
                dst.write(src.read())
            saved += 1

    if saved == 0:
        return None, (
            jsonify({"error": "Không có tile hợp lệ trong file zip (cần đúng dạng {z}/{x}/{y}.png)"}),
            400,
        )

    return {"ok": True, "saved": saved, "skipped": skipped}, None
