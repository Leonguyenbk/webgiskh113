from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import requests
from flask import current_app, jsonify

# =========================================================
# LỚP REPOSITORY GỐC — MỌI TRUY VẤN SUPABASE (PostgREST/RPC) ĐI QUA ĐÂY.
# Routes/services không tự gọi requests.* thẳng tới Supabase.
#
# Giữ đúng convention cũ của app.py: hàm trả (data, None) khi thành công
# hoặc (None, (jsonify(...), status)) khi lỗi — response lỗi tạo sẵn ở đây
# để giữ nguyên các thông báo lỗi thân thiện đã có (timeout, sai cột...)
# thay vì đổi sang cơ chế exception mới có thể làm lệch nội dung lỗi hiện
# tại đang hiển thị cho người dùng.
# =========================================================


def get_base_url() -> str:
    return current_app.config.get("SUPABASE_URL", "")


def get_service_headers() -> dict[str, str]:
    key = current_app.config.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not key:
        raise RuntimeError("Thiếu SUPABASE_SERVICE_ROLE_KEY")

    headers = {"apikey": key}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def missing_base_url_response():
    return jsonify({"error": "Thiếu SUPABASE_URL trong backend/.env"}), 500


def rest_request(
    method: str,
    table: str,
    *,
    params: dict | None = None,
    json_body=None,
    extra_headers: dict | None = None,
    timeout: int = 15,
):
    """Gọi PostgREST trực tiếp (GET/POST/PATCH/DELETE) trên 1 bảng bằng
    Service Role Key. Trả (response, None) nếu gọi được (kể cả response lỗi
    HTTP — caller tự kiểm response.ok), hoặc (None, response_loi) nếu thiếu
    cấu hình/lỗi mạng trước khi gọi được request."""
    base_url = get_base_url()
    if not base_url:
        return None, missing_base_url_response()

    try:
        headers = get_service_headers()
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)

    if extra_headers:
        headers = {**headers, **extra_headers}

    try:
        response = requests.request(
            method,
            f"{base_url}/rest/v1/{table}",
            headers=headers,
            params=params,
            json=json_body,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return None, (jsonify({"error": str(exc)}), 502)

    return response, None


def call_rpc(function_name: str, payload: dict, timeout: int = 30):
    """
    Gọi RPC Supabase.

    Trả về (ket_qua, None) khi thành công, hoặc (None, response_loi).
    """
    base_url = get_base_url()

    if not base_url:
        return None, missing_base_url_response()

    try:
        headers = {**get_service_headers(), "Content-Type": "application/json"}
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

        current_app.logger.error(
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


def fetch_all_rows(
    table: str,
    params: dict,
    headers: dict,
    requested_limit: int,
    page_size: int = 1000,
) -> list[dict]:
    # Tiện ích phân trang REST của Supabase — Supabase giới hạn "Max Rows"
    # mặc định 1000 dòng/request bất kể limit truyền vào, nên phải phân
    # trang bằng header Range để lấy hết dữ liệu.
    base_url = get_base_url()
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


def upsert_to_supabase(
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

    base_url = get_base_url()
    headers = {
        **get_service_headers(),
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
