# Nạp (thay toàn bộ) ranh giới 102 xã/phường từ shapefile vào bảng
# public.ranh_gioi_xa — lớp "Ranh giới xã" trên bản đồ (GET /api/ranh-xa).
#
# Trước đây bản đồ chỉ có ranh THÔN (ranh_gioi_thon, mới ~22 xã) nên không
# thấy được ranh xã ở các xã chưa nhập ranh thôn.
#
# - Shapefile WGS84 (EPSG:4326), trường ma_xa/ten_xa/loai/sap_nhap/dtich_km2/dan_so.
# - Hình lỗi được sửa bằng ST_MakeValid; lưu thêm geom_hien_thi (rút gọn
#   ~5 m) để API trả nhẹ, geom gốc giữ nguyên để truy vấn chính xác.
# - Tô 4 màu (xã giáp nhau khác màu), ưu tiên giữ màu cũ trong ranh_xa_mau
#   của các xã đã có ranh thôn để 2 lớp cùng màu.
# - Chạy trong 1 transaction: lỗi giữa chừng thì bảng giữ nguyên bản cũ.
#
# Chạy: cd backend && .venv\Scripts\python.exe scripts\import_ranh_xa.py "<đường dẫn .shp>"
import json
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

import psycopg2  # noqa: E402
import shapefile  # noqa: E402

from app.config import Config  # noqa: E402
from app.services.ranh_xa_mau_service import to_mau  # noqa: E402

DDL = """
create table if not exists public.ranh_gioi_xa (
    ma_xa text primary key,
    ten_xa text not null,
    loai text,
    sap_nhap text,
    dtich_km2 numeric,
    dan_so integer,
    mau smallint,
    geom geometry(MultiPolygon, 4326) not null,
    geom_hien_thi geometry(MultiPolygon, 4326) not null,
    cap_nhat_luc timestamptz not null default now()
);
create index if not exists ranh_gioi_xa_geom_idx on public.ranh_gioi_xa using gist (geom);
"""


def main(shp_path: str) -> int:
    r = shapefile.Reader(shp_path, encoding="utf-8")
    recs = []
    for sr in r.iterShapeRecords():
        d = sr.record.as_dict()
        ma = str(d.get("ma_xa") or "").strip()
        if not ma or not sr.shape.points:
            raise SystemExit(f"Bản ghi thiếu mã xã hoặc hình rỗng: {d}")
        recs.append((ma, d))
    ma_list = [m for m, _ in recs]
    if len(set(ma_list)) != len(ma_list):
        raise SystemExit("Shapefile có mã xã trùng nhau")

    conn = psycopg2.connect(Config.DATABASE_URL)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute("select ma_xa from danhsachxaphuong")
            db_xa = {x[0] for x in cur.fetchall()}
            la = sorted(set(ma_list) - db_xa)
            if la:
                raise SystemExit(f"Mã xã không có trong danhsachxaphuong: {la}")

            cur.execute("delete from public.ranh_gioi_xa")
            for (ma, d), sr in zip(recs, r.iterShapes()):
                cur.execute(
                    """
                    with g as (
                        select ST_Multi(ST_CollectionExtract(ST_MakeValid(
                                   ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 3)) as geom
                    )
                    insert into public.ranh_gioi_xa
                        (ma_xa, ten_xa, loai, sap_nhap, dtich_km2, dan_so, geom, geom_hien_thi)
                    select %s, %s, %s, %s, %s, %s, g.geom,
                           ST_Multi(ST_CollectionExtract(ST_MakeValid(
                               ST_SimplifyPreserveTopology(g.geom, 0.00005)), 3))
                    from g
                    """,
                    (
                        json.dumps(sr.__geo_interface__),
                        ma,
                        (d.get("ten_xa") or "").strip(),
                        (d.get("loai") or "").strip() or None,
                        (d.get("sap_nhap") or "").strip() or None,
                        d.get("dtich_km2"),
                        d.get("dan_so"),
                    ),
                )

            # Xã giáp nhau (cho phép hở/chồng ~30 m do sai số số hoá).
            cur.execute(
                """
                select a.ma_xa, coalesce(array_agg(b.ma_xa) filter (where b.ma_xa is not null), '{}')
                from public.ranh_gioi_xa a
                left join public.ranh_gioi_xa b
                  on a.ma_xa <> b.ma_xa and ST_DWithin(a.geom_hien_thi, b.geom_hien_thi, 0.0003)
                group by a.ma_xa
                """
            )
            ke = {m: set(k) for m, k in cur.fetchall()}
            cur.execute("select ma_xa, mau from public.ranh_xa_mau")
            mau_cu = dict(cur.fetchall())
            mau = to_mau(ke, mau_cu)
            for m, c in mau.items():
                cur.execute("update public.ranh_gioi_xa set mau = %s where ma_xa = %s", (c, m))
            trung = sum(1 for m in ke for n in ke[m] if m < n and mau[m] == mau[n])

            cur.execute(
                """
                select count(*), sum(ST_NPoints(geom)), sum(ST_NPoints(geom_hien_thi)),
                       count(*) filter (where not ST_IsValid(geom)),
                       round(sum(ST_Area(geom::geography)) / 1e6),
                       round(sum(dtich_km2))
                from public.ranh_gioi_xa
                """
            )
            n, p_goc, p_ht, loi, dt, dt_shp = cur.fetchone()
            print(f"Đã nạp {n} xã/phường — {p_goc:,} điểm gốc, {p_ht:,} điểm hiển thị, hình lỗi còn lại: {loi}")
            print(f"Tổng diện tích tính từ hình: {dt:,} km² (theo thuộc tính shapefile: {dt_shp:,} km²)")
            print(f"Tô màu: {len(mau)} xã, cặp giáp nhau trùng màu: {trung}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__ or "Cần đường dẫn file .shp")
    sys.exit(main(sys.argv[1]))
