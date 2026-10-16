"""Áp trực tiếp lên DB: thêm tính năng "trả lại nguyên trạng" (revert) cho
thửa Nhóm 3 đã bị đánh dấu "thuộc dự án" qua luu_ranh_du_an_va_danh_dau_nhom3.

Vấn đề trước đây: hàm đó CHỈ set thuoc_du_an = true, không bao giờ set lại
false — và không lưu lại thửa nào do RANH DỰ ÁN nào đánh dấu, nên không thể
gỡ đánh dấu riêng cho 1 ranh dự án cụ thể (vd. vẽ nhầm ranh, chọn nhầm file)
mà không ảnh hưởng tới ranh dự án khác.

Bổ sung:
1. Bảng public.nhom3_du_an_danh_dau — ghi lại CHÍNH XÁC ranh dự án nào đã
   đánh dấu thửa nào (ranh_du_an_id, ma_xa, so_to, so_thua).
2. Cột public.ranh_du_an.da_huy/huy_luc — đánh dấu 1 ranh dự án đã được trả
   lại nguyên trạng (không xoá, giữ lịch sử).
3. Cập nhật luu_ranh_du_an_va_danh_dau_nhom3 — vẫn CHỈ set true như cũ,
   nhưng giờ ghi thêm dòng theo dõi vào nhom3_du_an_danh_dau.
4. Hàm mới huy_danh_dau_du_an_nhom3(p_ranh_du_an_id) — gỡ đánh dấu
   thuoc_du_an = false cho thửa CHỈ thuộc ranh này (thửa còn giao với 1 ranh
   dự án KHÁC chưa huỷ thì vẫn giữ nguyên thuoc_du_an = true), xoá dòng theo
   dõi của ranh này, đánh dấu ranh đã huỷ.
5. Hàm mới danh_sach_ranh_du_an() — liệt kê ranh dự án đã lưu kèm số thửa
   đang bị đánh dấu bởi ranh đó, cho GUI chọn để trả lại nguyên trạng.
6. Backfill nhom3_du_an_danh_dau cho các ranh dự án đã lưu TRƯỚC KHI có bảng
   này (dựa vào thửa hiện đang thuoc_du_an=true + giao >=95% diện tích với
   ranh — đúng tiêu chí hàm luu_ranh_du_an_va_danh_dau_nhom3 vẫn dùng, không
   đổi). Chạy 1 lần, idempotent (on conflict do nothing)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SCHEMA_SQL = """
alter table public.ranh_du_an
    add column if not exists da_huy boolean not null default false,
    add column if not exists huy_luc timestamptz;

create table if not exists public.nhom3_du_an_danh_dau (
    ranh_du_an_id bigint not null references public.ranh_du_an(id) on delete cascade,
    ma_xa text not null,
    so_to integer not null,
    so_thua integer not null,
    danh_dau_luc timestamptz not null default now(),
    primary key (ranh_du_an_id, ma_xa, so_to, so_thua)
);

alter table public.nhom3_du_an_danh_dau enable row level security;

create index if not exists idx_nhom3_du_an_danh_dau_thua
    on public.nhom3_du_an_danh_dau (ma_xa, so_to, so_thua);

