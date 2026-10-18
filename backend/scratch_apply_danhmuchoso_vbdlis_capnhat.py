"""Áp trực tiếp lên DB các thay đổi cho "Danh mục hồ sơ lưu trữ"
(yêu cầu người dùng):
1. Số sêri GCN nhập tự do (bỏ regex bắt buộc 1-2 chữ cái + 6-8 số) — chỉ
   đổi ở Python (danhmuchoso_service.py), không có gì cần áp ở DB.
2. GCN đã có dữ liệu điện tử nơi khác (form Nhóm 4 / MPLIS) KHÔNG còn
   chặn nhập nữa — thêm cột danhmuchoso.da_co_tren_vbdlis đánh dấu thay
   vì chặn. Vẫn chặn nếu đã có SẴN TRONG CHÍNH danh mục (duplicate thật).
3. Thêm tính năng Sửa hồ sơ đã nhập — hàm danhmuchoso_cap_nhat() mới.

Idempotent — chạy lại không lỗi (add column if not exists, create or
replace function, drop function if exists trước khi đổi chữ ký)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SCHEMA_SQL = r"""
alter table public.danhmuchoso
    add column if not exists da_co_tren_vbdlis boolean not null default false;

drop function if exists public.danhmuchoso_kiem_tra_gcn(text);

create or replace function public.danhmuchoso_kiem_tra_gcn(p_so_seri_gcn text, p_exclude_id bigint default null)
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
as $$
    with gcn as (select trim(coalesce(p_so_seri_gcn, '')) as g)
    select jsonb_build_object(
        'da_nhap_form_nhom4', exists (
            select 1 from public.du_lieu_gcn x, gcn where trim(x.sophathanhgcn) = gcn.g and gcn.g <> ''
        ),
        'da_dong_bo_mplis', exists (
            select 1 from public.dong_bo_du_lieu x, gcn where trim(x.so_gcn_mplis) = gcn.g and gcn.g <> ''
        ),
        'da_co_trong_danh_muc', exists (
            select 1 from public.danhmuchoso x, gcn
            where trim(x.so_seri_gcn) = gcn.g and gcn.g <> ''
              and (p_exclude_id is null or x.id <> p_exclude_id)
        )
    ) || jsonb_build_object(
        'ton_tai', (
            exists (select 1 from public.du_lieu_gcn x, gcn where trim(x.sophathanhgcn) = gcn.g and gcn.g <> '')
            or exists (select 1 from public.dong_bo_du_lieu x, gcn where trim(x.so_gcn_mplis) = gcn.g and gcn.g <> '')
            or exists (
                select 1 from public.danhmuchoso x, gcn
                where trim(x.so_seri_gcn) = gcn.g and gcn.g <> ''
                  and (p_exclude_id is null or x.id <> p_exclude_id)
            )
        )
    );
$$;

revoke all on function public.danhmuchoso_kiem_tra_gcn(text, bigint) from public;
grant execute on function public.danhmuchoso_kiem_tra_gcn(text, bigint) to service_role;

drop function if exists public.danhmuchoso_them(
    integer, text, text, text, text, text, text, text, text, text, text, text
);
drop function if exists public.danhmuchoso_them(
    integer, text, text, text, text, text, text, text, text, text, text, text, text
);

create or replace function public.danhmuchoso_them(
    p_nam integer,
    p_chi_nhanh text,
    p_cap text,
    p_so_tt_ho_so text,
    p_ten_nguoi_su_dung_dat text,
    p_thua_dat_so_moi text,
    p_ban_do_so_moi text,
    p_thua_dat_so_cu text,
    p_ban_do_so_cu text,
    p_dia_chi_thua_dat text,
    p_so_seri_gcn text,
    p_loai_ho_so text,
    p_ghi_chu text,
    p_da_co_tren_vbdlis boolean default false
)
returns public.danhmuchoso
language sql
security definer
set search_path = public, extensions
as $$
    insert into public.danhmuchoso (
        nam, chi_nhanh, cap, so_tt_ho_so, ten_nguoi_su_dung_dat,
        thua_dat_so_moi, ban_do_so_moi, thua_dat_so_cu, ban_do_so_cu,
        dia_chi_thua_dat, so_seri_gcn, loai_ho_so, ghi_chu, da_co_tren_vbdlis
    ) values (
        p_nam, p_chi_nhanh, p_cap, p_so_tt_ho_so, p_ten_nguoi_su_dung_dat,
        p_thua_dat_so_moi, p_ban_do_so_moi, p_thua_dat_so_cu, p_ban_do_so_cu,
        p_dia_chi_thua_dat, trim(p_so_seri_gcn), p_loai_ho_so, p_ghi_chu, coalesce(p_da_co_tren_vbdlis, false)
    )
    returning *;
$$;

revoke all on function public.danhmuchoso_them(
    integer, text, text, text, text, text, text, text, text, text, text, text, text, boolean
) from public;
grant execute on function public.danhmuchoso_them(
    integer, text, text, text, text, text, text, text, text, text, text, text, text, boolean
) to service_role;

create or replace function public.danhmuchoso_cap_nhat(
    p_id bigint,
    p_nam integer,
    p_chi_nhanh text,
    p_cap text,
    p_so_tt_ho_so text,
    p_ten_nguoi_su_dung_dat text,
    p_thua_dat_so_moi text,
    p_ban_do_so_moi text,
    p_thua_dat_so_cu text,
    p_ban_do_so_cu text,
    p_dia_chi_thua_dat text,
    p_so_seri_gcn text,
    p_loai_ho_so text,
    p_ghi_chu text,
    p_da_co_tren_vbdlis boolean default false
)
returns public.danhmuchoso
language sql
security definer
set search_path = public, extensions
as $$
    update public.danhmuchoso set
        nam = p_nam,
        chi_nhanh = p_chi_nhanh,
        cap = p_cap,
        so_tt_ho_so = p_so_tt_ho_so,
        ten_nguoi_su_dung_dat = p_ten_nguoi_su_dung_dat,
        thua_dat_so_moi = p_thua_dat_so_moi,
        ban_do_so_moi = p_ban_do_so_moi,
        thua_dat_so_cu = p_thua_dat_so_cu,
        ban_do_so_cu = p_ban_do_so_cu,
        dia_chi_thua_dat = p_dia_chi_thua_dat,
        so_seri_gcn = trim(p_so_seri_gcn),
        loai_ho_so = p_loai_ho_so,
        ghi_chu = p_ghi_chu,
        da_co_tren_vbdlis = coalesce(p_da_co_tren_vbdlis, false)
    where id = p_id
    returning *;
$$;

revoke all on function public.danhmuchoso_cap_nhat(
    bigint, integer, text, text, text, text, text, text, text, text, text, text, text, text, boolean
) from public;
grant execute on function public.danhmuchoso_cap_nhat(
    bigint, integer, text, text, text, text, text, text, text, text, text, text, text, text, boolean
) to service_role;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    print("Áp schema danh mục hồ sơ: cột da_co_tren_vbdlis + hàm kiem_tra_gcn/them/cap_nhat...")
    cur.execute(SCHEMA_SQL)
    print("Xong.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
