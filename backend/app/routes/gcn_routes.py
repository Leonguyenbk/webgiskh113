from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from ..services import gcn_service
from ..utils.validators import check_import_token

gcn_bp = Blueprint("gcn", __name__)

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@gcn_bp.get("/api/gcn-stats")
def gcn_stats():
    data, error_response = gcn_service.get_stats()
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.get("/api/gcn-danh-sach")
def gcn_danh_sach():
    # Danh sách dòng du_lieu_gcn theo xã (trang "Danh sách thửa đã nhập")
    # — tên xã, số tờ, số thửa, mã định danh, ngày nhập. ?ma_xa=<mã
    # xã>&sort=asc|desc&limit=&offset=&so_to=&so_thua=
    data, error_response = gcn_service.get_danh_sach_da_nhap(
        request.args.get("ma_xa", ""),
        request.args.get("sort"),
        request.args.get("limit"),
        request.args.get("offset"),
        request.args.get("so_to"),
        request.args.get("so_thua"),
    )
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.get("/api/gcn-danh-sach/chi-tiet")
def gcn_danh_sach_chi_tiet():
    # Nút "Xem/Sửa" ở trang "Danh sách thửa đã nhập". ?ma_xa=&so_to=&so_thua=
    data, error_response = gcn_service.get_du_lieu_gcn_chi_tiet(
        request.args.get("ma_xa", ""),
        request.args.get("so_to", ""),
        request.args.get("so_thua", ""),
    )
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.patch("/api/gcn-danh-sach/chi-tiet/<int:row_id>")
def gcn_danh_sach_chi_tiet_sua(row_id: int):
    # Lưu thay đổi 1 dòng (1 chủ sử dụng) ở modal "Xem/Sửa" — CHỈ cho sửa
    # dòng nguồn "biểu Nhóm 4" (chặn ở service/repository). ?ma_xa=&so_to=&so_thua=
    body = request.get_json(silent=True) or {}
    data, error_response = gcn_service.update_du_lieu_gcn_chi_tiet(
        row_id,
        request.args.get("ma_xa", ""),
        request.args.get("so_to", ""),
        request.args.get("so_thua", ""),
        body,
    )
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.delete("/api/gcn-danh-sach/chi-tiet")
def gcn_danh_sach_chi_tiet_xoa():
    # Nút "Xóa để nhập lại" ở trang "Danh sách thửa đã nhập" — xóa toàn bộ
    # dòng (mọi chủ sử dụng) của 1 thửa, CHỈ áp dụng nguồn "biểu Nhóm 4"
    # (chặn ở service/repository). ?ma_xa=&so_to=&so_thua=
    data, error_response = gcn_service.delete_du_lieu_gcn_thua(
        request.args.get("ma_xa", ""),
        request.args.get("so_to", ""),
        request.args.get("so_thua", ""),
    )
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.get("/api/thong-ke-nguon-nhap")
def thong_ke_nguon_nhap():
    # Tổng số thửa đã nhập toàn dự án, tách Form (biểu Nhóm 4) / nguồn khác
    # (đồng bộ Google Sheet) — trang "/thong-ke-nguon-nhap".
    data, error_response = gcn_service.get_thong_ke_nguon_nhap()
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.get("/api/nhom3-con-thieu/tong-hop")
def nhom3_con_thieu_tong_hop():
    # ?to_giam_sat=1|2|3|4 (bỏ trống = tất cả) — lọc theo Tổ kiểm tra,
    # giám sát KH113 (Quyết định 867/QĐ-VPĐKĐĐ ngày 01/10/2026).
    data, error_response = gcn_service.get_nhom3_tong_hop(request.args.get("to_giam_sat"))
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.get("/api/nhom3-con-thieu/export-tong-hop")
def nhom3_con_thieu_export_tong_hop():
    # Xuất .xlsx tổng hợp tiến độ theo xã: khối lượng gửi xuống, đã vào dữ
    # liệu, đã nhập biểu, tổng đã làm, tỷ lệ. ?to_giam_sat=1|2|3|4 (bỏ
    # trống = tất cả).
    result, error_response = gcn_service.export_nhom3_tong_hop_xlsx(
        request.args.get("to_giam_sat")
    )
    if error_response:
        return error_response
    content, filename = result
    return Response(
        content,
        mimetype=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@gcn_bp.get("/api/nhom3-con-thieu/danh-sach")
def nhom3_con_thieu_danh_sach():
    # ?ma_xa=&limit=&offset=&co_nhap=1|0 (bỏ trống = tất cả trạng thái)
    data, error_response = gcn_service.get_nhom3_danh_sach_con_thieu(
        request.args.get("ma_xa"),
        request.args.get("limit"),
        request.args.get("offset"),
        request.args.get("co_nhap"),
    )
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.get("/api/nhom3-con-thieu/trend")
def nhom3_con_thieu_trend():
    # Dashboard trend tốc độ xử lý theo xã (thửa/ngày). ?ma_xa=&tu=<ISO
    # datetime, lọc từ thời điểm này trở đi>&den=<ISO datetime, tới thời
    # điểm này>
    data, error_response = gcn_service.get_nhom3_tien_do_trend(
        request.args.get("ma_xa"),
        request.args.get("tu"),
        request.args.get("den"),
    )
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.post("/api/nhom3-con-thieu/refresh")
def nhom3_con_thieu_refresh():
    # Tính lại bảng cache nhom3_trang_thai_cache (nhánh quét nặng). Gọi
    # TAY sau mỗi lần nạp thêm danh sách Nhóm 3 mới — không phải request
    # người dùng thường — nên chắn bằng IMPORT_TOKEN, giống /api/gcn-stats/refresh.
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    data, error_response = gcn_service.refresh_nhom3_cache()
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.get("/api/gcn-export-theo-nhom")
def gcn_export_theo_nhom():
    # Xuất .xlsx danh sách du_lieu_gcn của 1 xã đã thu thập + thuộc nhóm
    # KH 2959 (mặc định Nhóm 2). ?ma_xa=<mã xã>&nhom=Nhóm 2[,Nhóm 1]
    result, error_response = gcn_service.export_theo_nhom_xlsx(
        request.args.get("ma_xa", ""), request.args.get("nhom")
    )
    if error_response:
        return error_response
    content, filename = result
    return Response(
        content,
        mimetype=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@gcn_bp.get("/api/nhom3-con-thieu/export")
def nhom3_con_thieu_export():
    # Xuất .xlsx danh sách "tổng gửi xã" (đã trừ Nhóm 1/2 Chi nhánh KV
    # chưa nhập) của 1 xã — mã xã, số tờ, số thửa, mã định danh, ghi chú
    # trạng thái từng thửa. ?ma_xa=<mã xã>
    result, error_response = gcn_service.export_nhom3_con_thieu_xlsx(
        request.args.get("ma_xa", "")
    )
    if error_response:
        return error_response
    content, filename = result
    return Response(
        content,
        mimetype=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@gcn_bp.get("/api/nhom3-con-thieu/danh-sach-nhom1-chua-nhap")
def nhom3_con_thieu_danh_sach_nhom1_chua_nhap():
    # Thửa đã thuộc Nhóm 1 nhưng CHƯA nhập biểu (Chi nhánh khu vực làm
    # trực tiếp). ?ma_xa=&limit=&offset=
    data, error_response = gcn_service.get_nhom3_list_nhom1_chua_nhap(
        request.args.get("ma_xa"),
        request.args.get("limit"),
        request.args.get("offset"),
    )
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.get("/api/nhom3-con-thieu/danh-sach-nhom1-da-nhap")
def nhom3_con_thieu_danh_sach_nhom1_da_nhap():
    # Thửa đã thuộc Nhóm 1 ĐÃ nhập biểu (xã làm). ?ma_xa=&limit=&offset=
    data, error_response = gcn_service.get_nhom3_list_nhom1_da_nhap(
        request.args.get("ma_xa"),
        request.args.get("limit"),
        request.args.get("offset"),
    )
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.get("/api/gcn-export-nhom3")
def gcn_export_nhom3():
    # Xuất .xlsx đúng bố cục file mẫu TANAN.xlsx của 1 đơn vị hành chính —
    # chỉ thửa Nhóm 3 (chưa thuộc Nhóm 1/Nhóm 2 KH 2959), hoặc lấy hết.
    # ?ma_xa=<mã ĐVHC>&chi_nhom3=1 (mặc định 0 = lấy hết, không lọc nhóm).
    # File chứa dữ liệu cá nhân (CCCD, địa chỉ...) nên bắt buộc mã xác thực
    # IMPORT_TOKEN giống các endpoint quản trị khác — khác
    # /api/gcn-export-theo-nhom (không chặn) vì xuất TOÀN BỘ dữ liệu 1 xã,
    # không chỉ 1 nhóm KH 2959.
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    chi_nhom3 = request.args.get("chi_nhom3", "").strip().lower() in ("1", "true", "yes")
    result, error_response = gcn_service.export_nhom3_xlsx(
        request.args.get("ma_xa", ""), chi_nhom3
    )
    if error_response:
        return error_response
    content, filename = result
    return Response(
        content,
        mimetype=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@gcn_bp.post("/api/gcn-stats/refresh")
def gcn_stats_refresh():
    # Tính lại bảng cache thống kê thu thập (nhánh quét nặng). Dành cho
    # cron gọi định kỳ — không phải request người dùng — nên chắn bằng
    # IMPORT_TOKEN. Nếu đã bật pg_cron thì không cần endpoint này.
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    data, error_response = gcn_service.refresh_stats_cache()
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.get("/api/nguon-gcn")
def list_nguon_gcn():
    data, error_response = gcn_service.list_sources()
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.post("/api/nguon-gcn")
def create_nguon_gcn():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    body = request.get_json(silent=True) or {}
    data, error_response = gcn_service.create_source(body)
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.patch("/api/nguon-gcn/<path:ma_nguon>")
def update_nguon_gcn(ma_nguon: str):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    body = request.get_json(silent=True) or {}
    data, error_response = gcn_service.update_source(ma_nguon, body)
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.delete("/api/nguon-gcn/<path:ma_nguon>")
def delete_nguon_gcn(ma_nguon: str):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    data, error_response = gcn_service.delete_source(ma_nguon)
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.post("/api/nguon-gcn/<path:ma_nguon>/sync")
def sync_one_nguon_gcn(ma_nguon: str):
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    data, error_response = gcn_service.sync_one(ma_nguon)
    if error_response:
        return error_response
    return jsonify(data)


@gcn_bp.post("/api/nguon-gcn/sync-all")
def sync_all_nguon_gcn():
    if not check_import_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401

    data, error_response = gcn_service.sync_all()
    if error_response:
        return error_response
    return jsonify(data)
