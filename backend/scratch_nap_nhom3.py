"""Nạp danh sách Nhóm 3 vào bảng public.nhom3_can_thu_thap — chạy tay khi có
danh sách mới. SRC có thể là danh sách TOÀN BỘ (TRUNCATE rồi nạp lại) hoặc
danh sách BỔ SUNG cho 1 vài xã chưa có (UPSERT theo khoá ma_xa+so_to+so_thua,
không đụng tới các xã khác đã nạp trước đó) — chọn bằng tham số TRUNCATE_TRUOC.
CHI_THEM_MOI = True: file có thể chứa cả thửa đã nạp trước (trùng) lẫn thửa
mới bổ sung — CHỈ insert thửa chưa có trong bảng, giữ nguyên dòng trùng
(không update ma_dinh_danh của dòng đã có)."""
from __future__ import annotations

import sys

import openpyxl
import psycopg2
import psycopg2.extras

from app.config import Config

_BASE = r"D:\QUANGTUAN\webgiskh113\DANHSACHGUIXA\LOC DANH SACH GUI XA TUY HOA DONG HOA"
SRC_LIST = [
    _BASE + r"\BINH KIEN\22045_Phường Bình Kiến.xlsx",
    # Header cột A của sheet này là số 1 (không phải chữ "MAXA") nên dò
    # sheet tự động (chon_sheet_du_lieu) không nhận ra -> chỉ định thẳng
    # tên sheet duy nhất trong file.
    (_BASE + r"\DONG HOA\PHUONG DONG HOA - 365.xlsx", "DSCanThuThap,DangKy (Do VPĐK(2)"),
    _BASE + r"\HOA HIEP\PHUONG HOA HIEP -325.xlsx",
    # HOA XUAN -3605.xlsx: cột MAXA bị lỗi (số thứ tự dòng 1..16401, không
    # phải mã xã cố định) — ép mã xã = 22291 ("Xã Hòa Xuân", tra
    # danhsachxaphuong) vì cả file chỉ thuộc đúng 1 xã (đúng cấu trúc thư
    # mục LOC DANH SACH GUI XA TUY HOA DONG HOA: mỗi thư mục con = 1
    # xã/phường). SOTO/SOTHUA/MADINHDANH không bị ảnh hưởng.
    (_BASE + r"\HOA XUAN\HOA XUAN -3605.xlsx", None, "22291"),
]

# True = xoá hết bảng rồi nạp lại từ SRC (dùng khi SRC là danh sách đầy đủ
# toàn tỉnh/toàn danh mục). False = chỉ thêm/cập nhật các dòng trong SRC,
# giữ nguyên dữ liệu các xã khác đã có trong bảng (dùng khi SRC là danh
# sách bổ sung cho 1 vài xã mới).
TRUNCATE_TRUOC = False

# True = file SRC có lẫn cả thửa cũ đã nạp lẫn thửa mới bổ sung — chỉ
# insert thửa CHƯA có trong bảng, không update/đụng tới thửa đã trùng khoá.
CHI_THEM_MOI = True


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
    # src có thể là 1 đường dẫn (tự dò sheet dữ liệu), (đường dẫn, tên
    # sheet) khi 1 file có nhiều xã mỗi xã riêng 1 sheet, hoặc (đường dẫn,
    # tên sheet hoặc None, force_ma_xa) khi cột MAXA trong file bị lỗi
    # (không phải mã xã cố định) — ép mọi dòng về force_ma_xa, bỏ qua giá
    # trị cột MAXA gốc.
    force_ma_xa = None
    if isinstance(src, tuple):
        if len(src) == 3:
            path, sheet_name, force_ma_xa = src
        else:
            path, sheet_name = src
    else:
        path, sheet_name = src, None
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet_name] if sheet_name else chon_sheet_du_lieu(wb)
    rows = ws.iter_rows(values_only=True)
    next(rows)
    seen = {}
    for row in rows:
        ma_xa, so_to, so_thua, ma_dinh_danh = row[0], row[1], row[2], row[3]
        if force_ma_xa is not None:
            ma_xa = force_ma_xa
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
        elif CHI_THEM_MOI:
            cur.execute("select count(*) from nhom3_can_thu_thap")
            truoc = cur.fetchone()[0]
            psycopg2.extras.execute_values(
                cur,
                """insert into nhom3_can_thu_thap (ma_xa, so_to, so_thua, ma_dinh_danh) values %s
                on conflict (ma_xa, so_to, so_thua) do nothing""",
                danh_sach,
                page_size=5000,
            )
            cur.execute("select count(*) from nhom3_can_thu_thap")
            sau = cur.fetchone()[0]
            print(f"  -> thửa mới thêm vào: {sau - truoc}, thửa trùng bỏ qua: {len(danh_sach) - (sau - truoc)}")
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
