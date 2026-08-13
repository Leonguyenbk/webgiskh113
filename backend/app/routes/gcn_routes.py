from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import gcn_service
from ..utils.validators import check_import_token

gcn_bp = Blueprint("gcn", __name__)


@gcn_bp.get("/api/gcn-stats")
def gcn_stats():
    data, error_response = gcn_service.get_stats()
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
