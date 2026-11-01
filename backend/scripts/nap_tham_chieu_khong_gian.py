"""Nạp file BANGTHAMCHIEUKHONGGIANTHUADAT_*.xlsx (thửa đã tham chiếu không
gian nhưng chưa lên Nhóm 1) vào public.nhom3_tham_chieu_khong_gian — upsert
theo (ma_xa, so_to, so_thua), chạy lại với file mới chỉ thêm/cập nhật, không
xoá thửa cũ. Dòng thiếu số tờ/số thửa không gian (chưa tham chiếu) bỏ qua.

Cách chạy (từ thư mục backend):
    .venv/Scripts/python.exe scripts/nap_tham_chieu_khong_gian.py "<file.xlsx>"
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import psycopg2
from openpyxl import load_workbook
from psycopg2.extras import execute_values

from app.config import Config

COT_MA_XA = "maXa"
COT_SO_TO = "soHieuToBanDoKhongGian"
COT_SO_THUA = "soThuTuThuaKhongGian"
COT_GHI_CHU = "ghiChu"


def _so(value):
    text = str(value if value is not None else "").strip()
    return int(text) if text.isdigit() else None


def doc_file(path):
    ws = load_workbook(path, read_only=True).active
    rows = ws.iter_rows(values_only=True)
    header = [str(h or "").strip() for h in next(rows)]
    i_xa, i_to, i_thua = header.index(COT_MA_XA), header.index(COT_SO_TO), header.index(COT_SO_THUA)
    i_gc = header.index(COT_GHI_CHU) if COT_GHI_CHU in header else None
    items, bo_qua = {}, 0
    for r in rows:
        ma_xa = str(r[i_xa] or "").strip()
        so_to, so_thua = _so(r[i_to]), _so(r[i_thua])
        if not ma_xa or so_to is None or so_thua is None:
            bo_qua += 1
            continue
        ghi_chu = str(r[i_gc]).strip() if i_gc is not None and r[i_gc] not in (None, "") else None
        items[(ma_xa, so_to, so_thua)] = ghi_chu
    return items, bo_qua


def main():
    path = sys.argv[1]
    items, bo_qua = doc_file(path)
    nguon = os.path.basename(path)
    conn = psycopg2.connect(Config.DATABASE_URL)
    with conn, conn.cursor() as cur:
        execute_values(
            cur,
            """insert into public.nhom3_tham_chieu_khong_gian (ma_xa, so_to, so_thua, ghi_chu, nguon_file)
               values %s
               on conflict (ma_xa, so_to, so_thua) do update set
                   ghi_chu = excluded.ghi_chu, nguon_file = excluded.nguon_file, cap_nhat_luc = now()""",
            [(x, t, s, g, nguon) for (x, t, s), g in items.items()],
            page_size=5000,
        )
        cur.execute("select count(*) from public.nhom3_tham_chieu_khong_gian")
        tong = cur.fetchone()[0]
    print(f"Đã upsert {len(items)} thửa (bỏ qua {bo_qua} dòng thiếu số tờ/thửa không gian). Bảng hiện có {tong} thửa.")


if __name__ == "__main__":
    main()
