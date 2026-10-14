from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from ..services import danhmuchoso_service

danhmuchoso_bp = Blueprint("danhmuchoso", __name__)

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@danhmuchoso_bp.get("/api/danhmuchoso")
def danhmuchoso_list():
    data, error_response = danhmuchoso_service.get_danh_sach(
        request.args.get("limit"),
        request.args.get("offset"),
        request.args.get("keyword"),
        request.args.get("nam"),
    )
    if error_response:
        return error_response
    return jsonify(data)


@danhmuchoso_bp.get("/api/danhmuchoso/kiem-tra-gcn")
def danhmuchoso_kiem_tra_gcn():
    data, error_response = danhmuchoso_service.kiem_tra_gcn(request.args.get("so_seri_gcn"))
    if error_response:
        return error_response
    return jsonify(data)


@danhmuchoso_bp.post("/api/danhmuchoso")
def danhmuchoso_them():
    body = request.get_json(silent=True) or {}
    data, error_response = danhmuchoso_service.them_ho_so(body)
    if error_response:
        return error_response
    return jsonify(data), 201


@danhmuchoso_bp.get("/api/danhmuchoso/export")
def danhmuchoso_export():
    result, error_response = danhmuchoso_service.export_xlsx(
        request.args.get("nam"), request.args.get("keyword")
    )
    if error_response:
        return error_response
    content, filename = result
    return Response(
        content,
        mimetype=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
