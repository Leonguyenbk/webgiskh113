"""Áp trực tiếp lên DB: thêm lớp "Bản đồ đăng ký" vào bảng ban_do_nen —
cột loai ('dia_chinh' mặc định cho mọi tờ cũ | 'dang_ky'), khoá duy nhất
đổi thành (loai, ma_xa, so_to), 3 hàm register/in_view/by_ma_xa_so_to thêm
tham số p_loai mặc định 'dia_chinh' (code cũ gọi không truyền p_loai vẫn
chạy y như trước). Khớp supabase/schema.sql. Không xoá/sửa dữ liệu cũ.
Chạy 1 lần, idempotent, 1 transaction (lỗi giữa chừng thì không đổi gì)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SQL = r"""
alter table public.ban_do_nen
    add column if not exists loai text not null default 'dia_chinh';
alter table public.ban_do_nen drop constraint if exists ban_do_nen_loai_check;
alter table public.ban_do_nen
    add constraint ban_do_nen_loai_check check (loai in ('dia_chinh', 'dang_ky'));
alter table public.ban_do_nen drop constraint if exists ban_do_nen_ma_xa_so_to_key;
alter table public.ban_do_nen drop constraint if exists ban_do_nen_loai_ma_xa_so_to_key;
alter table public.ban_do_nen
    add constraint ban_do_nen_loai_ma_xa_so_to_key unique (loai, ma_xa, so_to);

-- API duy nhất mà Tool Windows gọi để hoàn tất đăng ký 1 tờ — CHỈ gọi sau
-- khi Tool đã upload xong 100% tile (WebGIS không tự biết tiến độ upload,
-- tin tưởng Tool chỉ gọi khi đã xong). Upsert theo (loai, ma_xa, so_to):
-- tờ đã có thì cập nhật geom/tile_url/tile_version mới (đúng chiều tăng
-- tile_version mỗi lần Tool xử lý lại — cache-busting). p_loai: 'dia_chinh'
-- (mặc định, Tool gửi lên /api/...) hoặc 'dang_ky' (Tool đặt URL server có
-- tiền tố /ban-do-dang-ky — xem ban_do_nen_routes.py).
drop function if exists public.register_ban_do_nen(
    text, integer, jsonb, text, integer, integer, integer, text
);
drop function if exists public.register_ban_do_nen(
    text, text, jsonb, text, integer, integer, integer, text
);
create or replace function public.register_ban_do_nen(
    p_ma_xa text,
    p_so_to text,
    p_geom_geojson jsonb,
    p_tile_url text,
    p_tile_version integer,
    p_min_zoom integer default null,
    p_max_zoom integer default null,
    p_ghi_chu text default null,
    p_loai text default 'dia_chinh'
)
returns bigint
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    result_id bigint;
begin
    insert into public.ban_do_nen (
        loai, ma_xa, so_to, geom, tile_url, tile_version, min_zoom, max_zoom, ghi_chu, trang_thai
    ) values (
        coalesce(p_loai, 'dia_chinh'), p_ma_xa, p_so_to,
        ST_SetSRID(ST_GeomFromGeoJSON(p_geom_geojson::text), 4326),
        p_tile_url, p_tile_version, p_min_zoom, p_max_zoom, p_ghi_chu, 'ready'
    )
    on conflict (loai, ma_xa, so_to) do update set
        geom = excluded.geom,
        tile_url = excluded.tile_url,
        tile_version = excluded.tile_version,
        min_zoom = excluded.min_zoom,
        max_zoom = excluded.max_zoom,
        ghi_chu = coalesce(excluded.ghi_chu, public.ban_do_nen.ghi_chu),
        trang_thai = 'ready',
        updated_at = now()
    returning id into result_id;
    return result_id;
end;
$$;

revoke all on function public.register_ban_do_nen(text, text, jsonb, text, integer, integer, integer, text, text) from public;
grant execute on function public.register_ban_do_nen(text, text, jsonb, text, integer, integer, integer, text, text) to service_role;

