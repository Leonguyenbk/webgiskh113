"""Áp trực tiếp lên DB: tách "tổng gửi xã" thành 2 cột rõ ràng theo yêu
cầu người dùng, thay vì gộp 1 cột như bản trước:

1. nhom3_tong_hop(): "tong"/"con_thieu" CHỈ trừ Nhóm 1/2 Chi nhánh KV
   chưa nhập (không trừ chưa liên kết không gian nữa) — cột tổng (A).
   Thêm "tong_tru_kg" = tong đã trừ thêm chua_lien_ket_khong_gian — cột
   tổng (B), dùng cho tỷ lệ thứ 2.

2. Hàm mới nhom3_list_tong_gui_xa(p_ma_xa, p_limit, p_offset) — danh sách
   phân trang đúng phạm vi cột "tong" (A) kèm ghi chú trạng thái từng
   thửa (Nhóm 1 - đã nhập biểu / Nhóm 3 - đã nhập biểu / Nhóm 3 - còn
   thiếu), dùng cho nút Excel DUY NHẤT trên trang /nhom-3-con-thieu (thay
   cho 3 nút Excel/Nhóm 1 đã nhập/Nhóm 1 chưa nhập cũ).

Chạy 1 lần, idempotent (CREATE OR REPLACE)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SCHEMA_SQL = r"""
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
            coalesce(kg.so_luong, 0) as chua_lien_ket_khong_gian
        from public.nhom3_trang_thai_cache c
        left join public.danhsachxaphuong xp on xp.ma_xa = c.ma_xa
        left join public.nhom3_to_giam_sat tg on tg.ma_xa = c.ma_xa
        left join public.nhom3_chua_lien_ket_khong_gian kg on kg.ma_xa = c.ma_xa
        where p_to_giam_sat is null or tg.to_giam_sat = p_to_giam_sat
        group by c.ma_xa, xp.ten_xa, tg.khu_vuc, tg.to_giam_sat, kg.so_luong
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
            null::text as ghi_chu
        from raw

        union all

        select g.ma_xa, xp.ten_xa, tg.khu_vuc, tg.to_giam_sat, 0, 0, 0, 0, 0, 0, 0, 0, 0, g.ghi_chu
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
        'theo_xa', coalesce(jsonb_agg(row_to_json(theo_xa) order by tong desc), '[]'::jsonb)
    )
    from theo_xa;
$$;

revoke all on function public.nhom3_tong_hop(integer) from public;
grant execute on function public.nhom3_tong_hop(integer) to service_role;

create or replace function public.nhom3_list_tong_gui_xa(
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
      and not (c.la_nhom_1_2 and not c.co_nhap);

    select coalesce(jsonb_agg(row_to_json(y)), '[]'::jsonb) into v_items
    from (
        select
            c.ma_xa, xp.ten_xa, c.so_to, c.so_thua, c.ma_dinh_danh,
            case
                when c.la_nhom_1_2 then 'Nhóm 1 - đã nhập biểu'
                when c.da_thu_thap then 'Nhóm 3 - đã nhập biểu'
                else 'Nhóm 3 - còn thiếu'
            end as ghi_chu
        from public.nhom3_trang_thai_cache c
        left join public.danhsachxaphuong xp on xp.ma_xa = c.ma_xa
        where (p_ma_xa is null or c.ma_xa = p_ma_xa)
          and not (c.la_nhom_1_2 and not c.co_nhap)
        order by c.ma_xa, c.so_to, c.so_thua
        limit p_limit offset p_offset
    ) y;

    return jsonb_build_object('total', v_total, 'items', v_items);
end;
$$;

revoke all on function public.nhom3_list_tong_gui_xa(text, integer, integer) from public;
grant execute on function public.nhom3_list_tong_gui_xa(text, integer, integer) to service_role;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()

    print("Ap dung nhom3_tong_hop (2 cot tong tach rieng) + nhom3_list_tong_gui_xa...")
    cur.execute(SCHEMA_SQL)
    conn.commit()

    cur.execute("select public.nhom3_tong_hop(null)")
    ket_qua = cur.fetchone()[0]
    for key in ("tong", "tong_tru_kg", "da_nhom_1_2_da_nhap", "da_nhom_1_2_chua_nhap",
                "da_thu_thap", "con_thieu", "chua_lien_ket_khong_gian"):
        print(f"   {key}: {ket_qua.get(key)}")

    cur.execute("select public.nhom3_list_tong_gui_xa('24250', 3, 0)")
    print("   mau nhom3_list_tong_gui_xa (Ea Nuol):", cur.fetchone()[0])

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