create or replace function public.luu_ranh_du_an_va_danh_dau_nhom3(
    p_ten text,
    p_geom_geojson text,
    p_nguon_file text default null,
    p_nguong_ty_le numeric default 95
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
set statement_timeout = '120s'
as $$
declare
    v_ranh geometry;
    v_ranh_id bigint;
    v_so_polygon integer;
    v_so_danh_dau integer;
begin
    if p_ten is null or trim(p_ten) = '' then
        raise exception 'Thiếu tên dự án';
    end if;
    if p_geom_geojson is null or trim(p_geom_geojson) = '' then
        raise exception 'Thiếu geometry ranh dự án';
    end if;

    begin
        v_ranh := ST_CollectionExtract(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(p_geom_geojson), 4326)), 3);
    exception when others then
        raise exception 'Ranh dự án không đọc được (GeoJSON lỗi): %', sqlerrm;
    end;

    if v_ranh is null or ST_IsEmpty(v_ranh) then
        raise exception 'Ranh dự án rỗng hoặc không có phần diện tích (polygon) sau khi xử lý';
    end if;

    v_so_polygon := ST_NumGeometries(ST_Multi(v_ranh));

    insert into public.ranh_du_an (ten, geom, so_polygon, nguon_file)
    values (trim(p_ten), ST_Multi(v_ranh), v_so_polygon, p_nguon_file)
    returning id into v_ranh_id;

    -- Không lọc "not n3.thuoc_du_an" ở đây nữa (khác bản cũ) — cần biết
    -- TOÀN BỘ thửa giao đủ ngưỡng với ranh này để ghi vào
    -- nhom3_du_an_danh_dau, kể cả thửa đã thuộc 1 ranh dự án khác từ trước.
    with giao as (
        select
            t.ma_xa, t.so_to, t.so_thua,
            ST_Area(t.geom::geography) as dien_tich_thua_m2,
            ST_Area(ST_Intersection(ST_MakeValid(t.geom), v_ranh)::geography) as dien_tich_giao_m2
        from public.thua_dat t
        join public.nhom3_can_thu_thap n3
            on n3.ma_xa = t.ma_xa and n3.so_to = t.so_to and n3.so_thua = t.so_thua
        where ST_Intersects(t.geom, v_ranh)
    ),
    du_an as (
        select ma_xa, so_to, so_thua
        from giao
        where dien_tich_thua_m2 > 0
          and (dien_tich_giao_m2 / dien_tich_thua_m2 * 100) >= p_nguong_ty_le
    )
    insert into public.nhom3_du_an_danh_dau (ranh_du_an_id, ma_xa, so_to, so_thua)
    select v_ranh_id, ma_xa, so_to, so_thua from du_an
    on conflict do nothing;

    update public.nhom3_can_thu_thap n3
    set thuoc_du_an = true
    from (
        select ma_xa, so_to, so_thua from public.nhom3_du_an_danh_dau where ranh_du_an_id = v_ranh_id
    ) du_an
    where n3.ma_xa = du_an.ma_xa and n3.so_to = du_an.so_to and n3.so_thua = du_an.so_thua
      and not n3.thuoc_du_an;

    get diagnostics v_so_danh_dau = row_count;

    return jsonb_build_object(
        'ranh_du_an_id', v_ranh_id,
        'ten', trim(p_ten),
        'so_polygon', v_so_polygon,
        'so_thua_danh_dau', v_so_danh_dau
    );
end;
$$;

revoke all on function public.luu_ranh_du_an_va_danh_dau_nhom3(text, text, text, numeric) from public;
grant execute on function public.luu_ranh_du_an_va_danh_dau_nhom3(text, text, text, numeric) to service_role;

-- Trả lại nguyên trạng ban đầu cho thửa Nhóm 3 do 1 ranh dự án đánh dấu —
-- CHỈ gỡ thuoc_du_an = false cho thửa KHÔNG còn bị ranh dự án nào khác
-- (chưa huỷ) đánh dấu, để không ảnh hưởng tới ranh dự án khác cùng giao
-- tới thửa đó. Không xoá public.ranh_du_an — chỉ đánh dấu da_huy = true để
-- giữ lịch sử (biết đã từng nạp + đã trả lại).
create or replace function public.huy_danh_dau_du_an_nhom3(p_ranh_du_an_id bigint)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
set statement_timeout = '60s'
as $$
declare
    v_ten text;
    v_da_huy boolean;
    v_so_go integer;
