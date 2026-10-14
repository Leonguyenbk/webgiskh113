"""Áp trực tiếp lên DB: thêm tham số p_co_nhap (lọc trạng thái) vào
nhom3_list_con_thieu(), khớp supabase/schema.sql. Chạy 1 lần."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SQL = """
drop function if exists public.nhom3_list_con_thieu(text, integer, integer);

create or replace function public.nhom3_list_con_thieu(
    p_ma_xa text default null,
    p_limit integer default 100,
    p_offset integer default 0,
    p_co_nhap boolean default null
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
begin
    select count(*) into v_total
    from public.nhom3_trang_thai_cache c
    where (p_ma_xa is null or c.ma_xa = p_ma_xa)
      and (p_co_nhap is null or c.co_nhap = p_co_nhap)
      and not c.la_nhom_1_2 and not c.da_thu_thap;

    select coalesce(jsonb_agg(row_to_json(y)), '[]'::jsonb) into v_items
    from (
        select
            c.ma_xa, xp.ten_xa, c.so_to, c.so_thua, c.ma_dinh_danh, c.co_nhap,
            case when c.co_nhap then 'Đã nhập nhưng sai form' else 'Chưa nhập' end as ghi_chu
        from public.nhom3_trang_thai_cache c
        left join public.danhsachxaphuong xp on xp.ma_xa = c.ma_xa
        where (p_ma_xa is null or c.ma_xa = p_ma_xa)
          and (p_co_nhap is null or c.co_nhap = p_co_nhap)
          and not c.la_nhom_1_2 and not c.da_thu_thap
        order by c.ma_xa, c.so_to, c.so_thua
        limit p_limit offset p_offset
    ) y;

    return jsonb_build_object('total', v_total, 'items', v_items);
end;
$$;

revoke all on function public.nhom3_list_con_thieu(text, integer, integer, boolean) from public;
grant execute on function public.nhom3_list_con_thieu(text, integer, integer, boolean) to service_role;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    print("Áp lại nhom3_list_con_thieu() với tham số p_co_nhap...")
    cur.execute(SQL)
    conn.commit()
    print("Xong.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
