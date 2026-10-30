from __future__ import annotations

import io
import os
from datetime import datetime, timedelta, timezone

import requests
from flask import current_app, jsonify
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill

import gcn_sync
from ..repositories import gcn_repository, nhom4_repository

# Nhóm KH 2959 hợp lệ cho chức năng "Xuất GCN theo nhóm".
_NHOM_HOP_LE = {"NHÓM 1", "NHÓM 2"}
_EXPORT_PAGE = 5000      # số dòng mỗi lần gọi RPC
_EXPORT_MAX = 300_000    # trần an toàn cho 1 lần xuất

# Trang "Danh sách thửa đã nhập" (/api/gcn-danh-sach) liệt kê thuộc tính
# theo trang, không phải xuất toàn bộ — trần thấp hơn nhiều so với
# _EXPORT_PAGE ở trên.
_DANH_SACH_DEFAULT_LIMIT = 100
_DANH_SACH_MAX_LIMIT = 200

# File mẫu TANAN.xlsx (biểu tổng hợp dữ liệu GCN) — hàng 1-4 là tiêu đề
# (có gộp ô), dữ liệu mẫu ở hàng 5 trở đi bị xóa và thay bằng dữ liệu thật
# khi xuất. Đường dẫn tương đối tới backend/data/ (xem backend/data/Thua_Dat.xsd
# cho cùng kiểu file tĩnh đóng gói theo backend).
_MAU_TANAN_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "TANAN.xlsx"
)
_MAU_TANAN_HEADER_ROWS = 4  # hàng 1-4: tiêu đề; dữ liệu bắt đầu từ hàng 5
_MAU_TANAN_SHEET = "Sheet1"

# Cột B..BG của mẫu TANAN.xlsx, ánh xạ theo TÊN cột public.du_lieu_gcn
# (không theo vị trí — cột "Phân loại thửa đất" nằm giữa mẫu (AY) chứ
# không cuối bảng như trong create_du_lieu_gcn.sql). None = cột mẫu không
# có dữ liệu tương ứng trong bảng (2 cột "Trạng thái xác thực số giấy tờ"
# BB/BE — chỉ có trên mẫu, không được đồng bộ/lưu).
_MAU_TANAN_COLUMNS = [
    ("B", "madvhc"),
    ("C", "sophathanhgcn"),
    ("D", "ngaycapgcn"),
    ("E", "sovaosogcn"),
    ("F", "tentochuc"),
    ("G", "madinhdanhtochuc"),
    ("H", "hovatenchusudung"),
    ("I", "sodinhdanhcanhan"),
    ("J", "ngaythangnamsinh"),
    ("K", "gioitinh"),
    ("L", "diachithuongtru"),
    ("M", "phapnhantrengcn"),
    ("N", "vaitrophapnhan"),
    ("O", "tenchusudunghientai"),
    ("P", "sodinhdanh_chusudunghientai"),
    ("Q", "diachi_chusudunghientai"),
    ("R", "lydothaydoi"),
    ("S", "madinhdanhthuadat"),
    ("T", "soto_gcn"),
    ("U", "sothua_gcn"),
    ("V", "soto"),
    ("W", "sothua"),
    ("X", "diachi_thuadat"),
    ("Y", "dientichthuadat"),
    ("Z", "loaidat1"),
    ("AA", "dientich1"),
    ("AB", "nguongoc1"),
    ("AC", "hinhthucsudung1"),
    ("AD", "thoihansudung1"),
    ("AE", "loaidat2"),
    ("AF", "dientich2"),
    ("AG", "nguongoc2"),
    ("AH", "hinhthucsudung2"),
    ("AI", "thoihansudung2"),
    ("AJ", "loaidat3"),
    ("AK", "dientich3"),
    ("AL", "nguongoc3"),
    ("AM", "hinhthucsudung3"),
    ("AN", "thoihansudung3"),
    ("AO", "loaitaisan"),
    ("AP", "khunhachungcu_honhop"),
    ("AQ", "nhachungcu"),
    ("AR", "socanho"),
    ("AS", "dientichxaydung"),
    ("AT", "dientichsan"),
    ("AU", "hinhthucsohuu"),
    ("AV", "thoihansohuu"),
    ("AW", "caphang"),
    ("AX", "tenfilequet"),
    ("AY", "phanloai"),
    ("AZ", "sogiayto1"),
    ("BA", "loaigiayto1"),
    ("BB", None),
    ("BC", "sogiayto2"),
    ("BD", "loaigiayto2"),
    ("BE", None),
    ("BF", "hosoquet"),
    ("BG", "guild"),
]

# Cột nên ghi dạng số (khớp kiểu số ở dữ liệu mẫu gốc) — dữ liệu trong
# du_lieu_gcn lưu dạng text nên chuyển đổi tốt nhất có thể, giữ nguyên text
# nếu không phải số hợp lệ.
_MAU_TANAN_INT_FIELDS = {"soto_gcn", "sothua_gcn", "soto", "sothua"}
_MAU_TANAN_FLOAT_FIELDS = {
    "dientichthuadat", "dientich1", "dientich2", "dientich3",
    "dientichxaydung", "dientichsan",
}


def _mau_tanan_cell_value(field: str, raw_value):
    value = (raw_value or "").strip() if isinstance(raw_value, str) else raw_value
    if value in (None, ""):
        return None
    if field in _MAU_TANAN_INT_FIELDS:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if field in _MAU_TANAN_FLOAT_FIELDS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return value


def get_stats():
    result, error_response = gcn_repository.gcn_thu_thap_theo_xa()
    if error_response:
        return None, error_response

    rows = result if isinstance(result, list) else []
    items = []
    as_of = None
    for row in rows:
        ma_xa = row.get("ma_xa")
        if not ma_xa:
            continue
        tong = int(row.get("tong_so_thua") or 0)
        da_nhap = int(row.get("da_nhap_bieu") or 0)
        computed_at = row.get("computed_at")
        if computed_at and (as_of is None or computed_at > as_of):
            as_of = computed_at
        items.append(
            {
                "ma_xa": ma_xa,
                "tong_so_thua": tong,
                "da_nhap_bieu": da_nhap,
                "chua_nhap_bieu": max(tong - da_nhap, 0),
            }
        )
    return {"items": items, "as_of": as_of}, None


def refresh_stats_cache():
    result, error_response = gcn_repository.refresh_gcn_thu_thap_theo_xa_cache()
    if error_response:
        return None, error_response
    # Hàm SQL trả về số dòng đã ghi vào cache (PostgREST bọc trong scalar).
    rows = result if isinstance(result, int) else None
    return {"ok": True, "rows": rows}, None


