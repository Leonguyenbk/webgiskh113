from __future__ import annotations

import io
import os

from flask import jsonify
from openpyxl import load_workbook

from ..repositories import danhmuchoso_repository

_DEFAULT_LIMIT = 100
_MAX_LIMIT = 500

# ĐÃ BỎ regex bắt buộc "1-2 chữ cái + 6-8 số" (yêu cầu người dùng: có GCN
# số phát hành toàn là số, không có chữ cái đầu) — số sêri GCN giờ nhập tự
# do, chỉ cần không rỗng.

# Tất cả các trường đều bắt buộc khi nhập 1 hồ sơ (yêu cầu người dùng) —
# TRỪ "Ghi chú" (không bắt buộc) và cặp "Thửa/Bản đồ (Mới)"/"Thửa/Bản đồ
# (Cũ)": theo đúng chú thích trên mẫu MAUFILE.xlsx ("Chỉ nhập thông tin
# cũ nếu như không có thông tin mới") — chỉ cần đủ 1 trong 2 cặp (xem
# kiểm tra riêng trong them_ho_so), không bắt cả 4 ô cùng lúc.
_REQUIRED_FIELDS = [
    ("chi_nhanh", "Chi nhánh"),
    ("cap", "Cặp"),
    ("so_tt_ho_so", "Số TT hồ sơ"),
    ("ten_nguoi_su_dung_dat", "Tên người sử dụng đất"),
    ("dia_chi_thua_dat", "Địa chỉ thửa đất"),
    ("loai_ho_so", "Loại hồ sơ"),
]

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
# Cột M "Đã có trên VBDLis" — thêm sau cùng, như chi_nhanh, tự ghi thêm
# header ở dòng 2 (xem export_xlsx), không đụng layout 11 cột gốc.
_MAU_COLUMNS.append("da_co_tren_vbdlis")
_MAU_VBDLIS_COL = len(_MAU_COLUMNS)  # cột M


def _int_or_none(raw):
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def kiem_tra_gcn(so_seri_gcn_raw: str | None, exclude_id_raw: str | None = None):
    so_seri_gcn = (so_seri_gcn_raw or "").strip().upper()
    if not so_seri_gcn:
        return None, (jsonify({"error": "Thiếu số sêri GCN"}), 400)

    exclude_id = _int_or_none(exclude_id_raw)
    result, error_response = danhmuchoso_repository.kiem_tra_gcn(so_seri_gcn, exclude_id)
    if error_response:
        return None, error_response
    return result or {"ton_tai": False}, None


def _validate_body(body: dict):
    """Kiểm tra các trường bắt buộc + cặp Thửa/Bản đồ — dùng chung cho
    them_ho_so và cap_nhat_ho_so. Trả (so_seri_gcn, None) nếu hợp lệ, hoặc
    (None, error_response)."""
    so_seri_gcn = str(body.get("so_seri_gcn") or "").strip().upper()
    if not so_seri_gcn:
        return None, (jsonify({"error": "Thiếu số sêri GCN"}), 400)

    if body.get("nam") in (None, ""):
        return None, (jsonify({"error": "Thiếu Năm"}), 400)
    if _int_or_none(body.get("nam")) is None:
        return None, (jsonify({"error": "Năm không hợp lệ"}), 400)

    for field, label in _REQUIRED_FIELDS:
        if not str(body.get(field) or "").strip():
            return None, (jsonify({"error": f"Thiếu {label}"}), 400)

    co_thua_moi = bool(str(body.get("thua_dat_so_moi") or "").strip()) and bool(
        str(body.get("ban_do_so_moi") or "").strip()
    )
    co_thua_cu = bool(str(body.get("thua_dat_so_cu") or "").strip()) and bool(
        str(body.get("ban_do_so_cu") or "").strip()
    )
    if not co_thua_moi and not co_thua_cu:
        return None, (
            jsonify(
                {
                    "error": "Thiếu thông tin thửa đất — nhập đủ cặp Thửa/Bản đồ (Mới) HOẶC cặp Thửa/Bản đồ (Cũ)."
                }
            ),
            400,
        )
    return so_seri_gcn, None


