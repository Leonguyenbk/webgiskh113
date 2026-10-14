"""Đánh dấu toàn bộ thửa của 1 số xã thuộc "dự án tổng thể" (nằm trong 1
dự án lớn khác, KHÔNG thuộc phạm vi đánh giá Nhóm 3 KH 2959) — khu vực
Đồng Xuân và Cư Kuin, theo yêu cầu người dùng. Khác với luồng thông thường
(nạp "danh sách gửi xã" rồi lưu ranh + chạy luu_ranh_du_an_va_danh_dau_nhom3
để dò giao >=95%): ở đây không có ranh vẽ tay và không có danh sách gửi xã
nào sẽ có cho các xã này -> insert thẳng TOÀN BỘ thửa trong thua_dat của
các xã này vào nhom3_can_thu_thap với thuoc_du_an=true ngay từ đầu (tái
dùng đúng cột/cơ chế đã có: refresh_nhom3_trang_thai_cache() loại các dòng
thuoc_du_an khỏi cache -> không tính vào khối lượng Nhóm 3 gửi xã; map
chính tô vàng + ghi "Thuộc dự án" cho các thửa này, xem
get_parcels_in_view/search_parcels + constants.js DU_AN_COLOR)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

MA_XA_LIST = [
    "22081",  # Xã Đồng Xuân
    "22090",  # Xã Xuân Lãnh
    "22096",  # Xã Phú Mỡ
    "22111",  # Xã Xuân Phước
    "24540",  # Xã Ea Ning
    "24544",  # Xã Ea Ktur
    "24561",  # Xã Dray Bhăng
]


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()

    cur.execute(
        """
        insert into public.nhom3_can_thu_thap (ma_xa, so_to, so_thua, ma_dinh_danh, thuoc_du_an)
        select p.ma_xa, p.so_to, p.so_thua, null, true
        from public.thua_dat p
        where p.ma_xa = any(%s)
        on conflict (ma_xa, so_to, so_thua) do update set thuoc_du_an = true
        """,
        (MA_XA_LIST,),
    )
    print("Đã đánh dấu thuộc_du_an=true, số dòng ảnh hưởng:", cur.rowcount)
    conn.commit()

    cur.execute(
        "select ma_xa, count(*) from public.nhom3_can_thu_thap where ma_xa = any(%s) group by ma_xa order by ma_xa",
        (MA_XA_LIST,),
    )
    for row in cur.fetchall():
        print(" ", row)

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
