"""Áp trực tiếp lên DB: 3 thay đổi công thức "tổng danh sách gửi xuống" /
"đã làm" cho trang /nhom-3-con-thieu (yêu cầu người dùng):

1. refresh_nhom3_trang_thai_cache(): trước đây thửa thuộc ranh dự án
   (thuoc_du_an) hoặc chưa có hình học trên bản đồ (chưa nhập GML) bị
   loại THẲNG khỏi cache, dù xã đã lỡ nhập biểu cho thửa đó. Giờ NGOẠI LỆ:
   nếu xã ĐÃ nhập biểu (co_nhap) cho đúng thửa đó thì vẫn tính vào cache
   (tính vào tổng + tính luôn cho xã), chỉ loại khi KHÔNG có dữ liệu nhập.

2. Bảng mới nhom3_chua_lien_ket_khong_gian (ma_xa, so_luong) — số thửa
   "chưa liên kết không gian" do VPĐK cung cấp thủ công sau (không có số
   tờ/thửa cụ thể, chỉ 1 con số/xã), mặc định 0.

3. nhom3_tong_hop(): "tong" và "con_thieu" giờ trừ thêm
   da_nhom_1_2_chua_nhap (khối lượng Chi nhánh KV làm trực tiếp, không
   phải việc của xã) và chua_lien_ket_khong_gian (bảng mới ở trên) — chỉ
   còn đúng phần việc xã phải làm. Tỷ lệ "đã làm" ở tầng ứng dụng vì vậy
   tính lại = (da_nhom_1_2_da_nhap + da_thu_thap) / tong (mới).

Chạy 1 lần, idempotent (CREATE OR REPLACE + CREATE TABLE IF NOT EXISTS),
rồi gọi refresh_nhom3_trang_thai_cache() để áp ngay cho dữ liệu hiện có."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SCHEMA_SQL = r"""
create table if not exists public.nhom3_chua_lien_ket_khong_gian (
    ma_xa text primary key,
    so_luong integer not null default 0 check (so_luong >= 0),
    ghi_chu text,
    cap_nhat_luc timestamptz not null default now()
);
alter table public.nhom3_chua_lien_ket_khong_gian enable row level security;

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
    left join public.thua_dat p
        on p.ma_xa = t.ma_xa and p.so_to = t.so_to and p.so_thua = t.so_thua
    left join public.nhom3_xa_ghi_chu gc
        on gc.ma_xa = t.ma_xa
    left join nhom12_keys n12
        on n12.ma_xa = t.ma_xa and n12.so_to = t.so_to and n12.so_thua = t.so_thua
    left join gcn_any_keys a
        on a.madvhc_soto_sothua = t.ma_xa || '_' || t.so_to::text || '_' || t.so_thua::text
    where gc.ma_xa is null
      and (
            (not t.thuoc_du_an and p.ma_xa is not null)
            or a.madvhc_soto_sothua is not null
          )
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
            (tong_cache - da_nhom_1_2_chua_nhap - chua_lien_ket_khong_gian) as tong,
            da_nhom_1_2, da_nhom_1_2_da_nhap, da_nhom_1_2_chua_nhap,
            da_thu_thap,
            (con_thieu_cache - chua_lien_ket_khong_gian) as con_thieu,
            da_nhap_chua_dat,
            chua_lien_ket_khong_gian,
            null::text as ghi_chu
        from raw

        union all

        select g.ma_xa, xp.ten_xa, tg.khu_vuc, tg.to_giam_sat, 0, 0, 0, 0, 0, 0, 0, 0, g.ghi_chu
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

    print("1/2 Tạo bảng nhom3_chua_lien_ket_khong_gian + cập nhật "
          "refresh_nhom3_trang_thai_cache/nhom3_tong_hop...")
    cur.execute(SCHEMA_SQL)
    conn.commit()

    print("2/2 Refresh cache để áp ngay cho dữ liệu hiện có (có thể mất ~1-2 phút)...")
    cur.execute("select public.refresh_nhom3_trang_thai_cache()")
    print("   -> tong dong cache:", cur.fetchone()[0])
    conn.commit()

    cur.execute("select public.nhom3_tong_hop(null)")
    ket_qua = cur.fetchone()[0]
    for key in ("tong", "da_nhom_1_2", "da_nhom_1_2_da_nhap", "da_nhom_1_2_chua_nhap",
                "da_thu_thap", "con_thieu", "chua_lien_ket_khong_gian"):
        print(f"   {key}: {ket_qua.get(key)}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
