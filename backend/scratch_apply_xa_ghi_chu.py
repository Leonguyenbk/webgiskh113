"""Áp trực tiếp lên DB: tạo bảng nhom3_xa_ghi_chu + cập nhật nhom3_tong_hop()
để gộp ghi chú riêng theo xã (khớp supabase/schema.sql), rồi seed ghi chú
cho khu vực Đồng Xuân/Cư Kuin (thuộc 1 dự án tổng thể khác, không có danh
sách gửi xã KH 2959 -> không đánh giá Nhóm 3). Chạy 1 lần."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SCHEMA_SQL = """
create table if not exists public.nhom3_xa_ghi_chu (
    ma_xa text primary key,
    ghi_chu text not null,
    tao_luc timestamptz not null default now()
);
alter table public.nhom3_xa_ghi_chu enable row level security;

create or replace function public.nhom3_tong_hop()
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
as $$
    with theo_xa as (
        select
            c.ma_xa,
            xp.ten_xa,
            count(*) as tong,
            count(*) filter (where c.la_nhom_1_2) as da_nhom_1_2,
            count(*) filter (where not c.la_nhom_1_2 and c.da_thu_thap) as da_thu_thap,
            count(*) filter (where not c.la_nhom_1_2 and not c.da_thu_thap) as con_thieu,
            null::text as ghi_chu
        from public.nhom3_trang_thai_cache c
        left join public.danhsachxaphuong xp on xp.ma_xa = c.ma_xa
        group by c.ma_xa, xp.ten_xa

        union all

        select g.ma_xa, xp.ten_xa, 0, 0, 0, 0, g.ghi_chu
        from public.nhom3_xa_ghi_chu g
        left join public.danhsachxaphuong xp on xp.ma_xa = g.ma_xa
        where not exists (
            select 1 from public.nhom3_trang_thai_cache c where c.ma_xa = g.ma_xa
        )
    )
    select jsonb_build_object(
        'tong', coalesce(sum(tong), 0),
        'da_nhom_1_2', coalesce(sum(da_nhom_1_2), 0),
        'da_thu_thap', coalesce(sum(da_thu_thap), 0),
        'con_thieu', coalesce(sum(con_thieu), 0),
        'theo_xa', coalesce(jsonb_agg(row_to_json(theo_xa) order by tong desc), '[]'::jsonb)
    )
    from theo_xa;
$$;

revoke all on function public.nhom3_tong_hop() from public;
grant execute on function public.nhom3_tong_hop() to service_role;
"""

GHI_CHU = "Thuộc dự án tổng thể khác — không có danh sách gửi xã KH 2959, không đánh giá Nhóm 3"

MA_XA_LIST = ["22081", "22090", "22096", "22111", "24540", "24544", "24561"]


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()

    print("1/2 Tạo bảng nhom3_xa_ghi_chu + cập nhật nhom3_tong_hop()...")
    cur.execute(SCHEMA_SQL)
    conn.commit()

    print("2/2 Seed ghi chú cho 7 xã Đồng Xuân/Cư Kuin...")
    for ma_xa in MA_XA_LIST:
        cur.execute(
            """insert into public.nhom3_xa_ghi_chu (ma_xa, ghi_chu) values (%s, %s)
               on conflict (ma_xa) do update set ghi_chu = excluded.ghi_chu""",
            (ma_xa, GHI_CHU),
        )
    conn.commit()

    cur.execute("select ma_xa, ghi_chu from public.nhom3_xa_ghi_chu order by ma_xa")
    for row in cur.fetchall():
        print(" ", row)

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
