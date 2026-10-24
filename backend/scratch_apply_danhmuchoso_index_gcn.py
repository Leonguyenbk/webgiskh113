"""Áp trực tiếp lên DB: index biểu thức trim(...) cho 3 cột GCN mà
danhmuchoso_kiem_tra_gcn tra cứu (xem supabase/schema.sql) — trước đó mỗi
lần kiểm tra quét tuần tự ~3,4 triệu dòng, 2-5 giây/lần. CONCURRENTLY: không
khoá ghi bảng trong lúc tạo. Chạy 1 lần, idempotent (IF NOT EXISTS)."""
from __future__ import annotations

import sys
import time

import psycopg2

from app.config import Config

INDEXES = [
    "create index concurrently if not exists idx_danhmuchoso_so_seri_gcn_trim on public.danhmuchoso (trim(so_seri_gcn))",
    "create index concurrently if not exists idx_du_lieu_gcn_sophathanhgcn_trim on public.du_lieu_gcn (trim(sophathanhgcn))",
    "create index concurrently if not exists idx_dong_bo_du_lieu_so_gcn_mplis_trim on public.dong_bo_du_lieu (trim(so_gcn_mplis))",
]


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    conn.autocommit = True  # CREATE INDEX CONCURRENTLY không chạy được trong transaction
    cur = conn.cursor()
    cur.execute("set statement_timeout = 0")
    for sql in INDEXES:
        start = time.time()
        cur.execute(sql)
        print(f"OK ({time.time() - start:.1f}s): {sql}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
