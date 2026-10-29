"""Áp trực tiếp lên DB: nhom3_tong_hop.tong_ke_hoach chỉ cộng Loại 3 đã làm
(loai_3_da_lam) — Loại 1 và Loại 2 KHÔNG tính vào "Tổng danh sách theo kế
hoạch" trên trang /nhom-3-con-thieu + Excel xuất (yêu cầu người dùng; trước
đó cộng cả Loại 1+2+3 làm tổng Phường Tuy Hòa vượt cả danh sách gửi xã).
"Đã thực hiện theo kế hoạch" vẫn cộng loai_123_da_lam ở tầng ứng dụng.
Sửa bằng cách lấy định nghĩa đang chạy rồi thay chuỗi, mỗi chỗ thay phải
khớp đúng 1 lần (khớp supabase/schema.sql). Chạy lại an toàn (đã có
loai_3_da_lam thì bỏ qua)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

THAY = [
    (
        "coalesce(l123.loai_1, 0) as loai_1_da_lam,\n",
        "coalesce(l123.loai_1, 0) as loai_1_da_lam,\n"
        "            coalesce(l123.loai_3, 0) as loai_3_da_lam,\n",
    ),
    (
        "(tong_cache - da_nhom_1_2_chua_nhap - chua_lien_ket_khong_gian + loai_123_da_lam) as tong_ke_hoach",
        "(tong_cache - da_nhom_1_2_chua_nhap - chua_lien_ket_khong_gian + loai_3_da_lam) as tong_ke_hoach",
    ),
]


def _thay(sql: str) -> str:
    for old, new in THAY:
        if sql.count(old) != 1:
            raise RuntimeError(f"chuỗi cần thay xuất hiện {sql.count(old)} lần: {old!r}")
        sql = sql.replace(old, new)
    return sql


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--schema":
        path = sys.argv[2]
        text = open(path, encoding="utf-8").read()
        start = text.index("create or replace function public.nhom3_tong_hop(")
        end = text.index("$$;", start) + 3
        open(path, "w", encoding="utf-8", newline="").write(text[:start] + _thay(text[start:end]) + text[end:])
        print("OK schema.sql")
        return

    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    cur.execute("set lock_timeout = '15s'")
    cur.execute("select pg_get_functiondef('public.nhom3_tong_hop(integer)'::regprocedure)")
    sql = cur.fetchone()[0]
    if "loai_3_da_lam" in sql:
        print("-- tong_ke_hoach da chi cong loai_3_da_lam, bo qua")
        return
    cur.execute(_thay(sql))
    conn.commit()
    cur.execute("select public.nhom3_tong_hop(null) -> 'tong_ke_hoach'")
    print("OK, tong_ke_hoach =", cur.fetchone()[0])


if __name__ == "__main__":
    sys.exit(main())
