"""Áp trực tiếp lên DB: thêm cột du_lieu_gcn.nhom3_du_du_lieu (lưu sẵn kết
quả _nhom3_gcn_du_du_lieu()) + trigger trg_nhom3_set_du_du_lieu (tự tính
lại khi insert/update, KHÔNG cần quét lại cả bảng) + index partial, rồi
sửa refresh_nhom3_trang_thai_cache() đọc thẳng cột này thay vì gọi hàm
regex per-row trong CTE gcn_du_keys (khớp supabase/schema.sql).

Lý do: CTE gcn_du_keys gọi _nhom3_gcn_du_du_lieu() cho TỪNG dòng
du_lieu_gcn MỖI LẦN refresh — sau khi bảng lên ~1.9 triệu dòng
(nhom3_can_thu_thap) + du_lieu_gcn 734k dòng, đo thực tế refresh chạy
20+ phút, statement_timeout 600s nhiều lúc không kịp hủy. Sau khi
chuyển sang đọc cột lưu sẵn: đo lại còn ~92s.

Chạy 1 lần — bước UPDATE backfill cho dữ liệu cũ (TRƯỚC khi có trigger)
tốn thời gian (quét + tính regex 734k dòng), nhưng chỉ cần chạy 1 lần
duy nhất; từ sau trigger, mọi insert/update mới tự cập nhật đúng cột,
không bao giờ cần quét lại toàn bộ nữa."""
from __future__ import annotations

import sys
import time

import psycopg2

from app.config import Config

SCHEMA_SQL = """
alter table public.du_lieu_gcn
    add column if not exists nhom3_du_du_lieu boolean not null default false;

create or replace function public._nhom3_set_du_du_lieu()
returns trigger
language plpgsql
as $$
begin
    new.nhom3_du_du_lieu := public._nhom3_gcn_du_du_lieu(new);
    return new;
end;
$$;

drop trigger if exists trg_nhom3_set_du_du_lieu on public.du_lieu_gcn;
create trigger trg_nhom3_set_du_du_lieu
before insert or update on public.du_lieu_gcn
for each row execute function public._nhom3_set_du_du_lieu();
"""

INDEX_SQL = """
create index if not exists idx_du_lieu_gcn_nhom3_du_du_lieu
    on public.du_lieu_gcn (madvhc_soto_sothua)
    where nhom3_du_du_lieu;
"""

REFRESH_FN_SQL = """
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
      and not public._nhom3_la_dat_to_chuc(p.ten_chu)
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
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()

    print("1/4 Thêm cột nhom3_du_du_lieu + trigger trg_nhom3_set_du_du_lieu...")
    cur.execute(SCHEMA_SQL)
    conn.commit()

    print("2/4 Backfill 1 lần cho dữ liệu cũ (có thể mất vài phút)...")
    cur2 = conn.cursor()
    cur2.execute("set statement_timeout = '0'")
    t0 = time.time()
    cur2.execute(
        "update public.du_lieu_gcn set nhom3_du_du_lieu = public._nhom3_gcn_du_du_lieu(du_lieu_gcn.*)"
    )
    conn.commit()
    print(f"  Xong, {cur2.rowcount} dòng, {round(time.time() - t0, 1)}s")

    print("3/4 Tạo index partial...")
    cur.execute(INDEX_SQL)
    conn.commit()

    print("4/4 Cập nhật refresh_nhom3_trang_thai_cache() đọc cột mới...")
    cur.execute(REFRESH_FN_SQL)
    conn.commit()

    cur.execute(
        "select count(*), count(*) filter (where nhom3_du_du_lieu) from public.du_lieu_gcn"
    )
    print("Tổng dòng / đã đủ dữ liệu:", cur.fetchone())

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
