from __future__ import annotations

from flask import jsonify, request

from ..repositories import ban_do_nen_repository

LIST_FILTER_FIELDS = ("ma_xa", "so_to", "trang_thai")


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
    so_to = body.get("so_to")
    tile_url = str(body.get("tile_url", "")).strip()
    geom = body.get("geom")

    if not ma_xa or so_to in (None, "") or not tile_url or not geom:
        return None, (jsonify({"error": "Thiếu ma_xa, so_to, geom hoặc tile_url"}), 400)

    try:
        so_to = int(so_to)
    except (TypeError, ValueError):
        return None, (jsonify({"error": "so_to phải là số nguyên"}), 400)

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


def get_in_xa(ma_xa: str):
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã xã"}), 400)
    result, error_response = ban_do_nen_repository.get_in_xa(ma_xa)
    if error_response:
        return None, error_response
    return result, None
