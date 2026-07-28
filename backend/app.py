from __future__ import annotations

import os

import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from gml_reader import parse_gml_bytes, rows_from_geojson
from sync_reader import parse_sync_file


load_dotenv()
app = Flask(__name__)

frontend_url = os.getenv("FRONTEND_URL", "*")
allowed_origins = (
    "*"
    if frontend_url == "*"
    else [origin.strip() for origin in frontend_url.split(",") if origin.strip()]
)
CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

VIETBANDO_TILE_URL = os.getenv(
    "VIETBANDO_TILE_URL",
    "https://images.vietbando.com/ImageLoader/GetImage.ashx"
    "?Ver=2016&LayerIds=VBD&Y={y}&X={x}&Level={z}",
)


def supabase_headers() -> dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not key:
        raise RuntimeError("Thiếu SUPABASE_SERVICE_ROLE_KEY")

    headers = {"apikey": key}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "webgis-api",
        "environment": os.getenv("RENDER", "local"),
    }


def fetch_all_rows(
    base_url: str,
    table: str,
    params: dict,
    headers: dict,
    requested_limit: int,
    page_size: int = 1000,
) -> list[dict]:
    # Supabase giới hạn "Max Rows" mặc định 1000 dòng/request bất kể limit
    # truyền vào, nên phải phân trang bằng header Range để lấy hết dữ liệu.
    rows = []
    start = 0
    while len(rows) < requested_limit:
        end = start + page_size - 1
        page_headers = {**headers, "Range-Unit": "items", "Range": f"{start}-{end}"}
        response = requests.get(
            f"{base_url}/rest/v1/{table}",
            headers=page_headers,
            params=params,
            timeout=60,
        )
        response.raise_for_status()
        page = response.json()
        rows.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return rows[:requested_limit]


SYNC_STATUS_FIELDS = [
    "da_xuat_so_dia_chinh_dien_tu",
    "chua_xuat_so_dia_chinh_dien_tu",
    "dong_bo_3_khoi",
    "khong_dong_bo_3_khoi",
    "chi_co_du_lieu_thuoc_tinh",
    "khop_csdlqg_dan_cu",
    "chua_khop_csdlqg_dan_cu",
    "khong_xac_dinh_csdlqg_dan_cu",
    "van_hanh_24_7",
    "khong_van_hanh_24_7",
    "phan_loai_ke_hoach_2959",
]


@app.get("/api/parcels")
def parcels():
    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        return jsonify({"error": "Thiếu SUPABASE_URL trong backend/.env"}), 500

    requested_limit = min(int(request.args.get("limit", 5000)), 50000)
    ma_xa = request.args.get("ma_xa", "").strip()

    parcel_params = {
        "select": "id,ma_xa,so_to,so_thua,muc_dich_su_dung,dien_tich,ten_chu,dia_chi,geom",
        "order": "so_to.asc,so_thua.asc",
    }
    sync_params = {
        "select": "ma_xa,so_to,so_thua," + ",".join(SYNC_STATUS_FIELDS),
        # Phân trang bằng header Range bắt buộc phải có order cố định,
        # nếu không Postgrest có thể trả thiếu/lặp dòng giữa các trang.
        "order": "ma_xa.asc,so_to.asc,so_thua.asc",
    }
    if ma_xa:
        parcel_params["ma_xa"] = f"eq.{ma_xa}"
        sync_params["ma_xa"] = f"eq.{ma_xa}"

    try:
        headers = supabase_headers()
        rows = fetch_all_rows(base_url, "thua_dat", parcel_params, headers, requested_limit)
        sync_rows = fetch_all_rows(base_url, "dong_bo_du_lieu", sync_params, headers, 50000)
    except (requests.RequestException, RuntimeError) as exc:
        return jsonify({"error": str(exc)}), 502

    def sync_key(record: dict) -> tuple:
        # ma_xa có thể lệch khoảng trắng/hoa-thường giữa dữ liệu GML và
        # CSV/Excel nhập tay, nên chuẩn hoá trước khi so khớp khóa.
        ma_xa_value = str(record.get("ma_xa") or "").strip().upper()
        return (ma_xa_value, record.get("so_to"), record.get("so_thua"))

    sync_by_key = {sync_key(row): row for row in sync_rows}

    features = []
    for row in rows:
        geometry = row.pop("geom", None)
        if not geometry:
            continue
        sync_info = sync_by_key.get(sync_key(row))
        row["dong_bo"] = {k: v for k, v in sync_info.items() if k not in ("ma_xa", "so_to", "so_thua")} if sync_info else None
        features.append(
            {
                "type": "Feature",
                "id": row.get("id"),
                "geometry": geometry,
                "properties": row,
            }
        )
    return jsonify({"type": "FeatureCollection", "features": features})


