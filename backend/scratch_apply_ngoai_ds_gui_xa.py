"""Áp trực tiếp lên DB: get_parcels_in_view + search_parcels trả thêm cờ
properties.ngoai_ds_gui_xa = thửa KHÔNG có trong danh sách gửi xã
(nhom3_can_thu_thap) của 1 xã ĐÃ có danh sách — bản đồ tô gần đen để người
thu thập không làm nhầm (yêu cầu người dùng, xem NGOAI_DS_COLOR trong
frontend/src/utils/constants.js). Sửa bằng cách lấy định nghĩa đang chạy rồi
thay chuỗi, mỗi chỗ thay phải khớp đúng 1 lần (khớp supabase/schema.sql).
Chạy lại an toàn (đã có ngoai_ds_gui_xa thì bỏ qua)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

FUNCS = [
    "public.get_parcels_in_view(double precision, double precision, double precision, double precision, "
    "double precision, double precision, integer, integer, text, double precision, text[])",
    "public.search_parcels(text, text[], integer, integer, integer, integer, double precision, text)",
]

OLD = "'thuoc_du_an', coalesce(n3.thuoc_du_an, false)\n"
NEW = (
    "'thuoc_du_an', coalesce(n3.thuoc_du_an, false),\n"
    "                -- Thửa không có trong danh sách gửi xã của 1 xã ĐÃ có danh\n"
    "                -- sách -> tô gần đen trên bản đồ (không thu thập nhầm), xem\n"
    "                -- NGOAI_DS_COLOR trong frontend/src/utils/constants.js.\n"
    "                'ngoai_ds_gui_xa', n3.ma_xa is null and exists (\n"
    "                    select 1 from public.nhom3_can_thu_thap x where x.ma_xa = t.ma_xa\n"
    "                )\n"
)


def _thay(sql: str) -> str:
    if sql.count(OLD) != 1:
        raise RuntimeError(f"chuỗi cần thay xuất hiện {sql.count(OLD)} lần: {OLD!r}")
    return sql.replace(OLD, NEW)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--schema":
        path = sys.argv[2]
        text = open(path, encoding="utf-8").read()
        for name in ("get_parcels_in_view", "search_parcels"):
            start = text.index(f"create or replace function public.{name}(")
            end = text.index("$$;", start) + 3
            text = text[:start] + _thay(text[start:end]) + text[end:]
        open(path, "w", encoding="utf-8", newline="").write(text)
        print("OK schema.sql")
        return

    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    cur.execute("set lock_timeout = '15s'")
    for fn in FUNCS:
        cur.execute("select pg_get_functiondef(%s::regprocedure)", (fn,))
        sql = cur.fetchone()[0]
        if "'ngoai_ds_gui_xa'" in sql:
            print("-- da co ngoai_ds_gui_xa, bo qua:", fn.split("(")[0])
            continue
        cur.execute(_thay(sql))
        print("OK", fn.split("(")[0])
    conn.commit()


if __name__ == "__main__":
    sys.exit(main())
