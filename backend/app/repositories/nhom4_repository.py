from __future__ import annotations

from flask import jsonify

from . import supabase_client

# Biểu Nhóm 4 KHÔNG có bảng riêng — ghi thẳng vào public.du_lieu_gcn sẵn có
# (cùng cấu trúc chủ sử dụng/GCN/thửa/loại đất), đánh dấu nguồn bằng
# ma_nguon='NHOM4_FORM' để phân biệt với dữ liệu đồng bộ từ Google Sheet.
# Nhờ vậy get_parcels_in_view/search_parcels/gcn_thu_thap_theo_xa (đều
# query public.du_lieu_gcn) tự động tính luôn dữ liệu nhập từ đây.
GCN_TABLE = "du_lieu_gcn"
DONG_BO_TABLE = "dong_bo_du_lieu"
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


def get_phan_loai(ma_xa: str, so_to: int, so_thua: int):
    """Đọc phan_loai_ke_hoach_2959 (Nhóm 1/Nhóm 2/...) của 1 thửa từ
    dong_bo_du_lieu — dùng để chặn nhập biểu Nhóm 4 cho thửa đã thuộc
    Nhóm 1/2 (coi như đã có dữ liệu từ trước, giống quy ước đã dùng ở
    gcn_thu_thap_theo_xa)."""
    response, error_response = supabase_client.rest_request(
        "GET",
        DONG_BO_TABLE,
        params={
            "select": "phan_loai_ke_hoach_2959",
            "ma_xa": f"eq.{ma_xa}",
            "so_to": f"eq.{so_to}",
            "so_thua": f"eq.{so_thua}",
            "limit": 1,
        },
    )
    rows, error_response = _json_or_error(response, error_response)
    if error_response:
        return None, error_response
    return (rows[0].get("phan_loai_ke_hoach_2959") if rows else None), None


def list_phan_loai_by_xa(ma_xa: str) -> tuple[dict[tuple[int, int], str] | None, tuple | None]:
    response, error_response = supabase_client.rest_request(
        "GET",
        DONG_BO_TABLE,
        params={"select": "so_to,so_thua,phan_loai_ke_hoach_2959", "ma_xa": f"eq.{ma_xa}"},
    )
    rows, error_response = _json_or_error(response, error_response)
    if error_response:
        return None, error_response
    return {(row["so_to"], row["so_thua"]): row.get("phan_loai_ke_hoach_2959") for row in rows}, None


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


def claim_keys(keys: list[str]):
    """Giữ chỗ nguyên tử cho danh sách khóa (madvhc_soto_sothua) TRƯỚC KHI
    insert_rows() — xem giải thích đầy đủ trong sync_gcn/create_du_lieu_gcn.sql
    (bảng nhom4_thua_da_nop + RPC nhom4_claim_keys). Trả lỗi 409 nếu có
    khóa nào đã bị request khác giữ chỗ trước (race 2 request nộp cùng lúc
    1 thửa)."""
    if not keys:
        return True, None
    _, error_response = supabase_client.call_rpc("nhom4_claim_keys", {"p_keys": keys})
    if error_response:
        body, _status = error_response
        return None, (body, 409)
    return True, None


def release_keys(keys: list[str]) -> None:
    """Bỏ giữ chỗ (dùng khi claim_keys() thành công nhưng insert_rows() sau
    đó lại lỗi vì lý do khác — tránh khóa vĩnh viễn 1 thửa không có dữ liệu
    thật nào được ghi). Best-effort, không chặn luồng nếu tự nó lỗi."""
    if not keys:
        return
    supabase_client.rest_request(
        "DELETE",
        "nhom4_thua_da_nop",
        params={"khoa": f"in.({','.join(keys)})"},
    )


def update_file_info_by_submission(submission_id: str, file_info: dict):
    """Cập nhật các cột file_*/tenfilequet SAU KHI upload Drive nền hoàn
    tất (xem nhom4_service._upload_files_background) — insert_rows() ghi
    các cột này rỗng trước để trả lời người nộp ngay, không chờ Drive."""
    ten_file_quet = ", ".join(
        name for name in (file_info.get("chinh_name"), file_info.get("phu_name")) if name
    )
    patch = {
        "file_chinh_drive_id": file_info.get("chinh_id"),
        "file_chinh_ten_file": file_info.get("chinh_name"),
        "file_phu_drive_id": file_info.get("phu_id"),
        "file_phu_ten_file": file_info.get("phu_name"),
        "tenfilequet": ten_file_quet or None,
    }
    response, error_response = supabase_client.rest_request(
        "PATCH",
        GCN_TABLE,
        params={"submission_id": f"eq.{submission_id}"},
        json_body=patch,
        extra_headers={"Content-Type": "application/json", "Prefer": "return=minimal"},
    )
    if error_response:
        return None, error_response
    if not response.ok:
        return None, (jsonify({"error": response.text}), response.status_code)
    return True, None
