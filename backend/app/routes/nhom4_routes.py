from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from ..services import nhom4_service

nhom4_bp = Blueprint("nhom4", __name__)


@nhom4_bp.get("/api/nhom4/kiem-tra-trung-thua")
def kiem_tra_trung_thua():
    ma_xa = request.args.get("ma_xa", "").strip()
    so_to = request.args.get("so_to", "").strip()
    so_thua = request.args.get("so_thua", "").strip()

    data, error_response = nhom4_service.check_trung_thua(ma_xa, so_to, so_thua)
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

    file_chinh = request.files.get("file_chinh")
    file_phu = request.files.get("file_phu")
    file_tbxn = request.files.get("file_tbxn")

    data, error_response = nhom4_service.submit_ho_so(payload, file_chinh, file_phu, file_tbxn)
    if error_response:
        return error_response
    return jsonify(data)
