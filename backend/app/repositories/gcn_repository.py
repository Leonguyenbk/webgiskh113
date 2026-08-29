from __future__ import annotations

from flask import jsonify

from . import supabase_client

NGUON_GCN_TABLE = "nguon_gcn"


def _json_or_error(response, error_response):
    if error_response:
        return None, error_response
    if not response.ok:
        return None, (jsonify({"error": response.text}), response.status_code)
    return response.json(), None


def gcn_thu_thap_theo_xa():
    # Hàm SQL giờ CHỈ đọc bảng cache gcn_thu_thap_theo_xa_cache (vài mili
    # giây) — phần quét nặng đã tách sang refresh_gcn_thu_thap_theo_xa_cache
    # (xem supabase/schema.sql). Không cần timeout HTTP dài như trước.
    return supabase_client.call_rpc("gcn_thu_thap_theo_xa", {}, timeout=15)


def refresh_gcn_thu_thap_theo_xa_cache():
    # Nhánh chậm: quét toàn bộ thua_dat để tính lại cache. Gọi từ cron
    # (pg_cron hoặc Render Cron qua POST /api/gcn-stats/refresh), KHÔNG
    # bao giờ từ request người dùng. Hàm SQL nới statement_timeout 120s
    # nên timeout HTTP ở đây phải lớn hơn.
    return supabase_client.call_rpc(
        "refresh_gcn_thu_thap_theo_xa_cache", {}, timeout=180
    )


def export_gcn_theo_nhom(ma_xa: str, nhom: list[str]):
    # Join du_lieu_gcn x dong_bo_du_lieu, lọc các thửa của xã đã thu thập
    # GCN và thuộc nhóm KH 2959 chỉ định. Trả nguyên dòng du_lieu_gcn.
    return supabase_client.call_rpc(
        "export_gcn_theo_nhom",
        {"p_ma_xa": ma_xa, "p_nhom": nhom},
        timeout=60,
    )


def list_nguon():
    response, error_response = supabase_client.rest_request(
        "GET", NGUON_GCN_TABLE, params={"select": "*", "order": "ma_nguon.asc"}
    )
    return _json_or_error(response, error_response)


def create_nguon(payload: dict):
    response, error_response = supabase_client.rest_request(
        "POST",
        NGUON_GCN_TABLE,
        json_body=payload,
        extra_headers={"Content-Type": "application/json", "Prefer": "return=representation"},
    )
    return _json_or_error(response, error_response)


def update_nguon(ma_nguon: str, updates: dict):
    response, error_response = supabase_client.rest_request(
        "PATCH",
        NGUON_GCN_TABLE,
        params={"ma_nguon": f"eq.{ma_nguon}"},
        json_body=updates,
        extra_headers={"Content-Type": "application/json", "Prefer": "return=representation"},
    )
    return _json_or_error(response, error_response)


def delete_nguon(ma_nguon: str):
    response, error_response = supabase_client.rest_request(
        "DELETE", NGUON_GCN_TABLE, params={"ma_nguon": f"eq.{ma_nguon}"}
    )
    if error_response:
        return None, error_response
    if not response.ok:
        return None, (jsonify({"error": response.text}), response.status_code)
    return True, None


def fetch_nguon_row(ma_nguon: str):
    response, error_response = supabase_client.rest_request(
        "GET", NGUON_GCN_TABLE, params={"select": "*", "ma_nguon": f"eq.{ma_nguon}"}
    )
    if error_response:
        return None, error_response
    response.raise_for_status()
    items = response.json()
    return (items[0] if items else None), None


def list_active_sources():
    response, error_response = supabase_client.rest_request(
        "GET",
        NGUON_GCN_TABLE,
        params={"select": "*", "kich_hoat": "eq.true", "order": "ma_nguon.asc"},
    )
    if error_response:
        return None, error_response
    response.raise_for_status()
    return response.json(), None
