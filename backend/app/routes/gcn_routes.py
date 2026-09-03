from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from ..services import gcn_service
from ..utils.validators import check_import_token

gcn_bp = Blueprint("gcn", __name__)

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@gcn_bp.get("/api/gcn-stats")
def gcn_stats():
    data, error_response = gcn_service.get_stats()
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.get("/api/gcn-export-theo-nhom")
def gcn_export_theo_nhom():
    # Xuất .xlsx danh sách du_lieu_gcn của 1 xã đã thu thập + thuộc nhóm
    # KH 2959 (mặc định Nhóm 2). ?ma_xa=<mã xã>&nhom=Nhóm 2[,Nhóm 1]
    result, error_response = gcn_service.export_theo_nhom_xlsx(
        request.args.get("ma_xa", ""), request.args.get("nhom")
    )
    if error_response:
        return error_response
    content, filename = result
    return Response(
        content,
        mimetype=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@gcn_bp.get("/api/gcn-export-nhom3")
def gcn_export_nhom3():
    # Xuất .xlsx đúng bố cục file mẫu TANAN.xlsx của 1 đơn vị hành chính —
    # chỉ thửa Nhóm 3 (chưa thuộc Nhóm 1/Nhóm 2 KH 2959), hoặc lấy hết.
    # ?ma_xa=<mã ĐVHC>&chi_nhom3=1 (mặc định 0 = lấy hết, không lọc nhóm).
    # File chứa dữ liệu cá nhân (CCCD, địa chỉ...) nên bắt buộc mã xác thực
    # IMPORT_TOKEN giống các endpoint quản trị khác — khác
    # /api/gcn-export-theo-nhom (không chặn) vì xuất TOÀN BỘ dữ liệu 1 xã,
    # không chỉ 1 nhóm KH 2959.
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    chi_nhom3 = request.args.get("chi_nhom3", "").strip().lower() in ("1", "true", "yes")
    result, error_response = gcn_service.export_nhom3_xlsx(
        request.args.get("ma_xa", ""), chi_nhom3
    )
    if error_response:
        return error_response
    content, filename = result
    return Response(
        content,
        mimetype=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@gcn_bp.post("/api/gcn-stats/refresh")
def gcn_stats_refresh():
    # Tính lại bảng cache thống kê thu thập (nhánh quét nặng). Dành cho
    # cron gọi định kỳ — không phải request người dùng — nên chắn bằng
    # IMPORT_TOKEN. Nếu đã bật pg_cron thì không cần endpoint này.
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    data, error_response = gcn_service.refresh_stats_cache()
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.get("/api/nguon-gcn")
def list_nguon_gcn():
    data, error_response = gcn_service.list_sources()
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.post("/api/nguon-gcn")
def create_nguon_gcn():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    body = request.get_json(silent=True) or {}
    data, error_response = gcn_service.create_source(body)
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.patch("/api/nguon-gcn/<path:ma_nguon>")
def update_nguon_gcn(ma_nguon: str):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    body = request.get_json(silent=True) or {}
    data, error_response = gcn_service.update_source(ma_nguon, body)
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.delete("/api/nguon-gcn/<path:ma_nguon>")
def delete_nguon_gcn(ma_nguon: str):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    data, error_response = gcn_service.delete_source(ma_nguon)
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.post("/api/nguon-gcn/<path:ma_nguon>/sync")
def sync_one_nguon_gcn(ma_nguon: str):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    data, error_response = gcn_service.sync_one(ma_nguon)
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.post("/api/nguon-gcn/sync-all")
def sync_all_nguon_gcn():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    data, error_response = gcn_service.sync_all()
    if error_response:
        return error_response
    return jsonify(data)
