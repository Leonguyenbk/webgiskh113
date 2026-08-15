from __future__ import annotations

from flask import jsonify

from . import supabase_client

# Biểu Nhóm 4 KHÔNG có bảng riêng — ghi thẳng vào public.du_lieu_gcn sẵn có
# (cùng cấu trúc chủ sử dụng/GCN/thửa/loại đất), đánh dấu nguồn bằng
# ma_nguon='NHOM4_FORM' để phân biệt với dữ liệu đồng bộ từ Google Sheet.
# Nhờ vậy get_parcels_in_view/search_parcels/gcn_thu_thap_theo_xa (đều
# query public.du_lieu_gcn) tự động tính luôn dữ liệu nhập từ đây.
GCN_TABLE = "du_lieu_gcn"
NHOM4_MA_NGUON = "NHOM4_FORM"
NHOM4_TEN_NGUON = "Biểu Nhóm 4 (nhập trực tiếp)"


def _json_or_error(response, error_response):
    if error_response:
        return None, error_response
    if not response.ok:
        return None, (jsonify({"error": response.text}), response.status_code)
    return response.json(), None


def list_existing_keys(ma_xa: str) -> tuple[set[str] | None, tuple | None]:
    response, error_response = supabase_client.rest_request(
        "GET",
        GCN_TABLE,
        params={"select": "madvhc_soto_sothua", "madvhc": f"eq.{ma_xa}"},
    )
    rows, error_response = _json_or_error(response, error_response)
    if error_response:
        return None, error_response

    keys = {row["madvhc_soto_sothua"] for row in rows if row.get("madvhc_soto_sothua")}
    return keys, None


def exists_key(key: str):
    response, error_response = supabase_client.rest_request(
        "GET",
        GCN_TABLE,
        params={"select": "id", "madvhc_soto_sothua": f"eq.{key}", "limit": 1},
    )
    rows, error_response = _json_or_error(response, error_response)
    if error_response:
        return None, error_response
    return bool(rows), None


def insert_rows(rows: list[dict]):
    response, error_response = supabase_client.rest_request(
        "POST",
        GCN_TABLE,
        json_body=rows,
        extra_headers={"Content-Type": "application/json", "Prefer": "return=minimal"},
    )
    if error_response:
        return None, error_response
    if not response.ok:
        return None, (jsonify({"error": response.text}), response.status_code)
    return True, None
