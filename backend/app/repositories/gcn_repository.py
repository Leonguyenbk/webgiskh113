from __future__ import annotations

from flask import jsonify

from . import supabase_client
from .nhom4_repository import NHOM4_MA_NGUON

NGUON_GCN_TABLE = "nguon_gcn"
DU_LIEU_GCN_TABLE = "du_lieu_gcn"


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


def export_gcn_theo_nhom_page(ma_xa: str, nhom: list[str], limit: int, offset: int):
    # 1 trang: join du_lieu_gcn x dong_bo_du_lieu, lọc thửa đã thu thập GCN
    # thuộc nhóm KH 2959. RPC trả jsonb (mảng object) — không bị PostgREST
    # cắt 1000 dòng. Hàm SQL đặt statement_timeout 60s.
    return supabase_client.call_rpc(
        "export_gcn_theo_nhom",
        {"p_ma_xa": ma_xa, "p_nhom": nhom, "p_limit": limit, "p_offset": offset},
        timeout=90,
    )


def export_du_lieu_gcn_page(ma_xa: str, chi_nhom3: bool, limit: int, offset: int):
    # 1 trang: LEFT JOIN du_lieu_gcn x dong_bo_du_lieu (khác
    # export_gcn_theo_nhom_page: không loại thửa chưa có dòng đồng bộ).
    # p_chi_nhom3=true lọc còn thửa chưa thuộc Nhóm 1/Nhóm 2 (KH 2959).
    return supabase_client.call_rpc(
        "export_du_lieu_gcn",
        {"p_ma_xa": ma_xa, "p_chi_nhom3": chi_nhom3, "p_limit": limit, "p_offset": offset},
        timeout=90,
    )


def list_da_nhap(
    ma_xa: str, sort_asc: bool, limit: int, offset: int, so_to: str | None, so_thua: str | None
):
    # 1 trang danh sách du_lieu_gcn theo xã (trang "Danh sách thửa đã
    # nhập") — xem public.list_du_lieu_gcn_da_nhap trong supabase/schema.sql.
    return supabase_client.call_rpc(
        "list_du_lieu_gcn_da_nhap",
        {
            "p_ma_xa": ma_xa,
            "p_sort_asc": sort_asc,
            "p_limit": limit,
            "p_offset": offset,
            "p_so_to": so_to,
            "p_so_thua": so_thua,
        },
        timeout=20,
    )


def thong_ke_nguon_nhap():
    # Tổng số thửa đã nhập toàn dự án, tách Form (NHOM4_FORM) / nguồn khác
    # — xem public.thong_ke_nguon_nhap trong supabase/schema.sql.
    return supabase_client.call_rpc("thong_ke_nguon_nhap", {}, timeout=25)


def nhom3_tong_hop(to_giam_sat: int | None = None):
    # Tổng hợp danh sách thửa cần thu thập Nhóm 3 (nhom3_can_thu_thap) so
    # với Nhóm 1/2 + đã thu thập — xem public.nhom3_tong_hop. p_to_giam_sat
    # lọc theo Tổ kiểm tra, giám sát (1-4, xem nhom3_to_giam_sat) — None =
    # tất cả.
    return supabase_client.call_rpc(
        "nhom3_tong_hop", {"p_to_giam_sat": to_giam_sat}, timeout=25
    )


def nhom3_list_con_thieu(ma_xa: str | None, limit: int, offset: int, co_nhap: bool | None = None):
    return supabase_client.call_rpc(
        "nhom3_list_con_thieu",
        {"p_ma_xa": ma_xa, "p_limit": limit, "p_offset": offset, "p_co_nhap": co_nhap},
        timeout=25,
    )


def nhom3_list_tong_gui_xa(ma_xa: str | None, limit: int, offset: int):
    # Danh sách "tổng gửi xã" (đã trừ Nhóm 1/2 chưa nhập của Chi nhánh KV)
    # kèm ghi chú trạng thái từng thửa — xem public.nhom3_list_tong_gui_xa.
    return supabase_client.call_rpc(
        "nhom3_list_tong_gui_xa",
        {"p_ma_xa": ma_xa, "p_limit": limit, "p_offset": offset},
        timeout=25,
    )


def nhom3_list_nhom1_chua_nhap(ma_xa: str | None, limit: int, offset: int):
    # Thửa đã thuộc Nhóm 1 (phan_loai_ke_hoach_2959) nhưng CHƯA có dòng
    # du_lieu_gcn nào (co_nhap=false) — nhóm này do Chi nhánh khu vực làm
    # trực tiếp, không qua form Nhóm 4/xã — xem public.nhom3_list_nhom1_chua_nhap.
    return supabase_client.call_rpc(
        "nhom3_list_nhom1_chua_nhap",
        {"p_ma_xa": ma_xa, "p_limit": limit, "p_offset": offset},
        timeout=25,
    )


