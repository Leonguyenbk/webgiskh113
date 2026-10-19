from __future__ import annotations

import datetime
import io
import os
import re

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


def _them_mot_dong(body: dict, bo_qua_trung_danh_muc: bool):
    """Dùng chung cho them_ho_so (nhập tay, 1 dòng) và import_xlsx (nhập
    hàng loạt từ file). bo_qua_trung_danh_muc=True: GCN đã có SẴN trong
    chính danh mục này vẫn cho nhập thêm (không chặn) — dùng khi import,
    để ghi nhận lịch sử (yêu cầu người dùng: 1 GCN có thể xuất hiện nhiều
    lần theo thời gian, không phải lúc nào cũng là nhập trùng tay). Trả
    (result, error_response, da_trung_trong_danh_muc)."""
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
    if da_trung and not bo_qua_trung_danh_muc:
        return None, (
            jsonify(
                {
                    "error": f"GCN \"{so_seri_gcn}\" đã có trong danh mục hồ sơ rồi — dùng tính năng Sửa nếu cần cập nhật, không nhập lại dòng mới.",
                    "chi_tiet": kiem_tra,
                }
            ),
            409,
        ), False
    da_co_tren_vbdlis = bool(kiem_tra.get("da_nhap_form_nhom4")) or bool(kiem_tra.get("da_dong_bo_mplis"))

    payload = _payload_tu_body(body, so_seri_gcn, da_co_tren_vbdlis, ngay)
    result, error_response = danhmuchoso_repository.them(payload)
    if error_response:
        return None, error_response, False
    return result, None, da_trung


def them_ho_so(body: dict):
    result, error_response, _da_trung = _them_mot_dong(body, bo_qua_trung_danh_muc=False)
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


_IMPORT_MAX_ROWS = 3000


def _xlsx_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


_NAM_TIEU_DE_RE = re.compile(r"NĂM\s*(\d{4})")


def _nam_tu_tieu_de(ws) -> int | None:
    """Tự đọc Năm từ tiêu đề dòng 1 "DANH MỤC HỒ SƠ LƯU TRỮ NĂM 2026" —
    mẫu gốc chỉ có 1 năm/file, ghi sẵn ở đây (yêu cầu người dùng: file đã
    đề năm rồi, không cần chọn lại thủ công nếu đọc được)."""
    title = str(ws.cell(row=1, column=1).value or "")
    match = _NAM_TIEU_DE_RE.search(title)
    return int(match.group(1)) if match else None


def import_xlsx(file_bytes: bytes, nam_raw: str | None, chi_nhanh_raw: str | None = None):
    """Nhập hàng loạt từ file .xlsx đúng layout mẫu MAUFILE.xlsx (cột
    A..M, dữ liệu từ dòng 4) — "Năm" đọc theo TỪNG DÒNG ở cột A (1 file
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
    try:
        wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception:
        return None, (jsonify({"error": "Không đọc được file .xlsx — kiểm tra lại file"}), 400)
    ws = wb[_MAU_SHEET] if _MAU_SHEET in wb.sheetnames else wb.active

    nam_tieu_de = _nam_tu_tieu_de(ws)
    nam_chon_tay = _int_or_none(nam_raw)
    chi_nhanh_chung = (chi_nhanh_raw or "").strip() or None

    thanh_cong = 0
    trung_danh_muc = 0
    loi: list[dict] = []
    so_dong_doc = 0
    cac_nam_da_dung: set[int] = set()

    for offset, row in enumerate(
        ws.iter_rows(min_row=_MAU_FIRST_DATA_ROW, max_col=_MAU_VBDLIS_COL, values_only=True)
    ):
        if so_dong_doc >= _IMPORT_MAX_ROWS:
            loi.append({"dong": _MAU_FIRST_DATA_ROW + offset, "loi": f"Vượt quá {_IMPORT_MAX_ROWS} dòng, dừng đọc"})
            break
        values = list(row) + [None] * (_MAU_VBDLIS_COL - len(row))
        core = values[:13]
        if not any(_xlsx_text(v) for v in core):
            continue  # dòng trống, bỏ qua không tính lỗi

        so_dong_doc += 1
        so_dong_file = _MAU_FIRST_DATA_ROW + offset

        nam_dong = _int_or_none(core[0]) or nam_tieu_de or nam_chon_tay
        if nam_dong is None:
            loi.append({
                "dong": so_dong_file,
                "loi": "Thiếu Năm — không có ở cột Năm, tiêu đề file lẫn ô chọn thủ công.",
            })
            continue
        cac_nam_da_dung.add(nam_dong)

        chi_nhanh_dong = _xlsx_text(values[_MAU_CHI_NHANH_COL - 1]) or chi_nhanh_chung
        body = {
            "nam": nam_dong,
            "ngay": core[1],  # datetime.date (ô Excel định dạng ngày) hoặc text DD/MM/YYYY — _them_mot_dong tự chuẩn hoá qua _parse_ngay
            "chi_nhanh": chi_nhanh_dong,
            "cap": _xlsx_text(core[2]),
            "so_tt_ho_so": _xlsx_text(core[3]),
            "ten_nguoi_su_dung_dat": _xlsx_text(core[4]),
            "thua_dat_so_moi": _xlsx_text(core[5]),
            "ban_do_so_moi": _xlsx_text(core[6]),
            "thua_dat_so_cu": _xlsx_text(core[7]),
            "ban_do_so_cu": _xlsx_text(core[8]),
            "dia_chi_thua_dat": _xlsx_text(core[9]),
            "so_seri_gcn": _xlsx_text(core[10]),
            "loai_ho_so": _xlsx_text(core[11]),
            "ghi_chu": _xlsx_text(core[12]),
        }

        _result, error_response, da_trung = _them_mot_dong(body, bo_qua_trung_danh_muc=True)
        if error_response:
            try:
                thong_bao = error_response[0].get_json().get("error", "Lỗi không rõ")
            except Exception:
                thong_bao = "Lỗi không rõ"
            loi.append({"dong": so_dong_file, "loi": thong_bao})
            continue
        thanh_cong += 1
        if da_trung:
            trung_danh_muc += 1

    return {
        "cac_nam_da_dung": sorted(cac_nam_da_dung),
        "tong_dong_doc": so_dong_doc,
        "thanh_cong": thanh_cong,
        "trung_danh_muc": trung_danh_muc,
        "so_dong_loi": len(loi),
        "loi": loi[:200],
    }, None
