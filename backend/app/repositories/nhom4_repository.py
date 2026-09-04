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
THUA_DAT_TABLE = "thua_dat"
NHOM4_MA_NGUON = "NHOM4_FORM"
NHOM4_TEN_NGUON = "Biểu Nhóm 4 (nhập trực tiếp)"


def _json_or_error(response, error_response):
    if error_response:
        return None, error_response
    if not response.ok:
        return None, (jsonify({"error": response.text}), response.status_code)
    return response.json(), None


def filter_existing_keys(keys: list[str]) -> tuple[set[str] | None, tuple | None]:
    """Trả về tập các khóa (madvhc_soto_sothua) ĐÃ CÓ ít nhất 1 bản ghi
    trong public.du_lieu_gcn.

    Đây là NGUỒN DUY NHẤT để xác định thửa đã có dữ liệu GCN (hiển thị màu
    xanh trên WebGIS, chặn nộp lại biểu Nhóm 4). Chỉ cần EXISTS 1 bản ghi
    cùng khóa là coi cả thửa đã có dữ liệu — 1 thửa có thể có nhiều dòng
    (nhiều chủ sử dụng/đồng sử dụng), không đặt UNIQUE trên khóa này.

    Query trực tiếp theo danh sách khóa cần kiểm (in.(...)) thay vì tải hết
    khóa của cả xã — nhẹ hơn và dùng lại được ngay trước khi INSERT."""
    unique_keys = sorted({k for k in keys if k})
    if not unique_keys:
        return set(), None

    in_list = ",".join(f'"{k}"' for k in unique_keys)
    response, error_response = supabase_client.rest_request(
        "GET",
        GCN_TABLE,
        params={"select": "madvhc_soto_sothua", "madvhc_soto_sothua": f"in.({in_list})"},
    )
    rows, error_response = _json_or_error(response, error_response)
    if error_response:
        return None, error_response

    return {row["madvhc_soto_sothua"] for row in rows if row.get("madvhc_soto_sothua")}, None


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


def exists_in_thua_dat(ma_xa: str, so_to: int, so_thua: int):
    """Thửa có thật trong public.thua_dat (đã nhập GML) không — biểu Nhóm 4
    chỉ nhận thửa CÓ THẬT trên bản đồ, tránh nộp nhầm số tờ/số thửa không
    tồn tại (dong_bo_du_lieu/du_lieu_gcn không tự phát hiện được lỗi này vì
    2 bảng đó không bắt buộc khớp với thua_dat)."""
    response, error_response = supabase_client.rest_request(
        "GET",
        THUA_DAT_TABLE,
        params={
            "select": "id",
            "ma_xa": f"eq.{ma_xa}",
            "so_to": f"eq.{so_to}",
            "so_thua": f"eq.{so_thua}",
            "limit": 1,
        },
    )
    rows, error_response = _json_or_error(response, error_response)
    if error_response:
        return None, error_response
    return bool(rows), None


def _thua_by_to(keys: list[tuple[int, int]]) -> dict[int, list[int]]:
    thua_by_to: dict[int, set[int]] = {}
    for so_to, so_thua in keys:
        thua_by_to.setdefault(so_to, set()).add(so_thua)
    return {so_to: sorted(thua_set) for so_to, thua_set in thua_by_to.items()}


def existing_thua_dat_keys(
    ma_xa: str, keys: list[tuple[int, int]]
) -> tuple[set[tuple[int, int]] | None, tuple | None]:
    """Trong các cặp (so_to, so_thua) truyền vào, cặp nào CÓ THẬT trong
    public.thua_dat (đã nhập GML) — dùng kiểm tra hàng loạt lúc nộp biểu
    Nhóm 4 (nhiều thửa/lần nộp), tránh gọi exists_in_thua_dat() lặp lại
    từng thửa.

    Hỏi ĐÍCH DANH theo từng số tờ (so_to=eq.X & so_thua=in.(các thửa của
    tờ đó trong lô)) thay vì tải toàn bộ thửa của xã/của tờ. Lý do: Supabase
    cắt cứng 1000 dòng/request. Xã đông thửa, hoặc lô nộp trải nhiều tờ, vẫn
    vượt 1000 -> thửa có thật bị rớt khỏi kết quả -> submit_ho_so() báo nhầm
    404 "không tồn tại trong dữ liệu thửa đất", dù ô kiểm tra realtime
    (exists_in_thua_dat, query đích danh) vẫn báo hợp lệ. Hỏi đúng các thửa
    đang nộp thì mỗi request chỉ trả tối đa số thửa của 1 tờ trong lô —
    không bao giờ chạm trần 1000."""
    found: set[tuple[int, int]] = set()
    for so_to, thua_list in _thua_by_to(keys).items():
        in_list = ",".join(str(v) for v in thua_list)
        response, error_response = supabase_client.rest_request(
            "GET",
            THUA_DAT_TABLE,
            params={
                "select": "so_to,so_thua",
                "ma_xa": f"eq.{ma_xa}",
                "so_to": f"eq.{so_to}",
                "so_thua": f"in.({in_list})",
            },
        )
        rows, error_response = _json_or_error(response, error_response)
        if error_response:
            return None, error_response
        found.update((row["so_to"], row["so_thua"]) for row in rows)
    return found, None


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


def phan_loai_for_keys(
    ma_xa: str, keys: list[tuple[int, int]]
) -> tuple[dict[tuple[int, int], str] | None, tuple | None]:
    """phan_loai_ke_hoach_2959 của ĐÚNG các cặp (so_to, so_thua) đang nộp,
    lấy từ dong_bo_du_lieu theo từng số tờ (so_to=eq.X & so_thua=in.(...)).
    Cùng lý do với existing_thua_dat_keys: tải cả xã/cả tờ có thể vượt trần
    1000 dòng của Supabase, khiến chốt chặn Nhóm 1/2 bỏ sót thửa nằm ngoài
    1000 dòng đầu."""
    out: dict[tuple[int, int], str] = {}
    for so_to, thua_list in _thua_by_to(keys).items():
        in_list = ",".join(str(v) for v in thua_list)
        response, error_response = supabase_client.rest_request(
            "GET",
            DONG_BO_TABLE,
            params={
                "select": "so_to,so_thua,phan_loai_ke_hoach_2959",
                "ma_xa": f"eq.{ma_xa}",
                "so_to": f"eq.{so_to}",
                "so_thua": f"in.({in_list})",
            },
        )
        rows, error_response = _json_or_error(response, error_response)
        if error_response:
            return None, error_response
        out.update(
            ((row["so_to"], row["so_thua"]), row.get("phan_loai_ke_hoach_2959"))
            for row in rows
        )
    return out, None


def get_dia_chi_thua_dat(ma_xa: str, so_to: int, so_thua: int):
    """Địa chỉ thửa đất tự sinh cho biểu Nhóm 4 — RPC get_dia_chi_thua_dat
    (xem supabase/schema.sql). Trả về chuỗi "Thôn ..., Xã ..., tỉnh Đắk Lắk"
    nếu xã có ranh thôn và tâm thửa rơi vào 1 thôn, ngược lại "Xã ..., tỉnh
    Đắk Lắk". None nếu không tìm được tên xã."""
    data, error_response = supabase_client.call_rpc(
        "get_dia_chi_thua_dat",
        {"p_ma_xa": ma_xa, "p_so_to": so_to, "p_so_thua": so_thua},
        timeout=20,
    )
    if error_response:
        return None, error_response
    return data, None


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
