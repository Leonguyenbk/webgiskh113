from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

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

# Trần cứng số thửa mỗi lô. Vượt mức này Supabase dễ chạm statement_timeout
# khi phải sinh GeoJSON cho quá nhiều hình học trong một câu lệnh.
MAX_PAGE_SIZE = 3000
DEFAULT_PAGE_SIZE = 1000

# Ngưỡng giản lược hình học theo mức zoom, đơn vị độ (EPSG:4326).
# 0.00001 độ ~ 1,1 m. Zoom càng xa càng giản lược mạnh vì màn hình
# không thể hiện nổi chi tiết ở mức đó.
SIMPLIFY_BY_ZOOM = (
    (17, 0.0),
    (15, 0.000008),
    (13, 0.000030),
    (11, 0.000080),
    (0, 0.000200),
)

SPATIAL_ARGS = (
    "west",
    "south",
    "east",
    "north",
    "center_lng",
    "center_lat",
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
    # Tiện ích phân trang REST của Supabase. Endpoint /api/parcels không còn
    # dùng hàm này nữa (đã chuyển sang RPC), nhưng giữ lại vì các tác vụ
    # đọc bảng khác vẫn cần.
    #
    # Supabase giới hạn "Max Rows" mặc định 1000 dòng/request bất kể limit
    # truyền vào, nên phải phân trang bằng header Range để lấy hết dữ liệu.
    endpoint = f"{base_url}/rest/v1/{table}"

    def fetch_page(start: int, count_exact: bool = False) -> tuple[list[dict], str]:
        end = start + page_size - 1
        page_headers = {**headers, "Range-Unit": "items", "Range": f"{start}-{end}"}
        if count_exact:
            page_headers["Prefer"] = "count=exact"
        response = requests.get(
            endpoint, headers=page_headers, params=params, timeout=60
        )
        response.raise_for_status()
        return response.json(), response.headers.get("Content-Range", "")

    first_page, content_range = fetch_page(0, count_exact=True)
    rows = first_page

    total = None
    if "/" in content_range:
        total_part = content_range.rsplit("/", 1)[-1]
        if total_part.isdigit():
            total = int(total_part)

    if total is None or len(first_page) < page_size:
        return rows[:requested_limit]

    remaining_limit = min(total, requested_limit)
    starts = list(range(page_size, remaining_limit, page_size))
    if starts:
        with ThreadPoolExecutor(max_workers=8) as executor:
            for page, _ in executor.map(fetch_page, starts):
                rows.extend(page)

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


# =========================================================
# TIỆN ÍCH CHO TRUY VẤN THEO KHUNG BẢN ĐỒ
# =========================================================


def simplify_for_zoom(zoom: int) -> float:
    """Trả về ngưỡng giản lược hình học ứng với mức zoom."""
    for min_zoom, tolerance in SIMPLIFY_BY_ZOOM:
        if zoom >= min_zoom:
            return tolerance
    return 0.0


def read_bbox():
    """
    Đọc và kiểm tra khung bản đồ từ query string.

    Trả về (values, None) khi hợp lệ, hoặc (None, response_loi) khi không.
    """
    missing = [name for name in SPATIAL_ARGS if request.args.get(name) in (None, "")]

    if missing:
        return None, (
            jsonify({"error": "Thiếu tham số khung bản đồ: " + ", ".join(missing)}),
            400,
        )

    try:
        values = {name: float(request.args[name]) for name in SPATIAL_ARGS}
    except (TypeError, ValueError):
        return None, (jsonify({"error": "Tọa độ khung bản đồ không phải số"}), 400)

    # Leaflet trả kinh độ ngoài [-180, 180] khi người dùng kéo bản đồ vòng
    # qua đường đổi ngày. Kẹp lại thay vì báo lỗi để bản đồ không đứng hình.
    for name in ("west", "east", "center_lng"):
        values[name] = max(-180.0, min(180.0, values[name]))

    for name in ("south", "north", "center_lat"):
        values[name] = max(-90.0, min(90.0, values[name]))

    if values["west"] >= values["east"] or values["south"] >= values["north"]:
        return None, (jsonify({"error": "Khung bản đồ không hợp lệ"}), 400)

    return values, None


def call_rpc(function_name: str, payload: dict, timeout: int = 30):
    """
    Gọi RPC Supabase.

    Trả về (ket_qua, None) khi thành công, hoặc (None, response_loi).
    """
    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")

    if not base_url:
        return None, (
            jsonify({"error": "Thiếu SUPABASE_URL trong backend/.env"}),
            500,
        )

    try:
        headers = {**supabase_headers(), "Content-Type": "application/json"}
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)

    try:
        response = requests.post(
            f"{base_url}/rest/v1/rpc/{function_name}",
            headers=headers,
            json=payload,
            timeout=timeout,
        )
    except requests.Timeout:
        return None, (
            jsonify({
                "error": (
                    "Supabase phản hồi quá chậm. "
                    "Hãy phóng to bản đồ để thu hẹp khu vực."
                )
            }),
            504,
        )
    except requests.RequestException as exc:
        return None, (jsonify({"error": str(exc)}), 502)

    if not response.ok:
        # Trả nguyên văn lỗi Postgres ra frontend: statement timeout,
        # sai SRID, sai tên cột đều lộ ra ở đây.
        try:
            detail = response.json()
        except ValueError:
            detail = {}

        message = (
            detail.get("message")
            or detail.get("error")
            or response.text
            or "Supabase trả về lỗi không rõ nguyên nhân"
        )

        app.logger.error(
            "RPC %s lỗi: status=%s, body=%s",
            function_name,
            response.status_code,
            response.text[:500],
        )

        if "statement timeout" in str(message).lower():
            message = (
                "Truy vấn vượt quá thời gian cho phép. "
                "Hãy phóng to bản đồ hoặc giảm số thửa mỗi lô."
            )

        return None, (jsonify({"error": message}), 502)

    try:
        return response.json(), None
    except ValueError:
        return None, (
            jsonify({"error": "Supabase trả về dữ liệu không phải JSON"}),
            502,
        )


