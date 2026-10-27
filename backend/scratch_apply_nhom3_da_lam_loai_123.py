"""Áp trực tiếp lên DB: nhom3_tong_hop trả thêm loai_123_da_lam = Loại 1 +
Loại 2 + Loại 3 đã làm (public.nhom3_loai_123_da_lam) theo từng xã và tổng —
"Đã thực hiện theo kế hoạch" trên trang /nhom-3-con-thieu + Excel xuất cộng
cả 3 loại như file KhoiLuongXa-KH113 (yêu cầu người dùng). tong_ke_hoach
giữ nguyên (chỉ cộng Loại 1). Sửa bằng cách lấy định nghĩa đang chạy rồi
thay chuỗi, mỗi chỗ thay phải khớp đúng 1 lần (khớp supabase/schema.sql).
Chạy lại an toàn (đã có loai_123_da_lam thì bỏ qua)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

REPLACES = [
    (
        "coalesce(l123.loai_1, 0) as loai_1_da_lam",
        "coalesce(l123.loai_1, 0) as loai_1_da_lam,\n"
        "            coalesce(l123.loai_1, 0) + coalesce(l123.loai_2, 0) + coalesce(l123.loai_3, 0) as loai_123_da_lam",
    ),
    (
        "kg.so_luong, l123.loai_1\n",
        "kg.so_luong, l123.loai_1, l123.loai_2, l123.loai_3\n",
    ),
    (
        "            loai_1_da_lam,\n",
        "            loai_1_da_lam,\n            loai_123_da_lam,\n",
    ),
    (
        "tg.to_giam_sat, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, g.ghi_chu",
        "tg.to_giam_sat, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, g.ghi_chu",
    ),
    (
        "'loai_1_da_lam', coalesce(sum(loai_1_da_lam), 0),",
        "'loai_1_da_lam', coalesce(sum(loai_1_da_lam), 0),\n"
        "        'loai_123_da_lam', coalesce(sum(loai_123_da_lam), 0),",
    ),
]


def _thay(sql: str) -> str:
    for old, new in REPLACES:
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
    if "as loai_123_da_lam" in sql:
        print("-- da co loai_123_da_lam, bo qua")
        return
    cur.execute(_thay(sql))
    conn.commit()
    cur.execute("select public.nhom3_tong_hop(null) -> 'loai_123_da_lam'")
    print("OK, loai_123_da_lam =", cur.fetchone()[0])


if __name__ == "__main__":
    sys.exit(main())
