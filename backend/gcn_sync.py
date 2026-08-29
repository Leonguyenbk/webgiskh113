from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import gspread
import requests
from google.oauth2.service_account import Credentials

# Đọc Google Sheet bằng Service Account — khác sync_gcn/ (chạy local, đọc
# credentials từ file service_account.json), ở đây backend chạy trên Render
# nên đọc credentials từ biến môi trường GOOGLE_SERVICE_ACCOUNT_JSON (nguyên
# văn nội dung file JSON key, dán thành 1 dòng vào Render → Environment).
GOOGLE_SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

WORKSHEET_NAME = "Trang tính1"
SHEET_RANGE = "B4:BE"
SHEET_START_ROW = 4
DU_LIEU_GCN_TABLE = "du_lieu_gcn"
BATCH_SIZE = 500

# Nguồn "biểu Nhóm 4" (nhom4_service ghi thẳng, madvhc từ form đã kiểm) —
# không đi qua sync_source. Mọi nguồn Google Sheet còn lại: ma_nguon
# chính là mã xã chuẩn (bảng nguon_gcn).
FORM_MA_NGUON = "NHOM4_FORM"

# Thứ tự PHẢI khớp chính xác cột B..BE trên Google Sheet (56 cột). Trùng với
# COLUMNS trong sync_gcn/config.py — hai bản tách riêng vì Render chỉ deploy
# thư mục backend/, không kéo theo sync_gcn/. Đổi cấu trúc Sheet thì phải sửa
# đồng thời cả hai file.
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

_client: gspread.Client | None = None


def _get_client() -> gspread.Client:
    global _client
    if _client is None:
        raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not raw:
            raise RuntimeError(
                "Thiếu GOOGLE_SERVICE_ACCOUNT_JSON trong backend/.env (nội dung "
                "file service_account.json, dán nguyên văn thành 1 dòng)"
            )
        try:
            info = json.loads(raw)
        except ValueError as exc:
            raise RuntimeError(
                f"GOOGLE_SERVICE_ACCOUNT_JSON không phải JSON hợp lệ: {exc}"
            ) from exc

        creds = Credentials.from_service_account_info(info, scopes=GOOGLE_SHEETS_SCOPES)
        _client = gspread.authorize(creds)
    return _client


def _row_is_blank(row: list) -> bool:
    return all(not str(value or "").strip() for value in row)


def _pad_row(row: list) -> list:
    if len(row) < len(COLUMNS):
        row = row + [None] * (len(COLUMNS) - len(row))
    elif len(row) > len(COLUMNS):
        row = row[: len(COLUMNS)]
    return row


def read_sheet_rows(sheet_url: str) -> list[dict[str, Any]]:
    """Đọc "Trang tính1"!B4:BF và trả về list dict theo COLUMNS.

    Ném exception nếu mở sheet/worksheet lỗi (sai URL, chưa share cho service
    account, sai tên worksheet...) — caller phải coi đây là lỗi của nguồn này
    và KHÔNG được đụng tới dữ liệu cũ trên Supabase.
    """
    client = _get_client()
    spreadsheet = client.open_by_url(sheet_url)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    raw_rows = worksheet.get(SHEET_RANGE)

    records: list[dict[str, Any]] = []
    for sheet_row_number, row in enumerate(raw_rows, start=SHEET_START_ROW):
        if not row or _row_is_blank(row):
            continue

        cleaned = [cell if cell != "" else None for cell in row]
        padded = _pad_row(cleaned)

        record = dict(zip(COLUMNS, padded))
        record["_dong_sheet"] = sheet_row_number
        records.append(record)

    return records


def _replace_source_rows(
    base_url: str, headers: dict[str, str], ma_nguon: str, rows: list[dict[str, Any]]
) -> int:
    # Giống sync_gcn/supabase_sync.replace_source: xóa dữ liệu cũ của nguồn
    # rồi insert lại theo batch — không phải transaction thật sự, nhưng chỉ
    # chạy sau khi đã đọc + chuẩn hóa xong toàn bộ Sheet ở read_sheet_rows.
    delete_response = requests.delete(
        f"{base_url}/rest/v1/{DU_LIEU_GCN_TABLE}",
        headers=headers,
        params={"ma_nguon": f"eq.{ma_nguon}"},
        timeout=60,
    )
    delete_response.raise_for_status()

    insert_headers = {
        **headers,
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    inserted = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        response = requests.post(
            f"{base_url}/rest/v1/{DU_LIEU_GCN_TABLE}",
            headers=insert_headers,
            json=batch,
            timeout=120,
        )
        response.raise_for_status()
        inserted += len(batch)

    return inserted


def sync_source(
    base_url: str,
    headers: dict[str, str],
    ma_nguon: str,
    ten_nguon: str,
    sheet_url: str,
) -> int:
    """Đồng bộ 1 nguồn: đọc Google Sheet rồi thay toàn bộ dữ liệu cũ của
    ma_nguon đó trong public.du_lieu_gcn. Trả về số dòng đã ghi."""
    records = read_sheet_rows(sheet_url)

    synced_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for record in records:
        row = dict(record)
        dong_sheet = row.pop("_dong_sheet")
        row["ma_nguon"] = ma_nguon
        row["ten_nguon"] = ten_nguon
        row["sheet_url"] = sheet_url
        row["dong_sheet"] = dong_sheet
        row["synced_at"] = synced_at
        # madvhc (cột B của Sheet) hay bị gõ sai (vd 247373 thay vì
        # 24373) -> khóa generated madvhc_soto_sothua lệch, co_gcn /
        # gcn_thu_thap_theo_xa không nhận. Với nguồn Sheet, ép madvhc =
        # ma_nguon (mã xã chuẩn từ nguon_gcn).
        if ma_nguon != FORM_MA_NGUON:
            row["madvhc"] = ma_nguon
        rows.append(row)

    return _replace_source_rows(base_url, headers, ma_nguon, rows)
