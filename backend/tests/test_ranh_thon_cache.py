"""Kiểm thử cache RAM cho get_ranh_gioi_thon (khắc phục Supabase CPU cao —
xem chú thích trong supabase/schema.sql và
backend/app/repositories/ranh_thon_repository.py).

Chạy: python -m unittest backend.tests.test_ranh_thon_cache
"""

from __future__ import annotations

import os
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from flask import Flask  # noqa: E402

from app.repositories import ranh_thon_repository  # noqa: E402
from app.repositories import supabase_client  # noqa: E402
from app.services import import_service  # noqa: E402


class RanhThonCacheTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.calls: list[tuple] = []
        self._orig_call_rpc = supabase_client.call_rpc

        # Xoá sạch cache RAM trước mỗi test — biến module-level sống lâu
        # hơn 1 test case.
        ranh_thon_repository.invalidate()

    def tearDown(self):
        supabase_client.call_rpc = self._orig_call_rpc
        ranh_thon_repository.invalidate()
        self.ctx.pop()

    def _stub_rpc(self, responder):
        def fake_call_rpc(function_name, payload, timeout=30):
            self.calls.append((function_name, payload))
            return responder(function_name, payload)

        supabase_client.call_rpc = fake_call_rpc

    # 1) Gọi 2 lần cùng ma_xa trong TTL -> chỉ 1 lượt gọi Supabase thật.
    def test_second_call_within_ttl_uses_cache(self):
        self._stub_rpc(lambda fn, payload: ({"type": "FeatureCollection", "features": []}, None))

        data1, err1 = ranh_thon_repository.get_ranh_gioi_thon("24373")
        data2, err2 = ranh_thon_repository.get_ranh_gioi_thon("24373")

        self.assertIsNone(err1)
        self.assertIsNone(err2)
        self.assertEqual(data1, data2)
        self.assertEqual(len(self.calls), 1, "lần gọi thứ 2 phải dùng cache, không gọi lại Supabase")

    # 2) Không cache lỗi — lỗi xong thì lần gọi kế tiếp phải thử lại Supabase.
    def test_error_response_not_cached(self):
        responses = [(None, ({"error": "boom"}, 502)), ({"ok": True}, None)]

        def responder(fn, payload):
            return responses.pop(0)

        self._stub_rpc(responder)

        data1, err1 = ranh_thon_repository.get_ranh_gioi_thon("24373")
        self.assertIsNone(data1)
        self.assertIsNotNone(err1)

        data2, err2 = ranh_thon_repository.get_ranh_gioi_thon("24373")
        self.assertIsNone(err2)
        self.assertEqual(data2, {"ok": True})
        self.assertEqual(len(self.calls), 2, "lỗi không được cache -> phải gọi lại Supabase lần 2")

    # 3) ma_xa=None (biến thể "lấy hết") và 1 ma_xa cụ thể là 2 khoá cache
    #    riêng, không trộn lẫn.
    def test_none_and_specific_ma_xa_are_separate_cache_keys(self):
        self._stub_rpc(
            lambda fn, payload: (
                {"p_ma_xa": payload["p_ma_xa"]},
                None,
            )
        )

        data_all, _ = ranh_thon_repository.get_ranh_gioi_thon(None)
        data_xa, _ = ranh_thon_repository.get_ranh_gioi_thon("24373")

        self.assertEqual(data_all, {"p_ma_xa": None})
        self.assertEqual(data_xa, {"p_ma_xa": "24373"})
        self.assertEqual(len(self.calls), 2)

    # 4) invalidate(ma_xa) xoá cache của đúng xã đó VÀ cache "toàn bộ xã".
    def test_invalidate_clears_specific_and_all_cache(self):
        self._stub_rpc(lambda fn, payload: ({"n": len(self.calls)}, None))

        ranh_thon_repository.get_ranh_gioi_thon(None)
        ranh_thon_repository.get_ranh_gioi_thon("24373")
        self.assertEqual(len(self.calls), 2)

        ranh_thon_repository.invalidate("24373")

        # Cả 2 khoá đều phải gọi lại Supabase sau invalidate.
        ranh_thon_repository.get_ranh_gioi_thon(None)
        ranh_thon_repository.get_ranh_gioi_thon("24373")
        self.assertEqual(len(self.calls), 4)


class RefreshRanhGioiThonCacheHelperTest(unittest.TestCase):
    """import_service._refresh_ranh_gioi_thon_cache: gọi RPC refresh cho
    từng xã, xoá cache RAM tương ứng, không làm hỏng response khi refresh
    lỗi (chỉ cảnh báo)."""

    def setUp(self):
        self.app = Flask(__name__)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self._orig_call_rpc = supabase_client.call_rpc
        self._orig_invalidate = ranh_thon_repository.invalidate
        self.rpc_calls: list[tuple] = []
        self.invalidated: list[str] = []
        ranh_thon_repository.invalidate = lambda ma_xa=None: self.invalidated.append(ma_xa)

    def tearDown(self):
        supabase_client.call_rpc = self._orig_call_rpc
        ranh_thon_repository.invalidate = self._orig_invalidate
        self.ctx.pop()

    def test_all_success_returns_no_warning(self):
        supabase_client.call_rpc = lambda fn, payload, timeout=30: (
            self.rpc_calls.append((fn, payload)) or (1, None)
        )

        warning = import_service._refresh_ranh_gioi_thon_cache(["24373", "24376"])

        self.assertIsNone(warning)
        self.assertEqual(
            self.rpc_calls,
            [
                ("refresh_ranh_gioi_thon_cache", {"p_ma_xa": "24373"}),
                ("refresh_ranh_gioi_thon_cache", {"p_ma_xa": "24376"}),
            ],
        )
        self.assertEqual(self.invalidated, ["24373", "24376"])

    def test_rpc_error_returns_warning_but_still_invalidates(self):
        supabase_client.call_rpc = lambda fn, payload, timeout=30: (
            None,
            ({"error": "timeout"}, 504),
        )

        warning = import_service._refresh_ranh_gioi_thon_cache(["24373"])

        self.assertIsNotNone(warning)
        self.assertIn("24373", warning)
        # Vẫn xoá cache RAM dù RPC lỗi — tránh giữ dữ liệu cũ vô thời hạn.
        self.assertEqual(self.invalidated, ["24373"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
