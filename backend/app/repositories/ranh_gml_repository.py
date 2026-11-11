"""Thửa đất giao với ranh do người dùng gửi lên — phục vụ Ranh_GML_Tool
(tool desktop xuất GML + Excel theo ranh, chạy ở máy KHÔNG kết nối được
CSDL nên phải gọi qua web).

Chỉ đọc. Ranh đi vào câu truy vấn dưới dạng jsonb tham số; PostGIS tính
phần chồng lấn, trạng thái từng thửa (cùng quy ước trang Nhóm 3) và trả
hình học thửa dạng GeoJSON EPSG:4326 để tool tự ghi GML VN-2000.
"""
from __future__ import annotations

import json

from .supabase_client import _CursorCtx

TT_UNG_THUA = "Nhóm 1 ứng thửa"
TT_NHOM12 = "Nhóm 1/2"
TT_N3_CO_DL = "Nhóm 3 - đã có dữ liệu"
TT_N3_THIEU = "Nhóm 3 - còn thiếu"
TT_NGOAI_DS = "Ngoài DS gửi xã"

_SQL = """
with vung as (
    select (v->>'stt')::int stt,
           ST_Subdivide(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(v->>'g'), 4326)), 256) g
    from jsonb_array_elements(%(vung)s::jsonb) v
),
cham as (
    select p.ma_xa, p.so_to, p.so_thua, v.stt,
           sum(ST_Area(ST_Intersection(ST_MakeValid(p.geom), v.g)::geography)) dt
    from public.thua_dat p
    join vung v on p.geom && v.g and ST_Intersects(p.geom, v.g)
    group by 1, 2, 3, 4
),
thua as (
    select distinct on (ma_xa, so_to, so_thua) ma_xa, so_to, so_thua, stt,
           sum(dt) over (partition by ma_xa, so_to, so_thua) dt_tong
    from cham
    order by ma_xa, so_to, so_thua, dt desc
)
select t.stt vung_stt, t.ma_xa, coalesce(d.ten_xa, '') ten_xa, t.so_to, t.so_thua,
       coalesce(p.ma_thua_dat, '') ma_thua_dat, coalesce(p.muc_dich_su_dung, '') loai_dat,
       coalesce(p.dien_tich, 0)::float8 dien_tich,
       coalesce(p.ten_chu_dk, '') ten_chu_dk, coalesce(p.ten_chu, '') ten_chu_sd, coalesce(p.dia_chi, '') dia_chi,
       coalesce((select r.ten_thon from public.ranh_gioi_thon r
                 where r.ma_xa = t.ma_xa and ST_Contains(r.geom, ST_PointOnSurface(p.geom)) limit 1), '') thon,
       round(t.dt_tong::numeric, 2)::float8 dt_chong_lan, round(ST_Area(p.geom::geography)::numeric, 2)::float8 dt_hinh_thua,
       case when k.ma_xa is not null then %(tt_ung)s
            when coalesce(c.la_nhom_1_2, false) then %(tt_n12)s
            when n.ma_xa is null then %(tt_ngoai)s
            when coalesce(c.da_thu_thap, false) or coalesce(c.co_nhap, false) then %(tt_codl)s
            else %(tt_thieu)s end trang_thai,
       ST_AsGeoJSON(p.geom, 9)::jsonb geometry
from thua t
join public.thua_dat p using (ma_xa, so_to, so_thua)
left join public.danhsachxaphuong d using (ma_xa)
left join (select distinct ma_xa, so_to, so_thua from public.nhom3_tham_chieu_khong_gian) k using (ma_xa, so_to, so_thua)
left join public.nhom3_can_thu_thap n using (ma_xa, so_to, so_thua)
left join public.nhom3_trang_thai_cache c using (ma_xa, so_to, so_thua)
order by t.ma_xa, t.so_to, t.so_thua
limit %(gioi_han)s
"""


def thua_giao_ranh(vung: list[dict], gioi_han: int, timeout_s: int = 90) -> list[dict]:
    """Ném psycopg2.Error nếu truy vấn lỗi (caller đổi thành response)."""
    with _CursorCtx(timeout=timeout_s) as cur:
        cur.execute("set transaction read only")
        cur.execute(_SQL, {
            "vung": json.dumps(vung), "gioi_han": gioi_han,
            "tt_ung": TT_UNG_THUA, "tt_n12": TT_NHOM12, "tt_ngoai": TT_NGOAI_DS,
            "tt_codl": TT_N3_CO_DL, "tt_thieu": TT_N3_THIEU,
        })
        return [dict(r) for r in cur.fetchall()]

