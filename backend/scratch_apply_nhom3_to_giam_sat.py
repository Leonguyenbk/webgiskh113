"""Áp trực tiếp lên DB: tạo bảng nhom3_to_giam_sat (ánh xạ xã -> khu vực ->
Tổ kiểm tra, giám sát 1-4, theo Quyết định 867/QĐ-VPĐKĐĐ ngày 01/10/2026 +
Danh sách kèm theo) + cập nhật nhom3_tong_hop() nhận p_to_giam_sat để lọc
(khớp supabase/schema.sql), rồi seed đủ 102 xã hiện có trong
danhsachxaphuong. Chạy 1 lần.

Map theo khối mã ma_xa liên tục từng huyện/khu vực cũ (tự kiểm chứng:
tổng từng Tổ phải khớp đúng danh sách khu vực trong Quyết định, và hợp
đủ 102/102 xã trong danhsachxaphuong, không thiếu không thừa — xem
main()). 2 trường hợp map theo suy luận, CHƯA xác nhận 100%: "Phường Phú
Yên" (22240, tạm xếp khu vực Tuy Hòa, cùng kiểu đặt tên với "Phường Buôn
Ma Thuột" 24133) và "Xã Ea Đrông" (24328, tạm xếp khu vực Buôn Hồ) — sửa
lại nếu sai."""
from __future__ import annotations

import sys

import psycopg2
import psycopg2.extras

from app.config import Config

SCHEMA_SQL = """
create table if not exists public.nhom3_to_giam_sat (
    ma_xa text primary key,
    khu_vuc text not null,
    to_giam_sat smallint not null check (to_giam_sat between 1 and 4),
    created_at timestamptz not null default now()
);
alter table public.nhom3_to_giam_sat enable row level security;

create or replace function public.nhom3_tong_hop(p_to_giam_sat integer default null)
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
            tg.khu_vuc,
            tg.to_giam_sat,
            count(*) as tong,
            count(*) filter (where c.la_nhom_1_2) as da_nhom_1_2,
            count(*) filter (where not c.la_nhom_1_2 and c.da_thu_thap) as da_thu_thap,
            count(*) filter (where not c.la_nhom_1_2 and not c.da_thu_thap) as con_thieu,
            count(*) filter (where not c.la_nhom_1_2 and c.co_nhap and not c.da_thu_thap) as da_nhap_chua_dat,
            null::text as ghi_chu
        from public.nhom3_trang_thai_cache c
        left join public.danhsachxaphuong xp on xp.ma_xa = c.ma_xa
        left join public.nhom3_to_giam_sat tg on tg.ma_xa = c.ma_xa
        where p_to_giam_sat is null or tg.to_giam_sat = p_to_giam_sat
        group by c.ma_xa, xp.ten_xa, tg.khu_vuc, tg.to_giam_sat

        union all

        select g.ma_xa, xp.ten_xa, tg.khu_vuc, tg.to_giam_sat, 0, 0, 0, 0, 0, g.ghi_chu
        from public.nhom3_xa_ghi_chu g
        left join public.danhsachxaphuong xp on xp.ma_xa = g.ma_xa
        left join public.nhom3_to_giam_sat tg on tg.ma_xa = g.ma_xa
        where (p_to_giam_sat is null or tg.to_giam_sat = p_to_giam_sat)
          and not exists (
              select 1 from public.nhom3_trang_thai_cache c where c.ma_xa = g.ma_xa
          )
    )
    select jsonb_build_object(
        'tong', coalesce(sum(tong), 0),
        'da_nhom_1_2', coalesce(sum(da_nhom_1_2), 0),
        'da_thu_thap', coalesce(sum(da_thu_thap), 0),
        'con_thieu', coalesce(sum(con_thieu), 0),
        'da_nhap_chua_dat', coalesce(sum(da_nhap_chua_dat), 0),
        'theo_xa', coalesce(jsonb_agg(row_to_json(theo_xa) order by tong desc), '[]'::jsonb)
    )
    from theo_xa;
$$;

revoke all on function public.nhom3_tong_hop(integer) from public;
grant execute on function public.nhom3_tong_hop(integer) to service_role;
"""

