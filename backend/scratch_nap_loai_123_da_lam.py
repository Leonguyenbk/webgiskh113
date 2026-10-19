"""Nạp số liệu "Đã làm Loại 1/2/3" theo xã từ file VPĐK gửi
(DANHSACHGUIXA/KhoiLuongXa-KH113-20261019.xlsx, sheet "Tong hop Nhom
3", cột MÃ XÃ/Đã làm Loại 1/Đã làm Loại 2/Đã làm Loại 3) vào bảng
public.nhom3_loai_123_da_lam — không có số tờ/số thửa cụ thể, chỉ 3 con
số/xã (cùng kiểu với scratch_nap_chua_lien_ket_khong_gian.py). File có
102 dòng dữ liệu, khớp đủ 102/102 xã trong danhsachxaphuong — đã kiểm
tra trước khi chạy. Chạy lại được nhiều lần (upsert), lần sau ghi đè số
liệu lần trước."""
from __future__ import annotations

import sys

import openpyxl
import psycopg2
import psycopg2.extras

from app.config import Config

SRC_FILE = "../DANHSACHGUIXA/KhoiLuongXa-KH113-20261019.xlsx"
SHEET_NAME = "Tong hop Nhom 3"


def doc_du_lieu():
    wb = openpyxl.load_workbook(SRC_FILE, read_only=True, data_only=True)
    ws = wb[SHEET_NAME]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    header = rows[0]
    assert header[0] == "MÃ XÃ", f"Cột A không phải MÃ XÃ: {header}"
    ket_qua = []
    for row in rows[1:]:
        ma_xa = str(row[0]).strip()
        if not ma_xa:
            continue
        loai_1 = int(row[2] or 0)
        loai_2 = int(row[3] or 0)
        loai_3 = int(row[4] or 0)
        ket_qua.append((ma_xa, loai_1, loai_2, loai_3))
    return ket_qua


def main():
    du_lieu = doc_du_lieu()
    print(f"Doc duoc {len(du_lieu)} dong tu {SRC_FILE}")

    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()

    cur.execute("select ma_xa from public.danhsachxaphuong")
    ma_xa_db = {r[0] for r in cur.fetchall()}
    ma_xa_file = {r[0] for r in du_lieu}
    thieu = ma_xa_file - ma_xa_db
    if thieu:
        print("CANH BAO - ma xa trong file khong co trong danhsachxaphuong:", thieu)

    psycopg2.extras.execute_values(
        cur,
        """
        insert into public.nhom3_loai_123_da_lam (ma_xa, loai_1, loai_2, loai_3, cap_nhat_luc)
        values %s
        on conflict (ma_xa) do update set
            loai_1 = excluded.loai_1,
            loai_2 = excluded.loai_2,
            loai_3 = excluded.loai_3,
            cap_nhat_luc = now()
        """,
        du_lieu,
        template="(%s, %s, %s, %s, now())",
    )
    conn.commit()

    cur.execute("select count(*), sum(loai_1), sum(loai_2), sum(loai_3) from public.nhom3_loai_123_da_lam")
    print("Sau khi nap:", cur.fetchone())

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
