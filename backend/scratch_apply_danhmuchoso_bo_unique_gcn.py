"""Áp trực tiếp lên DB: gỡ ràng buộc UNIQUE trên danhmuchoso.so_seri_gcn
(tạo từ scratch_apply_danhmuchoso.py ban đầu) — phát hiện khi test tính
năng "Nhập hàng loạt từ Excel": dù tầng ứng dụng (danhmuchoso_service)
đã cho phép GCN trùng (để ghi nhận lịch sử, yêu cầu người dùng), INSERT
vẫn bị DB chặn bởi constraint này, báo lỗi
"duplicate key value violates unique constraint danhmuchoso_so_seri_gcn_key".
Chạy 1 lần, idempotent (DROP ... IF EXISTS)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        "alter table public.danhmuchoso drop constraint if exists danhmuchoso_so_seri_gcn_key"
    )
    print("Da go constraint danhmuchoso_so_seri_gcn_key (neu co).")
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