def _payload_tu_body(body: dict, so_seri_gcn: str, da_co_tren_vbdlis: bool) -> dict:
    return {
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
        "da_co_tren_vbdlis": da_co_tren_vbdlis,
    }


def them_ho_so(body: dict):
    so_seri_gcn, error_response = _validate_body(body)
    if error_response:
        return None, error_response

    # KHÔNG còn chặn nhập khi GCN đã có dữ liệu điện tử ở nơi khác (đã
    # nhập form Nhóm 4 / đã đồng bộ MPLIS-VBDLis) — yêu cầu người dùng: hồ
    # sơ giấy vẫn phải catalog dù dữ liệu đã có sẵn, chỉ đánh dấu
    # da_co_tren_vbdlis để biết. CHỈ chặn khi GCN đã có SẴN TRONG CHÍNH
    # danh mục này (duplicate catalog thật sự) — dùng tính năng "Sửa" thay
    # vì tạo dòng mới trùng.
    kiem_tra, error_response = danhmuchoso_repository.kiem_tra_gcn(so_seri_gcn)
    if error_response:
        return None, error_response
    kiem_tra = kiem_tra or {}
    if kiem_tra.get("da_co_trong_danh_muc"):
        return None, (
            jsonify(
                {
                    "error": f"GCN \"{so_seri_gcn}\" đã có trong danh mục hồ sơ rồi — dùng tính năng Sửa nếu cần cập nhật, không nhập lại dòng mới.",
                    "chi_tiet": kiem_tra,
                }
            ),
            409,
        )
    da_co_tren_vbdlis = bool(kiem_tra.get("da_nhap_form_nhom4")) or bool(kiem_tra.get("da_dong_bo_mplis"))

    payload = _payload_tu_body(body, so_seri_gcn, da_co_tren_vbdlis)
    result, error_response = danhmuchoso_repository.them(payload)
    if error_response:
        return None, error_response
    return result, None


def cap_nhat_ho_so(row_id_raw, body: dict):
    row_id = _int_or_none(row_id_raw)
    if row_id is None:
        return None, (jsonify({"error": "id không hợp lệ"}), 400)

    so_seri_gcn, error_response = _validate_body(body)
    if error_response:
        return None, error_response

    kiem_tra, error_response = danhmuchoso_repository.kiem_tra_gcn(so_seri_gcn, row_id)
    if error_response:
        return None, error_response
    kiem_tra = kiem_tra or {}
    if kiem_tra.get("da_co_trong_danh_muc"):
        return None, (
            jsonify(
                {
                    "error": f"GCN \"{so_seri_gcn}\" đã có ở 1 hồ sơ khác trong danh mục — không thể đổi sang số này.",
                    "chi_tiet": kiem_tra,
                }
            ),
            409,
        )
    da_co_tren_vbdlis = bool(kiem_tra.get("da_nhap_form_nhom4")) or bool(kiem_tra.get("da_dong_bo_mplis"))

    payload = _payload_tu_body(body, so_seri_gcn, da_co_tren_vbdlis)
    result, error_response = danhmuchoso_repository.cap_nhat(row_id, payload)
    if error_response:
        return None, error_response
    if not result:
        return None, (jsonify({"error": f"Không tìm thấy hồ sơ id={row_id}"}), 404)
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
    if isinstance(value, bool):
        return "x" if value else ""
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

    # Cột L "Chi nhánh", cột M "Đã có trên VBDLis" — thêm sau cùng, ngoài
    # 11 cột mẫu gốc.
    ws.cell(row=2, column=_MAU_CHI_NHANH_COL, value="Chi nhánh")
    ws.cell(row=2, column=_MAU_VBDLIS_COL, value="Đã có trên VBDLis")

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
