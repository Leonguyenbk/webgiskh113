from __future__ import annotations

from flask import jsonify, request

from ..repositories import parcel_repository
from ..utils.geometry import simplify_for_zoom
from ..utils.validators import read_bbox, read_nhom_list, read_optional_int

# Trần cứng số thửa mỗi lô. Vượt mức này Supabase dễ chạm statement_timeout
# khi phải sinh GeoJSON cho quá nhiều hình học trong một câu lệnh.
MAX_PAGE_SIZE = 3000
DEFAULT_PAGE_SIZE = 1000


def _read_paging():
    try:
        requested_limit = min(
            max(int(request.args.get("limit", DEFAULT_PAGE_SIZE)), 1),
            MAX_PAGE_SIZE,
        )
        page_offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        return None, None, (jsonify({"error": "limit hoặc offset không hợp lệ"}), 400)
    return requested_limit, page_offset, None


def _as_feature_collection(result):
    if not isinstance(result, dict):
        return {"type": "FeatureCollection", "features": []}
    result.setdefault("type", "FeatureCollection")
    result.setdefault("features", [])
    return result


def get_count():
    values, error_response = read_bbox()
    if error_response:
        return None, error_response

    ma_xa = request.args.get("ma_xa", "").strip()
    nhom_list = read_nhom_list()

    result, error_response = parcel_repository.count_in_view(
        values["west"], values["south"], values["east"], values["north"],
        ma_xa or None, nhom_list or None,
    )
    if error_response:
        return None, error_response

    try:
        total = int(result)
    except (TypeError, ValueError):
        total = 0

    return {"total": total}, None


def get_extent():
    result, error_response = parcel_repository.get_extent()
    if error_response:
        return None, error_response
    if not isinstance(result, dict):
        return None, (jsonify({"error": "Bảng thửa đất chưa có dữ liệu"}), 404)
    return result, None


def get_parcels():
    try:
        requested_limit = min(
            max(int(request.args.get("limit", DEFAULT_PAGE_SIZE)), 1),
            MAX_PAGE_SIZE,
        )
        page_offset = max(int(request.args.get("offset", 0)), 0)
        zoom = int(float(request.args.get("zoom", 16)))
    except (TypeError, ValueError):
        return None, (jsonify({"error": "limit, offset hoặc zoom không hợp lệ"}), 400)

    values, error_response = read_bbox()
    if error_response:
        return None, error_response

    ma_xa = request.args.get("ma_xa", "").strip()
    nhom_list = read_nhom_list()

    result, error_response = parcel_repository.get_in_view(
        values["west"], values["south"], values["east"], values["north"],
        values["center_lng"], values["center_lat"],
        requested_limit, page_offset,
        ma_xa or None, simplify_for_zoom(zoom), nhom_list or None,
    )
    if error_response:
        return None, error_response

    return _as_feature_collection(result), None


def list_xa():
    result, error_response = parcel_repository.list_xa_phuong()
    if error_response:
        return None, error_response

    rows = result if isinstance(result, list) else []
    items = [
        {"ma_xa": row.get("ma_xa"), "ten_xa": row.get("ten_xa")}
        for row in rows
        if row.get("ma_xa")
    ]
    return {"items": items}, None


def search():
    ma_xa = request.args.get("ma_xa", "").strip()
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã xã"}), 400)

    nhom_list = read_nhom_list()

    so_to, error_response = read_optional_int("so_to")
    if error_response:
        return None, error_response

    so_thua, error_response = read_optional_int("so_thua")
    if error_response:
        return None, error_response

    requested_limit, page_offset, error_response = _read_paging()
    if error_response:
        return None, error_response

    ten_thon = request.args.get("ten_thon", "").strip() or None

    result, error_response = parcel_repository.search(
        ma_xa, nhom_list or None, so_to, so_thua, requested_limit, page_offset, 0, ten_thon
    )
    if error_response:
        return None, error_response

    return _as_feature_collection(result), None
