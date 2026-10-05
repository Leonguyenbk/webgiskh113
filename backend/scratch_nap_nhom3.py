"""Nạp 1 lần DANHSACHNHOM3BMT.xlsx vào bảng public.nhom3_can_thu_thap —
chạy 1 lần rồi thôi, không phải route/service thường trực."""
from __future__ import annotations

import openpyxl
import psycopg2
import psycopg2.extras

from app.config import Config

SRC = r"D:\QUANGTUAN\webgiskh113\DANHSACHNHOM3BMT.xlsx"


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

    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    cur.execute("truncate table nhom3_can_thu_thap restart identity")
    psycopg2.extras.execute_values(
        cur,
        "insert into nhom3_can_thu_thap (ma_xa, so_to, so_thua, ma_dinh_danh) values %s",
        danh_sach,
        page_size=5000,
    )
    conn.commit()
    cur.execute("select count(*) from nhom3_can_thu_thap")
    print("Đã nạp, tổng dòng trong bảng:", cur.fetchone()[0])
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