def upsert_to_supabase(
    base_url: str,
    table: str,
    on_conflict: str,
    resolution: str,
    rows: list[dict],
    batch_size: int = 200,
) -> int:
    # "ON CONFLICT DO UPDATE" (resolution=merge-duplicates) lỗi nếu cùng 1
    # câu lệnh có 2 dòng trùng khóa xung đột, nên phải loại trùng trước khi
    # gửi lên Supabase — giữ lại dòng xuất hiện sau cùng trong file nguồn.
    key_fields = [field.strip() for field in on_conflict.split(",")]
    deduped = {}
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        deduped[key] = row
    rows = list(deduped.values())

    headers = {
        **supabase_headers(),
        "Content-Type": "application/json",
        "Prefer": f"resolution={resolution},return=minimal",
    }
    endpoint = f"{base_url}/rest/v1/{table}?on_conflict={on_conflict}"
    imported = 0
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        response = requests.post(endpoint, headers=headers, json=batch, timeout=120)
        response.raise_for_status()
        imported += len(batch)
    return imported


def check_import_token() -> bool:
    import_token = os.getenv("IMPORT_TOKEN", "")
    return not import_token or request.headers.get("X-Import-Token", "") == import_token


@app.post("/api/import-gml")
def import_gml():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Thiếu file GML"}), 400

    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        return jsonify({"error": "Thiếu SUPABASE_URL trong backend/.env"}), 500

    try:
        data = parse_gml_bytes(uploaded.read())
    except Exception as exc:
        return jsonify({"error": f"Không đọc được file GML: {exc}"}), 400

    rows = rows_from_geojson(data)
    if not rows:
        return jsonify({"error": "File GML không có thửa đất hợp lệ"}), 400

    try:
        imported = upsert_to_supabase(
            base_url, "thua_dat", "ma_xa,so_to,so_thua", "ignore-duplicates", rows
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    except requests.RequestException as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return jsonify({"error": detail, "total": len(rows)}), 502

    return jsonify({"ok": True, "total": len(rows), "imported": imported})


@app.post("/api/import-dong-bo")
def import_dong_bo():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Thiếu file CSV/Excel"}), 400

    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        return jsonify({"error": "Thiếu SUPABASE_URL trong backend/.env"}), 500

    try:
        rows = parse_sync_file(uploaded.filename, uploaded.read())
    except Exception as exc:
        return jsonify({"error": f"Không đọc được file: {exc}"}), 400

    if not rows:
        return jsonify({"error": "File không có dòng dữ liệu hợp lệ"}), 400

    try:
        imported = upsert_to_supabase(
            base_url,
            "dong_bo_du_lieu",
            "ma_xa,so_to,so_thua",
            "merge-duplicates",
            rows,
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    except requests.RequestException as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return jsonify({"error": detail, "total": len(rows)}), 502

    return jsonify({"ok": True, "total": len(rows), "imported": imported})


@app.get("/api/tiles/<int:z>/<int:x>/<int:y>")
def vietbando_tile(z: int, x: int, y: int):
    if not 0 <= z <= 18:
        return jsonify({"error": "Mức zoom không hợp lệ"}), 400

    tile_url = VIETBANDO_TILE_URL.format(
        z=z,
        x=x,
        y=y,
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*,*/*;q=0.8",
    }

    referer = os.getenv("VIETBANDO_REFERER", "").strip()
    if referer:
        headers["Referer"] = referer

    try:
        app.logger.info("Đang gọi Vietbando: %s", tile_url)

        upstream = requests.get(
            tile_url,
            headers=headers,
            timeout=(10, 30),
            allow_redirects=True,
        )

        content_type = upstream.headers.get("Content-Type", "")

        app.logger.info(
            "Vietbando status=%s, content-type=%s, bytes=%s, final-url=%s",
            upstream.status_code,
            content_type,
            len(upstream.content),
            upstream.url,
        )

        if upstream.status_code != 200:
            body_preview = ""

            if not content_type.lower().startswith("image/"):
                body_preview = upstream.text[:500]

            app.logger.error(
                "Vietbando trả lỗi: status=%s, body=%s",
                upstream.status_code,
                body_preview,
            )

            return jsonify({
                "error": "Vietbando trả về mã lỗi",
                "upstream_status": upstream.status_code,
                "content_type": content_type,
                "final_url": upstream.url,
                "body": body_preview,
            }), 502

        if not content_type.lower().startswith("image/"):
            body_preview = upstream.text[:500]

            app.logger.error(
                "Vietbando không trả ảnh: content-type=%s, body=%s",
                content_type,
                body_preview,
            )

            return jsonify({
                "error": "Vietbando không trả dữ liệu ảnh",
                "content_type": content_type,
                "body": body_preview,
            }), 502

        return Response(
            upstream.content,
            status=200,
            content_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
            },
        )

    except requests.Timeout:
        app.logger.exception("Vietbando timeout: %s", tile_url)

        return jsonify({
            "error": "Máy chủ Vietbando phản hồi quá lâu",
        }), 504

    except requests.RequestException as exc:
        app.logger.exception(
            "Không kết nối được Vietbando: %s",
            exc,
        )

        return jsonify({
            "error": "Không kết nối được máy chủ Vietbando",
            "detail": str(exc),
        }), 502


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
