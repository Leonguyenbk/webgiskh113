from __future__ import annotations

import datetime
import io
import os
import re
import threading
import time
import unicodedata
import uuid

from flask import current_app, jsonify
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
# Cột A..M của MAUFILE.xlsx, đúng thứ tự merge header (xem DANHMUCHOSO/MAUFILE.xlsx)
# — bản mẫu có "Năm" (cột A) và "Ngày" (cột B, kiểu date thật — luôn
# DD/MM/YYYY khi hiển thị/nhập, xem _parse_ngay) riêng từng dòng.
# Cột N (chi_nhanh) KHÔNG có trong mẫu gốc — thêm sau cùng, tự ghi thêm
# header ở dòng 2 (xem export_xlsx), không đụng layout 13 cột gốc.
_MAU_COLUMNS = [
    "nam",
    "ngay",
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
_MAU_CHI_NHANH_COL = len(_MAU_COLUMNS)  # cột N
# Cột O "Đã có trên VBDLis" — thêm sau cùng, như chi_nhanh, tự ghi thêm
# header ở dòng 2 (xem export_xlsx), không đụng layout 13 cột gốc.
_MAU_COLUMNS.append("da_co_tren_vbdlis")
_MAU_VBDLIS_COL = len(_MAU_COLUMNS)  # cột O


def _int_or_none(raw):
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


_NGAY_DMY_RE = re.compile(r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$")


def _parse_ngay(raw):
    """Chuẩn hoá "Ngày" về datetime.date — web gửi ISO (YYYY-MM-DD, từ
    input type=date), Excel import có thể là ô date thật (openpyxl trả
    thẳng datetime.date/datetime) hoặc text "DD/MM/YYYY" (ngày-tháng-năm,
    yêu cầu người dùng: luôn hiểu theo kiểu Việt Nam, không phải
    MM/DD/YYYY kiểu Mỹ). Trả (date_hoặc_None, loi_hoặc_None)."""
    if raw is None or raw == "":
        return None, None
    if isinstance(raw, datetime.datetime):
        return raw.date(), None
    if isinstance(raw, datetime.date):
        return raw, None
    text = str(raw).strip()
    if not text:
        return None, None
    try:
        return datetime.date.fromisoformat(text), None
    except ValueError:
        pass
    match = _NGAY_DMY_RE.match(text)
    if match:
        ngay, thang, nam = (int(x) for x in match.groups())
        try:
            return datetime.date(nam, thang, ngay), None
        except ValueError:
            return None, f"Ngày \"{text}\" không hợp lệ (phải là DD/MM/YYYY)"
    return None, f"Ngày \"{text}\" không đúng định dạng DD/MM/YYYY"


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


def _payload_tu_body(body: dict, so_seri_gcn: str, da_co_tren_vbdlis: bool, ngay=None) -> dict:
    return {
        "nam": _int_or_none(body.get("nam")),
        "ngay": ngay.isoformat() if ngay else None,
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


def _them_mot_dong(body: dict):
    """Dùng chung cho them_ho_so (nhập tay, 1 dòng) và import_xlsx (nhập
    hàng loạt từ file). GCN đã có SẴN trong chính danh mục này vẫn cho
    nhập thêm (không chặn, cả nhập tay lẫn import) — yêu cầu người dùng: 1
    số sêri GCN có thể có nhiều dòng hồ sơ khác nhau. Trả (result,
    error_response, da_trung_trong_danh_muc) — cờ da_trung chỉ để thống
    kê/cảnh báo."""
    so_seri_gcn, error_response = _validate_body(body)
    if error_response:
        return None, error_response, False

    ngay, loi_ngay = _parse_ngay(body.get("ngay"))
    if loi_ngay:
        return None, (jsonify({"error": loi_ngay}), 400), False

    # KHÔNG chặn nhập khi GCN đã có dữ liệu điện tử ở nơi khác (đã nhập
    # form Nhóm 4 / đã đồng bộ MPLIS-VBDLis) — yêu cầu người dùng: hồ sơ
    # giấy vẫn phải catalog dù dữ liệu đã có sẵn, chỉ đánh dấu
    # da_co_tren_vbdlis để biết.
    kiem_tra, error_response = danhmuchoso_repository.kiem_tra_gcn(so_seri_gcn)
    if error_response:
        return None, error_response, False
    kiem_tra = kiem_tra or {}
    da_trung = bool(kiem_tra.get("da_co_trong_danh_muc"))
    da_co_tren_vbdlis = bool(kiem_tra.get("da_nhap_form_nhom4")) or bool(kiem_tra.get("da_dong_bo_mplis"))

    payload = _payload_tu_body(body, so_seri_gcn, da_co_tren_vbdlis, ngay)
    result, error_response = danhmuchoso_repository.them(payload)
    if error_response:
        return None, error_response, False
    return result, None, da_trung


def them_ho_so(body: dict):
    result, error_response, _da_trung = _them_mot_dong(body)
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

    ngay, loi_ngay = _parse_ngay(body.get("ngay"))
    if loi_ngay:
        return None, (jsonify({"error": loi_ngay}), 400)

    kiem_tra, error_response = danhmuchoso_repository.kiem_tra_gcn(so_seri_gcn, row_id)
    if error_response:
        return None, error_response
    kiem_tra = kiem_tra or {}
    # GCN đã có ở hồ sơ khác trong danh mục KHÔNG chặn đổi số (1 GCN có thể
    # có nhiều dòng hồ sơ) — chỉ tính lại da_co_tren_vbdlis.
    da_co_tren_vbdlis = bool(kiem_tra.get("da_nhap_form_nhom4")) or bool(kiem_tra.get("da_dong_bo_mplis"))

    payload = _payload_tu_body(body, so_seri_gcn, da_co_tren_vbdlis, ngay)
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

    # Cột N "Chi nhánh", cột O "Đã có trên VBDLis" — thêm sau cùng, ngoài
    # 13 cột mẫu gốc.
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
            if field == "ngay":
                ngay_value, _loi = _parse_ngay(row.get("ngay"))
                cell = ws.cell(row=r, column=col_idx, value=ngay_value)
                if ngay_value:
                    cell.number_format = "dd/mm/yyyy"
                continue
            ws.cell(row=r, column=col_idx, value=_xlsx_cell(row.get(field)))

    buf = io.BytesIO()
    wb.save(buf)
    ten_file = f"danh_muc_ho_so_{nam}.xlsx" if nam else "danh_muc_ho_so.xlsx"
    return (buf.getvalue(), ten_file), None


def tai_mau_xlsx():
    """Trả nguyên file mẫu trống DANHMUCHOSO/MAUFILE.xlsx (không dữ liệu)
    để tải về điền tay rồi nhập lại qua import_xlsx."""
    try:
        with open(_MAU_PATH, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return None, (jsonify({"error": "Thiếu file mẫu MAUFILE.xlsx trên server"}), 500)
    return (data, "MAUFILE.xlsx"), None


_IMPORT_MAX_ROWS = 5000


def _xlsx_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _chuan_hoa_tieu_de(value) -> str:
    """Bỏ dấu, chữ thường, gộp khoảng trắng — để so tên cột không phụ thuộc
    cách gõ ("Số sêri GCN" / "Số Sê ri giấy chứng nhận", xuống dòng...)."""
    text = unicodedata.normalize("NFD", _xlsx_text(value).replace("đ", "d").replace("Đ", "D"))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(text.lower().split())


# Nhận diện cột theo tên tiêu đề (đã _chuan_hoa_tieu_de) — thứ tự quan trọng:
# "Địa chỉ thửa đất (Chỉ ghi cấp xã...)" phải xét trước các cột "thửa đất".
_TIEU_DE_COT = [
    ("dia_chi_thua_dat", lambda t: t.startswith("dia chi")),
    ("thua_dat_so_moi", lambda t: t.startswith("thua dat so") and "moi" in t),
    ("thua_dat_so_cu", lambda t: t.startswith("thua dat so") and "(cu)" in t),
    ("ban_do_so_moi", lambda t: t.startswith("ban do so") and "moi" in t),
    ("ban_do_so_cu", lambda t: t.startswith("ban do so") and "(cu)" in t),
    ("ten_nguoi_su_dung_dat", lambda t: "ten nguoi" in t),
    ("so_seri_gcn", lambda t: "seri" in t or "se ri" in t),
    ("loai_ho_so", lambda t: t.startswith("loai ho so")),
    ("ghi_chu", lambda t: t.startswith("ghi chu")),
    ("chi_nhanh", lambda t: t.startswith("chi nhanh")),
    ("da_co_tren_vbdlis", lambda t: "vbdlis" in t),
    ("so_tt_ho_so", lambda t: t.startswith("stt") or t.startswith("so tt")),
    ("nam", lambda t: t == "nam"),
    ("ngay", lambda t: t == "ngay"),
    ("cap", lambda t: t == "cap"),
]


def _cot_theo_tieu_de(cells) -> dict[str, int]:
    cot: dict[str, int] = {}
    for idx, value in enumerate(cells):
        text = _chuan_hoa_tieu_de(value)
        if not text:
            continue
        for field, khop in _TIEU_DE_COT:
            if field not in cot and khop(text):
                cot[field] = idx
                break
    return cot


def _bo_cuc_file(ws) -> tuple[dict[str, int], int]:
    """Tìm dòng tiêu đề trong 10 dòng đầu (dòng có cả cột "Tên người sử dụng
    đất" lẫn "Số sêri") + dòng tiêu đề phụ ngay dưới (Thửa/Bản đồ Mới/Cũ),
    trả (field -> chỉ số cột 0-based, dòng dữ liệu đầu tiên). File không
    đúng mẫu cột (vd thiếu cột "Ngày" — các cột sau lệch sang trái 1 ô) vẫn
    đọc đúng. Không nhận ra tiêu đề thì dùng nguyên layout cố định của mẫu
    MAUFILE.xlsx như trước."""
    dau = list(ws.iter_rows(min_row=1, max_row=11, values_only=True))
    for i in range(min(10, len(dau))):
        cot = _cot_theo_tieu_de(dau[i])
        if "ten_nguoi_su_dung_dat" not in cot or "so_seri_gcn" not in cot:
            continue
        phu = _cot_theo_tieu_de(dau[i + 1]) if i + 1 < len(dau) else {}
        co_dong_phu = any(f.startswith(("thua_dat", "ban_do", "dia_chi")) for f in phu)
        for field, idx in phu.items():
            cot.setdefault(field, idx)
        return cot, i + 1 + (2 if co_dong_phu else 1)
    return {field: idx for idx, field in enumerate(_MAU_COLUMNS)}, _MAU_FIRST_DATA_ROW


_NAM_TIEU_DE_RE = re.compile(r"NĂM\s*(\d{4})")


def _nam_tu_tieu_de(ws) -> int | None:
    """Tự đọc Năm từ tiêu đề dòng 1 "DANH MỤC HỒ SƠ LƯU TRỮ NĂM 2026" —
    mẫu gốc chỉ có 1 năm/file, ghi sẵn ở đây (yêu cầu người dùng: file đã
    đề năm rồi, không cần chọn lại thủ công nếu đọc được)."""
    title = str(ws.cell(row=1, column=1).value or "")
    match = _NAM_TIEU_DE_RE.search(title)
    return int(match.group(1)) if match else None


def _doc_dong_xlsx(file_bytes: bytes, nam_raw: str | None, chi_nhanh_raw: str | None):
    """Đọc + ánh xạ cột toàn bộ file (nhanh, chưa ghi DB) — xem import_xlsx.
    Trả ((cac_dong, loi_doc, cac_nam), None) hoặc (None, error_response);
    cac_dong: list (số dòng trong file, body cho _them_mot_dong)."""
    try:
        wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception:
        return None, (jsonify({"error": "Không đọc được file .xlsx — kiểm tra lại file"}), 400)
    ws = wb[_MAU_SHEET] if _MAU_SHEET in wb.sheetnames else wb.active

    cot, dong_dau = _bo_cuc_file(ws)
    nam_tieu_de = _nam_tu_tieu_de(ws)
    nam_chon_tay = _int_or_none(nam_raw)
    chi_nhanh_chung = (chi_nhanh_raw or "").strip() or None

    def lay(values, field):
        idx = cot.get(field)
        return values[idx] if idx is not None and idx < len(values) else None

    cac_dong: list[tuple[int, dict]] = []
    loi: list[dict] = []
    cac_nam: set[int] = set()
    for offset, values in enumerate(ws.iter_rows(min_row=dong_dau, values_only=True)):
        values = list(values)
        if not any(_xlsx_text(lay(values, field)) for field in cot):
            continue  # dòng trống, bỏ qua không tính lỗi
        so_dong_file = dong_dau + offset
        if len(cac_dong) + len(loi) >= _IMPORT_MAX_ROWS:
            loi.append({"dong": so_dong_file, "loi": f"Vượt quá {_IMPORT_MAX_ROWS} dòng, dừng đọc"})
            break

        nam_dong = _int_or_none(lay(values, "nam")) or nam_tieu_de or nam_chon_tay
        if nam_dong is None:
            loi.append({
                "dong": so_dong_file,
                "loi": "Thiếu Năm — không có ở cột Năm, tiêu đề file lẫn ô chọn thủ công.",
            })
            continue
        cac_nam.add(nam_dong)

        body = {field: _xlsx_text(lay(values, field)) for field in _MAU_COLUMNS if field not in ("nam", "ngay", "chi_nhanh", "da_co_tren_vbdlis")}
        body["nam"] = nam_dong
        # datetime.date (ô Excel định dạng ngày) hoặc text DD/MM/YYYY —
        # _them_mot_dong tự chuẩn hoá qua _parse_ngay
        body["ngay"] = lay(values, "ngay")
        body["chi_nhanh"] = _xlsx_text(lay(values, "chi_nhanh")) or chi_nhanh_chung
        cac_dong.append((so_dong_file, body))
    return (cac_dong, loi, cac_nam), None


def _ghi_cac_dong(cac_dong, loi: list[dict], tien_do: dict | None = None):
    thanh_cong = 0
    trung_danh_muc = 0
    for so_dong_file, body in cac_dong:
        _result, error_response, da_trung = _them_mot_dong(body)
        if error_response:
            try:
                thong_bao = error_response[0].get_json().get("error", "Lỗi không rõ")
            except Exception:
                thong_bao = "Lỗi không rõ"
            loi.append({"dong": so_dong_file, "loi": thong_bao})
        else:
            thanh_cong += 1
            if da_trung:
                trung_danh_muc += 1
        if tien_do is not None:
            tien_do["da_xu_ly"] += 1
            tien_do["thanh_cong"] = thanh_cong
            tien_do["so_dong_loi"] = len(loi)
    return thanh_cong, trung_danh_muc


def _ket_qua_import(cac_dong, loi, cac_nam, thanh_cong, trung_danh_muc) -> dict:
    loi = sorted(loi, key=lambda item: item["dong"])
    return {
        "cac_nam_da_dung": sorted(cac_nam),
        "tong_dong_doc": len(cac_dong) + sum(1 for item in loi if item["loi"].startswith("Thiếu Năm")),
        "thanh_cong": thanh_cong,
        "trung_danh_muc": trung_danh_muc,
        "so_dong_loi": len(loi),
        "loi": loi[:200],
    }


# Import chạy nền (xem bat_dau_import) — file vài nghìn dòng mất nhiều phút
# (mỗi dòng 2 lượt gọi Supabase), vượt giới hạn 100 giây/request của
# Cloudflare; chạy đồng bộ thì trình duyệt báo lỗi trong khi server vẫn ghi
# tiếp, người dùng nhập lại => trùng dòng. Lưu trong RAM của process là đủ
# (chỉ 1 process Flask), mất khi restart — chỉ là tiến độ, không phải dữ liệu.
_IMPORT_JOBS: dict[str, dict] = {}
_IMPORT_JOBS_LOCK = threading.Lock()
_IMPORT_JOB_GIU_GIAY = 6 * 3600


def bat_dau_import(file_bytes: bytes, nam_raw: str | None, chi_nhanh_raw: str | None = None):
    """Đọc file ngay (lỗi file báo luôn 400), rồi ghi từng dòng trong thread
    nền. Trả {"job_id", "tong_dong"} — FE hỏi tiến độ qua trang_thai_import."""
    parsed, error_response = _doc_dong_xlsx(file_bytes, nam_raw, chi_nhanh_raw)
    if error_response:
        return None, error_response
    cac_dong, loi, cac_nam = parsed

    job_id = uuid.uuid4().hex
    job = {
        "trang_thai": "dang_chay",
        "tong_dong": len(cac_dong),
        "da_xu_ly": 0,
        "thanh_cong": 0,
        "so_dong_loi": len(loi),
        "ket_qua": None,
        "loi_he_thong": None,
        "bat_dau_luc": time.time(),
    }
    with _IMPORT_JOBS_LOCK:
        han = time.time() - _IMPORT_JOB_GIU_GIAY
        for cu in [k for k, v in _IMPORT_JOBS.items() if v["bat_dau_luc"] < han]:
            del _IMPORT_JOBS[cu]
        _IMPORT_JOBS[job_id] = job

    app = current_app._get_current_object()

    def chay():
        with app.app_context():
            try:
                thanh_cong, trung = _ghi_cac_dong(cac_dong, loi, job)
                job["ket_qua"] = _ket_qua_import(cac_dong, loi, cac_nam, thanh_cong, trung)
                job["trang_thai"] = "xong"
            except Exception as exc:  # noqa: BLE001 - báo lại cho FE thay vì chết im
                job["loi_he_thong"] = f"Lỗi khi nhập: {exc}"
                job["trang_thai"] = "loi"

    threading.Thread(target=chay, name=f"dmhs-import-{job_id[:8]}", daemon=True).start()
    return {"job_id": job_id, "tong_dong": len(cac_dong)}, None


def trang_thai_import(job_id: str):
    with _IMPORT_JOBS_LOCK:
        job = _IMPORT_JOBS.get(job_id or "")
    if job is None:
        return None, (
            jsonify({"error": "Không tìm thấy đợt nhập (server có thể đã khởi động lại) — tìm kiếm danh mục để xem dòng nào đã lưu."}),
            404,
        )
    return {k: v for k, v in job.items() if k != "bat_dau_luc"}, None


def import_xlsx(file_bytes: bytes, nam_raw: str | None, chi_nhanh_raw: str | None = None):
    """Nhập hàng loạt từ file .xlsx theo mẫu MAUFILE.xlsx — cột nhận diện
    theo TÊN TIÊU ĐỀ (xem _bo_cuc_file), file thiếu/thừa/đổi chỗ cột vẫn
    đọc đúng; không nhận ra tiêu đề thì dùng layout cố định A..O, dữ liệu
    từ dòng 4. "Năm" đọc theo TỪNG DÒNG ở cột Năm (1 file
    có thể gồm nhiều năm khác nhau). Dòng nào bỏ trống cột Năm thì lấy
    theo tiêu đề dòng 1 (xem _nam_tu_tieu_de, bản mẫu cũ chỉ có 1
    năm/file), rồi mới tới nam_raw (chọn tay cho cả đợt) — dòng nào
    không có năm từ cả 3 nguồn thì báo lỗi riêng dòng đó, không chặn cả
    batch. "Ngày" (cột B) nhận datetime.date (ô Excel định dạng ngày)
    hoặc text DD/MM/YYYY, không bắt buộc — xem _parse_ngay. "Chi nhánh"
    lấy theo cột N nếu dòng đó có giá trị (file xuất lại từ hệ thống,
    xem export_xlsx), ngược lại dùng giá trị chọn chung cho cả đợt nhập.
    GCN đã có sẵn trong danh mục KHÔNG bị chặn — vẫn nhập thêm để ghi
    nhận lịch sử (yêu cầu người dùng), chỉ báo lại số dòng trùng. Lỗi
    từng dòng không làm hỏng cả batch — dòng lỗi bị bỏ qua, báo cáo lại
    chi tiết để người dùng tự sửa file rồi nhập lại dòng đó."""
    parsed, error_response = _doc_dong_xlsx(file_bytes, nam_raw, chi_nhanh_raw)
    if error_response:
        return None, error_response
    cac_dong, loi, cac_nam = parsed
    thanh_cong, trung_danh_muc = _ghi_cac_dong(cac_dong, loi)
    return _ket_qua_import(cac_dong, loi, cac_nam, thanh_cong, trung_danh_muc), None
