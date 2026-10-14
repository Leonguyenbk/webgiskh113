from __future__ import annotations

from . import supabase_client


def kiem_tra_gcn(so_seri_gcn: str):
    # Đối chiếu 1 số sêri GCN với 3 nguồn (du_lieu_gcn, dong_bo_du_lieu từ
    # MPLIS, chính danhmuchoso) — xem public.danhmuchoso_kiem_tra_gcn.
    return supabase_client.call_rpc(
        "danhmuchoso_kiem_tra_gcn", {"p_so_seri_gcn": so_seri_gcn}, timeout=15
    )


def them(payload: dict):
    return supabase_client.call_rpc(
        "danhmuchoso_them",
        {
            "p_nam": payload.get("nam"),
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
        },
        timeout=15,
    )


def danh_sach(limit: int, offset: int, keyword: str | None, nam: int | None):
    return supabase_client.call_rpc(
        "danhmuchoso_list",
        {"p_limit": limit, "p_offset": offset, "p_keyword": keyword, "p_nam": nam},
        timeout=20,
    )
