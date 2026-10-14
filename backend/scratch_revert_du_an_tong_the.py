"""Hoàn tác scratch_mark_du_an_tong_the.py — user yêu cầu KHÔNG tô màu
vàng/không đánh dấu thuoc_du_an cho Đồng Xuân/Cư Kuin, chỉ cần note trong
bảng thống kê. Xoá lại các dòng vừa insert (toàn bộ có thuoc_du_an=true và
ma_dinh_danh is null cho đúng 7 mã xã đó — là dấu hiệu riêng của batch vừa
thêm, không đụng dòng nào khác)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

MA_XA_LIST = ["22081", "22090", "22096", "22111", "24540", "24544", "24561"]


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """
        delete from public.nhom3_can_thu_thap
        where ma_xa = any(%s) and thuoc_du_an and ma_dinh_danh is null
        """,
        (MA_XA_LIST,),
    )
    print("Đã xoá:", cur.rowcount, "dòng")
    conn.commit()

    cur.execute(
        "select ma_xa, count(*) from public.nhom3_can_thu_thap where ma_xa = any(%s) group by ma_xa",
        (MA_XA_LIST,),
    )
    print("còn lại:", cur.fetchall() or "không còn dòng nào (đúng kỳ vọng)")
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
