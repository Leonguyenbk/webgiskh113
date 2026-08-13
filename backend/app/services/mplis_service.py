from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app, jsonify

import mplis_sync
from ..repositories import mplis_repository, supabase_client
from ..utils.validators import UNG_THUA_ALLOWED_FIELDS, clean_text


def _validate_mode(ma_xa: str, so_to: str, so_thua: str) -> tuple[str | None, str | None]:
    """Trả (mode, None) nếu hợp lệ — mode là 'single' hoặc 'ward' — hoặc
    (None, thông báo lỗi) nếu không hợp lệ."""
    if not ma_xa:
        return None, "Chưa nhập mã xã."
    if bool(so_to) != bool(so_thua):
        return None, "Phải nhập cả Số tờ và Số thửa hoặc để trống cả hai."
    return ("single" if so_to else "ward"), None


def cap_nhat_phan_loai(body: dict):
    ma_xa = str(body.get("ma_xa", "")).strip()
    so_to = str(body.get("so_to", "")).strip()
    so_thua = str(body.get("so_thua", "")).strip()
    token = str(body.get("request_verification_token", "")).strip()
    cookie = str(body.get("cookie", "")).strip()

    mode, error = _validate_mode(ma_xa, so_to, so_thua)
    if error:
        return None, (jsonify({"error": error}), 400)
    if not token:
        return None, (jsonify({"error": "Chưa nhập Request Verification Token."}), 400)
    if not cookie:
        return None, (jsonify({"error": "Chưa nhập Cookie MPLIS."}), 400)

    base_url = supabase_client.get_base_url()
    if not base_url:
        return None, supabase_client.missing_base_url_response()
    try:
        headers = supabase_client.get_service_headers()
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)

    if mode == "single":
        try:
            result = mplis_sync.update_single_parcel(
                ma_xa, so_to, so_thua, token, cookie, base_url, headers
            )
        except mplis_sync.MplisSessionError as exc:
            return None, (jsonify({"error": str(exc)}), 401)
        except mplis_sync.MplisRequestError as exc:
            return None, (jsonify({"error": f"Không kết nối được MPLIS: {exc}"}), 502)
        except Exception:  # noqa: BLE001 - không được để lộ chi tiết lỗi thật cho người dùng
            current_app.logger.exception(
                "Cập nhật 1 thửa MPLIS lỗi: ma_xa=%s so_to=%s so_thua=%s", ma_xa, so_to, so_thua
            )
            return None, (jsonify({"error": "Có lỗi không xác định khi cập nhật."}), 500)

        return {"mode": "single", **result}, None

    # mode == "ward"
    job = mplis_sync.try_start_ward_job(ma_xa, so_to, so_thua, token, cookie, base_url, headers)
    if job is None:
        return None, (jsonify({"error": "Đang có một tiến trình cập nhật khác đang chạy."}), 409)

    return {"mode": "ward", "job_id": job.job_id, "status": job.status}, None


def get_job_status(job_id: str):
    job = mplis_sync.get_job(job_id)
    if job is None:
        return None, (jsonify({"error": "Không tìm thấy job"}), 404)
    return job.snapshot(), None


def list_ung_thua(ma_xa: str | None):
    result, error_response = mplis_repository.list_ung_thua(ma_xa)
    if error_response:
        return None, error_response
    return {"items": result}, None


def save_ung_thua(body: dict):
    ma_xa = str(body.get("ma_xa", "")).strip()

    try:
        so_to = int(body.get("so_to"))
        so_thua = int(body.get("so_thua"))
    except (TypeError, ValueError):
        return None, (jsonify({"error": "Thiếu hoặc sai định dạng so_to/so_thua"}), 400)

    if not ma_xa:
        return None, (jsonify({"error": "Thiếu ma_xa"}), 400)

    # Whitelist: chỉ nhận đúng các trường được phép cập nhật, không để
    # frontend gửi field tùy ý rồi update toàn bộ row (mục 12 yêu cầu).
    cleaned = {field: clean_text(body.get(field)) for field in UNG_THUA_ALLOWED_FIELDS}

    if not cleaned["to_thua_mplis"]:
        return None, (jsonify({"error": "Thiếu tờ thửa trên MPLIS"}), 400)

    payload = {
        "ma_xa": ma_xa,
        "so_to": so_to,
        "so_thua": so_thua,
        **cleaned,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    result, error_response = mplis_repository.upsert_ung_thua(payload)
    if error_response:
        return None, error_response

    return {"ok": True, "item": result[0] if result else payload}, None