def get_danh_sach_da_nhap(
    ma_xa: str,
    sort_raw: str | None,
    limit_raw: str | None,
    offset_raw: str | None,
    so_to_raw: str | None = None,
    so_thua_raw: str | None = None,
):
    """Trang 'Danh sách thửa đã nhập' — liệt kê từng dòng public.du_lieu_gcn
    theo xã (tên xã, số tờ, số thửa, mã định danh, ngày nhập), lọc thêm
    theo số tờ/số thửa (tùy chọn). Bắt buộc ma_xa (xem lý do CPU trong
    supabase/schema.sql, list_du_lieu_gcn_da_nhap)."""
    ma_xa = (ma_xa or "").strip()
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã xã"}), 400)

    sort_asc = (sort_raw or "").strip().lower() == "asc"
    so_to = (so_to_raw or "").strip() or None
    so_thua = (so_thua_raw or "").strip() or None

    try:
        limit = min(
            max(int(limit_raw or _DANH_SACH_DEFAULT_LIMIT), 1),
            _DANH_SACH_MAX_LIMIT,
        )
        offset = max(int(offset_raw or 0), 0)
    except (TypeError, ValueError):
        return None, (jsonify({"error": "limit hoặc offset không hợp lệ"}), 400)

    result, error_response = gcn_repository.list_da_nhap(
        ma_xa, sort_asc, limit, offset, so_to, so_thua
    )
    if error_response:
        return None, error_response

    if not isinstance(result, dict):
        result = {}
    result.setdefault("total", 0)
    result.setdefault("total_form", 0)
    result.setdefault("total_khac", 0)
    result.setdefault("items", [])
    return result, None


_GIO_VN = timezone(timedelta(hours=7))


def _ngay_nhap_excel(iso: str | None):
    # created_at (timestamptz, ISO) -> datetime giờ VN không kèm tz (openpyxl
    # không ghi được datetime có tzinfo).
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(_GIO_VN).replace(tzinfo=None)
    return dt


def export_danh_sach_da_nhap_xlsx(
    ma_xa: str,
    sort_raw: str | None,
    so_to_raw: str | None = None,
    so_thua_raw: str | None = None,
):
    """Xuất .xlsx TOÀN BỘ trang 'Danh sách thửa đã nhập' của 1 xã (đúng bộ
    lọc số tờ/số thửa + chiều sắp xếp đang chọn trên trang) — kèm ngày nhập
    và nguồn (biểu Nhóm 4 / đồng bộ Sheet). Không chứa CCCD/tên/địa chỉ
    nên không cần IMPORT_TOKEN, giống /api/gcn-danh-sach."""
    ma_xa = (ma_xa or "").strip()
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã xã"}), 400)

    sort_asc = (sort_raw or "").strip().lower() == "asc"
    so_to = (so_to_raw or "").strip() or None
    so_thua = (so_thua_raw or "").strip() or None

    rows: list = []
    offset = 0
    while True:
        page, error_response = gcn_repository.list_da_nhap(
            ma_xa, sort_asc, _EXPORT_PAGE, offset, so_to, so_thua
        )
        if error_response:
            return None, error_response
        page = page if isinstance(page, dict) else {}
        items = page.get("items") if isinstance(page.get("items"), list) else []
        rows.extend(items)
        if len(items) < _EXPORT_PAGE or len(rows) >= _EXPORT_MAX:
            break
        offset += _EXPORT_PAGE

    wb = Workbook()
    ws = wb.active
    ws.title = "Da nhap"
    ws.append(["STT", "Xã / phường", "Mã xã", "Số tờ", "Số thửa", "Mã định danh", "Ngày nhập", "Nguồn"])
    for index, row in enumerate(rows, start=1):
        ws.append([
            index,
            _xlsx_cell(row.get("ten_xa")),
            _xlsx_cell(row.get("ma_xa")),
            _xlsx_cell(row.get("so_to")),
            _xlsx_cell(row.get("so_thua")),
            _xlsx_cell(row.get("ma_dinh_danh")),
            _ngay_nhap_excel(row.get("ngay_nhap")),
            "Biểu Nhóm 4" if row.get("is_form") else "Đồng bộ Sheet",
        ])
        ws.cell(row=ws.max_row, column=7).number_format = "dd/mm/yyyy hh:mm:ss"
    if not rows:
        ws.append(["", "Xã/phường này chưa có dữ liệu đã nhập"])
    for col, width in zip("ABCDEFGH", (7, 24, 9, 8, 9, 22, 20, 15)):
        ws.column_dimensions[col].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return (buf.getvalue(), f"danh_sach_da_nhap_{ma_xa}.xlsx"), None


# Cột CHO PHÉP sửa qua trang web (nút "Xem/Sửa" ở "Danh sách thửa đã
# nhập") — CHỈ áp dụng cho dòng nguồn "biểu Nhóm 4" (chặn ở
# gcn_repository.update_du_lieu_gcn_row bằng điều kiện ma_nguon, đây là lớp
# whitelist thứ 2 chặn client gửi thừa cột không cho sửa như id/ma_nguon/
# submission_id/madvhc/soto/sothua — đổi số tờ/số thửa coi như 1 thửa khác,
# ngoài phạm vi "sửa nếu nhập sai", phải nộp lại từ đầu).
DU_LIEU_GCN_EDITABLE_FIELDS = (
    "sophathanhgcn", "ngaycapgcn", "sovaosogcn",
    "tentochuc", "madinhdanhtochuc",
    "hovatenchusudung", "ngaythangnamsinh", "gioitinh", "sodinhdanhcanhan",
    "diachithuongtru", "phapnhantrengcn", "vaitrophapnhan",
    "tenchusudunghientai", "sodinhdanh_chusudunghientai", "diachi_chusudunghientai",
    "lydothaydoi",
    "madinhdanhthuadat", "soto_gcn", "sothua_gcn",
    "diachi_thuadat", "dientichthuadat",
    "loaidat1", "dientich1", "nguongoc1", "hinhthucsudung1", "thoihansudung1",
    "loaidat2", "dientich2", "nguongoc2", "hinhthucsudung2", "thoihansudung2",
    "loaidat3", "dientich3", "nguongoc3", "hinhthucsudung3", "thoihansudung3",
    "ghichu",
)


def _to_int_or_error(value, label: str):
    try:
        return int(str(value).strip()), None
    except (TypeError, ValueError):
        return None, (jsonify({"error": f"{label} không hợp lệ: {value!r}"}), 400)


