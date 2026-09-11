from __future__ import annotations

import threading
import time

from . import supabase_client

# Cache RAM ngắn hạn cho get_ranh_gioi_thon(), khoá theo p_ma_xa (None = lấy
# hết mọi xã). Lý do cần thêm lớp này dù Postgres đã có bảng cache riêng
# (ranh_gioi_thon_cache, xem supabase/schema.sql): App.jsx gọi biến thể
# p_ma_xa=None mỗi khi component <App> MOUNT LẠI (người dùng rời trang bản
# đồ rồi quay lại — router tự chế trong main.jsx unmount/mount lại <App>
# theo path, không giữ state), tức là rất nhiều request giống hệt nhau
# trong thời gian ngắn. Cache RAM ở đây bớt luôn cả vòng gọi HTTP tới
# PostgREST/Supabase cho các lần lặp lại đó.
#
# Deploy hiện tại (render.yaml: --workers 1 --threads 8) chỉ có 1 tiến
# trình worker nên dict module-level này được mọi thread dùng chung, an
# toàn — NẾU sau này tăng lên nhiều worker (process riêng biệt, không chia
# sẻ bộ nhớ), cache RAM mỗi worker sẽ lệch nhau tạm thời (tối đa
# _CACHE_TTL_SECONDS); dữ liệu "đúng" lâu dài vẫn luôn nằm ở
# ranh_gioi_thon_cache trên Postgres, cache RAM ở đây chỉ là lớp tăng tốc,
# không phải nguồn sự thật.
_CACHE_TTL_SECONDS = 300

_state_lock = threading.Lock()
_cache: dict[str | None, tuple[float, dict]] = {}
_inflight_locks: dict[str | None, threading.Lock] = {}


def _fresh(key: str | None):
    cached = _cache.get(key)
    if cached and (time.monotonic() - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]
    return None


def get_ranh_gioi_thon(ma_xa: str | None):
    key = ma_xa or None

    hit = _fresh(key)
    if hit is not None:
        return hit, None

    # Chống "cache stampede": cache hết hạn đúng lúc nhiều người cùng mở
    # lại trang bản đồ thì chỉ 1 request thật sự gọi Supabase cho mỗi
    # ma_xa, các request tới sau đợi rồi dùng chung kết quả thay vì mỗi
    # request tự gọi Supabase riêng.
    with _state_lock:
        request_lock = _inflight_locks.setdefault(key, threading.Lock())

    with request_lock:
        hit = _fresh(key)  # 1 luồng khác có thể vừa tính xong trong lúc chờ khoá
        if hit is not None:
            return hit, None

        data, error_response = supabase_client.call_rpc(
            "get_ranh_gioi_thon", {"p_ma_xa": ma_xa}, timeout=20
        )
        if error_response:
            # KHÔNG cache lỗi (vd Supabase tạm quá tải) — lần gọi kế tiếp
            # thử lại ngay thay vì giữ lỗi trong cache suốt TTL.
            return None, error_response

        with _state_lock:
            _cache[key] = (time.monotonic(), data)
        return data, None


def invalidate(ma_xa: str | None = None) -> None:
    """Xoá cache RAM ngay sau khi ranh_gioi_thon vừa bị ghi (import/xoá ở
    import_service.py) — không đợi hết TTL mới thấy dữ liệu mới.

    ma_xa=<mã cụ thể>: xoá đúng cache của xã đó VÀ cache "toàn bộ xã" (vì
    biến thể p_ma_xa=None luôn bao gồm cả xã này).
    ma_xa=None (mặc định): xoá sạch toàn bộ cache — dùng khi không chắc
    chắn những xã nào bị ảnh hưởng."""
    with _state_lock:
        if ma_xa is None:
            _cache.clear()
            return
        _cache.pop(ma_xa, None)
        _cache.pop(None, None)
