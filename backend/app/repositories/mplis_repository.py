from __future__ import annotations

import requests
from flask import jsonify

from . import supabase_client

UNG_THUA_TABLE = "ung_thua_mplis"


def list_ung_thua(ma_xa: str | None):
    params = {"select": "*", "order": "updated_at.desc"}
    if ma_xa:
        params["ma_xa"] = f"eq.{ma_xa}"

    response, error_response = supabase_client.rest_request("GET", UNG_THUA_TABLE, params=params)
    if error_response:
        return None, error_response
    if not response.ok:
        return None, (jsonify({"error": response.text}), response.status_code)
    return response.json(), None


def upsert_ung_thua(payload: dict):
    # on_conflict phải nằm nguyên trong URL (không qua params) — giữ đúng
    # cách PostgREST đang được gọi ở các chỗ upsert khác trong dự án
    # (xem supabase_client.upsert_to_supabase, import_gml.py).
    base_url = supabase_client.get_base_url()
    if not base_url:
        return None, supabase_client.missing_base_url_response()

    try:
        headers = {
            **supabase_client.get_service_headers(),
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        }
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)

    try:
        response = requests.post(
            f"{base_url}/rest/v1/{UNG_THUA_TABLE}?on_conflict=ma_xa,so_to,so_thua",
            headers=headers,
            json=payload,
            timeout=15,
        )
    except requests.RequestException as exc:
        return None, (jsonify({"error": str(exc)}), 502)

    if not response.ok:
        return None, (jsonify({"error": response.text}), response.status_code)
    return response.json(), None
