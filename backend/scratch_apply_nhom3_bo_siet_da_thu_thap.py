"""Áp trực tiếp lên DB: bỏ yêu cầu "đạt chuẩn đủ dữ liệu" (nhom3_du_du_lieu)
khỏi việc tính da_thu_thap trong nhom3_trang_thai_cache.

Lý do (yêu cầu người dùng): trong danh sách "đã làm" của Nhóm 3 gửi xã,
không siết điều kiện chất lượng dữ liệu nữa — thửa đất đã được nhập (có
ít nhất 1 dòng du_lieu_gcn), có trong danh sách gửi xã, là tính đã làm
luôn, không cần đạt đủ các điều kiện của _nhom3_gcn_du_du_lieu nữa.

da_thu_thap giờ đọc từ cùng nguồn với co_nhap (gcn_any_keys) thay vì
gcn_du_keys (lọc theo nhom3_du_du_lieu). Cột nhom3_du_du_lieu trên
du_lieu_gcn vẫn giữ lại, không xoá, chỉ không còn dùng để tính
da_thu_thap nữa.

Chỉ cần refresh lại cache — không cần backfill cột nào trên du_lieu_gcn.
Chạy 1 lần."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SCHEMA_SQL = r"""
create or replace function public.refresh_nhom3_trang_thai_cache()
returns integer
language plpgsql
security definer
set search_path = public, extensions
set statement_timeout = '180s'
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
    with
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
        (a.madvhc_soto_sothua is not null) as da_thu_thap,
        (a.madvhc_soto_sothua is not null) as co_nhap,
        v_now
    from public.nhom3_can_thu_thap t
    join public.thua_dat p
        on p.ma_xa = t.ma_xa and p.so_to = t.so_to and p.so_thua = t.so_thua
    left join public.nhom3_xa_ghi_chu gc
        on gc.ma_xa = t.ma_xa
    left join nhom12_keys n12
        on n12.ma_xa = t.ma_xa and n12.so_to = t.so_to and n12.so_thua = t.so_thua
    left join gcn_any_keys a
        on a.madvhc_soto_sothua = t.ma_xa || '_' || t.so_to::text || '_' || t.so_thua::text
    where not t.thuoc_du_an
      and gc.ma_xa is null
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


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    print("1/2 Cập nhật refresh_nhom3_trang_thai_cache — da_thu_thap = co_nhap (bỏ siết đạt chuẩn)...")
    cur.execute(SCHEMA_SQL)

    print("2/2 Refresh lại cache (có thể mất ~100s)...")
    cur.execute("set statement_timeout = 0")
    cur.execute("select public.refresh_nhom3_trang_thai_cache()")
    print("   -> tổng dòng cache:", cur.fetchone()[0])

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
