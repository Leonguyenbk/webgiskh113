from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import mplis_service
from ..utils.validators import check_import_token

mplis_bp = Blueprint("mplis", __name__)


# =========================================================
# CẬP NHẬT TRẠNG THÁI TỪ MPLIS (public.dong_bo_du_lieu) — trang quản trị
# "Cập nhật MPLIS", cần mã xác thực (IMPORT_TOKEN) như các endpoint nhập
# liệu khác.
# =========================================================


@mplis_bp.post("/api/admin/cap-nhat-phan-loai")
def cap_nhat_phan_loai_mplis():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    body = request.get_json(silent=True) or {}
    data, error_response = mplis_service.cap_nhat_phan_loai(body)
    if error_response:
        return error_response
    return jsonify(data)


@mplis_bp.get("/api/admin/cap-nhat-phan-loai/<job_id>")
def cap_nhat_phan_loai_mplis_status(job_id: str):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    data, error_response = mplis_service.get_job_status(job_id)
    if error_response:
        return error_response
    return jsonify(data)
