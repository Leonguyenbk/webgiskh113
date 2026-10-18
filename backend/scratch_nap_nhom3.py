"""Nạp danh sách Nhóm 3 vào bảng public.nhom3_can_thu_thap — chạy tay khi có
danh sách mới. SRC có thể là danh sách TOÀN BỘ (TRUNCATE rồi nạp lại) hoặc
danh sách BỔ SUNG cho 1 vài xã chưa có (UPSERT theo khoá ma_xa+so_to+so_thua,
không đụng tới các xã khác đã nạp trước đó) — chọn bằng tham số TRUNCATE_TRUOC.
CHI_THEM_MOI = True: file có thể chứa cả thửa đã nạp trước (trùng) lẫn thửa
mới bổ sung — CHỈ insert thửa chưa có trong bảng, giữ nguyên dòng trùng
(không update ma_dinh_danh của dòng đã có).

XOA_THEO_MA_XA_TRUOC = True: dùng khi VPĐK gửi lại file THAY THẾ cho 1 vài
xã cụ thể (không phải toàn tỉnh, không phải chỉ bổ sung) — XOÁ HẾT dòng
nhom3_can_thu_thap của đúng những mã xã xuất hiện trong SRC_LIST rồi nạp
lại từ đầu, các xã khác không đụng tới. Cờ thuoc_du_an của các dòng bị xoá
sẽ mất theo (reset về false cho dòng nạp lại) — kiểm tra trước nếu xã đó
từng đánh dấu ranh dự án (xem public.ranh_du_an) thì chạy lại
luu_ranh_du_an_va_danh_dau_nhom3 sau khi nạp."""
from __future__ import annotations

import sys

import openpyxl
import psycopg2
import psycopg2.extras

from app.config import Config

# "DANHSACHGUIXA/DS GIAO VỀ": VPĐK gửi lại file THAY THẾ cho 10 xã (5 xã
# Tuy An - Phú Yên + 5 xã Ea Kar - Đắk Lắk) — ma_xa trong mỗi file đã kiểm
# tra khớp đúng với mã trong tên file. Không cần force_ma_xa. Trong 10 xã
# này chỉ có 24376 (Ea Knốp) đang có thửa đánh dấu thuoc_du_an (3 thửa, có
# 6 dòng tracking trong nhom3_du_an_danh_dau) — nhớ chạy lại UPDATE từ
# nhom3_du_an_danh_dau cho ma_xa='24376' sau khi nạp.
_GIAOVE = r"D:\QUANGTUAN\webgiskh113\DANHSACHGUIXA\DS GIAO VỀ"
SRC_LIST = [
    rf"{_GIAOVE}\22114_Xã Tuy An Bắc.xlsx",
    rf"{_GIAOVE}\22120_Xã Tuy An Đông.xlsx",
    rf"{_GIAOVE}\22132_Xã Tuy An Tây.xlsx",
    rf"{_GIAOVE}\22147_Xã Ô Loan.xlsx",
    rf"{_GIAOVE}\22153_Xã Tuy An Nam.xlsx",
    rf"{_GIAOVE}\24373_Xã Ea Kar.xlsx",
    rf"{_GIAOVE}\24376_Xã Ea Knốp.xlsx",
    rf"{_GIAOVE}\24400_Xã Ea Păl.xlsx",
    rf"{_GIAOVE}\24403_Xã Ea Ô.xlsx",
    rf"{_GIAOVE}\24406_Xã Cư Yang.xlsx",
]

# True = xoá hết bảng rồi nạp lại từ SRC (dùng khi SRC là danh sách đầy đủ
# toàn tỉnh/toàn danh mục). False = chỉ thêm/cập nhật các dòng trong SRC,
# giữ nguyên dữ liệu các xã khác đã có trong bảng (dùng khi SRC là danh
# sách bổ sung cho 1 vài xã mới).
TRUNCATE_TRUOC = False

# True = file SRC có lẫn cả thửa cũ đã nạp lẫn thửa mới bổ sung — chỉ
# insert thửa CHƯA có trong bảng, không update/đụng tới thửa đã trùng khoá.
CHI_THEM_MOI = False

# True = xoá hết dòng hiện có của đúng những mã xã xuất hiện trong SRC_LIST
# rồi nạp lại từ đầu (file SRC là danh sách THAY THẾ cho các xã đó, không
# phải bổ sung) — các xã khác không nạp trong lần này giữ nguyên.
XOA_THEO_MA_XA_TRUOC = True


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

    danh_sach_theo_src = {src: doc_danh_sach(src) for src in SRC_LIST} if XOA_THEO_MA_XA_TRUOC else None

    if XOA_THEO_MA_XA_TRUOC:
        ma_xa_can_xoa = sorted({row[0] for ds in danh_sach_theo_src.values() for row in ds})
        cur.execute("delete from nhom3_can_thu_thap where ma_xa = any(%s)", (ma_xa_can_xoa,))
        print(f"Đã xoá {cur.rowcount} dòng cũ của các mã xã {ma_xa_can_xoa}")
        conn.commit()

    for src in SRC_LIST:
        danh_sach = danh_sach_theo_src[src] if danh_sach_theo_src is not None else doc_danh_sach(src)
        ma_xa_trong_file = sorted({row[0] for row in danh_sach})
        print(f"{src}: {len(danh_sach)} thửa duy nhất, mã xã: {ma_xa_trong_file}")

        if TRUNCATE_TRUOC or XOA_THEO_MA_XA_TRUOC:
            psycopg2.extras.execute_values(
                cur,
                """insert into nhom3_can_thu_thap (ma_xa, so_to, so_thua, ma_dinh_danh) values %s
                on conflict (ma_xa, so_to, so_thua) do nothing""",
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
