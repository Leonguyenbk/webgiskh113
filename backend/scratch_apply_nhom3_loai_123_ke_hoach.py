"""Áp trực tiếp lên DB: thêm bảng nhom3_loai_123_da_lam (khối lượng
"Loại 1/2/3" ĐÃ LÀM theo xã, do VPĐK gửi song song ngoài hệ thống — xem
DANHSACHGUIXA/KhoiLuongXa-KH113-*.xlsx) và cập nhật nhom3_tong_hop cộng
thêm cột Loại 1 vào cả tổng lẫn đã làm để ra "tổng/tỷ lệ theo kế hoạch"
(yêu cầu người dùng: nền Tổng B — đã trừ Chi nhánh KV + trừ chưa liên
kết không gian — cộng thêm CHỈ cột Loại 1; Loại 2/3 lưu lại tham khảo,
chưa dùng công thức). Chạy lại được nhiều lần (idempotent)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SCHEMA_SQL = r"""
create table if not exists public.nhom3_loai_123_da_lam (
    ma_xa text primary key,
    loai_1 integer not null default 0 check (loai_1 >= 0),
    loai_2 integer not null default 0 check (loai_2 >= 0),
    loai_3 integer not null default 0 check (loai_3 >= 0),
    cap_nhat_luc timestamptz not null default now()
);
alter table public.nhom3_loai_123_da_lam enable row level security;

create or replace function public.nhom3_tong_hop(p_to_giam_sat integer default null)
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
as $$
    with raw as (
        select
            c.ma_xa,
            xp.ten_xa,
            tg.khu_vuc,
            tg.to_giam_sat,
            count(*) as tong_cache,
            count(*) filter (where c.la_nhom_1_2) as da_nhom_1_2,
            count(*) filter (where c.la_nhom_1_2 and c.co_nhap) as da_nhom_1_2_da_nhap,
            count(*) filter (where c.la_nhom_1_2 and not c.co_nhap) as da_nhom_1_2_chua_nhap,
            count(*) filter (where not c.la_nhom_1_2 and c.da_thu_thap) as da_thu_thap,
            count(*) filter (where not c.la_nhom_1_2 and not c.da_thu_thap) as con_thieu_cache,
            count(*) filter (where not c.la_nhom_1_2 and c.co_nhap and not c.da_thu_thap) as da_nhap_chua_dat,
            coalesce(kg.so_luong, 0) as chua_lien_ket_khong_gian,
            coalesce(l123.loai_1, 0) as loai_1_da_lam
        from public.nhom3_trang_thai_cache c
        left join public.danhsachxaphuong xp on xp.ma_xa = c.ma_xa
        left join public.nhom3_to_giam_sat tg on tg.ma_xa = c.ma_xa
        left join public.nhom3_chua_lien_ket_khong_gian kg on kg.ma_xa = c.ma_xa
        left join public.nhom3_loai_123_da_lam l123 on l123.ma_xa = c.ma_xa
        where p_to_giam_sat is null or tg.to_giam_sat = p_to_giam_sat
        group by c.ma_xa, xp.ten_xa, tg.khu_vuc, tg.to_giam_sat, kg.so_luong, l123.loai_1
    ),
    theo_xa as (
        select
            ma_xa, ten_xa, khu_vuc, to_giam_sat,
            (tong_cache - da_nhom_1_2_chua_nhap) as tong,
            da_nhom_1_2, da_nhom_1_2_da_nhap, da_nhom_1_2_chua_nhap,
            da_thu_thap,
            con_thieu_cache as con_thieu,
            da_nhap_chua_dat,
            chua_lien_ket_khong_gian,
            (tong_cache - da_nhom_1_2_chua_nhap - chua_lien_ket_khong_gian) as tong_tru_kg,
            loai_1_da_lam,
            (tong_cache - da_nhom_1_2_chua_nhap - chua_lien_ket_khong_gian + loai_1_da_lam) as tong_ke_hoach,
            null::text as ghi_chu
        from raw

        union all

        select g.ma_xa, xp.ten_xa, tg.khu_vuc, tg.to_giam_sat, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, g.ghi_chu
        from public.nhom3_xa_ghi_chu g
        left join public.danhsachxaphuong xp on xp.ma_xa = g.ma_xa
        left join public.nhom3_to_giam_sat tg on tg.ma_xa = g.ma_xa
        where (p_to_giam_sat is null or tg.to_giam_sat = p_to_giam_sat)
          and not exists (
              select 1 from raw r where r.ma_xa = g.ma_xa
          )
    )
    select jsonb_build_object(
        'tong', coalesce(sum(tong), 0),
        'da_nhom_1_2', coalesce(sum(da_nhom_1_2), 0),
        'da_nhom_1_2_da_nhap', coalesce(sum(da_nhom_1_2_da_nhap), 0),
        'da_nhom_1_2_chua_nhap', coalesce(sum(da_nhom_1_2_chua_nhap), 0),
        'da_thu_thap', coalesce(sum(da_thu_thap), 0),
        'con_thieu', coalesce(sum(con_thieu), 0),
        'da_nhap_chua_dat', coalesce(sum(da_nhap_chua_dat), 0),
        'chua_lien_ket_khong_gian', coalesce(sum(chua_lien_ket_khong_gian), 0),
        'tong_tru_kg', coalesce(sum(tong_tru_kg), 0),
        'loai_1_da_lam', coalesce(sum(loai_1_da_lam), 0),
        'tong_ke_hoach', coalesce(sum(tong_ke_hoach), 0),
        'theo_xa', coalesce(jsonb_agg(row_to_json(theo_xa) order by tong desc), '[]'::jsonb)
    )
    from theo_xa;
$$;

revoke all on function public.nhom3_tong_hop(integer) from public;
grant execute on function public.nhom3_tong_hop(integer) to service_role;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    print("Them bang nhom3_loai_123_da_lam + cap nhat nhom3_tong_hop...")
    cur.execute(SCHEMA_SQL)
    conn.commit()
    cur.execute(
        "select column_name from information_schema.columns "
        "where table_name='nhom3_loai_123_da_lam' order by ordinal_position"
    )
    print("Cot bang moi:", [r[0] for r in cur.fetchall()])
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