# =========================================================
# ĐẾM SỐ THỬA TRONG KHUNG
# Chỉ đụng index GIST, không sinh GeoJSON nên rất nhanh.
# Frontend gọi trước để biết khung hiện tại còn bao nhiêu thửa chưa vẽ.
# =========================================================


@app.get("/api/parcels/count")
def parcels_count():
    values, error_response = read_bbox()

    if error_response:
        return error_response

    ma_xa = request.args.get("ma_xa", "").strip()

    result, error_response = call_rpc(
        "count_parcels_in_view",
        {
            "p_west": values["west"],
            "p_south": values["south"],
            "p_east": values["east"],
            "p_north": values["north"],
            "p_ma_xa": ma_xa or None,
        },
        timeout=20,
    )

    if error_response:
        return error_response

    try:
        total = int(result)
    except (TypeError, ValueError):
        total = 0

    return jsonify({"total": total})

@app.get("/api/parcels/extent")
def parcels_extent():
    result, error_response = call_rpc("get_parcels_extent", {}, timeout=20)

    if error_response:
        return error_response

    if not isinstance(result, dict):
        return jsonify({"error": "Bảng thửa đất chưa có dữ liệu"}), 404

    return jsonify(result)

# =========================================================
# LẤY THỬA THEO KHUNG BẢN ĐỒ
# =========================================================


@app.get("/api/parcels")
def parcels():
    try:
        requested_limit = min(
            max(int(request.args.get("limit", DEFAULT_PAGE_SIZE)), 1),
            MAX_PAGE_SIZE,
        )
        page_offset = max(int(request.args.get("offset", 0)), 0)
        zoom = int(float(request.args.get("zoom", 16)))
    except (TypeError, ValueError):
        return jsonify({"error": "limit, offset hoặc zoom không hợp lệ"}), 400

    values, error_response = read_bbox()

    if error_response:
        return error_response

    ma_xa = request.args.get("ma_xa", "").strip()

    result, error_response = call_rpc(
        "get_parcels_in_view",
        {
            "p_west": values["west"],
            "p_south": values["south"],
            "p_east": values["east"],
            "p_north": values["north"],
            "p_center_lng": values["center_lng"],
            "p_center_lat": values["center_lat"],
            "p_limit": requested_limit,
            "p_offset": page_offset,
            "p_ma_xa": ma_xa or None,
            "p_simplify": simplify_for_zoom(zoom),
        },
        timeout=45,
    )

    if error_response:
        return error_response

    if not isinstance(result, dict):
        return jsonify({"type": "FeatureCollection", "features": []})

    result.setdefault("type", "FeatureCollection")
    result.setdefault("features", [])

    return jsonify(result)


# =========================================================
# TRA CỨU THEO BỘ LỌC: mã xã (bắt buộc) + nhóm + số tờ + số thửa
# Không lọc theo khung bản đồ như /api/parcels, nên phải luôn có mã xã
# để tránh quét toàn tỉnh.
# =========================================================

ALLOWED_NHOM = {"NHÓM 1", "NHÓM 2", "DEFAULT"}


def read_optional_int(name: str):
    """Đọc tham số int tùy chọn. Trả về (giá_trị, None) hoặc (None, response_loi)."""
    raw = request.args.get(name, "").strip()
    if not raw:
        return None, None
    try:
        return int(raw), None
    except ValueError:
        return None, (jsonify({"error": f"{name} phải là số nguyên"}), 400)


@app.get("/api/parcels/xa-list")
def parcels_xa_list():
    result, error_response = call_rpc("list_ma_xa", {}, timeout=20)

    if error_response:
        return error_response

    rows = result if isinstance(result, list) else []
    items = sorted({row.get("ma_xa") for row in rows if row.get("ma_xa")})

    return jsonify({"items": items})


@app.get("/api/parcels/search")
def parcels_search():
    ma_xa = request.args.get("ma_xa", "").strip()
    if not ma_xa:
        return jsonify({"error": "Thiếu mã xã"}), 400

    nhom = request.args.get("nhom", "").strip().upper()
    if nhom and nhom not in ALLOWED_NHOM:
        return jsonify({"error": "Giá trị nhóm không hợp lệ"}), 400

    so_to, error_response = read_optional_int("so_to")
    if error_response:
        return error_response

    so_thua, error_response = read_optional_int("so_thua")
    if error_response:
        return error_response

    try:
        requested_limit = min(
            max(int(request.args.get("limit", DEFAULT_PAGE_SIZE)), 1),
            MAX_PAGE_SIZE,
        )
        page_offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        return jsonify({"error": "limit hoặc offset không hợp lệ"}), 400

    result, error_response = call_rpc(
        "search_parcels",
        {
            "p_ma_xa": ma_xa,
            "p_nhom": nhom or None,
            "p_so_to": so_to,
            "p_so_thua": so_thua,
            "p_limit": requested_limit,
            "p_offset": page_offset,
            "p_simplify": 0,
        },
        timeout=45,
    )

    if error_response:
        return error_response

    if not isinstance(result, dict):
        return jsonify({"type": "FeatureCollection", "features": []})

    result.setdefault("type", "FeatureCollection")
    result.setdefault("features", [])

    return jsonify(result)


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