from __future__ import annotations

from datetime import datetime, timezone

import requests
from flask import current_app, jsonify

import gcn_sync
from ..repositories import gcn_repository, supabase_client


def get_stats():
    result, error_response = gcn_repository.gcn_thu_thap_theo_xa()
    if error_response:
        return None, error_response

    rows = result if isinstance(result, list) else []
    items = []
    as_of = None
    for row in rows:
        ma_xa = row.get("ma_xa")
        if not ma_xa:
            continue
        tong = int(row.get("tong_so_thua") or 0)
        da_nhap = int(row.get("da_nhap_bieu") or 0)
        computed_at = row.get("computed_at")
        if computed_at and (as_of is None or computed_at > as_of):
            as_of = computed_at
        items.append(
            {
                "ma_xa": ma_xa,
                "tong_so_thua": tong,
                "da_nhap_bieu": da_nhap,
                "chua_nhap_bieu": max(tong - da_nhap, 0),
            }
        )
    return {"items": items, "as_of": as_of}, None


def refresh_stats_cache():
    result, error_response = gcn_repository.refresh_gcn_thu_thap_theo_xa_cache()
    if error_response:
        return None, error_response
    # Hàm SQL trả về số dòng đã ghi vào cache (PostgREST bọc trong scalar).
    rows = result if isinstance(result, int) else None
    return {"ok": True, "rows": rows}, None


def list_sources():
    result, error_response = gcn_repository.list_nguon()
    if error_response:
        return None, error_response
    return {"items": result}, None


def create_source(body: dict):
    ma_nguon = str(body.get("ma_nguon", "")).strip()
    ten_nguon = str(body.get("ten_nguon", "")).strip()
    url = str(body.get("url", "")).strip()
    kich_hoat = bool(body.get("kich_hoat", True))

    if not ma_nguon or not url:
        return None, (jsonify({"error": "Thiếu ma_nguon hoặc url"}), 400)

    payload = {"ma_nguon": ma_nguon, "ten_nguon": ten_nguon, "url": url, "kich_hoat": kich_hoat}
    result, error_response = gcn_repository.create_nguon(payload)
    if error_response:
        return None, error_response
    items = result
    return {"ok": True, "item": items[0] if items else payload}, None


def update_source(ma_nguon: str, body: dict):
    updates: dict = {}
    if "ten_nguon" in body:
        updates["ten_nguon"] = str(body["ten_nguon"]).strip()
    if "url" in body:
        updates["url"] = str(body["url"]).strip()
    if "kich_hoat" in body:
        updates["kich_hoat"] = bool(body["kich_hoat"])

    if not updates:
        return None, (jsonify({"error": "Không có trường nào để cập nhật"}), 400)

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    result, error_response = gcn_repository.update_nguon(ma_nguon, updates)
    if error_response:
        return None, error_response
    if not result:
        return None, (jsonify({"error": "Không tìm thấy nguồn"}), 404)
    return {"ok": True, "item": result[0]}, None


def delete_source(ma_nguon: str):
    _, error_response = gcn_repository.delete_nguon(ma_nguon)
    if error_response:
        return None, error_response
    return {"ok": True}, None


def _get_supabase_context():
    base_url = supabase_client.get_base_url()
    if not base_url:
        return None, None, supabase_client.missing_base_url_response()
    try:
        headers = supabase_client.get_service_headers()
    except RuntimeError as exc:
        return None, None, (jsonify({"error": str(exc)}), 500)
    return base_url, headers, None


def sync_one(ma_nguon: str):
    base_url, headers, error_response = _get_supabase_context()
    if error_response:
        return None, error_response

    try:
        source, error_response = gcn_repository.fetch_nguon_row(ma_nguon)
    except requests.RequestException as exc:
        return None, (jsonify({"error": str(exc)}), 502)
    if error_response:
        return None, error_response
    if not source:
        return None, (jsonify({"error": "Không tìm thấy nguồn"}), 404)
    if not source.get("url"):
        return None, (jsonify({"error": "Nguồn chưa có URL"}), 400)

    try:
        imported = gcn_sync.sync_source(
            base_url, headers, ma_nguon, source.get("ten_nguon") or "", source["url"]
        )
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)
    except Exception as exc:  # noqa: BLE001 - lỗi đọc Sheet (sai URL/chưa share/sai tên trang tính...) phải báo rõ
        current_app.logger.exception("Đồng bộ GCN lỗi: ma_nguon=%s", ma_nguon)
        return None, (jsonify({"error": f"Đồng bộ thất bại: {exc}"}), 502)

    return {"ok": True, "ma_nguon": ma_nguon, "imported": imported}, None


def sync_all():
    base_url, headers, error_response = _get_supabase_context()
    if error_response:
        return None, error_response

    try:
        sources, error_response = gcn_repository.list_active_sources()
    except requests.RequestException as exc:
        return None, (jsonify({"error": str(exc)}), 502)
    if error_response:
        return None, error_response

    results = []
    for source in sources:
        ma_nguon = source.get("ma_nguon")
        url = source.get("url")
        if not ma_nguon or not url:
            continue

        try:
            imported = gcn_sync.sync_source(
                base_url, headers, ma_nguon, source.get("ten_nguon") or "", url
            )
        except Exception as exc:  # noqa: BLE001 - 1 nguồn lỗi không được chặn các nguồn khác
            current_app.logger.exception("Đồng bộ GCN lỗi: ma_nguon=%s", ma_nguon)
            results.append({"ma_nguon": ma_nguon, "ok": False, "error": str(exc)})
        else:
            results.append({"ma_nguon": ma_nguon, "ok": True, "imported": imported})

    return {"ok": True, "results": results}, None
