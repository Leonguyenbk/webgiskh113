"""Nạp danh sách Nhóm 3 vào bảng public.nhom3_can_thu_thap — chạy tay khi có
danh sách mới. SRC có thể là danh sách TOÀN BỘ (TRUNCATE rồi nạp lại) hoặc
danh sách BỔ SUNG cho 1 vài xã chưa có (UPSERT theo khoá ma_xa+so_to+so_thua,
không đụng tới các xã khác đã nạp trước đó) — chọn bằng tham số TRUNCATE_TRUOC."""
from __future__ import annotations

import sys

import openpyxl
import psycopg2
import psycopg2.extras

from app.config import Config

SRC = r"D:\QUANGTUAN\webgiskh113\TamGiang_Nhom3.xlsx"

# True = xoá hết bảng rồi nạp lại từ SRC (dùng khi SRC là danh sách đầy đủ
# toàn tỉnh/toàn danh mục). False = chỉ thêm/cập nhật các dòng trong SRC,
# giữ nguyên dữ liệu các xã khác đã có trong bảng (dùng khi SRC là danh
# sách bổ sung cho 1 vài xã mới).
TRUNCATE_TRUOC = False


def doc_danh_sach():
    wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
    ws = wb["Sheet1"]
    rows = ws.iter_rows(values_only=True)
    next(rows)
    seen = {}
    for ma_xa, so_to, so_thua, ma_dinh_danh in rows:
        if ma_xa is None or so_to is None or so_thua is None:
            continue
        key = (str(int(ma_xa)), int(so_to), int(so_thua))
        seen[key] = ma_dinh_danh  # dòng trùng: giữ mã định danh của dòng cuối cùng
    wb.close()
    return [(ma_xa, so_to, so_thua, ma_dinh_danh) for (ma_xa, so_to, so_thua), ma_dinh_danh in seen.items()]


def main():
    danh_sach = doc_danh_sach()
    print(f"{len(danh_sach)} thửa duy nhất để nạp")
    ma_xa_trong_file = sorted({row[0] for row in danh_sach})
    print("mã xã trong file:", ma_xa_trong_file)

    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()

    if TRUNCATE_TRUOC:
        cur.execute("truncate table nhom3_can_thu_thap restart identity")
        psycopg2.extras.execute_values(
            cur,
            "insert into nhom3_can_thu_thap (ma_xa, so_to, so_thua, ma_dinh_danh) values %s",
            danh_sach,
            page_size=5000,
        )
    else:
        psycopg2.extras.execute_values(
            cur,
            """insert into nhom3_can_thu_thap (ma_xa, so_to, so_thua, ma_dinh_danh) values %s
            on conflict (ma_xa, so_to, so_thua) do update set ma_dinh_danh = excluded.ma_dinh_danh""",
            danh_sach,
            page_size=5000,
        )

    conn.commit()
    cur.execute("select count(*) from nhom3_can_thu_thap")
    print("Đã nạp, tổng dòng trong bảng:", cur.fetchone()[0])
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
