from __future__ import annotations

from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from config import COLUMNS, GOOGLE_CREDENTIALS_FILE, SHEET_RANGE, WORKSHEET_NAME

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

_client: gspread.Client | None = None


def get_client() -> gspread.Client:
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client


def _row_is_blank(row: list[str]) -> bool:
    return all(not str(value or "").strip() for value in row)


def _pad_row(row: list[Any]) -> list[Any]:
    if len(row) < len(COLUMNS):
        row = row + [None] * (len(COLUMNS) - len(row))
    elif len(row) > len(COLUMNS):
        row = row[: len(COLUMNS)]
    return row


def read_sheet_rows(sheet_url: str) -> list[dict[str, Any]]:
    """Đọc "Trang tính1"!B3:BE và trả về list dict theo COLUMNS.

    Mỗi dict có thêm khoá "_dong_sheet" (số dòng thật trên Google Sheet,
    dùng để lưu vào cột dong_sheet). Bỏ qua dòng trống hoàn toàn, không
    lọc trùng — mỗi dòng Sheet là một bản ghi riêng.

    Ném exception nếu mở sheet/worksheet lỗi (sai URL, chưa share cho
    service account, sai tên worksheet...) — caller phải coi đây là lỗi
    của nguồn này và KHÔNG được đụng tới dữ liệu cũ trên Supabase.
    """
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    raw_rows = worksheet.get(SHEET_RANGE)

    records: list[dict[str, Any]] = []
    for sheet_row_number, row in enumerate(raw_rows, start=3):
        if not row or _row_is_blank(row):
            continue

        cleaned = [cell if cell != "" else None for cell in row]
        padded = _pad_row(cleaned)

        record = dict(zip(COLUMNS, padded))
        record["_dong_sheet"] = sheet_row_number
        records.append(record)

    return records