-- Lấy các tờ bản đồ (đúng loại p_loai) giao khung nhìn hiện tại — dùng cho
-- tile loader (viewport) và lớp ranh+nhãn trên bản đồ chính. Mặc định chỉ
-- trả tờ đã 'ready' và đang kich_hoat; p_include_all=true dùng cho trang
-- quản trị.
drop function if exists public.get_ban_do_nen_in_view(
    double precision, double precision, double precision, double precision, boolean
);
create or replace function public.get_ban_do_nen_in_view(
    p_west double precision,
    p_south double precision,
    p_east double precision,
    p_north double precision,
    p_include_all boolean default false,
    p_loai text default 'dia_chinh'
)
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
as $$
    select jsonb_build_object(
        'type', 'FeatureCollection',
        'features', coalesce(jsonb_agg(feature), '[]'::jsonb)
    )
    from (
        select jsonb_build_object(
            'type', 'Feature',
            'id', b.id,
            'geometry', ST_AsGeoJSON(b.geom)::jsonb,
            'properties', jsonb_build_object(
                'id', b.id,
                'loai', b.loai,
                'ma_xa', b.ma_xa,
                'so_to', b.so_to,
                'tile_url', b.tile_url,
                'tile_version', b.tile_version,
                'min_zoom', b.min_zoom,
                'max_zoom', b.max_zoom,
                'ghi_chu', b.ghi_chu,
                'trang_thai', b.trang_thai,
                'updated_at', b.updated_at
            )
        ) as feature
        from public.ban_do_nen b
        where b.geom && ST_MakeEnvelope(p_west, p_south, p_east, p_north, 4326)
          and b.loai = coalesce(p_loai, 'dia_chinh')
          and (p_include_all or (b.trang_thai = 'ready' and b.kich_hoat))
        order by b.so_to
    ) features;
$$;

revoke all on function public.get_ban_do_nen_in_view(double precision, double precision, double precision, double precision, boolean, text) from public;
grant execute on function public.get_ban_do_nen_in_view(double precision, double precision, double precision, double precision, boolean, text) to service_role;

-- Tra cứu tờ bản đồ (đúng loại p_loai) theo mã xã (+ số tờ tùy chọn) — dùng
-- cho ô tìm kiếm trên bản đồ chính và trang quản trị, không lọc theo khung
-- nhìn/trạng thái.
drop function if exists public.get_ban_do_nen_by_ma_xa_so_to(text, integer);
drop function if exists public.get_ban_do_nen_by_ma_xa_so_to(text, text);
create or replace function public.get_ban_do_nen_by_ma_xa_so_to(
    p_ma_xa text,
    p_so_to text default null,
    p_loai text default 'dia_chinh'
)
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
as $$
    select jsonb_build_object(
        'type', 'FeatureCollection',
        'features', coalesce(jsonb_agg(feature), '[]'::jsonb)
    )
    from (
        select jsonb_build_object(
            'type', 'Feature',
            'id', b.id,
            'geometry', ST_AsGeoJSON(b.geom)::jsonb,
            'properties', jsonb_build_object(
                'id', b.id,
                'loai', b.loai,
                'ma_xa', b.ma_xa,
                'so_to', b.so_to,
                'tile_url', b.tile_url,
                'tile_version', b.tile_version,
                'min_zoom', b.min_zoom,
                'max_zoom', b.max_zoom,
                'ghi_chu', b.ghi_chu,
                'trang_thai', b.trang_thai,
                'updated_at', b.updated_at
            )
        ) as feature
        from public.ban_do_nen b
        where b.ma_xa = p_ma_xa
          and b.loai = coalesce(p_loai, 'dia_chinh')
          and (p_so_to is null or b.so_to = p_so_to)
    ) features;
$$;

revoke all on function public.get_ban_do_nen_by_ma_xa_so_to(text, text, text) from public;
grant execute on function public.get_ban_do_nen_by_ma_xa_so_to(text, text, text) to service_role;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    cur.execute(SQL)
    conn.commit()
    cur.execute("select loai, count(*) from public.ban_do_nen group by 1 order by 1")
    print("Da them lop Ban do dang ky. So to theo loai:", cur.fetchall())
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
