from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from gml_reader import read_gml, rows_from_geojson, write_geojson


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_GML = BASE_DIR / "data" / "Thua_Dat.gml"
DEFAULT_OUTPUT = BASE_DIR / "data" / "thua_dat_4326.geojson"


def upload_rows(rows: list[dict], batch_size: int = 100) -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("Thiếu DATABASE_URL trong backend/.env")

    # Gọi thẳng hàm Postgres public.upsert_thua_dat_diff (xem
    # supabase/schema.sql) — cùng hàm mà backend Flask dùng cho luồng nhập
    # GML qua web (app/services/import_service.py), nên hành vi upsert
    # (insert thửa mới, cập nhật thửa đổi hình học/thuộc tính) giống hệt.
    conn = psycopg2.connect(database_url)
    try:
        with conn, conn.cursor() as cur:
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                cur.execute(
                    "select public.upsert_thua_dat_diff(%s::jsonb)",
                    (psycopg2.extras.Json(batch),),
                )
                print(f"Đã nhập {min(start + len(batch), len(rows))}/{len(rows)} thửa")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Nhập GML thửa đất vào Supabase")
    parser.add_argument("--gml", default=str(DEFAULT_GML))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()

    data = read_gml(args.gml)
    write_geojson(data, args.output)
    print(f"Đã đọc {len(data['features'])} thửa; GeoJSON: {args.output}")

    if not args.export_only:
        upload_rows(rows_from_geojson(data))
        print("Hoàn tất nhập dữ liệu Supabase.")


if __name__ == "__main__":
    main()
