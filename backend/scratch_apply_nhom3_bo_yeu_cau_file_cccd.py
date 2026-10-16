"""Áp trực tiếp lên DB: nới tiêu chí "đủ dữ liệu" của Nhóm 3
(_nhom3_gcn_du_du_lieu) — bỏ yêu cầu bắt buộc có tên file quét
(tenfilequet). Khớp thay đổi song song ở biểu Nhóm 4 (không còn bắt buộc
chọn file chính khi nộp — backend/app/services/nhom4_service.py,
backend/app/utils/nhom4_validation.py cũng bỏ luôn yêu cầu CCCD đủ 12 số,
nhưng CCCD CHƯA BAO GIỜ được hàm SQL này kiểm tra độ dài nên không cần đổi
gì ở đây cho phần CCCD).

Lý do: nhiều nơi nhập dữ liệu không có sẵn file quét để đính kèm (dữ liệu
cũ/đồng bộ Sheet), và nhiều nơi nhập CCCD bị mất số 0 ở đầu (còn 11 số) nên
bị chặn nộp bởi yêu cầu đủ 12 số — cả 2 khiến thửa bị tính "con thiếu" dù
dữ liệu thực tế coi như đã đủ.

CHỈ cần backfill lại cột nhom3_du_du_lieu cho các dòng ĐANG false — hàm
mới chỉ NỚI LỎNG hơn hàm cũ (bỏ bớt 1 điều kiện), không bao giờ làm 1 dòng
đang true thành false, nên dòng true giữ nguyên, không cần quét lại. Chạy
1 lần."""
from __future__ import annotations

import sys

import psycopg2

from app.config import Config

SCHEMA_SQL = """
create or replace function public._nhom3_gcn_du_du_lieu(g public.du_lieu_gcn)
returns boolean
language sql
immutable
as $$
    select
        trim(coalesce(g.dientichthuadat, '')) <> ''
        and trim(coalesce(g.loaidat1, '')) <> ''
        and trim(coalesce(g.dientich1, '')) <> ''
        and public._nhom3_nguon_goc_hop_le(g.nguongoc1)
        and trim(coalesce(g.hinhthucsudung1, '')) <> ''
        and trim(coalesce(g.thoihansudung1, '')) <> ''
        and (
            starts_with(trim(coalesce(g.sophathanhgcn, '')), 'CHUACOGIAY_')
            or (
                public._nhom3_so_phat_hanh_hop_le(g.sophathanhgcn)
                and trim(coalesce(g.ngaycapgcn, '')) <> ''
            )
        )
        and (
            trim(coalesce(g.tentochuc, '')) <> ''
            or (
                trim(coalesce(g.hovatenchusudung, '')) <> ''
                and trim(coalesce(g.sodinhdanhcanhan, '')) <> ''
                and trim(coalesce(g.ngaythangnamsinh, '')) <> ''
                and trim(coalesce(g.gioitinh, '')) <> ''
                and trim(coalesce(g.diachithuongtru, '')) <> ''
                and public._nhom3_phap_nhan_hop_le(g.phapnhantrengcn)
                and public._nhom3_vai_tro_phap_nhan_hop_le(g.vaitrophapnhan)
            )
        )
        and (
            (
                trim(coalesce(g.loaidat2, '')) = ''
                and trim(coalesce(g.dientich2, '')) = ''
                and trim(coalesce(g.nguongoc2, '')) = ''
                and trim(coalesce(g.hinhthucsudung2, '')) = ''
                and trim(coalesce(g.thoihansudung2, '')) = ''
            )
            or (
                trim(coalesce(g.loaidat2, '')) <> ''
                and trim(coalesce(g.dientich2, '')) <> ''
                and public._nhom3_nguon_goc_hop_le(g.nguongoc2)
                and trim(coalesce(g.hinhthucsudung2, '')) <> ''
                and trim(coalesce(g.thoihansudung2, '')) <> ''
            )
        )
$$;

revoke all on function public._nhom3_gcn_du_du_lieu(public.du_lieu_gcn) from public;
grant execute on function public._nhom3_gcn_du_du_lieu(public.du_lieu_gcn) to service_role;
"""

BACKFILL_SQL = """
update public.du_lieu_gcn
set nhom3_du_du_lieu = public._nhom3_gcn_du_du_lieu(du_lieu_gcn.*)
where not nhom3_du_du_lieu;
"""


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur = conn.cursor()

    print("1/2 Cập nhật _nhom3_gcn_du_du_lieu — bỏ yêu cầu tenfilequet...")
    cur.execute(SCHEMA_SQL)
    conn.commit()

    print("2/2 Backfill nhom3_du_du_lieu cho các dòng đang false...")
    cur.execute(BACKFILL_SQL)
    print(f"   -> {cur.rowcount} dòng được quét lại")
    conn.commit()

    cur.execute("select count(*) from public.du_lieu_gcn where nhom3_du_du_lieu")
    print("Tổng dòng nhom3_du_du_lieu = true sau khi nới:", cur.fetchone()[0])

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
