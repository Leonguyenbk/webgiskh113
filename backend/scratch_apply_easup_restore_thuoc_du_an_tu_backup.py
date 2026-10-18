"""Khôi phục cờ thuoc_du_an cho 785 thửa Ea Súp (24211) từ bản backup sáng
nay (webgis_20261018_030002.dump) — scratch_apply_easup_restore_thuoc_du_an.py
(đọc từ nhom3_du_an_danh_dau) trả về 0 vì 785 thửa này được đánh dấu TRƯỚC
khi cơ chế ranh_du_an/nhom3_du_an_danh_dau tồn tại (xã nạp lúc 08:43
13/10, cơ chế ranh thêm lúc 15:19 cùng ngày — xem git log 62c91a7/3ea0117)
nên không có dòng tracking nào để dò lại bằng khoá. Danh sách (so_to,
so_thua) đã trích từ backup ra scratch_easup_thuoc_du_an_keys.tsv (785
dòng, dùng pg_restore --data-only -t nhom3_can_thu_thap). Chỉ áp cho thửa
nào SAU KHI nạp lại (scratch_nap_nhom3.py, XOA_THEO_MA_XA_TRUOC) vẫn còn
khớp đúng so_to/so_thua cũ — thửa nào không còn trong danh sách mới (đổi
số) thì bỏ qua, không có gì để đánh dấu lại. Chạy 1 lần."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

MA_XA = "24211"
KEYS_FILE = "scratch_easup_thuoc_du_an_keys.tsv"


def main():
    with open(KEYS_FILE, encoding="utf-8") as f:
        keys = [tuple(int(x) for x in line.strip().split("\t")) for line in f if line.strip()]
    print(f"Đọc {len(keys)} khoá (so_to, so_thua) từ {KEYS_FILE}")

    conn = psycopg2.connect(Config.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    so_to_arr = [k[0] for k in keys]
    so_thua_arr = [k[1] for k in keys]
    cur.execute(
        """
        update public.nhom3_can_thu_thap n3
        set thuoc_du_an = true
        from unnest(%s::integer[], %s::integer[]) as k(so_to, so_thua)
        where n3.ma_xa = %s and n3.so_to = k.so_to and n3.so_thua = k.so_thua
        """,
        (so_to_arr, so_thua_arr, MA_XA),
    )
    print(f"Đã khôi phục thuoc_du_an cho {cur.rowcount}/{len(keys)} thửa (ma_xa={MA_XA})")

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
