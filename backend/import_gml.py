from __future__ import annotations

import argparse
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from gml_reader import read_gml, write_geojson


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_GML = BASE_DIR / "data" / "Thua_Dat.gml"
DEFAULT_OUTPUT = BASE_DIR / "data" / "thua_dat_4326.geojson"


def rows_from_geojson(data: dict) -> list[dict]:
    rows = []
    for feature in data["features"]:
        props = feature["properties"]
        rows.append({**props, "geom": feature["geometry"]})
    return rows


def upload_rows(rows: list[dict], batch_size: int = 100) -> None:
    load_dotenv()
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not service_key:
        raise RuntimeError(
            "Thiếu SUPABASE_URL hoặc SUPABASE_SERVICE_ROLE_KEY trong backend/.env"
        )

    endpoint = f"{url}/rest/v1/thua_dat?on_conflict=ma_xa,so_to,so_thua"
    headers = {
        "apikey": service_key,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    if not service_key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {service_key}"

    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        response = requests.post(endpoint, headers=headers, json=batch, timeout=120)
        if not response.ok:
            raise RuntimeError(
                f"Supabase trả lỗi {response.status_code}: {response.text}"
            )
        print(f"Đã nhập {min(start + len(batch), len(rows))}/{len(rows)} thửa")


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
