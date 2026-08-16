from __future__ import annotations

from . import supabase_client


def get_ranh_gioi_thon(ma_xa: str | None):
    return supabase_client.call_rpc("get_ranh_gioi_thon", {"p_ma_xa": ma_xa}, timeout=20)
