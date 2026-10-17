"""Áp trực tiếp lên DB: thêm "Nhà nước giao đất để quản lý" (và các biến
thể: NN giao để quản lý, Nhà nước giao quản lý, lỗi gõ "nươớc"...) vào danh
sách nguồn gốc sử dụng đất hợp lệ (_nhom3_nguon_goc_hop_le).

Lý do: đây là nguồn gốc CÓ THẬT — đất công ích/đất Nhà nước giao UBND xã
quản lý — khác hẳn các nguồn gốc hộ gia đình/cá nhân đã có trong danh sách
(nhận chuyển nhượng, thừa kế, tặng cho, Nhà nước giao đất có/không thu
tiền...), KHÔNG phải lỗi nhập sai nên bị chặn oan khỏi "đã đủ dữ liệu".
Phân tích tại Tuy An Đông cho thấy đây là nguyên nhân chính (88%) khiến
thửa "đã nhập biểu" bị tính "chưa đạt chuẩn".

CHỈ cần backfill lại nhom3_du_du_lieu cho các dòng ĐANG false — hàm mới
chỉ NỚI LỎNG hơn (thêm 1 điều kiện or), không bao giờ làm 1 dòng đang true
thành false. Sau đó refresh lại nhom3_trang_thai_cache. Chạy 1 lần."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SCHEMA_SQL = r"""
create or replace function public._nhom3_nguon_goc_hop_le(gia_tri text)
returns boolean
language sql
immutable
set search_path = public, extensions
as $$
    with v as (
        select regexp_replace(
                 lower(extensions.unaccent(coalesce(gia_tri, ''))),
                 '\s+', ' ', 'g'
               ) as t
    )
    select
        t <> ''
        and (
            t ~ 'chuyen nhuong|sang nhuong|mua lai'
            or t ~ 'thua ke'
            or t ~ 'tang cho|cho tang|tang tu'
            or t ~ 'nha nuoc giao dat (khong|co) thu tien'
            or t ~ 'cho thue dat.*tra tien (hang nam|mot lan)'
            or t ~ 'cnq.{0,3}(ktt|ctt)'
            or (t ~ 'cong nhan' and t ~ 'thu tien')
            or t ~ '(nha nuo+c|nn) giao.{0,10}quan ly'
        )
    from v
$$;

revoke all on function public._nhom3_nguon_goc_hop_le(text) from public;
grant execute on function public._nhom3_nguon_goc_hop_le(text) to service_role;
"""

BACKFILL_SQL = """
update public.du_lieu_gcn
set nhom3_du_du_lieu = public._nhom3_gcn_du_du_lieu(du_lieu_gcn.*)
where not nhom3_du_du_lieu;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    print("1/3 Cập nhật _nhom3_nguon_goc_hop_le — thêm 'Nhà nước giao đất để quản lý'...")
    cur.execute(SCHEMA_SQL)

    print("2/3 Backfill nhom3_du_du_lieu cho các dòng đang false...")
    cur.execute("set statement_timeout = 0")
    cur.execute(BACKFILL_SQL)
    print(f"   -> {cur.rowcount} dòng được quét lại")

    print("3/3 Refresh lại nhom3_trang_thai_cache (có thể mất ~100s)...")
    cur.execute("select public.refresh_nhom3_trang_thai_cache()")
    print("   -> tổng dòng cache:", cur.fetchone()[0])

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
