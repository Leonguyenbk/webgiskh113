from __future__ import annotations

import requests
from flask import jsonify

import gml_reader
import shapefile_reader
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

    # Nhập lại GML cùng 1 xã = ĐỒNG BỘ theo xã đó, không chỉ thêm dòng mới:
    # thửa cũ có thể đã bị tách thành nhiều thửa mới trong file mới, nên
    # thửa nào không còn xuất hiện trong file phải bị xóa; thửa còn giữ
    # lại thì cập nhật thông tin/hình học mới nhất (upsert, không còn bỏ
    # qua trùng như trước). Gom theo xã vì mỗi lần nhập chỉ nên đụng tới
    # đúng những xã có mặt trong file, không ảnh hưởng xã khác.
    keys_by_xa: dict[str, list[str]] = {}
    for row in rows:
        keys_by_xa.setdefault(row["ma_xa"], []).append(f"{row['so_to']}_{row['so_thua']}")

    deleted = 0
    try:
        for ma_xa, keep_keys in keys_by_xa.items():
            count, error_response = supabase_client.call_rpc(
                "delete_thua_dat_not_in", {"p_ma_xa": ma_xa, "p_keep_keys": keep_keys}, timeout=60
            )
            if error_response:
                return None, error_response
            deleted += int(count or 0)
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)

    try:
        imported, error_response = supabase_client.upsert_thua_dat_diff(rows)
        if error_response:
            return None, error_response
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)

    return {
        "ok": True,
        "total": len(rows),
        "imported": imported,
        "deleted": deleted,
        "xa": list(keys_by_xa.keys()),
    }, None


def import_ranh_thon(file_stream):
    base_url = supabase_client.get_base_url()
    if not base_url:
        return None, supabase_client.missing_base_url_response()

    try:
        rows = list(shapefile_reader.iter_rows(file_stream))
    except Exception as exc:  # noqa: BLE001 - lỗi parse file người dùng tải lên, phải báo rõ nguyên nhân
        return None, (jsonify({"error": f"Không đọc được file Shapefile: {exc}"}), 400)

    if not rows:
        return None, (jsonify({"error": "File Shapefile không có ranh thôn hợp lệ"}), 400)

    # Đồng bộ theo xã giống import_gml: thôn không còn trong file mới (đổi
    # tên/vẽ lại/gộp) bị xóa, thôn còn lại thì thêm mới/cập nhật hình học.
    thon_by_xa: dict[str, list[str]] = {}
    for row in rows:
        thon_by_xa.setdefault(row["ma_xa"], []).append(row["ten_thon"])

    deleted = 0
    try:
        for ma_xa, keep_thon in thon_by_xa.items():
            count, error_response = supabase_client.call_rpc(
                "delete_ranh_gioi_thon_not_in", {"p_ma_xa": ma_xa, "p_keep_thon": keep_thon}, timeout=60
            )
            if error_response:
                return None, error_response
            deleted += int(count or 0)
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)

    try:
        imported = supabase_client.upsert_to_supabase(
            "ranh_gioi_thon", "ma_xa,ten_thon", "merge-duplicates", rows
        )
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)
    except requests.RequestException as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return None, (jsonify({"error": detail, "total": len(rows)}), 502)

    return {
        "ok": True,
        "total": len(rows),
        "imported": imported,
        "deleted": deleted,
        "xa": list(thon_by_xa.keys()),
    }, None


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