def _make_madvhc_soto_sothua(ma_xa: str, so_to: int, so_thua: int) -> str:
    # Phải khớp đúng cột generated madvhc_soto_sothua trong du_lieu_gcn
    # (xem sync_gcn/create_du_lieu_gcn.sql) — so_to/so_thua ở đây luôn là
    # số nguyên nên normalize_so_text cho kết quả giống str(int).
    return f"{ma_xa.strip()}_{so_to}_{so_thua}"


def get_du_lieu_gcn_chi_tiet(ma_xa_raw: str, so_to_raw: str, so_thua_raw: str):
    """Trang 'Danh sách thửa đã nhập' — nút 'Xem/Sửa': toàn bộ dòng (1 dòng/
    chủ sử dụng) đã nhập cho 1 thửa, kèm cờ cho biết sửa được hay chỉ xem
    (nguồn 'biểu Nhóm 4' mới sửa được — dữ liệu đồng bộ Google Sheet bị ghi
    đè lại ở lần đồng bộ sau)."""
    ma_xa = (ma_xa_raw or "").strip()
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã xã"}), 400)
    so_to, error_response = _to_int_or_error(so_to_raw, "Số tờ")
    if error_response:
        return None, error_response
    so_thua, error_response = _to_int_or_error(so_thua_raw, "Số thửa")
    if error_response:
        return None, error_response

    key = _make_madvhc_soto_sothua(ma_xa, so_to, so_thua)
    rows, error_response = gcn_repository.get_du_lieu_gcn_rows(key)
    if error_response:
        return None, error_response
    if not rows:
        return None, (jsonify({"error": "Thửa này chưa có dữ liệu trong du_lieu_gcn"}), 404)

    sua_duoc = rows[0].get("ma_nguon") == nhom4_repository.NHOM4_MA_NGUON
    items = [
        {"id": row.get("id"), **{field: row.get(field) for field in DU_LIEU_GCN_EDITABLE_FIELDS}}
        for row in rows
    ]
    return {
        "ma_xa": ma_xa,
        "so_to": so_to,
        "so_thua": so_thua,
        "ten_nguon": rows[0].get("ten_nguon"),
        "sua_duoc": sua_duoc,
        "items": items,
    }, None


def update_du_lieu_gcn_chi_tiet(row_id_raw, ma_xa_raw: str, so_to_raw: str, so_thua_raw: str, body: dict):
    """Lưu thay đổi 1 dòng (1 chủ sử dụng) ở modal 'Xem/Sửa'. Chỉ nhận các
    cột trong DU_LIEU_GCN_EDITABLE_FIELDS — cột khác trong body bị bỏ qua
    im lặng (không phải lỗi, phòng trường hợp frontend gửi thừa field hiển
    thị không cần sửa như file_*_ten_file)."""
    row_id, error_response = _to_int_or_error(row_id_raw, "id")
    if error_response:
        return None, error_response
    ma_xa = (ma_xa_raw or "").strip()
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã xã"}), 400)
    so_to, error_response = _to_int_or_error(so_to_raw, "Số tờ")
    if error_response:
        return None, error_response
    so_thua, error_response = _to_int_or_error(so_thua_raw, "Số thửa")
    if error_response:
        return None, error_response

    if not isinstance(body, dict):
        return None, (jsonify({"error": "Thiếu dữ liệu cần sửa"}), 400)
    updates = {}
    for field in DU_LIEU_GCN_EDITABLE_FIELDS:
        if field in body:
            value = body[field]
            updates[field] = value.strip() or None if isinstance(value, str) else value
    if not updates:
        return None, (jsonify({"error": "Không có trường nào để sửa"}), 400)

    key = _make_madvhc_soto_sothua(ma_xa, so_to, so_thua)
    rows, error_response = gcn_repository.update_du_lieu_gcn_row(row_id, key, updates)
    if error_response:
        return None, error_response
    if not rows:
        return None, (
            jsonify(
                {
                    "error": (
                        "Không sửa được — có thể dòng này không phải nhập từ biểu Nhóm 4 "
                        "(đồng bộ từ Google Sheet) hoặc id không khớp thửa đang xem."
                    )
                }
            ),
            409,
        )
    return {"item": rows[0]}, None


def delete_du_lieu_gcn_thua(ma_xa_raw: str, so_to_raw: str, so_thua_raw: str):
    """Trang 'Danh sách thửa đã nhập' — nút 'Xóa để nhập lại': xóa TOÀN BỘ
    dòng (mọi chủ sử dụng) đã nhập cho 1 thửa để nộp lại từ đầu qua biểu
    Nhóm 4. CHỈ áp dụng cho thửa nguồn 'biểu Nhóm 4' — chặn xóa dữ liệu
    đồng bộ Google Sheet (giống update_du_lieu_gcn_chi_tiet, dữ liệu đó bị
    nạp lại ở lần đồng bộ sau nên xóa tay vô nghĩa)."""
    ma_xa = (ma_xa_raw or "").strip()
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã xã"}), 400)
    so_to, error_response = _to_int_or_error(so_to_raw, "Số tờ")
    if error_response:
        return None, error_response
    so_thua, error_response = _to_int_or_error(so_thua_raw, "Số thửa")
    if error_response:
        return None, error_response

    key = _make_madvhc_soto_sothua(ma_xa, so_to, so_thua)
    rows, error_response = gcn_repository.get_du_lieu_gcn_rows(key)
    if error_response:
        return None, error_response
    if not rows:
        return None, (jsonify({"error": "Thửa này chưa có dữ liệu trong du_lieu_gcn"}), 404)
    if rows[0].get("ma_nguon") != nhom4_repository.NHOM4_MA_NGUON:
        return None, (
            jsonify(
                {
                    "error": (
                        "Không xóa được — dữ liệu thửa này đồng bộ từ Google Sheet, "
                        "không phải nhập từ biểu Nhóm 4."
                    )
                }
            ),
            409,
        )

    deleted, error_response = gcn_repository.delete_du_lieu_gcn_rows(key)
    if error_response:
        return None, error_response
    return {"ok": True, "deleted": len(deleted or [])}, None


def get_thong_ke_nguon_nhap():
    """Trang '/thong-ke-nguon-nhap' — tổng số thửa đã nhập toàn dự án, tách
    Form (biểu Nhóm 4) / nguồn khác (đồng bộ Google Sheet)."""
    result, error_response = gcn_repository.thong_ke_nguon_nhap()
    if error_response:
        return None, error_response
    if not isinstance(result, dict):
        result = {}
    result.setdefault("total", 0)
    result.setdefault("total_form", 0)
    result.setdefault("total_khac", 0)
    result.setdefault("theo_xa", [])
    return result, None


_TO_GIAM_SAT_HOP_LE = {1, 2, 3, 4}


