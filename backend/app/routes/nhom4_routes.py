from __future__ import annotations

import json

from flask import Blueprint, jsonify, request, send_from_directory

from ..repositories.local_file_storage import SCANS_DIR
from ..services import nhom4_service
from ..utils.validators import check_import_token

nhom4_bp = Blueprint("nhom4", __name__)


@nhom4_bp.get("/files/nhom4-scans/<ma_xa>/<filename>")
def get_nhom4_scan(ma_xa: str, filename: str):
    # Hồ sơ quét chứa CCCD/thông tin cá nhân — không public như tile bản đồ
    # nền, phải có đúng mã xác thực admin mới tải được.
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401
    return send_from_directory(SCANS_DIR / ma_xa, filename)


@nhom4_bp.get("/api/nhom4/kiem-tra-trung-thua")
def kiem_tra_trung_thua():
    ma_xa = request.args.get("ma_xa", "").strip()
    so_to = request.args.get("so_to", "").strip()
    so_thua = request.args.get("so_thua", "").strip()

    data, error_response = nhom4_service.check_trung_thua(ma_xa, so_to, so_thua)
    if error_response:
        return error_response
    return jsonify(data)


@nhom4_bp.get("/api/nhom4/dia-chi-thua-dat")
def dia_chi_thua_dat():
    ma_xa = request.args.get("ma_xa", "").strip()
    so_to = request.args.get("so_to", "").strip()
    so_thua = request.args.get("so_thua", "").strip()

    data, error_response = nhom4_service.get_dia_chi_thua_dat(ma_xa, so_to, so_thua)
    if error_response:
        return error_response
    return jsonify(data)


@nhom4_bp.post("/api/nhom4/ho-so")
def submit_ho_so():
    raw_payload = request.form.get("payload", "")
    try:
        payload = json.loads(raw_payload) if raw_payload else {}
    except ValueError:
        return jsonify({"error": "Dữ liệu payload không phải JSON hợp lệ"}), 400

    # Mỗi thửa trong payload["thua_list"] có 1 bộ hồ sơ quét riêng — frontend
    # gửi field name đánh số theo thứ tự: file_chinh_0/file_phu_0/file_tbxn_0
    # cho thửa đầu, file_chinh_1/... cho thửa kế tiếp, v.v.
    so_thua = len(payload.get("thua_list") or [])
    files_by_parcel = [
        {
            "chinh": request.files.get(f"file_chinh_{i}"),
            "phu": request.files.get(f"file_phu_{i}"),
            "tbxn": request.files.get(f"file_tbxn_{i}"),
        }
        for i in range(so_thua)
    ]

    data, error_response = nhom4_service.submit_ho_so(payload, files_by_parcel)
    if error_response:
        return error_response
    return jsonify(data)
