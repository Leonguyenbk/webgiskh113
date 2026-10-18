"""Nạp ranh dự án/đấu giá từ RANHDUAN/DANHSACHDUAN (48 file ThuaDat.gml,
mỗi file 1 khu vực/xã) vào public.ranh_du_an và khoanh vùng/đánh dấu
thuoc_du_an=true cho thửa Nhóm 3 giao >=95% diện tích — dùng ĐÚNG hàm RPC
luu_ranh_du_an_va_danh_dau_nhom3 đã có (xem commit 3ea0117/3a4ffcc/ac6cb54),
KHÔNG nạp vào bảng thua_dat.

Các file này tuy đóng khung bằng schema app:ThuaDat (giống Thua_Dat.gml
thửa đất thật) nhưng maXa/maThuaDat luôn rỗng, soHieuToBanDo/soThuTuThua
bằng 0 hoặc chỉ là số thứ tự lô (1,1 / 1,2...), diện tích hàng chục nghìn
m2 -> không phải thửa đã đăng ký, mà là polygon RANH khu đấu giá (có thể
gồm nhiều polygon rời nhau trong cùng 1 file/1 xã). Dùng lại phần đọc
hình học + chuyển hệ toạ độ EPSG:9218 -> 4326 của gml_reader.read_gml,
gộp toàn bộ polygon trong 1 file thành 1 GeometryCollection rồi gọi RPC
1 lần/file (RPC tự ST_CollectionExtract lấy phần polygon, ST_Multi đếm
so_polygon).

Tên dự án (p_ten) = "<thư mục cấp 1>/<thư mục lá>" để biết file nào tạo
ra ranh nào. Bỏ qua Level_1.gml (lớp CAD, không phải ranh đấu giá).
Chạy 1 lần — RPC insert thêm 1 dòng ranh_du_an mới mỗi lần gọi (không
upsert), nên KHÔNG chạy lại nếu đã chạy thành công cho file đó."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

from app.config import Config
from gml_reader import read_gml

BASE_DIR = Path(r"D:\QUANGTUAN\webgiskh113\RANHDUAN\DANHSACHDUAN")

# (thư mục cấp 1, đường dẫn tương đối tới ThuaDat.gml tính từ BASE_DIR)
FILES = [
    ("Buôn Đôn-ranh đấu giá", r"Buôn Đôn-ranh đấu giá\BUON DON\buon don\ThuaDat.gml"),
    ("Buôn Đôn-ranh đấu giá", r"Buôn Đôn-ranh đấu giá\BUON DON\ea nuol\ThuaDat.gml"),
    ("Buôn Đôn-ranh đấu giá", r"Buôn Đôn-ranh đấu giá\BUON DON\ea wer\ThuaDat.gml"),
    ("Ea Súp-ranh đấu giá", r"Ea Súp-ranh đấu giá\h ea sup\ea rok\ThuaDat.gml"),
    ("Ea Súp-ranh đấu giá", r"Ea Súp-ranh đấu giá\h ea sup\ea sup\ThuaDat.gml"),
    ("Ea Súp-ranh đấu giá", r"Ea Súp-ranh đấu giá\h ea sup\ia lop\ThuaDat.gml"),
    ("Ea Súp-ranh đấu giá", r"Ea Súp-ranh đấu giá\h ea sup\ia rve\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\BUON HO\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\BUON MA THUOT\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\CU BAO\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\CU YANG\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\DAK LIENG\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\DLIE YA\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\EA KLY\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\EA RIENG\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\EA ROK\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\EA SUP\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\HOA PHU\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\KRONG A\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\KRONG NANG\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\LIEN SON LAK\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\NAM KA\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\PHU XUAN\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\TAN LAP\ThuaDat.gml"),
    ("GML DOT 1 _ CONG HUY", r"GML DOT 1 _ CONG HUY\GML DOT 1 _ CONG HUY\YANG MAO\ThuaDat.gml"),
    ("GML DOT 2 _ CONG HUY", r"GML DOT 2 _ CONG HUY\GML DOT 2 _ CONG HUY\DUK KMAL\ThuaDat.gml"),
    ("GML DOT 2 _ CONG HUY", r"GML DOT 2 _ CONG HUY\GML DOT 2 _ CONG HUY\EA BUNG\ThuaDat.gml"),
    ("GML DOT 2 _ CONG HUY", r"GML DOT 2 _ CONG HUY\GML DOT 2 _ CONG HUY\EA DRANG\ThuaDat.gml"),
    ("GML DOT 2 _ CONG HUY", r"GML DOT 2 _ CONG HUY\GML DOT 2 _ CONG HUY\EA DRONG\ThuaDat.gml"),
    ("GML DOT 2 _ CONG HUY", r"GML DOT 2 _ CONG HUY\GML DOT 2 _ CONG HUY\EA KAO\ThuaDat.gml"),
    ("GML DOT 2 _ CONG HUY", r"GML DOT 2 _ CONG HUY\GML DOT 2 _ CONG HUY\EA KAR\ThuaDat.gml"),
    ("GML DOT 2 _ CONG HUY", r"GML DOT 2 _ CONG HUY\GML DOT 2 _ CONG HUY\EA KNOP\ThuaDat.gml"),
    ("GML DOT 2 _ CONG HUY", r"GML DOT 2 _ CONG HUY\GML DOT 2 _ CONG HUY\EA NA\ThuaDat.gml"),
    ("GML DOT 2 _ CONG HUY", r"GML DOT 2 _ CONG HUY\GML DOT 2 _ CONG HUY\EA NUOL\ThuaDat.gml"),
    ("GML DOT 2 _ CONG HUY", r"GML DOT 2 _ CONG HUY\GML DOT 2 _ CONG HUY\EA PAL\ThuaDat.gml"),
    ("RANH DAU GIA-KV BUON HO", r"RANH DAU GIA-KV BUON HO\RANH DAU GIA-KV BUON HO\EADRONG\ThuaDat.gml"),
    ("RANH DAU GIA-KV BUON HO", r"RANH DAU GIA-KV BUON HO\RANH DAU GIA-KV BUON HO\P.BUON HO\ThuaDat.gml"),
    ("RANH DAU GIA-KV BUON HO", r"RANH DAU GIA-KV BUON HO\RANH DAU GIA-KV BUON HO\P.CUBAO\ThuaDat.gml"),
    ("RANH DAU GIA-KV EAHLEO", r"RANH DAU GIA-KV EAHLEO\RANH DAU GIA-KV EAHLEO\EADRANG\ThuaDat.gml"),
    ("RANH DAU GIA-KV EAHLEO", r"RANH DAU GIA-KV EAHLEO\RANH DAU GIA-KV EAHLEO\XA EAKHAL\ThuaDat.gml"),
    ("SƠN HOA-DAU GIA", r"SƠN HOA-DAU GIA\SƠN HOA-DAU GIA\SON HOA 2\ThuaDat.gml"),
    ("SƠN HOA-DAU GIA", r"SƠN HOA-DAU GIA\SƠN HOA-DAU GIA\SON HOA1\ThuaDat.gml"),
    ("SƠN HOA-DAU GIA", r"SƠN HOA-DAU GIA\SƠN HOA-DAU GIA\SON HOA3\ThuaDat.gml"),
    ("Sông Cầu-ranh đấu giá", r"Sông Cầu-ranh đấu giá\SONG CAU\SONG CAU\song cau\ThuaDat.gml"),
    ("Sông Cầu-ranh đấu giá", r"Sông Cầu-ranh đấu giá\SONG CAU\SONG CAU\xuan canh\ThuaDat.gml"),
    ("Sông Cầu-ranh đấu giá", r"Sông Cầu-ranh đấu giá\SONG CAU\SONG CAU\xuan dai\ThuaDat.gml"),
    ("Sông Cầu-ranh đấu giá", r"Sông Cầu-ranh đấu giá\SONG CAU\SONG CAU\XUAN LOC\ThuaDat.gml"),
    ("Sông Cầu-ranh đấu giá", r"Sông Cầu-ranh đấu giá\SONG CAU\SONG CAU\xuan tho\ThuaDat.gml"),
]


def main():
    conn = psycopg2.connect(Config.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    tong_danh_dau = 0
    loi = []
    for nhom, rel in FILES:
        leaf = Path(rel).parent.name
        ten = f"{nhom}/{leaf}"
        path = BASE_DIR / rel
        data = read_gml(path)
        if not data["features"]:
            print(f"-- {ten}: 0 polygon đọc được, bỏ qua")
            continue
        geom = {
            "type": "GeometryCollection",
            "geometries": [f["geometry"] for f in data["features"]],
        }
        try:
            cur.execute(
                "select public.luu_ranh_du_an_va_danh_dau_nhom3(%s, %s, %s, %s)",
                (ten, json.dumps(geom), rel, 95),
            )
            ket_qua = cur.fetchone()[0]
            so_danh_dau = ket_qua["so_thua_danh_dau"]
            tong_danh_dau += so_danh_dau
            print(f"OK {ten}: {len(data['features'])} polygon, "
                  f"ranh_du_an_id={ket_qua['ranh_du_an_id']}, danh dau {so_danh_dau} thua")
        except Exception as exc:
            loi.append((ten, str(exc)))
            print(f"LOI {ten}: {exc}")

    print()
    print("Tong so thua Nhom 3 duoc danh dau thuoc_du_an=true:", tong_danh_dau)
    if loi:
        print(f"Co {len(loi)} file loi:")
        for ten, msg in loi:
            print(" -", ten, ":", msg)

    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