def _parse_to_giam_sat(raw: str | None):
    text = (raw or "").strip()
    if not text:
        return None, None
    try:
        value = int(text)
    except ValueError:
        return None, (jsonify({"error": "to_giam_sat không hợp lệ"}), 400)
    if value not in _TO_GIAM_SAT_HOP_LE:
        return None, (jsonify({"error": "to_giam_sat phải là 1, 2, 3 hoặc 4"}), 400)
    return value, None


def get_nhom3_tong_hop(to_giam_sat_raw: str | None = None):
    """Trang '/nhom-3-con-thieu' — tổng hợp danh sách thửa cần thu thập
    Nhóm 3 (bảng nhom3_can_thu_thap) so với Nhóm 1/2 và đã thu thập. Lọc
    tuỳ chọn theo Tổ kiểm tra, giám sát (1-4, xem nhom3_to_giam_sat —
    Quyết định 867/QĐ-VPĐKĐĐ ngày 01/10/2026)."""
    to_giam_sat, error_response = _parse_to_giam_sat(to_giam_sat_raw)
    if error_response:
        return None, error_response

    result, error_response = gcn_repository.nhom3_tong_hop(to_giam_sat)
    if error_response:
        return None, error_response
    if not isinstance(result, dict):
        result = {}
    result.setdefault("tong", 0)
    result.setdefault("da_nhom_1_2", 0)
    result.setdefault("da_nhom_1_2_da_nhap", 0)
    result.setdefault("da_nhom_1_2_chua_nhap", 0)
    result.setdefault("da_thu_thap", 0)
    result.setdefault("con_thieu", 0)
    result.setdefault("da_nhap_chua_dat", 0)
    result.setdefault("chua_lien_ket_khong_gian", 0)
    result.setdefault("tong_tru_kg", 0)
    result.setdefault("theo_xa", [])
    # Hiển thị "Số liệu cập nhật lúc ..." trên trang — lỗi đọc thì bỏ qua
    # (None), không làm hỏng cả trang thống kê.
    result["cap_nhat_luc"] = gcn_repository.nhom3_cache_computed_at()
    return result, None


# nhom3_ty_le_gui_xuong mất ~4s (nối danh sách ~1,8 triệu thửa với cache)
# trong khi cache Nhóm 3 chỉ đổi mỗi 2 giờ — giữ kết quả vài phút.
_TY_LE_CACHE_GIAY = 300
_ty_le_cache: dict[int | None, tuple[datetime, dict]] = {}


def get_nhom3_ty_le_gui_xuong(to_giam_sat_raw: str | None = None):
    """Trang '/nhom-3-ty-le' — theo xã: số lượng gửi xuống (đã trừ dự án),
    Nhóm 1/2 trong danh sách, đã nhập biểu trong danh sách; tổng và tỷ lệ
    tính ở frontend."""
    to_giam_sat, error_response = _parse_to_giam_sat(to_giam_sat_raw)
    if error_response:
        return None, error_response

    now = datetime.now(_GIO_VN)
    cached = _ty_le_cache.get(to_giam_sat)
    if cached and (now - cached[0]).total_seconds() < _TY_LE_CACHE_GIAY:
        return cached[1], None

    result, error_response = gcn_repository.nhom3_ty_le_gui_xuong(to_giam_sat)
    if error_response:
        return None, error_response
    if not isinstance(result, dict):
        result = {}
    result.setdefault("gui_xuong", 0)
    result.setdefault("nhom_1", 0)
    result.setdefault("da_nhap_bieu", 0)
    result.setdefault("theo_xa", [])
    _ty_le_cache[to_giam_sat] = (now, result)
    return result, None


