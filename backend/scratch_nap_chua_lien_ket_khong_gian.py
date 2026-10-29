"""Nạp số liệu "chưa liên kết không gian" theo xã từ file VPĐK gửi
(KhoiLuongXa-KH113-20261016.xlsx, sheet TongHopXa, cột "Chưa liên kết
KG") vào bảng public.nhom3_chua_lien_ket_khong_gian — không có số tờ/số
thửa cụ thể, chỉ 1 con số/xã (yêu cầu người dùng, xem
scratch_apply_nhom3_lo_nhap_tru_chi_nhanh_kg.py). File có 102 dòng dữ
liệu (dòng đầu là tổng cộng, bỏ qua) khớp đủ 102/102 xã trong
danhsachxaphuong — đã kiểm tra trước khi chạy. Chạy lại được nhiều lần
(upsert), lần sau ghi đè số liệu lần trước."""
from __future__ import annotations

import sys

import openpyxl
import psycopg2
import psycopg2.extras

from app.config import Config

SRC = r"D:\QUANGTUAN\webgiskh113\KhoiLuongXa-KH113-20261016.xlsx"
NGUON_FILE = "KhoiLuongXa-KH113-20261016.xlsx"


def doc_du_lieu():
    wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
    ws = wb["TongHopXa"]
    rows = list(ws.iter_rows(values_only=True))
    data_rows = [r for r in rows[5:] if r[2] is not None]
    wb.close()
    ket_qua = []
    for r in data_rows:
        ma_xa = str(r[2]).strip()
        ten_xa = r[4]
        kg = int(r[24] or 0)
        # Cột 8 "Nhóm 1 chưa nhập biểu (Chi nhánh KV làm)" lúc chốt số — mốc
        # để nhom3_tong_hop trừ phần Chi nhánh ứng thêm (xem schema.sql).
        n1_goc = int(r[8] or 0)
        ket_qua.append((ma_xa, kg, n1_goc, ten_xa))
    return ket_qua


def main():
    du_lieu = doc_du_lieu()
    print(f"Doc duoc {len(du_lieu)} xa tu file")
    tong = sum(kg for _, kg, _, _ in du_lieu)
    print("Tong cong chua lien ket khong gian:", tong)

    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    psycopg2.extras.execute_values(
        cur,
        """
        insert into public.nhom3_chua_lien_ket_khong_gian (ma_xa, so_luong, n1_chua_nhap_goc, ghi_chu, cap_nhat_luc)
        values %s
        on conflict (ma_xa) do update set
            so_luong = excluded.so_luong,
            n1_chua_nhap_goc = excluded.n1_chua_nhap_goc,
            ghi_chu = excluded.ghi_chu,
            cap_nhat_luc = now()
        """,
        [(ma_xa, kg, n1_goc, f"Nguon: {NGUON_FILE} ({ten_xa})") for ma_xa, kg, n1_goc, ten_xa in du_lieu],
        template="(%s, %s, %s, %s, now())",
    )
    print("Da upsert:", cur.rowcount, "dong")
    conn.commit()

    cur.execute("select count(*), sum(so_luong) from public.nhom3_chua_lien_ket_khong_gian")
    print("Kiem tra lai bang:", cur.fetchone())

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
