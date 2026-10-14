"""Áp trực tiếp lên DB: thêm cột nhom3_trang_thai_cache.co_nhap (phân biệt
"đã nhập nhưng sai form" với "chưa nhập") + cập nhật
refresh_nhom3_trang_thai_cache()/nhom3_list_con_thieu() khớp supabase/schema.sql.
Chạy 1 lần, không cần lặp lại."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

ALTER_SQL = """
alter table public.nhom3_trang_thai_cache
    add column if not exists co_nhap boolean not null default false;
"""

REFRESH_FUNC_SQL = """
create or replace function public.refresh_nhom3_trang_thai_cache()
returns integer
language plpgsql
security definer
set search_path = public, extensions
set statement_timeout = '300s'
set work_mem = '512MB'
as $$
declare
    v_now timestamptz := now();
    v_rows integer;
begin
    perform pg_advisory_xact_lock(hashtext('refresh_nhom3_trang_thai_cache'));

    if exists (
        select 1 from public.nhom3_trang_thai_cache
        where computed_at > v_now - interval '1 minute'
    ) then
        select count(*) into v_rows from public.nhom3_trang_thai_cache;
        return v_rows;
    end if;

    insert into public.nhom3_trang_thai_cache
        (ma_xa, so_to, so_thua, ma_dinh_danh, la_nhom_1_2, da_thu_thap, co_nhap, computed_at)
    with gcn_du_keys as (
        select distinct g.madvhc_soto_sothua
        from public.du_lieu_gcn g
        where public._nhom3_gcn_du_du_lieu(g)
    ),
    gcn_any_keys as (
        select distinct g.madvhc_soto_sothua
        from public.du_lieu_gcn g
    ),
    nhom12_keys as (
        select d.ma_xa, d.so_to, d.so_thua
        from public.dong_bo_du_lieu d
        where upper(trim(d.phan_loai_ke_hoach_2959)) in ('NHÓM 1', 'NHÓM 2')
    )
    select
        t.ma_xa, t.so_to, t.so_thua, t.ma_dinh_danh,
        (n12.ma_xa is not null) as la_nhom_1_2,
        (k.madvhc_soto_sothua is not null) as da_thu_thap,
        (a.madvhc_soto_sothua is not null) as co_nhap,
        v_now
    from public.nhom3_can_thu_thap t
    join public.thua_dat p
        on p.ma_xa = t.ma_xa and p.so_to = t.so_to and p.so_thua = t.so_thua
    left join nhom12_keys n12
        on n12.ma_xa = t.ma_xa and n12.so_to = t.so_to and n12.so_thua = t.so_thua
    left join gcn_du_keys k
        on k.madvhc_soto_sothua = t.ma_xa || '_' || t.so_to::text || '_' || t.so_thua::text
    left join gcn_any_keys a
        on a.madvhc_soto_sothua = t.ma_xa || '_' || t.so_to::text || '_' || t.so_thua::text
    where not t.thuoc_du_an
    on conflict (ma_xa, so_to, so_thua) do update set
        ma_dinh_danh = excluded.ma_dinh_danh,
        la_nhom_1_2  = excluded.la_nhom_1_2,
        da_thu_thap  = excluded.da_thu_thap,
        co_nhap      = excluded.co_nhap,
        computed_at  = excluded.computed_at;

    get diagnostics v_rows = row_count;

    delete from public.nhom3_trang_thai_cache where computed_at < v_now;

    insert into public.nhom3_tien_do_lich_su (ma_xa, tong, da_nhom_1_2, da_thu_thap, con_thieu, ghi_nhan_luc)
    select
        ma_xa,
        count(*) as tong,
        count(*) filter (where la_nhom_1_2) as da_nhom_1_2,
        count(*) filter (where not la_nhom_1_2 and da_thu_thap) as da_thu_thap,
        count(*) filter (where not la_nhom_1_2 and not da_thu_thap) as con_thieu,
        v_now
    from public.nhom3_trang_thai_cache
    group by ma_xa;

    return v_rows;
end;
$$;

revoke all on function public.refresh_nhom3_trang_thai_cache() from public;
grant execute on function public.refresh_nhom3_trang_thai_cache() to service_role;
"""

LIST_FUNC_SQL = """
create or replace function public.nhom3_list_con_thieu(
    p_ma_xa text default null,
    p_limit integer default 100,
    p_offset integer default 0
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
      and not c.la_nhom_1_2 and not c.da_thu_thap;

    select coalesce(jsonb_agg(row_to_json(y)), '[]'::jsonb) into v_items
    from (
        select
            c.ma_xa, xp.ten_xa, c.so_to, c.so_thua, c.ma_dinh_danh, c.co_nhap,
            case when c.co_nhap then 'Đã nhập nhưng sai form' else 'Chưa nhập' end as ghi_chu
        from public.nhom3_trang_thai_cache c
        left join public.danhsachxaphuong xp on xp.ma_xa = c.ma_xa
        where (p_ma_xa is null or c.ma_xa = p_ma_xa)
          and not c.la_nhom_1_2 and not c.da_thu_thap
        order by c.ma_xa, c.so_to, c.so_thua
        limit p_limit offset p_offset
    ) y;

    return jsonb_build_object('total', v_total, 'items', v_items);
end;
$$;

revoke all on function public.nhom3_list_con_thieu(text, integer, integer) from public;
grant execute on function public.nhom3_list_con_thieu(text, integer, integer) to service_role;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    print("1/3 ALTER TABLE thêm cột co_nhap...")
    cur.execute(ALTER_SQL)

    print("2/3 CREATE OR REPLACE refresh_nhom3_trang_thai_cache()...")
    cur.execute(REFRESH_FUNC_SQL)

    print("3/3 CREATE OR REPLACE nhom3_list_con_thieu()...")
    cur.execute(LIST_FUNC_SQL)

    conn.commit()
    print("Đã áp schema. Đang chạy refresh_nhom3_trang_thai_cache() để điền co_nhap cho dữ liệu hiện có...")

    cur2 = conn.cursor()
    cur2.execute("set statement_timeout = '300s'")
    cur2.execute("select public.refresh_nhom3_trang_thai_cache()")
    rows = cur2.fetchone()[0]
    conn.commit()
    print(f"Refresh xong, tổng dòng trong cache: {rows}")

    cur2.execute(
        "select count(*) from public.nhom3_trang_thai_cache where co_nhap and not da_thu_thap"
    )
    sai_form = cur2.fetchone()[0]
    cur2.execute(
        "select count(*) from public.nhom3_trang_thai_cache where not co_nhap and not da_thu_thap"
    )
    chua_nhap = cur2.fetchone()[0]
    print(f"Còn thiếu - đã nhập nhưng sai form: {sai_form}, chưa nhập: {chua_nhap}")

    cur.close()
    cur2.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
