"""Ranh giới 102 xã/phường (bảng public.ranh_gioi_xa, nạp bằng
backend/scripts/import_ranh_xa.py) cho lớp "Ranh giới xã" trên bản đồ.

Dữ liệu gần như tĩnh (chỉ đổi khi chạy lại script nạp) nên cache RAM 10
phút; trả geom_hien_thi (đã rút gọn ~5 m), toạ độ làm tròn 5 chữ số (~1 m)
để file GeoJSON nhẹ.
"""
from __future__ import annotations

import threading
import time

from flask import jsonify

from . import supabase_client

_CACHE_TTL_SECONDS = 600
_lock = threading.Lock()
_cache: tuple[float, dict] | None = None


def get_ranh_gioi_xa():
    global _cache
    hit = _cache
    if hit and time.monotonic() - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1], None
    with _lock:  # chống nhiều request cùng tính lại khi cache vừa hết hạn
        hit = _cache
        if hit and time.monotonic() - hit[0] < _CACHE_TTL_SECONDS:
            return hit[1], None
        try:
            with supabase_client._CursorCtx(timeout=30) as cur:
                cur.execute(
                    """
                    select json_build_object(
                        'type', 'FeatureCollection',
                        'features', coalesce(json_agg(json_build_object(
                            'type', 'Feature',
                            'geometry', ST_AsGeoJSON(geom_hien_thi, 5)::json,
                            'properties', json_build_object(
                                'ma_xa', ma_xa, 'ten_xa', ten_xa, 'loai', loai,
                                'mau', mau, 'dtich_km2', dtich_km2, 'dan_so', dan_so,
                                'sap_nhap', sap_nhap)
                        ) order by ma_xa), '[]'::json)
                    ) as fc
                    from public.ranh_gioi_xa
                    """
                )
                data = cur.fetchone()["fc"]
        except Exception as exc:  # noqa: BLE001 - không cache lỗi, lần sau thử lại
            return None, (jsonify({"error": f"Không tải được ranh giới xã: {exc}"}), 500)
        _cache = (time.monotonic(), data)
        return data, None