def nhom3_list_nhom1_da_nhap(ma_xa: str | None, limit: int, offset: int):
    # Đối xứng với nhom3_list_nhom1_chua_nhap — thửa Nhóm 1 ĐÃ có dòng
    # du_lieu_gcn (co_nhap=true), do xã làm — xem public.nhom3_list_nhom1_da_nhap.
    return supabase_client.call_rpc(
        "nhom3_list_nhom1_da_nhap",
        {"p_ma_xa": ma_xa, "p_limit": limit, "p_offset": offset},
        timeout=25,
    )


def nhom3_tien_do_trend(ma_xa: str | None, tu: str | None, den: str | None):
    # Trend tiến độ theo xã (thửa/ngày) — xem public.nhom3_tien_do_trend.
    return supabase_client.call_rpc(
        "nhom3_tien_do_trend", {"p_ma_xa": ma_xa, "p_tu": tu, "p_den": den}, timeout=20
    )


def refresh_nhom3_trang_thai_cache():
    # Nhánh chậm: quét toàn bộ nhom3_can_thu_thap để tính lại cache
    # nhom3_trang_thai_cache. Gọi TAY (POST /api/nhom3-con-thieu/refresh)
    # sau mỗi lần nạp thêm danh sách Nhóm 3 mới — không có cron. Hàm SQL
    # nới statement_timeout 300s nên timeout HTTP ở đây phải lớn hơn.
    return supabase_client.call_rpc(
        "refresh_nhom3_trang_thai_cache", {}, timeout=200
    )


def nhom3_cache_computed_at():
    # Thời điểm tính cache nhom3_trang_thai_cache gần nhất — refresh gán
    # cùng 1 computed_at cho mọi dòng rồi xoá dòng cũ hơn, nên đọc 1 dòng
    # là đủ (không cần sửa hàm SQL nhom3_tong_hop).
    response, error_response = supabase_client.rest_request(
        "GET", "nhom3_trang_thai_cache", params={"select": "computed_at", "limit": 1}
    )
    rows, error_response = _json_or_error(response, error_response)
    if error_response or not rows:
        return None
    value = rows[0].get("computed_at")
    # ISO 8601 có "T" — mọi trình duyệt đều new Date() được (jsonify mặc
    # định ra dạng RFC 822, str() thì có dấu cách: Safari không đọc được).
    return value.isoformat() if hasattr(value, "isoformat") else value


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


def get_du_lieu_gcn_rows(madvhc_soto_sothua: str):
    # Mọi dòng (1 dòng/chủ sử dụng) của 1 thửa — trang "Danh sách thửa đã
    # nhập" (nút "Xem/Sửa"). select "*" rồi lọc cột ở service layer, không
    # lọc ở đây để còn biết ma_nguon (quyết định cho sửa hay chỉ xem).
    response, error_response = supabase_client.rest_request(
        "GET",
        DU_LIEU_GCN_TABLE,
        params={"select": "*", "madvhc_soto_sothua": f"eq.{madvhc_soto_sothua}", "order": "id.asc"},
    )
    return _json_or_error(response, error_response)


def delete_du_lieu_gcn_rows(madvhc_soto_sothua: str):
    # Xóa TOÀN BỘ dòng (mọi chủ sử dụng) của 1 thửa để nhập lại — nút "Xóa
    # để nhập lại" ở trang "Danh sách thửa đã nhập". CHỈ xóa được dòng
    # nguồn "biểu Nhóm 4" (NHOM4_MA_NGUON), giống update_du_lieu_gcn_row —
    # dữ liệu đồng bộ Google Sheet bị nạp lại ở lần đồng bộ sau nên xóa tay
    # ở đây vô nghĩa (chặn luôn ở điều kiện lọc, không chỉ ở UI).
    response, error_response = supabase_client.rest_request(
        "DELETE",
        DU_LIEU_GCN_TABLE,
        params={
            "madvhc_soto_sothua": f"eq.{madvhc_soto_sothua}",
            "ma_nguon": f"eq.{NHOM4_MA_NGUON}",
        },
        extra_headers={"Prefer": "return=representation"},
    )
    return _json_or_error(response, error_response)


def update_du_lieu_gcn_row(row_id: int, madvhc_soto_sothua: str, updates: dict):
    # CHỈ sửa được dòng nguồn "biểu Nhóm 4" (NHOM4_MA_NGUON) — dữ liệu đồng
    # bộ Google Sheet bị ghi đè lại ở lần đồng bộ sau nên sửa tay ở đây vô
    # nghĩa (chặn luôn ở điều kiện lọc, không chỉ ở UI). Thêm điều kiện
    # madvhc_soto_sothua để chặn id không khớp thửa đang xem (phòng hờ).
    response, error_response = supabase_client.rest_request(
        "PATCH",
        DU_LIEU_GCN_TABLE,
        params={
            "id": f"eq.{row_id}",
            "madvhc_soto_sothua": f"eq.{madvhc_soto_sothua}",
            "ma_nguon": f"eq.{NHOM4_MA_NGUON}",
        },
        json_body=updates,
        extra_headers={"Content-Type": "application/json", "Prefer": "return=representation"},
    )
    return _json_or_error(response, error_response)
