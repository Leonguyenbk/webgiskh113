"""Áp trực tiếp lên DB: thêm cột danhmuchoso.chi_nhanh + cập nhật
danhmuchoso_them()/danhmuchoso_list() khớp supabase/schema.sql. Chạy 1 lần."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SQL = """
alter table public.danhmuchoso add column if not exists chi_nhanh text;
create index if not exists idx_danhmuchoso_chi_nhanh on public.danhmuchoso (chi_nhanh);

drop function if exists public.danhmuchoso_them(
    integer, text, text, text, text, text, text, text, text, text, text, text
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
    p_ghi_chu text
)
returns public.danhmuchoso
language sql
security definer
set search_path = public, extensions
as $$
    insert into public.danhmuchoso (
        nam, chi_nhanh, cap, so_tt_ho_so, ten_nguoi_su_dung_dat,
        thua_dat_so_moi, ban_do_so_moi, thua_dat_so_cu, ban_do_so_cu,
        dia_chi_thua_dat, so_seri_gcn, loai_ho_so, ghi_chu
    ) values (
        p_nam, p_chi_nhanh, p_cap, p_so_tt_ho_so, p_ten_nguoi_su_dung_dat,
        p_thua_dat_so_moi, p_ban_do_so_moi, p_thua_dat_so_cu, p_ban_do_so_cu,
        p_dia_chi_thua_dat, trim(p_so_seri_gcn), p_loai_ho_so, p_ghi_chu
    )
    returning *;
$$;

revoke all on function public.danhmuchoso_them(
    integer, text, text, text, text, text, text, text, text, text, text, text, text
) from public;
grant execute on function public.danhmuchoso_them(
    integer, text, text, text, text, text, text, text, text, text, text, text, text
) to service_role;

drop function if exists public.danhmuchoso_list(integer, integer, text, integer);

create or replace function public.danhmuchoso_list(
    p_limit integer default 100,
    p_offset integer default 0,
    p_keyword text default null,
    p_nam integer default null,
    p_chi_nhanh text default null
)
returns jsonb
language plpgsql
stable
security definer
set search_path = public, extensions
as $$
declare
    v_total integer;
    v_items jsonb;
    v_kw text := '%' || coalesce(trim(p_keyword), '') || '%';
begin
    select count(*) into v_total
    from public.danhmuchoso d
    where (p_nam is null or d.nam = p_nam)
      and (p_chi_nhanh is null or trim(p_chi_nhanh) = '' or d.chi_nhanh = p_chi_nhanh)
      and (
          p_keyword is null or trim(p_keyword) = ''
          or d.ten_nguoi_su_dung_dat ilike v_kw
          or d.so_seri_gcn ilike v_kw
          or d.so_tt_ho_so ilike v_kw
          or d.cap ilike v_kw
      );

    select coalesce(jsonb_agg(row_to_json(y)), '[]'::jsonb) into v_items
    from (
        select d.*
        from public.danhmuchoso d
        where (p_nam is null or d.nam = p_nam)
          and (p_chi_nhanh is null or trim(p_chi_nhanh) = '' or d.chi_nhanh = p_chi_nhanh)
          and (
              p_keyword is null or trim(p_keyword) = ''
              or d.ten_nguoi_su_dung_dat ilike v_kw
              or d.so_seri_gcn ilike v_kw
              or d.so_tt_ho_so ilike v_kw
              or d.cap ilike v_kw
          )
        order by d.id desc
        limit p_limit offset p_offset
    ) y;

    return jsonb_build_object('total', v_total, 'items', v_items);
end;
$$;

revoke all on function public.danhmuchoso_list(integer, integer, text, integer, text) from public;
grant execute on function public.danhmuchoso_list(integer, integer, text, integer, text) to service_role;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    print("Áp cột chi_nhanh + hàm danhmuchoso_them/list...")
    cur.execute(SQL)
    conn.commit()
    print("Xong.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
