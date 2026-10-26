"""Áp trực tiếp lên DB: tạo hàm public.thong_ke_nhom3_xa(p_ma_xa, p_so_ngay)
— thống kê Nhóm 3 của 1 xã theo ranh thôn + số thửa nhập biểu web theo
ngày, dùng cho API dashboard /api/thong-ke/buon-ma-thuot (khớp
supabase/schema.sql). Chạy lại an toàn (create or replace)."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SCHEMA_SQL = r"""
create or replace function public.thong_ke_nhom3_xa(p_ma_xa text, p_so_ngay integer default 60)
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
set statement_timeout = '30s'
as $$
    with n3 as (
        select
            c.la_nhom_1_2,
            c.co_nhap,
            c.da_thu_thap,
            coalesce(n.thuoc_du_an, false) as thuoc_du_an,
            t.geom,
            t.muc_dich_su_dung
        from public.nhom3_trang_thai_cache c
        left join public.nhom3_can_thu_thap n
            on n.ma_xa = c.ma_xa and n.so_to = c.so_to and n.so_thua = c.so_thua
        left join public.thua_dat t
            on t.ma_xa = c.ma_xa and t.so_to = c.so_to and t.so_thua = c.so_thua
        where c.ma_xa = p_ma_xa
    ),
    gan_thon as (
        select
            n3.*,
            coalesce(
                (
                    select r.ten_thon
                    from public.ranh_gioi_thon r
                    where r.ma_xa = p_ma_xa
                      and n3.geom is not null
                      and ST_Contains(r.geom, ST_PointOnSurface(n3.geom))
                    limit 1
                ),
                case when n3.geom is null then '(Chưa có trên bản đồ)' else '(Ngoài ranh thôn)' end
            ) as ten_thon
        from n3
    ),
    theo_thon as (
        select
            ten_thon,
            -- Cùng quy ước "tong" của nhom3_tong_hop: không tính thửa Nhóm
            -- 1/2 chưa nhập biểu (Chi nhánh làm trực tiếp).
            count(*) filter (where not (la_nhom_1_2 and not co_nhap)) as tong,
            count(*) filter (where la_nhom_1_2) as da_nhom_1_2,
            count(*) filter (where not la_nhom_1_2 and da_thu_thap) as da_thu_thap,
            count(*) filter (where not la_nhom_1_2 and not da_thu_thap) as con_thieu,
            count(*) filter (
                where not la_nhom_1_2 and not da_thu_thap
                  and (muc_dich_su_dung ilike '%ODT%' or muc_dich_su_dung ilike '%ONT%')
            ) as con_thieu_dat_o,
            count(*) filter (where not la_nhom_1_2 and not da_thu_thap and thuoc_du_an) as con_thieu_thuoc_du_an
        from gan_thon
        group by ten_thon
    ),
    -- Thửa nhập qua biểu Nhóm 4 trên web theo ngày (giờ Việt Nam) — chỉ
    -- tính nguồn NHOM4_FORM: dòng đồng bộ Google Sheet bị tạo lại mỗi lần
    -- đồng bộ nên created_at của chúng không phải ngày nhập thật.
    theo_ngay as (
        select ngay, count(*) as so_thua
        from (
            select (min(g.created_at) at time zone 'Asia/Ho_Chi_Minh')::date as ngay
            from public.du_lieu_gcn g
            where g.madvhc = p_ma_xa and g.ma_nguon = 'NHOM4_FORM'
            group by g.madvhc_soto_sothua
        ) f
        where ngay >= (now() at time zone 'Asia/Ho_Chi_Minh')::date - greatest(coalesce(p_so_ngay, 60), 1) + 1
        group by ngay
    )
    select jsonb_build_object(
        'so_thon', (select count(*) from public.ranh_gioi_thon where ma_xa = p_ma_xa),
        'theo_thon', coalesce(
            (
                select jsonb_agg(
                    to_jsonb(tt) || jsonb_build_object(
                        'ty_le_hoan_thanh',
                        case when tt.tong > 0
                             then round((tt.da_nhom_1_2 + tt.da_thu_thap) * 100.0 / tt.tong, 1)
                             else 0 end
                    )
                    order by tt.con_thieu desc, tt.ten_thon
                )
                from theo_thon tt
            ),
            '[]'::jsonb
        ),
        'nhap_bieu_web_theo_ngay', coalesce(
            (select jsonb_agg(to_jsonb(tn) order by tn.ngay) from theo_ngay tn),
            '[]'::jsonb
        )
    );
$$;

revoke all on function public.thong_ke_nhom3_xa(text, integer) from public;
grant execute on function public.thong_ke_nhom3_xa(text, integer) to service_role;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()
    cur.execute("set lock_timeout = '15s'")
    cur.execute(SCHEMA_SQL)
    conn.commit()
    cur.execute("select jsonb_array_length(public.thong_ke_nhom3_xa('24133') -> 'theo_thon')")
    print("OK, so dong theo_thon BMT:", cur.fetchone()[0])
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
