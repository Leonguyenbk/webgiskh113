"""Kiểm tra file PDF có CHỮ KÝ SỐ hay không (yêu cầu từ 15/11/2026: file chính
của biểu Nhóm 4 — Đơn đăng ký / Giấy chứng nhận — phải là bản đã ký số).

Kiểm tra theo CẤU TRÚC PDF (chuẩn ISO 32000 / PAdES), không cần thư viện mật
mã: một chữ ký số thật luôn có từ điển chữ ký với /ByteRange [0 b c d] trỏ
đúng vùng dữ liệu được ký và /Contents <hex> nằm giữa (b..c) chứa khối
PKCS#7/CMS khác rỗng. File chỉ có ô ký trống (placeholder, /Contents toàn số
0) hoặc ảnh chụp chữ ký dán vào thì KHÔNG đạt. Chưa xác minh chuỗi chứng thư
(VNPT-CA, Viettel-CA...) — muốn xác minh sâu hơn cần thêm thư viện pyHanko.
"""
from __future__ import annotations

import re

_BYTE_RANGE_RE = re.compile(rb"/ByteRange\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\]")
_HEX_RE = re.compile(rb"^<\s*([0-9A-Fa-f\s]+)>$")


def co_chu_ky_so(data: bytes) -> bool:
    if not data or b"/ByteRange" not in data:
        return False
    n = len(data)
    for m in _BYTE_RANGE_RE.finditer(data):
        a, b, c, d = (int(x) for x in m.groups())
        if a != 0 or b <= 0 or c <= b or c + d > n:
            continue
        khoi = data[b:c].strip()
        hm = _HEX_RE.match(khoi)
        if not hm:
            continue
        hex_ky = re.sub(rb"\s+", b"", hm.group(1)).rstrip(b"0")
        # Khối CMS thật dài hàng nghìn byte; placeholder chưa ký toàn số 0.
        if len(hex_ky) >= 200:
            return True
    return False
