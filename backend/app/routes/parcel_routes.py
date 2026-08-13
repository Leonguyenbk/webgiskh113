from __future__ import annotations

from flask import Blueprint, jsonify

from ..services import parcel_service

parcel_bp = Blueprint("parcel", __name__)


@parcel_bp.get("/api/parcels/count")
def parcels_count():
    data, error_response = parcel_service.get_count()
    if error_response:
        return error_response
    return jsonify(data)


@parcel_bp.get("/api/parcels/extent")
def parcels_extent():
    data, error_response = parcel_service.get_extent()
    if error_response:
        return error_response
    return jsonify(data)


@parcel_bp.get("/api/parcels")
def parcels():
    data, error_response = parcel_service.get_parcels()
    if error_response:
        return error_response
    return jsonify(data)


@parcel_bp.get("/api/parcels/xa-list")
def parcels_xa_list():
    data, error_response = parcel_service.list_xa()
    if error_response:
        return error_response
    return jsonify(data)


@parcel_bp.get("/api/parcels/search")
def parcels_search():
    data, error_response = parcel_service.search()
    if error_response:
        return error_response
    return jsonify(data)
