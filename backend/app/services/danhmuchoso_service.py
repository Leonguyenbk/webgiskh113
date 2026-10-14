from __future__ import annotations

import io
import os

from flask import jsonify
from openpyxl import load_workbook

from ..repositories import danhmuchoso_repository

_DEFAULT_LIMIT = 100
_MAX_LIMIT = 500

_MAU_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "MAUFILE.xlsx")
_MAU_SHEET = "Sheet1"
_MAU_FIRST_DATA_ROW = 4
# Cột A..K của MAUFILE.xlsx, đúng thứ tự merge header (xem DANHMUCHOSO/MAUFILE.xlsx).
# Cột L (chi_nhanh) KHÔNG có trong mẫu gốc — thêm sau cùng, tự ghi thêm
# header ở dòng 2 (xem export_xlsx), không đụng layout 11 cột gốc.
_MAU_COLUMNS = [
    "cap",
    "so_tt_ho_so",
    "ten_nguoi_su_dung_dat",
    "thua_dat_so_moi",
    "ban_do_so_moi",
    "thua_dat_so_cu",
    "ban_do_so_cu",
    "dia_chi_thua_dat",
    "so_seri_gcn",
    "loai_ho_so",
    "ghi_chu",
    "chi_nhanh",
]
_MAU_CHI_NHANH_COL = len(_MAU_COLUMNS)  # cột L

_NGUON_LABEL = {
    "da_nhap_form_nhom4": "đã nhập form Nhóm 4",
    "da_dong_bo_mplis": "đã đồng bộ từ MPLIS",
    "da_co_trong_danh_muc": "đã có trong danh mục hồ sơ",
}


def _int_or_none(raw):
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def kiem_tra_gcn(so_seri_gcn_raw: str | None):
    so_seri_gcn = (so_seri_gcn_raw or "").strip()
    if not so_seri_gcn:
        return None, (jsonify({"error": "Thiếu số sêri GCN"}), 400)

    result, error_response = danhmuchoso_repository.kiem_tra_gcn(so_seri_gcn)
    if error_response:
        return None, error_response
    return result or {"ton_tai": False}, None


def them_ho_so(body: dict):
    so_seri_gcn = str(body.get("so_seri_gcn") or "").strip()
    if not so_seri_gcn:
        return None, (jsonify({"error": "Thiếu số sêri GCN"}), 400)

    kiem_tra, error_response = danhmuchoso_repository.kiem_tra_gcn(so_seri_gcn)
    if error_response:
        return None, error_response
    if kiem_tra and kiem_tra.get("ton_tai"):
        nguon = [label for key, label in _NGUON_LABEL.items() if kiem_tra.get(key)]
        return None, (
            jsonify(
                {
                    "error": f"GCN \"{so_seri_gcn}\" đã tồn tại trên hệ thống ({', '.join(nguon)}) — không thể nhập lại.",
                    "chi_tiet": kiem_tra,
                }
            ),
            409,
        )

    payload = {
        "nam": _int_or_none(body.get("nam")),
        "chi_nhanh": body.get("chi_nhanh"),
        "cap": body.get("cap"),
        "so_tt_ho_so": body.get("so_tt_ho_so"),
        "ten_nguoi_su_dung_dat": body.get("ten_nguoi_su_dung_dat"),
        "thua_dat_so_moi": body.get("thua_dat_so_moi"),
        "ban_do_so_moi": body.get("ban_do_so_moi"),
        "thua_dat_so_cu": body.get("thua_dat_so_cu"),
        "ban_do_so_cu": body.get("ban_do_so_cu"),
        "dia_chi_thua_dat": body.get("dia_chi_thua_dat"),
        "so_seri_gcn": so_seri_gcn,
        "loai_ho_so": body.get("loai_ho_so"),
        "ghi_chu": body.get("ghi_chu"),
    }
    result, error_response = danhmuchoso_repository.them(payload)
    if error_response:
        return None, error_response
    return result, None


def get_danh_sach(limit_raw, offset_raw, keyword_raw, nam_raw, chi_nhanh_raw=None):
    try:
        limit = min(max(int(limit_raw or _DEFAULT_LIMIT), 1), _MAX_LIMIT)
        offset = max(int(offset_raw or 0), 0)
    except (TypeError, ValueError):
        return None, (jsonify({"error": "limit hoặc offset không hợp lệ"}), 400)

    keyword = (keyword_raw or "").strip() or None
    nam = _int_or_none(nam_raw)
    chi_nhanh = (chi_nhanh_raw or "").strip() or None

    result, error_response = danhmuchoso_repository.danh_sach(limit, offset, keyword, nam, chi_nhanh)
    if error_response:
        return None, error_response
    if not isinstance(result, dict):
        result = {}
    result.setdefault("total", 0)
    result.setdefault("items", [])
    return result, None


def _xlsx_cell(value):
    if value is None:
        return ""
    return value


def export_xlsx(nam_raw: str | None, keyword_raw: str | None, chi_nhanh_raw: str | None = None):
    nam = _int_or_none(nam_raw)
    keyword = (keyword_raw or "").strip() or None
    chi_nhanh = (chi_nhanh_raw or "").strip() or None

    rows: list = []
    offset = 0
    page_size = 5000
    while True:
        page, error_response = danhmuchoso_repository.danh_sach(
            page_size, offset, keyword, nam, chi_nhanh
        )
        if error_response:
            return None, error_response
        page = page if isinstance(page, dict) else {}
        items = page.get("items") if isinstance(page.get("items"), list) else []
        rows.extend(items)
        if len(items) < page_size:
            break
        offset += page_size

    try:
        wb = load_workbook(_MAU_PATH)
    except FileNotFoundError:
        return None, (jsonify({"error": "Thiếu file mẫu MAUFILE.xlsx trên server"}), 500)
    ws = wb[_MAU_SHEET] if _MAU_SHEET in wb.sheetnames else wb.active

    # Cột L "Chi nhánh" — thêm sau cùng, ngoài 11 cột mẫu gốc.
    ws.cell(row=2, column=_MAU_CHI_NHANH_COL, value="Chi nhánh")

    if nam:
        # Tiêu đề mẫu: "DANH MỤC HỒ SƠ LƯU TRỮ NĂM ….." — thay phần sau
        # "NĂM" bằng năm thật, không phụ thuộc đúng từng dấu "…"/".".
        title = str(ws.cell(row=1, column=1).value or "")
        idx = title.rfind("NĂM")
        if idx != -1:
            title = title[: idx + len("NĂM")] + f" {nam}"
        ws.cell(row=1, column=1, value=title)

    for i, row in enumerate(rows):
        r = _MAU_FIRST_DATA_ROW + i
        for col_idx, field in enumerate(_MAU_COLUMNS, start=1):
            ws.cell(row=r, column=col_idx, value=_xlsx_cell(row.get(field)))

    buf = io.BytesIO()
    wb.save(buf)
    ten_file = f"danh_muc_ho_so_{nam}.xlsx" if nam else "danh_muc_ho_so.xlsx"
    return (buf.getvalue(), ten_file), None
