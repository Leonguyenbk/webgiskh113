from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    sys.exit("Thiếu SUPABASE_URL hoặc SUPABASE_SERVICE_KEY trong sync_gcn/.env")

WORKSHEET_NAME = "Trang tính1"
SHEET_RANGE = "B3:BE"
TABLE_NAME = "du_lieu_gcn"
# Danh sách nguồn (ma_nguon/ten_nguon/url/kich_hoat) quản lý qua trang
# "Nhập đường link" trên WebGIS — không còn đọc từ file Excel local.
NGUON_GCN_TABLE = "nguon_gcn"
BATCH_SIZE = 500

# Thứ tự phải khớp chính xác với các cột B..BE trên Google Sheet (56 cột,
# map cứng theo vị trí — không dựa vào tiêu đề Sheet).
COLUMNS = [
    "madvhc",
    "sophathanhgcn",
    "ngaycapgcn",
    "sovaosogcn",
    "tentochuc",
    "madinhdanhtochuc",
    "hovatenchusudung",
    "ngaythangnamsinh",
    "gioitinh",
    "sodinhdanhcanhan",
    "diachithuongtru",
    "phapnhantrengcn",
    "vaitrophapnhan",
    "tenchusudunghientai",
    "sodinhdanh_chusudunghientai",
    "diachi_chusudunghientai",
    "lydothaydoi",
    "madinhdanhthuadat",
    "soto_gcn",
    "sothua_gcn",
    "soto",
    "sothua",
    "diachi_thuadat",
    "dientichthuadat",
    "loaidat1",
    "dientich1",
    "nguongoc1",
    "hinhthucsudung1",
    "thoihansudung1",
    "loaidat2",
    "dientich2",
    "nguongoc2",
    "hinhthucsudung2",
    "thoihansudung2",
    "loaidat3",
    "dientich3",
    "nguongoc3",
    "hinhthucsudung3",
    "thoihansudung3",
    "loaitaisan",
    "khunhachungcu_honhop",
    "nhachungcu",
    "socanho",
    "dientichxaydung",
    "dientichsan",
    "hinhthucsohuu",
    "thoihansohuu",
    "caphang",
    "tenfilequet",
    "sogiayto1",
    "loaigiayto1",
    "sogiayto2",
    "loaigiayto2",
    "hosoquet",
    "guild",
    "phanloai",
]

if len(COLUMNS) != 56:
    sys.exit(f"COLUMNS phải có đúng 56 phần tử, hiện có {len(COLUMNS)}")
