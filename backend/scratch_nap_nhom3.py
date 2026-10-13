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

SRC_LIST = [
    (r"D:\QUANGTUAN\webgiskh113\DANHSACHGUIXA\DS giao khu vuc krong nang.xlsx", "krong nang"),
    (r"D:\QUANGTUAN\webgiskh113\DANHSACHGUIXA\DS giao khu vuc krong nang.xlsx", "phu xuan"),
    (r"D:\QUANGTUAN\webgiskh113\DANHSACHGUIXA\DS giao khu vuc krong nang.xlsx", "Dlie Ya"),
]
# BỎ QUA sheet "Tam giang" (mã xã 24352) trong cùng file — đã nạp trước đó rồi.

# True = xoá hết bảng rồi nạp lại từ SRC (dùng khi SRC là danh sách đầy đủ
# toàn tỉnh/toàn danh mục). False = chỉ thêm/cập nhật các dòng trong SRC,
# giữ nguyên dữ liệu các xã khác đã có trong bảng (dùng khi SRC là danh
# sách bổ sung cho 1 vài xã mới).
TRUNCATE_TRUOC = False


def chon_sheet_du_lieu(wb):
    # File VPĐK xuất thẳng có thêm sheet "NHAT_KY" (log) trước sheet dữ
    # liệu thật — chọn sheet nào có header bắt đầu bằng MAXA/SOTO/SOTHUA,
    # thay vì giả định luôn là "Sheet1".
    if "Sheet1" in wb.sheetnames:
        return wb["Sheet1"]
    for name in wb.sheetnames:
        ws = wb[name]
        header = next(ws.iter_rows(values_only=True), None)
        if header and str(header[0]).strip().upper() == "MAXA":
            return ws
    raise ValueError("Không tìm thấy sheet dữ liệu (header MAXA/SOTO/SOTHUA) trong file")


def doc_danh_sach(src):
    # src có thể là 1 đường dẫn (tự dò sheet dữ liệu) hoặc (đường dẫn, tên
    # sheet) khi 1 file có nhiều xã, mỗi xã riêng 1 sheet.
    path, sheet_name = src if isinstance(src, tuple) else (src, None)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet_name] if sheet_name else chon_sheet_du_lieu(wb)
    rows = ws.iter_rows(values_only=True)
    next(rows)
    seen = {}
    for row in rows:
        ma_xa, so_to, so_thua, ma_dinh_danh = row[0], row[1], row[2], row[3]
        if ma_xa is None or so_to is None or so_thua is None:
            continue
        try:
            key = (str(int(ma_xa)), int(so_to), int(so_thua))
        except (ValueError, TypeError):
            print(f"  !! bỏ qua dòng lỗi (không phải số): {row[:4]}")
            continue
        seen[key] = ma_dinh_danh  # dòng trùng: giữ mã định danh của dòng cuối cùng
    wb.close()
    return [(ma_xa, so_to, so_thua, ma_dinh_danh) for (ma_xa, so_to, so_thua), ma_dinh_danh in seen.items()]


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()

    if TRUNCATE_TRUOC:
        cur.execute("truncate table nhom3_can_thu_thap restart identity")

    for src in SRC_LIST:
        danh_sach = doc_danh_sach(src)
        ma_xa_trong_file = sorted({row[0] for row in danh_sach})
        print(f"{src}: {len(danh_sach)} thửa duy nhất, mã xã: {ma_xa_trong_file}")

        if TRUNCATE_TRUOC:
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