def export_nhom3_tong_hop_xlsx(to_giam_sat_raw: str | None = None):
    """Xuất .xlsx tổng hợp tiến độ Nhóm 3 theo xã (lọc tuỳ chọn theo Tổ
    kiểm tra, giám sát 1-4) — Y HỆT bảng "Chi tiết theo xã/phường" trên
    trang /nhom-3-con-thieu (xem SORT_COLUMNS trong Nhom3ConThieuPage.jsx).
    2 cột "tổng" tách riêng (yêu cầu người dùng): "tong" chỉ trừ Nhóm 1/2
    Chi nhánh KV chưa nhập; "tong_tru_kg" trừ thêm chưa liên kết không
    gian — mỗi cột tổng có 1 cột % tương ứng, cùng tử số Đã làm = Nhóm 1
    đã nhập + đã nhập đủ dữ liệu. Thêm cặp cột "theo kế hoạch" (yêu cầu
    người dùng): tổng và đã làm cùng cộng thêm Loại 1+2+3
    đã làm (public.nhom3_loai_123_da_lam, VPĐK gửi song song ngoài hệ thống) trên nền tổng đã trừ KG — phân
    biệt với phần hệ thống tự theo dõi ("Loại 4") ở các cột trước. Xã
    "ghi chú" (thuộc dự án tổng thể khác, xem nhom3_xa_ghi_chu) vẫn liệt
    kê nhưng số liệu = 0, % bỏ trống."""
    to_giam_sat, error_response = _parse_to_giam_sat(to_giam_sat_raw)
    if error_response:
        return None, error_response

    result, error_response = gcn_repository.nhom3_tong_hop(to_giam_sat)
    if error_response:
        return None, error_response
    result = result if isinstance(result, dict) else {}
    theo_xa = result.get("theo_xa") if isinstance(result.get("theo_xa"), list) else []

    wb = Workbook()
    ws = wb.active
    ws.title = "Tong hop Nhom 3"[:31]
    ws.append([
        "Tổ giám sát", "Khu vực", "Mã xã", "Xã/Phường",
        "Tổng gửi xã (đã trừ Chi nhánh KV)",
        "Nhóm 1 đã nhập biểu (Xã làm)", "Nhóm 1 chưa nhập biểu (Chi nhánh KV làm)",
        "Đã nhập đủ dữ liệu", "Đã làm", "%", "Còn thiếu", "Chưa liên kết không gian",
        "Tổng gửi xã (đã trừ Chi nhánh KV + chưa liên kết KG)", "% (trừ cả chưa liên kết KG)",
        "Tổng theo kế hoạch (đã gồm Loại 1+2+3 đã làm)", "Đã thực hiện theo kế hoạch (gồm Loại 1+2+3 đã làm)", "% theo kế hoạch",
        "Ghi chú",
    ])

    tong_chung = nhom12_da_nhap_chung = nhom12_chua_nhap_chung = 0
    da_thu_thap_chung = con_thieu_chung = chua_lien_ket_chung = tong_tru_kg_chung = 0
    loai_123_chung = tong_ke_hoach_chung = 0
    for row in theo_xa:
        tong = int(row.get("tong") or 0)
        nhom12_da_nhap = int(row.get("da_nhom_1_2_da_nhap") or 0)
        nhom12_chua_nhap = int(row.get("da_nhom_1_2_chua_nhap") or 0)
        da_thu_thap = int(row.get("da_thu_thap") or 0)
        con_thieu = int(row.get("con_thieu") or 0)
        chua_lien_ket = int(row.get("chua_lien_ket_khong_gian") or 0)
        tong_tru_kg = int(row.get("tong_tru_kg") or 0)
        loai_123_da_lam = int(row.get("loai_123_da_lam") or 0)
        tong_ke_hoach = int(row.get("tong_ke_hoach") or 0)
        da_lam = nhom12_da_nhap + da_thu_thap
        # Đã thực hiện theo kế hoạch cộng cả Loại 1+2+3 đã làm (như file
        # KhoiLuongXa-KH113); tổng kế hoạch cũng cộng Loại 1+2+3.
        da_lam_ke_hoach = da_lam + loai_123_da_lam
        percent = round(da_lam / tong * 1000) / 10 if tong > 0 else None
        percent_tru_kg = round(da_lam / tong_tru_kg * 1000) / 10 if tong_tru_kg > 0 else None
        percent_ke_hoach = round(da_lam_ke_hoach / tong_ke_hoach * 1000) / 10 if tong_ke_hoach > 0 else None
        tong_chung += tong
        nhom12_da_nhap_chung += nhom12_da_nhap
        nhom12_chua_nhap_chung += nhom12_chua_nhap
        da_thu_thap_chung += da_thu_thap
        con_thieu_chung += con_thieu
        chua_lien_ket_chung += chua_lien_ket
        tong_tru_kg_chung += tong_tru_kg
        loai_123_chung += loai_123_da_lam
        tong_ke_hoach_chung += tong_ke_hoach
        ws.append([
            _xlsx_cell(row.get("to_giam_sat")),
            _xlsx_cell(row.get("khu_vuc")),
            _xlsx_cell(row.get("ma_xa")),
            _xlsx_cell(row.get("ten_xa")),
            tong,
            nhom12_da_nhap,
            nhom12_chua_nhap,
            da_thu_thap,
            da_lam,
            f"{percent}%" if percent is not None else "",
            con_thieu,
            chua_lien_ket,
            tong_tru_kg,
            f"{percent_tru_kg}%" if percent_tru_kg is not None else "",
            tong_ke_hoach,
            da_lam_ke_hoach,
            f"{percent_ke_hoach}%" if percent_ke_hoach is not None else "",
            _xlsx_cell(row.get("ghi_chu")),
        ])

    da_lam_chung = nhom12_da_nhap_chung + da_thu_thap_chung
    da_lam_ke_hoach_chung = da_lam_chung + loai_123_chung
    percent_chung = round(da_lam_chung / tong_chung * 1000) / 10 if tong_chung > 0 else None
    percent_tru_kg_chung = round(da_lam_chung / tong_tru_kg_chung * 1000) / 10 if tong_tru_kg_chung > 0 else None
    percent_ke_hoach_chung = (
        round(da_lam_ke_hoach_chung / tong_ke_hoach_chung * 1000) / 10 if tong_ke_hoach_chung > 0 else None
    )
    ws.append([
        "", "", "", "TỔNG CỘNG",
        tong_chung, nhom12_da_nhap_chung, nhom12_chua_nhap_chung,
        da_thu_thap_chung, da_lam_chung,
        f"{percent_chung}%" if percent_chung is not None else "",
        con_thieu_chung, chua_lien_ket_chung,
        tong_tru_kg_chung,
        f"{percent_tru_kg_chung}%" if percent_tru_kg_chung is not None else "",
        tong_ke_hoach_chung,
        da_lam_ke_hoach_chung,
        f"{percent_ke_hoach_chung}%" if percent_ke_hoach_chung is not None else "",
        "",
    ])

    buf = io.BytesIO()
    wb.save(buf)
    ten_to = f"to{to_giam_sat}" if to_giam_sat else "tatca"
    return (buf.getvalue(), f"nhom3_tong_hop_{ten_to}.xlsx"), None


_NHOM3_DEFAULT_LIMIT = 100
_NHOM3_MAX_LIMIT = 500


def get_nhom3_tien_do_trend(ma_xa_raw: str | None, tu_raw: str | None, den_raw: str | None = None):
    """Dashboard trend tốc độ xử lý Nhóm 3 (thửa/ngày) theo xã — đọc lịch sử
    nhom3_tien_do_lich_su, mỗi lát cắt ghi lúc refresh cache chạy (lịch 3
    giờ/lần, xem register_refresh_nhom3_stats_task.ps1). tu/den lọc
    KHOẢNG HIỂN THỊ — tốc độ của điểm đầu khoảng vẫn tính đúng (dựa vào
    lát trước đó, kể cả nằm ngoài khoảng), xem nhom3_tien_do_trend trong
    supabase/schema.sql."""
    ma_xa = (ma_xa_raw or "").strip() or None
    tu = (tu_raw or "").strip() or None
    den = (den_raw or "").strip() or None

    result, error_response = gcn_repository.nhom3_tien_do_trend(ma_xa, tu, den)
    if error_response:
        return None, error_response
    if not isinstance(result, list):
        result = []
    return {"items": result}, None


# API dashboard riêng Phường Buôn Ma Thuột (/api/thong-ke/buon-ma-thuot) —
# gộp dòng của phường trong nhom3_tong_hop (~3s), thống kê theo ranh thôn
# (~1.3s) và trend tiến độ, nên giữ kết quả trong bộ nhớ vài phút: số liệu
# Nhóm 3 chỉ đổi khi refresh cache (3 giờ/lần), dashboard gọi liên tục
# không làm nặng DB.
_BMT_MA_XA = "24133"
_BMT_CACHE_GIAY = 300
_BMT_SO_NGAY_MAC_DINH = 30
_BMT_SO_NGAY_TOI_DA = 365
_bmt_cache: dict[int, tuple[datetime, dict]] = {}


