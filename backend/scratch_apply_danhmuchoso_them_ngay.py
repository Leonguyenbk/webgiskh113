"""Áp trực tiếp lên DB: thêm cột "Ngày" (kiểu date) cho danh mục hồ sơ —
yêu cầu người dùng: nhận ngày tháng kiểu DD/MM/YYYY, web cho chọn (input
date), file Excel import sẽ ép định dạng về kiểu đó khi đọc (xem
danhmuchoso_service._parse_ngay). Cập nhật danhmuchoso_them/cap_nhat
thêm tham số p_ngay (danhmuchoso_list dùng select d.* nên tự động có cột
mới, không cần sửa). Chạy 1 lần, idempotent (ADD COLUMN IF NOT EXISTS +
DROP FUNCTION IF EXISTS trước khi tạo lại với chữ ký mới)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SCHEMA_SQL = r"""
alter table public.danhmuchoso add column if not exists ngay date;

drop function if exists public.danhmuchoso_them(
    integer, text, text, text, text, text, text, text, text, text, text, text, text, boolean
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
    p_da_co_tren_vbdlis boolean default false,
    p_ngay date default null
)
returns public.danhmuchoso
language sql
security definer
set search_path = public, extensions
as $$
    insert into public.danhmuchoso (
        nam, ngay, chi_nhanh, cap, so_tt_ho_so, ten_nguoi_su_dung_dat,
        thua_dat_so_moi, ban_do_so_moi, thua_dat_so_cu, ban_do_so_cu,
        dia_chi_thua_dat, so_seri_gcn, loai_ho_so, ghi_chu, da_co_tren_vbdlis
    ) values (
        p_nam, p_ngay, p_chi_nhanh, p_cap, p_so_tt_ho_so, p_ten_nguoi_su_dung_dat,
        p_thua_dat_so_moi, p_ban_do_so_moi, p_thua_dat_so_cu, p_ban_do_so_cu,
        p_dia_chi_thua_dat, trim(p_so_seri_gcn), p_loai_ho_so, p_ghi_chu, coalesce(p_da_co_tren_vbdlis, false)
    )
    returning *;
$$;

revoke all on function public.danhmuchoso_them(
    integer, text, text, text, text, text, text, text, text, text, text, text, text, boolean, date
) from public;
grant execute on function public.danhmuchoso_them(
    integer, text, text, text, text, text, text, text, text, text, text, text, text, boolean, date
) to service_role;

drop function if exists public.danhmuchoso_cap_nhat(
    bigint, integer, text, text, text, text, text, text, text, text, text, text, text, text, boolean
);

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
    p_da_co_tren_vbdlis boolean default false,
    p_ngay date default null
)
returns public.danhmuchoso
language sql
security definer
set search_path = public, extensions
as $$
    update public.danhmuchoso set
        nam = p_nam,
        ngay = p_ngay,
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
    bigint, integer, text, text, text, text, text, text, text, text, text, text, text, text, boolean, date
) from public;
grant execute on function public.danhmuchoso_cap_nhat(
    bigint, integer, text, text, text, text, text, text, text, text, text, text, text, text, boolean, date
) to service_role;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    print("Them cot ngay + cap nhat danhmuchoso_them/cap_nhat...")
    cur.execute(SCHEMA_SQL)
    conn.commit()
    cur.execute("select column_name from information_schema.columns where table_name='danhmuchoso' and column_name='ngay'")
    print("Kiem tra cot ngay:", cur.fetchone())
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
