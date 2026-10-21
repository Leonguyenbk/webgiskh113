"""Khôi phục cờ thuoc_du_an cho 3 xã Ea Rốk (24217), Ea Bung (24229),
Ea Súp (24211) sau khi xoá/nạp lại nhom3_can_thu_thap (scratch_nap_nhom3.py,
XOA_THEO_MA_XA_TRUOC, 20261021) — xoá hết dòng cũ thì mất luôn cờ
thuoc_du_an của thửa đã từng đánh dấu thuộc ranh dự án.

Bước 1: khôi phục từ public.nhom3_du_an_danh_dau (giống
scratch_apply_easup_restore_thuoc_du_an.py) — đủ cho 24217 (47 thửa) và
24229 (7 thửa).

Bước 2: riêng 24211 còn 785 thửa đánh dấu TRƯỚC khi có bảng tracking này
(xem scratch_apply_easup_restore_thuoc_du_an_tu_backup.py) — khôi phục
thêm từ scratch_easup_thuoc_du_an_keys.tsv. Chạy 1 lần."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

MA_XA_LIST = ["24217", "24229", "24211"]
KEYS_FILE_24211 = "scratch_easup_thuoc_du_an_keys.tsv"


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(
        """
        update public.nhom3_can_thu_thap n3
        set thuoc_du_an = true
        from public.nhom3_du_an_danh_dau d
        where n3.ma_xa = d.ma_xa and n3.so_to = d.so_to and n3.so_thua = d.so_thua
          and n3.ma_xa = any(%s)
          and not n3.thuoc_du_an
        """,
        (MA_XA_LIST,),
    )
    print(f"Đã khôi phục thuoc_du_an từ nhom3_du_an_danh_dau cho {cur.rowcount} thửa ({MA_XA_LIST})")

    with open(KEYS_FILE_24211, encoding="utf-8") as f:
        keys = [tuple(int(x) for x in line.strip().split("\t")) for line in f if line.strip()]
    print(f"Đọc {len(keys)} khoá (so_to, so_thua) từ {KEYS_FILE_24211} (riêng 24211)")

    so_to_arr = [k[0] for k in keys]
    so_thua_arr = [k[1] for k in keys]
    cur.execute(
        """
        update public.nhom3_can_thu_thap n3
        set thuoc_du_an = true
        from unnest(%s::integer[], %s::integer[]) as k(so_to, so_thua)
        where n3.ma_xa = '24211' and n3.so_to = k.so_to and n3.so_thua = k.so_thua
          and not n3.thuoc_du_an
        """,
        (so_to_arr, so_thua_arr),
    )
    print(f"Đã khôi phục thêm thuoc_du_an từ backup cho {cur.rowcount} thửa (ma_xa=24211)")

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
