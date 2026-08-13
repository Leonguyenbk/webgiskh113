from __future__ import annotations

import requests
from flask import jsonify

import gml_reader
from sync_reader import parse_sync_file
from ..repositories import supabase_client


def import_gml(file_stream):
    base_url = supabase_client.get_base_url()
    if not base_url:
        return None, supabase_client.missing_base_url_response()

    try:
        # Đọc thẳng từ stream upload (không .read() cả file vào bytes)
        # và parse GML kiểu streaming để tránh hết bộ nhớ với file lớn.
        rows = list(gml_reader.iter_rows(file_stream))
    except Exception as exc:  # noqa: BLE001 - lỗi parse file người dùng tải lên, phải báo rõ nguyên nhân
        return None, (jsonify({"error": f"Không đọc được file GML: {exc}"}), 400)

    if not rows:
        return None, (jsonify({"error": "File GML không có thửa đất hợp lệ"}), 400)

    try:
        imported = supabase_client.upsert_to_supabase(
            "thua_dat", "ma_xa,so_to,so_thua", "ignore-duplicates", rows
        )
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)
    except requests.RequestException as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return None, (jsonify({"error": detail, "total": len(rows)}), 502)

    return {"ok": True, "total": len(rows), "imported": imported}, None


def import_dong_bo(filename: str, data: bytes):
    base_url = supabase_client.get_base_url()
    if not base_url:
        return None, supabase_client.missing_base_url_response()

    try:
        rows = parse_sync_file(filename, data)
    except Exception as exc:  # noqa: BLE001 - lỗi parse file người dùng tải lên, phải báo rõ nguyên nhân
        return None, (jsonify({"error": f"Không đọc được file: {exc}"}), 400)

    if not rows:
        return None, (jsonify({"error": "File không có dòng dữ liệu hợp lệ"}), 400)

    try:
        imported = supabase_client.upsert_to_supabase(
            "dong_bo_du_lieu", "ma_xa,so_to,so_thua", "merge-duplicates", rows
        )
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)
    except requests.RequestException as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return None, (jsonify({"error": detail, "total": len(rows)}), 502)

    return {"ok": True, "total": len(rows), "imported": imported}, None