begin
    select ten, da_huy into v_ten, v_da_huy
    from public.ranh_du_an where id = p_ranh_du_an_id;

    if v_ten is null then
        raise exception 'Không tìm thấy ranh dự án id %', p_ranh_du_an_id;
    end if;
    if v_da_huy then
        raise exception 'Ranh dự án "%" đã được trả lại nguyên trạng trước đó', v_ten;
    end if;

    with cua_ranh_nay as (
        select ma_xa, so_to, so_thua
        from public.nhom3_du_an_danh_dau
        where ranh_du_an_id = p_ranh_du_an_id
    ),
    con_ranh_khac as (
        select distinct d.ma_xa, d.so_to, d.so_thua
        from public.nhom3_du_an_danh_dau d
        join public.ranh_du_an r on r.id = d.ranh_du_an_id
        join cua_ranh_nay c
            on c.ma_xa = d.ma_xa and c.so_to = d.so_to and c.so_thua = d.so_thua
        where d.ranh_du_an_id <> p_ranh_du_an_id
          and not r.da_huy
    ),
    chi_ranh_nay as (
        select ma_xa, so_to, so_thua from cua_ranh_nay
        except
        select ma_xa, so_to, so_thua from con_ranh_khac
    )
    update public.nhom3_can_thu_thap n3
    set thuoc_du_an = false
    from chi_ranh_nay c
    where n3.ma_xa = c.ma_xa and n3.so_to = c.so_to and n3.so_thua = c.so_thua;

    get diagnostics v_so_go = row_count;

    delete from public.nhom3_du_an_danh_dau where ranh_du_an_id = p_ranh_du_an_id;

    update public.ranh_du_an set da_huy = true, huy_luc = now() where id = p_ranh_du_an_id;

    return jsonb_build_object(
        'ranh_du_an_id', p_ranh_du_an_id,
        'ten', v_ten,
        'so_thua_go_danh_dau', v_so_go
    );
end;
$$;

revoke all on function public.huy_danh_dau_du_an_nhom3(bigint) from public;
grant execute on function public.huy_danh_dau_du_an_nhom3(bigint) to service_role;

-- Liệt kê ranh dự án đã lưu (kể cả đã huỷ) kèm số thửa hiện đang bị đánh
-- dấu bởi ranh đó — cho GUI tool desktop chọn để trả lại nguyên trạng.
create or replace function public.danh_sach_ranh_du_an()
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
as $$
    select coalesce(jsonb_agg(row_to_json(t) order by t.tao_luc desc), '[]'::jsonb)
    from (
        select
            r.id as ranh_du_an_id,
            r.ten,
            r.nguon_file,
            r.so_polygon,
            r.tao_luc,
            r.da_huy,
            r.huy_luc,
            (select count(*) from public.nhom3_du_an_danh_dau d where d.ranh_du_an_id = r.id)::int
                as so_thua_dang_danh_dau
        from public.ranh_du_an r
    ) t;
$$;

revoke all on function public.danh_sach_ranh_du_an() from public;
grant execute on function public.danh_sach_ranh_du_an() to service_role;
"""

BACKFILL_SQL = """
insert into public.nhom3_du_an_danh_dau (ranh_du_an_id, ma_xa, so_to, so_thua)
select r.id, t.ma_xa, t.so_to, t.so_thua
from public.ranh_du_an r
join public.thua_dat t on ST_Intersects(t.geom, r.geom)
join public.nhom3_can_thu_thap n3
    on n3.ma_xa = t.ma_xa and n3.so_to = t.so_to and n3.so_thua = t.so_thua
where n3.thuoc_du_an
  and ST_Area(t.geom::geography) > 0
  and (ST_Area(ST_Intersection(ST_MakeValid(t.geom), r.geom)::geography)
       / ST_Area(t.geom::geography) * 100) >= 95
on conflict do nothing;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()

    print("1/3 Tạo bảng nhom3_du_an_danh_dau + cột ranh_du_an.da_huy/huy_luc + "
          "cập nhật luu_ranh_du_an_va_danh_dau_nhom3 + hàm mới huy_danh_dau_du_an_nhom3/"
          "danh_sach_ranh_du_an...")
    cur.execute(SCHEMA_SQL)
    conn.commit()

    print("2/3 Backfill nhom3_du_an_danh_dau cho ranh dự án đã lưu trước đó "
          "(dựa vào thửa đang thuoc_du_an=true + giao >=95%)...")
    cur.execute(BACKFILL_SQL)
    print(f"   -> đã ghi {cur.rowcount} dòng theo dõi")
    conn.commit()

    print("3/3 Kiểm tra lại:")
    cur.execute(
        "select r.id, r.ten, r.da_huy, count(d.*) as so_thua_dang_danh_dau "
        "from public.ranh_du_an r left join public.nhom3_du_an_danh_dau d on d.ranh_du_an_id = r.id "
        "group by r.id, r.ten, r.da_huy order by r.id"
    )
    for row in cur.fetchall():
        print(" ", row)

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