def get_thong_ke_buon_ma_thuot(so_ngay_raw: str | None):
    """Số liệu Nhóm 3 của Phường Buôn Ma Thuột cho dashboard bên ngoài:
    tổng quan (cùng số với trang /nhom-3-con-thieu), theo từng thôn/TDP,
    số thửa nhập biểu web theo ngày và trend tiến độ trong so_ngay ngày
    gần nhất (mặc định 30)."""
    try:
        so_ngay = int((so_ngay_raw or "").strip() or _BMT_SO_NGAY_MAC_DINH)
    except ValueError:
        return None, (jsonify({"error": "so_ngay không hợp lệ"}), 400)
    so_ngay = min(max(so_ngay, 1), _BMT_SO_NGAY_TOI_DA)

    now = datetime.now(_GIO_VN)
    cached = _bmt_cache.get(so_ngay)
    if cached and (now - cached[0]).total_seconds() < _BMT_CACHE_GIAY:
        return cached[1], None

    tong_hop, error_response = gcn_repository.nhom3_tong_hop(None)
    if error_response:
        return None, error_response
    theo_xa = (tong_hop.get("theo_xa") if isinstance(tong_hop, dict) else None) or []
    tong_quan = next((x for x in theo_xa if x.get("ma_xa") == _BMT_MA_XA), None)
    if tong_quan is None:
        return None, (jsonify({"error": "Chưa có số liệu Nhóm 3 của Phường Buôn Ma Thuột"}), 404)

    theo_thon, error_response = gcn_repository.thong_ke_nhom3_xa(_BMT_MA_XA, so_ngay)
    if error_response:
        return None, error_response
    if not isinstance(theo_thon, dict):
        theo_thon = {}

    tu = (now - timedelta(days=so_ngay)).isoformat()
    tien_do, error_response = gcn_repository.nhom3_tien_do_trend(_BMT_MA_XA, tu, None)
    if error_response:
        return None, error_response

    result = {
        "ma_xa": _BMT_MA_XA,
        "ten_xa": tong_quan.get("ten_xa"),
        "cap_nhat_luc": gcn_repository.nhom3_cache_computed_at(),
        "tao_luc": now.isoformat(),
        "so_ngay": so_ngay,
        "tong_quan": tong_quan,
        "so_thon": theo_thon.get("so_thon", 0),
        "theo_thon": theo_thon.get("theo_thon", []),
        "nhap_bieu_web_theo_ngay": theo_thon.get("nhap_bieu_web_theo_ngay", []),
        "tien_do": tien_do if isinstance(tien_do, list) else [],
    }
    _bmt_cache[so_ngay] = (now, result)
    return result, None


def refresh_nhom3_cache():
    result, error_response = gcn_repository.refresh_nhom3_trang_thai_cache()
    if error_response:
        return None, error_response
    # Hàm SQL trả về số dòng đã ghi vào cache (PostgREST bọc trong scalar).
    rows = result if isinstance(result, int) else None
    return {"ok": True, "rows": rows}, None


def get_nhom3_danh_sach_con_thieu(
    ma_xa_raw: str | None,
    limit_raw: str | None,
    offset_raw: str | None,
    co_nhap_raw: str | None = None,
):
    """Danh sách phân trang thửa còn thiếu dữ liệu (Nhóm 3, chỉ thửa có
    bản đồ), lọc theo xã (tuỳ chọn) và trạng thái (tuỳ chọn: co_nhap=1 =
    "đã nhập nhưng sai form", co_nhap=0 = "chưa nhập", bỏ trống = tất cả)."""
    ma_xa = (ma_xa_raw or "").strip() or None

    co_nhap_text = (co_nhap_raw or "").strip().lower()
    if co_nhap_text in ("1", "true", "yes"):
        co_nhap = True
    elif co_nhap_text in ("0", "false", "no"):
        co_nhap = False
    elif co_nhap_text:
        return None, (jsonify({"error": "co_nhap không hợp lệ"}), 400)
    else:
        co_nhap = None

    try:
        limit = min(max(int(limit_raw or _NHOM3_DEFAULT_LIMIT), 1), _NHOM3_MAX_LIMIT)
        offset = max(int(offset_raw or 0), 0)
    except (TypeError, ValueError):
        return None, (jsonify({"error": "limit hoặc offset không hợp lệ"}), 400)

    result, error_response = gcn_repository.nhom3_list_con_thieu(ma_xa, limit, offset, co_nhap)
    if error_response:
        return None, error_response
    if not isinstance(result, dict):
        result = {}
    result.setdefault("total", 0)
    result.setdefault("items", [])
    return result, None


def get_nhom3_list_nhom1_chua_nhap(ma_xa_raw: str | None, limit_raw: str | None, offset_raw: str | None):
    """Danh sách phân trang thửa đã thuộc Nhóm 1 nhưng CHƯA có dòng
    du_lieu_gcn nào (chưa nhập biểu qua xã/form Nhóm 4) — nhóm do Chi
    nhánh khu vực làm trực tiếp (yêu cầu người dùng, tách riêng khỏi
    "còn thiếu" của Nhóm 3)."""
    ma_xa = (ma_xa_raw or "").strip() or None
    try:
        limit = min(max(int(limit_raw or _NHOM3_DEFAULT_LIMIT), 1), _NHOM3_MAX_LIMIT)
        offset = max(int(offset_raw or 0), 0)
    except (TypeError, ValueError):
        return None, (jsonify({"error": "limit hoặc offset không hợp lệ"}), 400)

    result, error_response = gcn_repository.nhom3_list_nhom1_chua_nhap(ma_xa, limit, offset)
    if error_response:
        return None, error_response
    if not isinstance(result, dict):
        result = {}
    result.setdefault("total", 0)
    result.setdefault("items", [])
    return result, None


def get_nhom3_list_nhom1_da_nhap(ma_xa_raw: str | None, limit_raw: str | None, offset_raw: str | None):
    """Đối xứng với get_nhom3_list_nhom1_chua_nhap — thửa Nhóm 1 ĐÃ có
    dòng du_lieu_gcn (đã nhập biểu qua xã/form Nhóm 4)."""
    ma_xa = (ma_xa_raw or "").strip() or None
    try:
        limit = min(max(int(limit_raw or _NHOM3_DEFAULT_LIMIT), 1), _NHOM3_MAX_LIMIT)
        offset = max(int(offset_raw or 0), 0)
    except (TypeError, ValueError):
        return None, (jsonify({"error": "limit hoặc offset không hợp lệ"}), 400)

    result, error_response = gcn_repository.nhom3_list_nhom1_da_nhap(ma_xa, limit, offset)
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
    if isinstance(value, (dict, list)):
        return str(value)
    return value


