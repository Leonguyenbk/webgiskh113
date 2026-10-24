"""Áp trực tiếp lên DB: viết lại danhmuchoso_kiem_tra_gcn bỏ CTE (xem
supabase/schema.sql) — bản cũ không dùng được index trim(...) (tạo bởi
scratch_apply_danhmuchoso_index_gcn.py), 0,6-2 giây/lần; bản mới < 1 ms,
kết quả y hệt. Giữ nguyên chữ ký hàm + quyền. Chạy 1 lần, idempotent."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SQL = r"""
create or replace function public.danhmuchoso_kiem_tra_gcn(p_so_seri_gcn text, p_exclude_id bigint default null)
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
as $$
    select jsonb_build_object(
        'da_nhap_form_nhom4', f.n4,
        'da_dong_bo_mplis', f.mplis,
        'da_co_trong_danh_muc', f.dm,
        'ton_tai', f.n4 or f.mplis or f.dm
    )
    from (
        select
            v.g <> '' and exists (
                select 1 from public.du_lieu_gcn x where trim(x.sophathanhgcn) = v.g
            ) as n4,
            v.g <> '' and exists (
                select 1 from public.dong_bo_du_lieu x where trim(x.so_gcn_mplis) = v.g
            ) as mplis,
            v.g <> '' and exists (
                select 1 from public.danhmuchoso x
                where trim(x.so_seri_gcn) = v.g
                  and (p_exclude_id is null or x.id <> p_exclude_id)
            ) as dm
        from (select trim(coalesce(p_so_seri_gcn, '')) as g) v
    ) f;
$$;

revoke all on function public.danhmuchoso_kiem_tra_gcn(text, bigint) from public;
grant execute on function public.danhmuchoso_kiem_tra_gcn(text, bigint) to service_role;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    cur.execute(SQL)
    conn.commit()
    cur.execute("select public.danhmuchoso_kiem_tra_gcn('KHONG_CO_GCN_NAY', null)")
    print("Da cap nhat danhmuchoso_kiem_tra_gcn, thu:", cur.fetchone()[0])
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
