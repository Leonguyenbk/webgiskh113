from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

import gcn_sync
import gml_reader
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

# Thư mục chứa file .mbtiles lớp địa chính. Không hardcode tên file — tự dò
# file .mbtiles đầu tiên trong backend/data khi có request, nên đổi tên/thay
# file không cần sửa code.
MBTILES_DATA_DIR = Path(__file__).resolve().parent / "data"

MBTILES_MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}

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
    nhom_list = read_nhom_list()

    result, error_response = call_rpc(
        "count_parcels_in_view",
        {
            "p_west": values["west"],
            "p_south": values["south"],
            "p_east": values["east"],
            "p_north": values["north"],
            "p_ma_xa": ma_xa or None,
            "p_nhom": nhom_list or None,
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
    nhom_list = read_nhom_list()

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
            "p_nhom": nhom_list or None,
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

def read_nhom_list() -> list[str]:
    # Trả về danh sách nhóm cần lọc (rỗng nghĩa là không lọc). "DEFAULT" là
    # giá trị đặc biệt cho "chưa phân loại", còn lại là nguyên văn giá trị
    # phan_loai_ke_hoach_2959 — không giới hạn trước danh sách nhóm hợp lệ,
    # để sau này thêm nhóm mới (Nhóm 3, 4...) không cần sửa code backend.
    raw = request.args.get("nhom", "").strip()
    if not raw:
        return []
    values = [item.strip().upper() for item in raw.split(",")]
    return [value for value in values if value]


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
    result, error_response = call_rpc("list_xa_phuong", {}, timeout=20)

    if error_response:
        return error_response

    rows = result if isinstance(result, list) else []
    items = [
        {"ma_xa": row.get("ma_xa"), "ten_xa": row.get("ten_xa")}
        for row in rows
        if row.get("ma_xa")
    ]

    return jsonify({"items": items})


# =========================================================
# THỐNG KÊ THU THẬP DỮ LIỆU GCN THEO XÃ (cho trang dashboard)
# =========================================================


@app.get("/api/gcn-stats")
def gcn_stats():
    result, error_response = call_rpc("gcn_thu_thap_theo_xa", {}, timeout=30)

    if error_response:
        return error_response

    rows = result if isinstance(result, list) else []
    items = []
    for row in rows:
        ma_xa = row.get("ma_xa")
        if not ma_xa:
            continue
        tong = int(row.get("tong_so_thua") or 0)
        da_nhap = int(row.get("da_nhap_bieu") or 0)
        items.append(
            {
                "ma_xa": ma_xa,
                "tong_so_thua": tong,
                "da_nhap_bieu": da_nhap,
                "chua_nhap_bieu": max(tong - da_nhap, 0),
            }
        )

    return jsonify({"items": items})


@app.get("/api/parcels/search")
def parcels_search():
    ma_xa = request.args.get("ma_xa", "").strip()
    if not ma_xa:
        return jsonify({"error": "Thiếu mã xã"}), 400

    nhom_list = read_nhom_list()

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
            "p_nhom": nhom_list or None,
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
        # Đọc thẳng từ stream upload (không .read() cả file vào bytes)
        # và parse GML kiểu streaming để tránh hết bộ nhớ với file lớn.
        rows = list(gml_reader.iter_rows(uploaded.stream))
    except Exception as exc:
        return jsonify({"error": f"Không đọc được file GML: {exc}"}), 400

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


# =========================================================
# LỚP PHỦ RASTER ĐỊA CHÍNH (MBTiles)
# Đọc trực tiếp file .mbtiles trong backend/data bằng sqlite3, không qua
# server tile riêng. Mỗi request tự mở/đóng connection (read-only).
# =========================================================


def find_mbtiles_path() -> Path | None:
    if not MBTILES_DATA_DIR.is_dir():
        return None
    matches = sorted(MBTILES_DATA_DIR.glob("*.mbtiles"))
    return matches[0] if matches else None


def open_mbtiles_readonly(path: Path) -> sqlite3.Connection:
    # uri=True + mode=ro: mở read-only, không tạo/khóa ghi lên file.
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def read_mbtiles_metadata(conn: sqlite3.Connection) -> dict[str, str]:
    cursor = conn.execute("SELECT name, value FROM metadata")
    return dict(cursor.fetchall())


@app.get("/api/tiles/diachinh/metadata")
def diachinh_metadata():
    path = find_mbtiles_path()
    if path is None:
        return jsonify({"error": "Không tìm thấy file .mbtiles trong backend/data"}), 404

    conn = open_mbtiles_readonly(path)
    try:
        meta = read_mbtiles_metadata(conn)
    finally:
        conn.close()

    bounds = meta.get("bounds")
    center = meta.get("center")

    if not center and bounds:
        try:
            west, south, east, north = (float(value) for value in bounds.split(","))
            center = f"{(west + east) / 2},{(south + north) / 2}"
        except ValueError:
            center = None

    return jsonify(
        {
            "bounds": bounds,
            "center": center,
            "minzoom": meta.get("minzoom"),
            "maxzoom": meta.get("maxzoom"),
            "format": meta.get("format", "png"),
        }
    )


@app.get("/api/tiles/diachinh/<int:z>/<int:x>/<int:y>.png")
def diachinh_tile(z: int, x: int, y: int):
    path = find_mbtiles_path()
    if path is None:
        return jsonify({"error": "Không tìm thấy file .mbtiles trong backend/data"}), 404

    # MapLibre/Leaflet gọi tile theo trục XYZ (y tăng dần từ trên xuống),
    # còn MBTiles lưu theo TMS (y tăng dần từ dưới lên) nên phải đảo trục y.
    tms_y = (1 << z) - 1 - y

    conn = open_mbtiles_readonly(path)
    try:
        cursor = conn.execute(
            "SELECT tile_data FROM tiles "
            "WHERE zoom_level = ? AND tile_column = ? AND tile_row = ? LIMIT 1",
            (z, x, tms_y),
        )
        row = cursor.fetchone()

        if row is None:
            return jsonify({"error": "Không có tile"}), 404

        meta = read_mbtiles_metadata(conn)
    finally:
        conn.close()

    tile_format = (meta.get("format") or "png").lower()
    mimetype = MBTILES_MIME_TYPES.get(tile_format, "image/png")

    return Response(
        row[0],
        status=200,
        mimetype=mimetype,
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


def validate_mbtiles_structure(path: Path) -> str | None:
    # Kiểm tra sơ bộ trước khi chấp nhận file, tránh 1 file .mbtiles hỏng/
    # không đúng chuẩn làm gãy endpoint tile đang phục vụ người dùng khác.
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return "Không mở được file bằng sqlite3"

    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "tiles" not in tables or "metadata" not in tables:
            return "File không có đủ bảng 'tiles' và 'metadata' theo chuẩn MBTiles"
    except sqlite3.DatabaseError:
        return "File không phải SQLite/MBTiles hợp lệ"
    finally:
        conn.close()

    return None


@app.get("/api/mbtiles")
def list_mbtiles():
    if not MBTILES_DATA_DIR.is_dir():
        return jsonify({"items": []})

    active_path = find_mbtiles_path()
    items = [
        {
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "active": path == active_path,
        }
        for path in sorted(MBTILES_DATA_DIR.glob("*.mbtiles"))
    ]

    return jsonify({"items": items})


@app.post("/api/mbtiles")
def upload_mbtiles():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Thiếu file .mbtiles"}), 400

    filename = secure_filename(uploaded.filename)
    if not filename.lower().endswith(".mbtiles"):
        return jsonify({"error": "Chỉ chấp nhận file .mbtiles"}), 400

    MBTILES_DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = MBTILES_DATA_DIR / filename
    tmp_target = target.with_name(target.name + ".uploading")

    uploaded.save(tmp_target)

    error = validate_mbtiles_structure(tmp_target)
    if error:
        tmp_target.unlink(missing_ok=True)
        return jsonify({"error": error}), 400

    tmp_target.replace(target)

    return jsonify(
        {"ok": True, "filename": filename, "size_bytes": target.stat().st_size}
    )


@app.delete("/api/mbtiles/<path:filename>")
def delete_mbtiles(filename: str):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    safe_name = secure_filename(filename)
    if safe_name != filename or not safe_name.lower().endswith(".mbtiles"):
        return jsonify({"error": "Tên file không hợp lệ"}), 400

    target = MBTILES_DATA_DIR / safe_name
    if not target.is_file():
        return jsonify({"error": "Không tìm thấy file"}), 404

    target.unlink()

    return jsonify({"ok": True})


# =========================================================
# NGUỒN GOOGLE SHEET CHO ĐỒNG BỘ GCN (public.nguon_gcn)
# CRUD qua PostgREST bằng Service Role Key. sync_gcn/main.py đọc bảng
# này (thay vì file Excel local) để biết cần đồng bộ những Google Sheet
# nào — trang "Nhập đường link" chỉ quản lý danh sách, không tự chạy
# đồng bộ.
# =========================================================

NGUON_GCN_TABLE = "nguon_gcn"


@app.get("/api/nguon-gcn")
def list_nguon_gcn():
    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        return jsonify({"error": "Thiếu SUPABASE_URL trong backend/.env"}), 500

    try:
        headers = supabase_headers()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    try:
        response = requests.get(
            f"{base_url}/rest/v1/{NGUON_GCN_TABLE}",
            headers=headers,
            params={"select": "*", "order": "ma_nguon.asc"},
            timeout=15,
        )
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502

    if not response.ok:
        return jsonify({"error": response.text}), response.status_code

    return jsonify({"items": response.json()})


@app.post("/api/nguon-gcn")
def create_nguon_gcn():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    body = request.get_json(silent=True) or {}
    ma_nguon = str(body.get("ma_nguon", "")).strip()
    ten_nguon = str(body.get("ten_nguon", "")).strip()
    url = str(body.get("url", "")).strip()
    kich_hoat = bool(body.get("kich_hoat", True))

    if not ma_nguon or not url:
        return jsonify({"error": "Thiếu ma_nguon hoặc url"}), 400

    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        return jsonify({"error": "Thiếu SUPABASE_URL trong backend/.env"}), 500

    try:
        headers = {
            **supabase_headers(),
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    payload = {
        "ma_nguon": ma_nguon,
        "ten_nguon": ten_nguon,
        "url": url,
        "kich_hoat": kich_hoat,
    }

    try:
        response = requests.post(
            f"{base_url}/rest/v1/{NGUON_GCN_TABLE}",
            headers=headers,
            json=payload,
            timeout=15,
        )
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502

    if not response.ok:
        return jsonify({"error": response.text}), response.status_code

    items = response.json()
    return jsonify({"ok": True, "item": items[0] if items else payload})


@app.patch("/api/nguon-gcn/<path:ma_nguon>")
def update_nguon_gcn(ma_nguon: str):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    body = request.get_json(silent=True) or {}
    updates: dict = {}
    if "ten_nguon" in body:
        updates["ten_nguon"] = str(body["ten_nguon"]).strip()
    if "url" in body:
        updates["url"] = str(body["url"]).strip()
    if "kich_hoat" in body:
        updates["kich_hoat"] = bool(body["kich_hoat"])

    if not updates:
        return jsonify({"error": "Không có trường nào để cập nhật"}), 400

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        return jsonify({"error": "Thiếu SUPABASE_URL trong backend/.env"}), 500

    try:
        headers = {
            **supabase_headers(),
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    try:
        response = requests.patch(
            f"{base_url}/rest/v1/{NGUON_GCN_TABLE}",
            headers=headers,
            params={"ma_nguon": f"eq.{ma_nguon}"},
            json=updates,
            timeout=15,
        )
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502

    if not response.ok:
        return jsonify({"error": response.text}), response.status_code

    items = response.json()
    if not items:
        return jsonify({"error": "Không tìm thấy nguồn"}), 404

    return jsonify({"ok": True, "item": items[0]})


@app.delete("/api/nguon-gcn/<path:ma_nguon>")
def delete_nguon_gcn(ma_nguon: str):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        return jsonify({"error": "Thiếu SUPABASE_URL trong backend/.env"}), 500

    try:
        headers = supabase_headers()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    try:
        response = requests.delete(
            f"{base_url}/rest/v1/{NGUON_GCN_TABLE}",
            headers=headers,
            params={"ma_nguon": f"eq.{ma_nguon}"},
            timeout=15,
        )
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502

    if not response.ok:
        return jsonify({"error": response.text}), response.status_code

    return jsonify({"ok": True})


# =========================================================
# ĐỒNG BỘ DỮ LIỆU GCN TỪ GOOGLE SHEET (public.du_lieu_gcn)
# Chạy ngay trên backend (thay vì chỉ chạy local qua sync_gcn/main.py) để
# trang "Nhập đường link" có nút Đồng bộ, và để GitHub Actions gọi định kỳ
# (xem .github/workflows/sync-gcn.yml). Cần biến môi trường
# GOOGLE_SERVICE_ACCOUNT_JSON trên Render — xem sync_gcn/README.md.
# =========================================================


def fetch_nguon_gcn_row(base_url: str, headers: dict, ma_nguon: str) -> dict | None:
    response = requests.get(
        f"{base_url}/rest/v1/{NGUON_GCN_TABLE}",
        headers=headers,
        params={"select": "*", "ma_nguon": f"eq.{ma_nguon}"},
        timeout=15,
    )
    response.raise_for_status()
    items = response.json()
    return items[0] if items else None


@app.post("/api/nguon-gcn/<path:ma_nguon>/sync")
def sync_one_nguon_gcn(ma_nguon: str):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        return jsonify({"error": "Thiếu SUPABASE_URL trong backend/.env"}), 500

    try:
        headers = supabase_headers()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    try:
        source = fetch_nguon_gcn_row(base_url, headers, ma_nguon)
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502

    if not source:
        return jsonify({"error": "Không tìm thấy nguồn"}), 404
    if not source.get("url"):
        return jsonify({"error": "Nguồn chưa có URL"}), 400

    try:
        imported = gcn_sync.sync_source(
            base_url, headers, ma_nguon, source.get("ten_nguon") or "", source["url"]
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:  # noqa: BLE001 - lỗi đọc Sheet (sai URL/chưa share/sai tên trang tính...) phải báo rõ
        app.logger.exception("Đồng bộ GCN lỗi: ma_nguon=%s", ma_nguon)
        return jsonify({"error": f"Đồng bộ thất bại: {exc}"}), 502

    return jsonify({"ok": True, "ma_nguon": ma_nguon, "imported": imported})


@app.post("/api/nguon-gcn/sync-all")
def sync_all_nguon_gcn():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not base_url:
        return jsonify({"error": "Thiếu SUPABASE_URL trong backend/.env"}), 500

    try:
        headers = supabase_headers()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    try:
        response = requests.get(
            f"{base_url}/rest/v1/{NGUON_GCN_TABLE}",
            headers=headers,
            params={"select": "*", "kich_hoat": "eq.true", "order": "ma_nguon.asc"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502

    sources = response.json()
    results = []

    for source in sources:
        ma_nguon = source.get("ma_nguon")
        url = source.get("url")
        if not ma_nguon or not url:
            continue

        try:
            imported = gcn_sync.sync_source(
                base_url, headers, ma_nguon, source.get("ten_nguon") or "", url
            )
        except Exception as exc:  # noqa: BLE001 - 1 nguồn lỗi không được chặn các nguồn khác
            app.logger.exception("Đồng bộ GCN lỗi: ma_nguon=%s", ma_nguon)
            results.append({"ma_nguon": ma_nguon, "ok": False, "error": str(exc)})
        else:
            results.append({"ma_nguon": ma_nguon, "ok": True, "imported": imported})

    return jsonify({"ok": True, "results": results})


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