def export_theo_nhom_xlsx(ma_xa: str, nhom_raw: str | None):
    """Xuất .xlsx: các dòng du_lieu_gcn của xã đã thu thập GCN và thuộc
    nhóm KH 2959 chỉ định. Trả về ((bytes, ten_file), None) hoặc
    (None, response_loi)."""
    ma_xa = (ma_xa or "").strip()
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã xã"}), 400)

    raw = nhom_raw or "Nhóm 2"
    nhom = [n.strip() for n in raw.split(",") if n.strip()]
    xau = [n.upper() for n in nhom if n.upper() in _NHOM_HOP_LE]
    if not xau:
        return None, (jsonify({"error": "Nhóm không hợp lệ (chỉ Nhóm 1 / Nhóm 2)"}), 400)

    rows: list = []
    offset = 0
    while True:
        page, error_response = gcn_repository.export_gcn_theo_nhom_page(
            ma_xa, nhom, _EXPORT_PAGE, offset
        )
        if error_response:
            return None, error_response
        page = page if isinstance(page, list) else []
        rows.extend(page)
        if len(page) < _EXPORT_PAGE or len(rows) >= _EXPORT_MAX:
            break
        offset += _EXPORT_PAGE

    wb = Workbook()
    ws = wb.active
    ws.title = "GCN"[:31]
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([_xlsx_cell(row.get(h)) for h in headers])
    else:
        ws.append(["Không có dữ liệu khớp"])

    buf = io.BytesIO()
    wb.save(buf)
    nhom_ten = "_".join(n.upper().replace("NHÓM ", "N").replace(" ", "") for n in nhom)
    return (buf.getvalue(), f"gcn_{nhom_ten}_{ma_xa}.xlsx"), None


def export_nhom3_xlsx(ma_xa: str, chi_nhom3: bool):
    """Xuất .xlsx đúng bố cục file mẫu TANAN.xlsx: toàn bộ dữ liệu GCN của
    1 đơn vị hành chính, hoặc chỉ thửa Nhóm 3 (chưa thuộc Nhóm 1/Nhóm 2 KH
    2959) nếu chi_nhom3=True. Trả về ((bytes, ten_file), None) hoặc
    (None, response_loi)."""
    ma_xa = (ma_xa or "").strip()
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã đơn vị hành chính"}), 400)

    rows: list = []
    offset = 0
    while True:
        page, error_response = gcn_repository.export_du_lieu_gcn_page(
            ma_xa, chi_nhom3, _EXPORT_PAGE, offset
        )
        if error_response:
            return None, error_response
        page = page if isinstance(page, list) else []
        rows.extend(page)
        if len(page) < _EXPORT_PAGE or len(rows) >= _EXPORT_MAX:
            break
        offset += _EXPORT_PAGE

    try:
        wb = load_workbook(_MAU_TANAN_PATH)
    except FileNotFoundError:
        return None, (jsonify({"error": "Thiếu file mẫu TANAN.xlsx trên server"}), 500)
    ws = wb[_MAU_TANAN_SHEET] if _MAU_TANAN_SHEET in wb.sheetnames else wb.active

    # Xóa hết dữ liệu mẫu (hàng 5 trở đi) trước khi ghi dữ liệu thật.
    first_data_row = _MAU_TANAN_HEADER_ROWS + 1
    if ws.max_row >= first_data_row:
        ws.delete_rows(first_data_row, ws.max_row - first_data_row + 1)

    for i, row in enumerate(rows):
        r = first_data_row + i
        ws.cell(row=r, column=1, value=i + 1)  # cột A: Số TT
        for col_letter, field in _MAU_TANAN_COLUMNS:
            if field is None:
                continue
            ws[f"{col_letter}{r}"] = _mau_tanan_cell_value(field, row.get(field))

    buf = io.BytesIO()
    wb.save(buf)
    pham_vi = "nhom3" if chi_nhom3 else "toanbo"
    return (buf.getvalue(), f"du_lieu_gcn_{ma_xa}_{pham_vi}.xlsx"), None


_CON_THIEU_FILL_DA_LAM = PatternFill("solid", fgColor="FFF9E79F")  # vàng nhạt


def export_nhom3_con_thieu_xlsx(ma_xa: str):
    """Xuất .xlsx TOÀN BỘ danh sách "tổng gửi xã" của 1 xã/phường — mã xã,
    số tờ, số thửa, mã định danh, ghi chú trạng thái từng thửa (Nhóm 1 -
    đã nhập biểu / Nhóm 3 - đã nhập biểu / Nhóm 3 - còn thiếu). Thay cho 3
    nút Excel riêng trước đây (còn thiếu / Nhóm 1 đã nhập / Nhóm 1 chưa
    nhập) — giờ gộp làm 1 danh sách duy nhất đúng phạm vi cột "tổng gửi
    xã" (đã trừ Nhóm 1/2 Chi nhánh KV chưa nhập, xem nhom3_tong_hop.tong)
    kèm ghi chú để phân biệt (yêu cầu người dùng).

    THÊM (yêu cầu người dùng, phát hiện khi tra Ea Păl): còn liệt kê thêm
    thửa ĐÃ nhập (có dòng du_lieu_gcn) nhưng KHÔNG nằm trong danh sách kế
    hoạch gửi xã (nhom3_can_thu_thap) — vốn vô hình hoàn toàn với số liệu
    Nhóm 3 trước đây. Ghi chú riêng theo phân loại Nhóm 1/2 nếu có ("Nhóm 1
    - đã nhập nhưng không có trong danh sách gửi xã"...), còn lại ghi
    "Đã nhập nhưng không có trong danh sách gửi xã" — xem
    public.nhom3_list_tong_gui_xa (supabase/schema.sql).

    Tô vàng dòng "đã nhập" (đã có người làm, kể cả 2 loại ghi chú mới ở
    trên) để phân biệt trực quan với dòng "còn thiếu". Trang
    '/nhom-3-con-thieu', icon tải Excel cuối mỗi dòng xã. Không chứa thông
    tin cá nhân (CCCD/tên/địa chỉ) nên không cần IMPORT_TOKEN, giống
    /api/gcn-danh-sach."""
    ma_xa = (ma_xa or "").strip()
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã xã"}), 400)

    rows: list = []
    offset = 0
    while True:
        page, error_response = gcn_repository.nhom3_list_tong_gui_xa(ma_xa, _EXPORT_PAGE, offset)
        if error_response:
            return None, error_response
        page = page if isinstance(page, dict) else {}
        items = page.get("items") if isinstance(page.get("items"), list) else []
        rows.extend(items)
        if len(items) < _EXPORT_PAGE or len(rows) >= _EXPORT_MAX:
            break
        offset += _EXPORT_PAGE

    wb = Workbook()
    ws = wb.active
    ws.title = "Tong gui xa"[:31]
    ws.append(["Mã xã", "Số tờ", "Số thửa", "Mã định danh", "Ghi chú"])
    for row in rows:
        ws.append([
            _xlsx_cell(row.get("ma_xa")),
            _xlsx_cell(row.get("so_to")),
            _xlsx_cell(row.get("so_thua")),
            _xlsx_cell(row.get("ma_dinh_danh")),
            _xlsx_cell(row.get("ghi_chu")),
        ])
        if "đã nhập" in (row.get("ghi_chu") or ""):
            r = ws.max_row
            for col in range(1, 6):
                ws.cell(row=r, column=col).fill = _CON_THIEU_FILL_DA_LAM
    if not rows:
        ws.append(["Không có thửa trong danh sách gửi xã"])

    buf = io.BytesIO()
    wb.save(buf)
    return (buf.getvalue(), f"nhom3_tong_gui_xa_{ma_xa}.xlsx"), None


