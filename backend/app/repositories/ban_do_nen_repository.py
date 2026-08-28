from __future__ import annotations

from flask import jsonify

from . import supabase_client

TABLE = "ban_do_nen"


def _json_or_error(response, error_response):
    if error_response:
        return None, error_response
    if not response.ok:
        return None, (jsonify({"error": response.text}), response.status_code)
    return response.json(), None


def list_all(params: dict):
    response, error_response = supabase_client.rest_request(
        "GET", TABLE, params={"select": "*", "order": "ma_xa.asc,so_to.asc", **params}
    )
    return _json_or_error(response, error_response)


def get_by_id(id_: int):
    response, error_response = supabase_client.rest_request(
        "GET", TABLE, params={"select": "*", "id": f"eq.{id_}"}
    )
    items, error_response = _json_or_error(response, error_response)
    if error_response:
        return None, error_response
    return (items[0] if items else None), None


def update(id_: int, patch: dict):
    response, error_response = supabase_client.rest_request(
        "PATCH",
        TABLE,
        params={"id": f"eq.{id_}"},
        json_body=patch,
        extra_headers={"Content-Type": "application/json", "Prefer": "return=representation"},
    )
    return _json_or_error(response, error_response)


def delete(id_: int):
    response, error_response = supabase_client.rest_request(
        "DELETE", TABLE, params={"id": f"eq.{id_}"}
    )
    if error_response:
        return None, error_response
    if not response.ok:
        return None, (jsonify({"error": response.text}), response.status_code)
    return True, None


def get_in_view(west, south, east, north, include_all: bool = False):
    return supabase_client.call_rpc(
        "get_ban_do_nen_in_view",
        {
            "p_west": west,
            "p_south": south,
            "p_east": east,
            "p_north": north,
            "p_include_all": include_all,
        },
        timeout=20,
    )


def search(ma_xa: str, so_to=None):
    return supabase_client.call_rpc(
        "get_ban_do_nen_by_ma_xa_so_to", {"p_ma_xa": ma_xa, "p_so_to": so_to}, timeout=15
    )


def register(payload: dict):
    return supabase_client.call_rpc("register_ban_do_nen", payload, timeout=20)
