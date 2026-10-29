from __future__ import annotations

import requests
from flask import current_app, jsonify

import gml_reader
import shapefile_reader
from sync_reader import parse_sync_file
from ..repositories import ranh_thon_repository, supabase_client


def _refresh_ranh_gioi_thon_cache(ma_xa_list) -> str | None:
    """Tính lại public.ranh_gioi_thon_cache cho từng xã vừa ghi (xem
    supabase/schema.sql, refresh_ranh_gioi_thon_cache) rồi xoá cache RAM ở
    backend (ranh_thon_repository) — để get_ranh_gioi_thon() thấy dữ liệu
    mới NGAY, không đợi hết TTL. Chủ động gọi ở đây (sau khi ghi xong) thay
    vì trigger DB, vì đây là 2 đường ghi ranh_gioi_thon DUY NHẤT trong toàn
    dự án (grep xác nhận) — dễ theo dõi hơn trigger.

    Lỗi refresh KHÔNG làm hỏng response import/xoá (dữ liệu đã ghi thành
    công) — chỉ log cảnh báo và trả lại cho caller để đính kèm vào response,
    admin biết mà tự chạy lại `select public.refresh_ranh_gioi_thon_cache(
    '<ma_xa>');` nếu cần."""
    warnings = []
    for ma_xa in ma_xa_list:
        _, error_response = supabase_client.call_rpc(
            "refresh_ranh_gioi_thon_cache", {"p_ma_xa": ma_xa}, timeout=30
        )
        if error_response:
            current_app.logger.warning(
                "refresh_ranh_gioi_thon_cache lỗi cho xã %s (dữ liệu ranh_gioi_thon "
                "đã ghi thành công, chỉ cache bị cũ tạm thời)",
                ma_xa,
            )
            warnings.append(ma_xa)
        ranh_thon_repository.invalidate(ma_xa)
    return (
        f"Không làm mới được cache hiển thị cho xã: {', '.join(warnings)} — "
        "dữ liệu đã lưu, bản đồ có thể vẫn hiện thôn cũ tạm thời."
        if warnings
        else None
    )


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


def import_ranh_thon(file_stream, filename: str = ""):
    base_url = supabase_client.get_base_url()
    if not base_url:
        return None, supabase_client.missing_base_url_response()

    # Nhận cả Shapefile (.zip) như trước lẫn GML (.gml/.xml) — 2 định dạng
    # cho ra cùng hình dạng dòng {"ma_xa","ten_thon","geom"} nên phần đồng
    # bộ/upsert phía dưới dùng chung, chỉ khác bước đọc file.
    la_gml = filename.lower().endswith((".gml", ".xml"))
    try:
        if la_gml:
            rows = list(gml_reader.iter_rows_ranh_thon(file_stream))
        else:
            rows = list(shapefile_reader.iter_rows(file_stream))
    except Exception as exc:  # noqa: BLE001 - lỗi parse file người dùng tải lên, phải báo rõ nguyên nhân
        nguon = "GML" if la_gml else "Shapefile"
        return None, (jsonify({"error": f"Không đọc được file {nguon}: {exc}"}), 400)

    if not rows:
        nguon = "GML" if la_gml else "Shapefile"
        return None, (jsonify({"error": f"File {nguon} không có ranh thôn hợp lệ"}), 400)

    # Nhiều vùng cùng (mã xã, tên thôn) — 1 thôn vẽ thành nhiều mảnh — gộp
    # thành 1 MultiPolygon. Trước đây upsert chỉ giữ vùng xuất hiện sau
    # cùng nên mất các mảnh còn lại ("Đã nhập 14/16 thôn").
    so_vung = len(rows)
    gop: dict[tuple[str, str], dict] = {}
    so_manh: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["ma_xa"], row["ten_thon"])
        if key in gop:
            gop[key]["geom"]["coordinates"].extend(row["geom"]["coordinates"])
            so_manh[key] += 1
        else:
            gop[key] = row
            so_manh[key] = 1
    rows = list(gop.values())
    thon_gop = [
        {"ma_xa": ma_xa, "ten_thon": ten_thon, "so_vung": n}
        for (ma_xa, ten_thon), n in so_manh.items()
        if n > 1
    ]

    # Chỉ thêm mới/cập nhật hình học theo (mã xã, tên thôn), KHÔNG xóa thôn
    # không có trong file: sau sáp nhập 1 xã mới nhập ranh thôn cũ theo từng
    # xã cũ (mỗi xã cũ 1 file), trước đây file sau xóa sạch thôn của file
    # trước. Cần làm lại cả xã thì dùng "Xóa ranh thôn của xã" rồi nhập lại.
    thon_by_xa: dict[str, list[str]] = {}
    for row in rows:
        thon_by_xa.setdefault(row["ma_xa"], []).append(row["ten_thon"])

    deleted = 0

    try:
        imported = supabase_client.upsert_to_supabase(
            "ranh_gioi_thon", "ma_xa,ten_thon", "merge-duplicates", rows
        )
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)
    except requests.RequestException as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return None, (jsonify({"error": detail, "total": len(rows)}), 502)

    cache_warning = _refresh_ranh_gioi_thon_cache(thon_by_xa.keys())

    result = {
        "ok": True,
        "total": len(rows),
        "imported": imported,
        "so_vung": so_vung,
        "thon_gop": thon_gop,
        "deleted": deleted,
        "xa": list(thon_by_xa.keys()),
    }
    if cache_warning:
        result["cache_warning"] = cache_warning
    return result, None


def delete_ranh_thon(ma_xa: str):
    """Xóa toàn bộ ranh giới thôn của 1 xã khỏi public.ranh_gioi_thon.
    Trả về danh sách tên thôn đã xóa để hiển thị lại cho người dùng."""
    ma_xa = (ma_xa or "").strip()
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã xã cần xóa"}), 400)

    # PostgREST DELETE + Prefer: return=representation để đếm/liệt kê thôn đã
    # xóa; chỉ lấy cột ten_thon (bỏ geom cho nhẹ). Không cần RPC riêng.
    response, error_response = supabase_client.rest_request(
        "DELETE",
        "ranh_gioi_thon",
        params={"ma_xa": f"eq.{ma_xa}", "select": "ten_thon"},
        extra_headers={"Prefer": "return=representation"},
        timeout=30,
    )
    if error_response:
        return None, error_response

    if not response.ok:
        try:
            detail = response.json()
            message = detail.get("message") or detail.get("error") or response.text
        except ValueError:
            message = response.text or "Supabase trả về lỗi không rõ nguyên nhân"
        return None, (jsonify({"error": message}), 502)

    try:
        deleted_rows = response.json()
    except ValueError:
        deleted_rows = []
    if not isinstance(deleted_rows, list):
        deleted_rows = []

    ten_thon = sorted(
        {str(row.get("ten_thon") or "").strip() for row in deleted_rows if row.get("ten_thon")}
    )

    cache_warning = _refresh_ranh_gioi_thon_cache([ma_xa])

    result = {
        "ok": True,
        "ma_xa": ma_xa,
        "deleted": len(deleted_rows),
        "ten_thon": ten_thon,
    }
    if cache_warning:
        result["cache_warning"] = cache_warning
    return result, None


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