def export_nhom3_con_lai_gui_xuong_xlsx(ma_xa: str):
    """Trang '/nhom-3-ty-le' — xuất .xlsx danh sách CÒN LẠI của 1 xã: thửa
    trong danh sách gửi xuống (đã trừ dự án) chưa Nhóm 1/2, chưa nhập biểu,
    gồm cả thửa chưa có trên bản đồ; kèm thôn theo ranh thôn. Không chứa
    thông tin cá nhân nên không cần IMPORT_TOKEN (như export_nhom3_con_thieu_xlsx)."""
    ma_xa = (ma_xa or "").strip()
    if not ma_xa:
        return None, (jsonify({"error": "Thiếu mã xã"}), 400)

    rows, error_response = gcn_repository.nhom3_list_con_lai_gui_xuong(ma_xa)
    if error_response:
        return None, error_response
    rows = rows if isinstance(rows, list) else []

    wb = Workbook()
    ws = wb.active
    ws.title = "Con lai"
    ws.append(["STT", "Mã xã", "Thôn/buôn", "Số tờ", "Số thửa", "Mã định danh",
               "Mục đích sử dụng", "Diện tích (m²)", "Có trên bản đồ"])
    for i, row in enumerate(rows, 1):
        ws.append([
            i,
            ma_xa,
            _xlsx_cell(row.get("thon") or ("(Ngoài ranh thôn)" if row.get("co_ban_do") else "")),
            _xlsx_cell(row.get("so_to")),
            _xlsx_cell(row.get("so_thua")),
            _xlsx_cell(row.get("ma_dinh_danh")),
            _xlsx_cell(row.get("muc_dich_su_dung")),
            _xlsx_cell(row.get("dien_tich")),
            "Có" if row.get("co_ban_do") else "Không",
        ])
    for col, width in zip("ABCDEFGHI", (7, 8, 24, 7, 8, 16, 16, 13, 13)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    if rows:
        ws.auto_filter.ref = ws.dimensions
    else:
        ws.append(["Không còn thửa nào"])

    buf = io.BytesIO()
    wb.save(buf)
    return (buf.getvalue(), f"nhom3_con_lai_{ma_xa}.xlsx"), None


def list_sources():
    result, error_response = gcn_repository.list_nguon()
    if error_response:
        return None, error_response
    return {"items": result}, None


def create_source(body: dict):
    ma_nguon = str(body.get("ma_nguon", "")).strip()
    ten_nguon = str(body.get("ten_nguon", "")).strip()
    url = str(body.get("url", "")).strip()
    kich_hoat = bool(body.get("kich_hoat", True))

    if not ma_nguon or not url:
        return None, (jsonify({"error": "Thiếu ma_nguon hoặc url"}), 400)

    payload = {"ma_nguon": ma_nguon, "ten_nguon": ten_nguon, "url": url, "kich_hoat": kich_hoat}
    result, error_response = gcn_repository.create_nguon(payload)
    if error_response:
        return None, error_response
    items = result
    return {"ok": True, "item": items[0] if items else payload}, None


def update_source(ma_nguon: str, body: dict):
    updates: dict = {}
    if "ten_nguon" in body:
        updates["ten_nguon"] = str(body["ten_nguon"]).strip()
    if "url" in body:
        updates["url"] = str(body["url"]).strip()
    if "kich_hoat" in body:
        updates["kich_hoat"] = bool(body["kich_hoat"])

    if not updates:
        return None, (jsonify({"error": "Không có trường nào để cập nhật"}), 400)

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    result, error_response = gcn_repository.update_nguon(ma_nguon, updates)
    if error_response:
        return None, error_response
    if not result:
        return None, (jsonify({"error": "Không tìm thấy nguồn"}), 404)
    return {"ok": True, "item": result[0]}, None


def delete_source(ma_nguon: str):
    _, error_response = gcn_repository.delete_nguon(ma_nguon)
    if error_response:
        return None, error_response
    return {"ok": True}, None


def sync_one(ma_nguon: str):
    try:
        source, error_response = gcn_repository.fetch_nguon_row(ma_nguon)
    except requests.RequestException as exc:
        return None, (jsonify({"error": str(exc)}), 502)
    if error_response:
        return None, error_response
    if not source:
        return None, (jsonify({"error": "Không tìm thấy nguồn"}), 404)
    if not source.get("url"):
        return None, (jsonify({"error": "Nguồn chưa có URL"}), 400)

    try:
        imported = gcn_sync.sync_source(
            ma_nguon, source.get("ten_nguon") or "", source["url"]
        )
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)
    except Exception as exc:  # noqa: BLE001 - lỗi đọc Sheet (sai URL/chưa share/sai tên trang tính...) phải báo rõ
        current_app.logger.exception("Đồng bộ GCN lỗi: ma_nguon=%s", ma_nguon)
        return None, (jsonify({"error": f"Đồng bộ thất bại: {exc}"}), 502)

    return {"ok": True, "ma_nguon": ma_nguon, "imported": imported}, None


def sync_all():
    try:
        sources, error_response = gcn_repository.list_active_sources()
    except requests.RequestException as exc:
        return None, (jsonify({"error": str(exc)}), 502)
    if error_response:
        return None, error_response

    results = []
    for source in sources:
        ma_nguon = source.get("ma_nguon")
        url = source.get("url")
        if not ma_nguon or not url:
            continue

        try:
            imported = gcn_sync.sync_source(ma_nguon, source.get("ten_nguon") or "", url)
        except Exception as exc:  # noqa: BLE001 - 1 nguồn lỗi không được chặn các nguồn khác
            current_app.logger.exception("Đồng bộ GCN lỗi: ma_nguon=%s", ma_nguon)
            results.append({"ma_nguon": ma_nguon, "ok": False, "error": str(exc)})
        else:
            results.append({"ma_nguon": ma_nguon, "ok": True, "imported": imported})

    return {"ok": True, "results": results}, None