MAPPING = {
    1: {
        "Tuy Hòa": ["22015", "22045", "22240"],
        "Đông Hòa": ["22258", "22261", "22291"],
        "Tuy An": ["22114", "22120", "22132", "22147", "22153"],
        "Buôn Đôn": ["24235", "24241", "24250"],
        "Ea Súp": ["24211", "24214", "24217", "24221", "24229"],
    },
    2: {
        "Phú Hòa": ["22303", "22319"],
        "Tây Hòa": ["22250", "22255", "22276", "22285"],
        "Cư Kuin": ["24540", "24544", "24561"],
        "Krông Ana": ["24538", "24559", "24568"],
        "Krông Bông": ["24448", "24454", "24472", "24478", "24484"],
        "Lắk": ["24580", "24595", "24598", "24604", "24607"],
    },
    3: {
        "Buôn Ma Thuột": ["24121", "24133", "24154", "24163", "24169", "24175"],
        "Buôn Hồ": ["24305", "24328", "24340"],
        "Cư M’gar": ["24259", "24265", "24277", "24280", "24286", "24301"],
        "Ea H’leo": ["24181", "24184", "24187", "24193", "24208"],
        "Krông Búk": ["24310", "24313", "24316"],
        "Krông Năng": ["24343", "24346", "24352", "24364"],
    },
    4: {
        "Sơn Hòa": ["22165", "22171", "22177", "22192"],
        "Sông Hinh": ["22207", "22222", "22225", "22237"],
        "Đồng Xuân": ["22081", "22090", "22096", "22111"],
        "Sông Cầu": ["22051", "22057", "22060", "22075", "22076"],
        "Krông Pắc": ["24490", "24496", "24502", "24505", "24526", "24529"],
        "Ea Kar": ["24373", "24376", "24400", "24403", "24406"],
        "M’Drắk": ["24412", "24415", "24433", "24436", "24444", "24445"],
    },
}


def main():
    rows = [
        (ma_xa, khu_vuc, to_so)
        for to_so, khu_vucs in MAPPING.items()
        for khu_vuc, xa_list in khu_vucs.items()
        for ma_xa in xa_list
    ]
    print(f"Tổng số xã trong MAPPING: {len(rows)}")

    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()

    print("1/3 Tạo bảng nhom3_to_giam_sat + cập nhật nhom3_tong_hop(p_to_giam_sat)...")
    cur.execute(SCHEMA_SQL)
    conn.commit()

    print("2/3 Đối chiếu với danhsachxaphuong (phải khớp 102/102, không thiếu không thừa)...")
    cur.execute("select ma_xa from public.danhsachxaphuong")
    all_xa = {r[0] for r in cur.fetchall()}
    mapped_xa = {r[0] for r in rows}
    thieu = sorted(all_xa - mapped_xa)
    thua = sorted(mapped_xa - all_xa)
    if thieu or thua:
        print("  !! LỆCH DỮ LIỆU — xã chưa map:", thieu, "| xã map thừa (không có trong danhsachxaphuong):", thua)
        print("  Dừng lại, không seed — kiểm tra lại MAPPING trước khi chạy lại.")
        cur.close()
        conn.close()
        return 1
    print(f"  OK — khớp đủ {len(all_xa)}/{len(all_xa)} xã.")

    print("3/3 Seed bảng nhom3_to_giam_sat...")
    psycopg2.extras.execute_values(
        cur,
        """insert into public.nhom3_to_giam_sat (ma_xa, khu_vuc, to_giam_sat) values %s
           on conflict (ma_xa) do update set khu_vuc = excluded.khu_vuc, to_giam_sat = excluded.to_giam_sat""",
        rows,
    )
    conn.commit()

    cur.execute("select to_giam_sat, count(*) from public.nhom3_to_giam_sat group by to_giam_sat order by to_giam_sat")
    for row in cur.fetchall():
        print(" ", row)

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
