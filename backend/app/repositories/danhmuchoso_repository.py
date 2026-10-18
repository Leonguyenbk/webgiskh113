from __future__ import annotations

from . import supabase_client


def kiem_tra_gcn(so_seri_gcn: str, exclude_id: int | None = None):
    # Đối chiếu 1 số sêri GCN với 3 nguồn (du_lieu_gcn, dong_bo_du_lieu từ
    # MPLIS, chính danhmuchoso) — xem public.danhmuchoso_kiem_tra_gcn.
    # exclude_id: loại trừ chính dòng đang sửa khỏi "đã có trong danh mục"
    # (gọi từ modal "Cập nhật hồ sơ"), để None khi nhập hồ sơ mới.
    payload = {"p_so_seri_gcn": so_seri_gcn}
    if exclude_id is not None:
        payload["p_exclude_id"] = exclude_id
    return supabase_client.call_rpc("danhmuchoso_kiem_tra_gcn", payload, timeout=15)


def _payload_chung(payload: dict) -> dict:
    return {
        "p_nam": payload.get("nam"),
        "p_chi_nhanh": payload.get("chi_nhanh"),
        "p_cap": payload.get("cap"),
        "p_so_tt_ho_so": payload.get("so_tt_ho_so"),
        "p_ten_nguoi_su_dung_dat": payload.get("ten_nguoi_su_dung_dat"),
        "p_thua_dat_so_moi": payload.get("thua_dat_so_moi"),
        "p_ban_do_so_moi": payload.get("ban_do_so_moi"),
        "p_thua_dat_so_cu": payload.get("thua_dat_so_cu"),
        "p_ban_do_so_cu": payload.get("ban_do_so_cu"),
        "p_dia_chi_thua_dat": payload.get("dia_chi_thua_dat"),
        "p_so_seri_gcn": payload.get("so_seri_gcn"),
        "p_loai_ho_so": payload.get("loai_ho_so"),
        "p_ghi_chu": payload.get("ghi_chu"),
        "p_da_co_tren_vbdlis": bool(payload.get("da_co_tren_vbdlis")),
    }


def them(payload: dict):
    return supabase_client.call_rpc("danhmuchoso_them", _payload_chung(payload), timeout=15)


def cap_nhat(row_id: int, payload: dict):
    return supabase_client.call_rpc(
        "danhmuchoso_cap_nhat",
        {"p_id": row_id, **_payload_chung(payload)},
        timeout=15,
    )


def danh_sach(limit: int, offset: int, keyword: str | None, nam: int | None, chi_nhanh: str | None = None):
    return supabase_client.call_rpc(
        "danhmuchoso_list",
        {
            "p_limit": limit,
            "p_offset": offset,
            "p_keyword": keyword,
            "p_nam": nam,
            "p_chi_nhanh": chi_nhanh,
        },
        timeout=20,
    )
