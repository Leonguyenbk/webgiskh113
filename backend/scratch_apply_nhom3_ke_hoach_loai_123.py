"""Áp trực tiếp lên DB: nhom3_tong_hop.tong_ke_hoach cộng cả Loại 1 + Loại 2
+ Loại 3 đã làm (loai_123_da_lam) thay vì chỉ Loại 1 — "Tổng danh sách theo
kế hoạch" trên trang /nhom-3-con-thieu + Excel xuất (yêu cầu người dùng),
cùng phạm vi với "Đã thực hiện theo kế hoạch". Sửa bằng cách lấy định nghĩa
đang chạy rồi thay chuỗi, mỗi chỗ thay phải khớp đúng 1 lần (khớp
supabase/schema.sql). Chạy lại an toàn (đã cộng loai_123_da_lam thì bỏ qua)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

OLD = "(tong_cache - da_nhom_1_2_chua_nhap - chua_lien_ket_khong_gian + loai_1_da_lam) as tong_ke_hoach"
NEW = "(tong_cache - da_nhom_1_2_chua_nhap - chua_lien_ket_khong_gian + loai_123_da_lam) as tong_ke_hoach"


def _thay(sql: str) -> str:
    if sql.count(OLD) != 1:
        raise RuntimeError(f"chuỗi cần thay xuất hiện {sql.count(OLD)} lần: {OLD!r}")
    return sql.replace(OLD, NEW)


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
    if NEW in sql:
        print("-- tong_ke_hoach da cong loai_123_da_lam, bo qua")
        return
    cur.execute(_thay(sql))
    conn.commit()
    cur.execute("select public.nhom3_tong_hop(null) -> 'tong_ke_hoach'")
    print("OK, tong_ke_hoach =", cur.fetchone()[0])


if __name__ == "__main__":
    sys.exit(main())
