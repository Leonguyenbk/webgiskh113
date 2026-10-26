"""Áp trực tiếp lên DB: thêm cột thua_dat.ten_chu_dk (tên chủ đăng ký theo
sổ mục kê cũ — khác ten_chu là chủ hiện tại đọc từ app:tenChu của GML) và
trả thêm trường này trong properties của get_parcels_in_view (cả 2
overload)/search_parcels để khung "Thông tin thửa đất" hiển thị (khớp
supabase/schema.sql).

upsert_thua_dat_diff: ten_chu_dk chỉ GHI khi dòng đưa vào có giá trị — file
GML không có thẻ tenChuDK (đa số bản đồ hiện tại) nạp lại sẽ KHÔNG xóa mất
tên chủ ĐK đã có. Sửa bằng cách lấy định nghĩa đang chạy trong DB rồi thay
chuỗi, mỗi chỗ thay phải khớp đúng 1 lần, không khớp thì dừng (rollback).
Chạy lại an toàn (đã có ten_chu_dk thì bỏ qua hàm đó)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

PROPS_OLD = "'ten_chu', t.ten_chu,"
PROPS_NEW = "'ten_chu', t.ten_chu,\n                'ten_chu_dk', t.ten_chu_dk,"

UPSERT_REPLACES = [
    (
        "nullif(r->>'ten_chu', '') as ten_chu,",
        "nullif(r->>'ten_chu', '') as ten_chu,\n"
        "            nullif(r->>'ten_chu_dk', '') as ten_chu_dk,",
    ),
    (
        "or t.ten_chu is distinct from i.ten_chu",
        "or t.ten_chu is distinct from i.ten_chu\n"
        "           or (i.ten_chu_dk is not null and t.ten_chu_dk is distinct from i.ten_chu_dk)",
    ),
    (
        "(ma_xa, so_to, so_thua, ma_thua_dat, muc_dich_su_dung, dien_tich, ten_chu, dia_chi, geom, updated_at)",
        "(ma_xa, so_to, so_thua, ma_thua_dat, muc_dich_su_dung, dien_tich, ten_chu, ten_chu_dk, dia_chi, geom, updated_at)",
    ),
    (
        "select ma_xa, so_to, so_thua, ma_thua_dat, muc_dich_su_dung, dien_tich, ten_chu, dia_chi, geom, now()",
        "select ma_xa, so_to, so_thua, ma_thua_dat, muc_dich_su_dung, dien_tich, ten_chu, ten_chu_dk, dia_chi, geom, now()",
    ),
    (
        "ten_chu = excluded.ten_chu,",
        "ten_chu = excluded.ten_chu,\n"
        "            ten_chu_dk = coalesce(excluded.ten_chu_dk, thua_dat.ten_chu_dk),",
    ),
]


def _thay(sql: str, old: str, new: str, ten: str) -> str:
    if sql.count(old) != 1:
        raise RuntimeError(f"{ten}: chuỗi cần thay xuất hiện {sql.count(old)} lần: {old!r}")
    return sql.replace(old, new)


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    cur.execute("set lock_timeout = '15s'")
    cur.execute("alter table public.thua_dat add column if not exists ten_chu_dk text")

    cur.execute(
        """
        select p.oid::regprocedure::text, pg_get_functiondef(p.oid)
        from pg_proc p join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public'
          and p.proname in ('get_parcels_in_view', 'search_parcels', 'upsert_thua_dat_diff')
        """
    )
    for ten, sql in cur.fetchall():
        if "ten_chu_dk" in sql:
            print("-- da co ten_chu_dk, bo qua:", ten)
            continue
        if ten.startswith("upsert_thua_dat_diff"):
            for old, new in UPSERT_REPLACES:
                sql = _thay(sql, old, new, ten)
        elif PROPS_OLD not in sql:
            # overload get_parcels_in_view cũ (không có p_nhom) vốn không trả
            # ten_chu, backend không gọi nữa — để nguyên.
            print("-- khong tra ten_chu, bo qua:", ten)
            continue
        else:
            sql = _thay(sql, PROPS_OLD, PROPS_NEW, ten)
        cur.execute(sql)
        print("OK", ten)

    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
