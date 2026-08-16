from __future__ import annotations

from . import supabase_client


def count_in_view(west, south, east, north, ma_xa, nhom):
    return supabase_client.call_rpc(
        "count_parcels_in_view",
        {
            "p_west": west,
            "p_south": south,
            "p_east": east,
            "p_north": north,
            "p_ma_xa": ma_xa,
            "p_nhom": nhom,
        },
        timeout=20,
    )


def get_extent():
    return supabase_client.call_rpc("get_parcels_extent", {}, timeout=20)


def get_in_view(
    west, south, east, north, center_lng, center_lat, limit, offset, ma_xa, simplify, nhom
):
    return supabase_client.call_rpc(
        "get_parcels_in_view",
        {
            "p_west": west,
            "p_south": south,
            "p_east": east,
            "p_north": north,
            "p_center_lng": center_lng,
            "p_center_lat": center_lat,
            "p_limit": limit,
            "p_offset": offset,
            "p_ma_xa": ma_xa,
            "p_simplify": simplify,
            "p_nhom": nhom,
        },
        timeout=45,
    )


def list_xa_phuong():
    return supabase_client.call_rpc("list_xa_phuong", {}, timeout=20)


def search(ma_xa, nhom, so_to, so_thua, limit, offset, simplify=0, ten_thon=None):
    return supabase_client.call_rpc(
        "search_parcels",
        {
            "p_ma_xa": ma_xa,
            "p_nhom": nhom,
            "p_so_to": so_to,
            "p_so_thua": so_thua,
            "p_limit": limit,
            "p_offset": offset,
            "p_simplify": simplify,
            "p_ten_thon": ten_thon,
        },
        timeout=45,
    )
