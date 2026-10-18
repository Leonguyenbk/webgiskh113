"""Khôi phục cờ thuoc_du_an cho xã Ea Súp (24211) sau khi xoá/nạp lại
nhom3_can_thu_thap (scratch_nap_nhom3.py, XOA_THEO_MA_XA_TRUOC) — xoá hết
dòng cũ thì mất luôn cờ thuoc_du_an của 785 thửa đã từng đánh dấu thuộc
ranh dự án.

KHÔNG cần tính lại giao ranh (geometry) — bảng nhom3_du_an_danh_dau đã
lưu sẵn đúng (ma_xa, so_to, so_thua) nào đã được 1 ranh dự án CHƯA HUỶ
đánh dấu (huy_danh_dau_du_an_nhom3 xoá thẳng dòng khỏi bảng này khi huỷ,
nên dòng còn lại trong bảng luôn là marking đang có hiệu lực) — chỉ cần
UPDATE lại thuoc_du_an = true cho thửa nào (sau khi nạp lại) vẫn khớp
đúng so_to/so_thua đã lưu. Chạy 1 lần, ngay sau khi nạp lại Ea Súp."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

MA_XA = "24211"


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(
        """
        update public.nhom3_can_thu_thap n3
        set thuoc_du_an = true
        from public.nhom3_du_an_danh_dau d
        where n3.ma_xa = d.ma_xa and n3.so_to = d.so_to and n3.so_thua = d.so_thua
          and n3.ma_xa = %s
          and not n3.thuoc_du_an
        """,
        (MA_XA,),
    )
    print(f"Đã khôi phục thuoc_du_an cho {cur.rowcount} thửa (ma_xa={MA_XA})")

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
