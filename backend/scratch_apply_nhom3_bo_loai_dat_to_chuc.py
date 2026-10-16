"""Áp trực tiếp lên DB: REVERT việc loại "đất tổ chức" (thua_dat.ten_chu
khớp _nhom3_la_dat_to_chuc, ví dụ "UBND xã") khỏi
refresh_nhom3_trang_thai_cache().

Lý do: yêu cầu trước đó hiểu nhầm phạm vi — "đất tổ chức" chỉ nên phân
biệt RIÊNG trên bản đồ (nếu cần), KHÔNG được loại khỏi đếm/danh sách "còn
thiếu" dùng để chỉ đạo nhập biểu Nhóm 4 (xã vẫn phải thu thập/nhập dữ liệu
cho các thửa này — ví dụ đất công ích 5% do UBND xã quản lý vẫn là thửa có
thật, cần có dữ liệu). Hàm _nhom3_la_dat_to_chuc() vẫn giữ lại (không xoá)
phòng khi cần cho mục đích hiển thị riêng trên bản đồ sau này.

Chạy 1 lần — đưa đất tổ chức trở lại đếm bình thường, rồi refresh cache."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SCHEMA_SQL = """
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
    with gcn_du_keys as (
        select distinct g.madvhc_soto_sothua
        from public.du_lieu_gcn g
        where g.nhom3_du_du_lieu
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
    left join public.nhom3_xa_ghi_chu gc
        on gc.ma_xa = t.ma_xa
    left join nhom12_keys n12
        on n12.ma_xa = t.ma_xa and n12.so_to = t.so_to and n12.so_thua = t.so_thua
    left join gcn_du_keys k
        on k.madvhc_soto_sothua = t.ma_xa || '_' || t.so_to::text || '_' || t.so_thua::text
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

    print("1/2 Cập nhật refresh_nhom3_trang_thai_cache — bỏ loại đất tổ chức...")
    cur.execute(SCHEMA_SQL)

    print("2/2 Refresh lại cache (có thể mất ~100s)...")
    cur.execute("set statement_timeout = 0")
    cur.execute("select public.refresh_nhom3_trang_thai_cache()")
    print("   -> tổng dòng cache:", cur.fetchone()[0])

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
