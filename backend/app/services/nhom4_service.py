from __future__ import annotations

import re
import threading
import uuid

from flask import current_app, jsonify

from ..repositories import google_drive_client, nhom4_repository
from ..repositories.nhom4_repository import NHOM4_MA_NGUON, NHOM4_TEN_NGUON
from ..utils.nhom4_validation import normalize_thoi_han_su_dung, validate_payload

MAX_PDF_BYTES = 20 * 1024 * 1024

# Thửa đã thuộc Nhóm 1/Nhóm 2 (KH 2959) coi như đã có dữ liệu từ trước —
# không cần nhập biểu Nhóm 4 nữa, giống quy ước đã dùng ở
# gcn_thu_thap_theo_xa (supabase/schema.sql).
NHOM_1_2 = {"NHÓM 1", "NHÓM 2"}


def _is_nhom_1_2(phan_loai) -> bool:
    return str(phan_loai or "").strip().upper() in NHOM_1_2


def _to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _make_key(ma_xa: str, so_to, so_thua) -> str:
    # Phải khớp đúng công thức cột generated madvhc_soto_sothua trong
    # du_lieu_gcn (trim(madvhc) || '_' || normalize_so_text(soto) || '_' ||
    # normalize_so_text(sothua)) — so_to/so_thua ở đây luôn là số nguyên nên
    # normalize_so_text cho kết quả giống str(int) trong Python.
    return f"{ma_xa.strip()}_{so_to}_{so_thua}"


def check_trung_thua(ma_xa: str, so_to: str, so_thua: str):
    so_to_int = _to_int(so_to)
    so_thua_int = _to_int(so_thua)
    if not ma_xa or so_to_int is None or so_thua_int is None:
        return {"trung": False, "nhom_1_2": False, "ton_tai": False}, None

    ton_tai, error_response = nhom4_repository.exists_in_thua_dat(ma_xa, so_to_int, so_thua_int)
    if error_response:
        return None, error_response

    trung, error_response = nhom4_repository.exists_key(_make_key(ma_xa, so_to_int, so_thua_int))
    if error_response:
        return None, error_response

    phan_loai, error_response = nhom4_repository.get_phan_loai(ma_xa, so_to_int, so_thua_int)
    if error_response:
        return None, error_response

    return {
        "trung": trung,
        "nhom_1_2": _is_nhom_1_2(phan_loai),
        "phan_loai": phan_loai,
        "ton_tai": ton_tai,
    }, None


def get_dia_chi_thua_dat(ma_xa: str, so_to: str, so_thua: str):
    """Địa chỉ thửa đất tự sinh để điền sẵn ô "Địa chỉ thửa đất" ở biểu
    Nhóm 4. Thiếu tham số thì trả rỗng (frontend giữ nguyên ô đang có)."""
    ma_xa = (ma_xa or "").strip()
    so_to_int = _to_int(so_to)
    so_thua_int = _to_int(so_thua)
    if not ma_xa or so_to_int is None or so_thua_int is None:
        return {"dia_chi": ""}, None

    dia_chi, error_response = nhom4_repository.get_dia_chi_thua_dat(ma_xa, so_to_int, so_thua_int)
    if error_response:
        return None, error_response
    return {"dia_chi": dia_chi or ""}, None


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return cleaned or "HSQ.pdf"


def _validate_pdf(file_storage, label: str) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    content_type = (file_storage.mimetype or "").lower()
    if content_type != "application/pdf":
        return f"{label}: chỉ cho phép file PDF."

    header = file_storage.stream.read(5)
    file_storage.stream.seek(0)
    if header[:4] != b"%PDF":
        return f"{label}: nội dung file không phải PDF hợp lệ."

    return None


def _default_so_phat_hanh(ma_xa: str, so_to, so_thua) -> str:
    # Quy ước giống bieumau/Validate.js cũ: khi "Chưa được cấp GCN" thì
    # sophathanhgcn không để trống mà đánh dấu bằng tiền tố này — phân biệt
    # được với số phát hành GCN thật khi tra cứu, không cần thêm cột riêng
    # lưu "chế độ hồ sơ" trong du_lieu_gcn.
    return f"CHUACOGIAY_{ma_xa}_{so_to}_{so_thua}"


def _build_rows(payload: dict, submission_id: str, file_info: dict) -> list[dict]:
    ma_xa = payload["ma_xa"]
    che_do = payload.get("che_do") or ""
    doi_tuong = payload.get("doi_tuong") or "Hộ gia đình, cá nhân"
    gcn = payload.get("gcn") or {}
    to_chuc = payload.get("to_chuc") or {}
    nguoi_hien_tai = payload.get("nguoi_su_dung_hien_tai") or {}
    parcels = payload.get("thua_list") or []
    da_co_gcn = che_do == "Đã có GCN"
    la_to_chuc = doi_tuong == "Tổ chức"

    ten_file_quet = ", ".join(
        name
        for name in (
            file_info.get("chinh_name"),
            file_info.get("phu_name"),
            file_info.get("tbxn_name"),
        )
        if name
    )

    if la_to_chuc:
        owners = [
            {
                "ho_ten": to_chuc.get("ho_ten_dai_dien", ""),
                "ngay_sinh": to_chuc.get("ngay_sinh_dai_dien", ""),
                "gioi_tinh": to_chuc.get("gioi_tinh_dai_dien", ""),
                "cccd": to_chuc.get("ma_dinh_danh_ca_nhan_dai_dien", ""),
                "dia_chi_thuong_tru": to_chuc.get("dia_chi_thuong_tru_dai_dien", ""),
                "phap_nhan": "Tổ chức",
                "vai_tro_phap_nhan": "",
            }
        ]
    else:
        owners = [
            owner
            for owner in (payload.get("owners") or [])
            if owner.get("ho_ten") or owner.get("cccd")
        ]

    rows = []
    for parcel in parcels:
        thua = parcel.get("thua") or {}
        dat1 = parcel.get("dat1") or {}
        dat2 = parcel.get("dat2") or {}
        so_to = _to_int(thua.get("so_to"))
        so_thua = _to_int(thua.get("so_thua"))

        so_phat_hanh = gcn.get("so_phat_hanh") if da_co_gcn else _default_so_phat_hanh(ma_xa, so_to, so_thua)

        for owner in owners:
            rows.append(
                {
                    "ma_nguon": NHOM4_MA_NGUON,
                    "ten_nguon": NHOM4_TEN_NGUON,
                    "submission_id": submission_id,
                    "madvhc": ma_xa,
                    "soto": str(so_to),
                    "sothua": str(so_thua),
                    "madinhdanhthuadat": thua.get("ma_dinh_danh") or None,
                    "sophathanhgcn": so_phat_hanh,
                    "ngaycapgcn": gcn.get("ngay_cap") if da_co_gcn else None,
                    "sovaosogcn": gcn.get("so_vao_so") if da_co_gcn else None,
                    "soto_gcn": thua.get("so_to_gcn") if da_co_gcn else None,
                    "sothua_gcn": thua.get("so_thua_gcn") if da_co_gcn else None,
                    "tentochuc": to_chuc.get("ten_to_chuc") if la_to_chuc else None,
                    "madinhdanhtochuc": to_chuc.get("ma_dinh_danh_to_chuc") if la_to_chuc else None,
                    "hovatenchusudung": owner.get("ho_ten", ""),
                    "ngaythangnamsinh": owner.get("ngay_sinh", ""),
                    "gioitinh": owner.get("gioi_tinh", ""),
                    "sodinhdanhcanhan": owner.get("cccd", ""),
                    "diachithuongtru": owner.get("dia_chi_thuong_tru", ""),
                    "phapnhantrengcn": owner.get("phap_nhan", ""),
                    "vaitrophapnhan": owner.get("vai_tro_phap_nhan", ""),
                    "diachi_thuadat": thua.get("dia_chi_thua_dat", ""),
                    "dientichthuadat": thua.get("dien_tich_thua_dat"),
                    "loaidat1": dat1.get("loai_dat", ""),
                    "dientich1": dat1.get("dien_tich"),
                    "nguongoc1": dat1.get("nguon_goc_su_dung", ""),
                    "hinhthucsudung1": dat1.get("hinh_thuc_su_dung", ""),
                    "thoihansudung1": normalize_thoi_han_su_dung(dat1.get("loai_dat"), dat1.get("thoi_han_su_dung")),
                    "loaidat2": dat2.get("loai_dat"),
                    "dientich2": dat2.get("dien_tich"),
                    "nguongoc2": dat2.get("nguon_goc_su_dung"),
                    "hinhthucsudung2": dat2.get("hinh_thuc_su_dung"),
                    "thoihansudung2": normalize_thoi_han_su_dung(dat2.get("loai_dat"), dat2.get("thoi_han_su_dung"))
                    if dat2.get("loai_dat")
                    else dat2.get("thoi_han_su_dung"),
                    "ghichu": thua.get("ghi_chu") or payload.get("ghi_chu"),
                    "tenchusudunghientai": nguoi_hien_tai.get("ho_ten") or None,
                    "sodinhdanh_chusudunghientai": nguoi_hien_tai.get("cccd") or None,
                    "diachi_chusudunghientai": nguoi_hien_tai.get("dia_chi_thuong_tru") or None,
                    "lydothaydoi": nguoi_hien_tai.get("ly_do_thay_doi") or None,
                    "tenfilequet": ten_file_quet or None,
                    "file_chinh_drive_id": file_info.get("chinh_id"),
                    "file_chinh_ten_file": file_info.get("chinh_name"),
                    "file_phu_drive_id": file_info.get("phu_id"),
                    "file_phu_ten_file": file_info.get("phu_name"),
                    "file_tbxn_drive_id": file_info.get("tbxn_id"),
                    "file_tbxn_ten_file": file_info.get("tbxn_name"),
                }
            )

    return rows


def submit_ho_so(payload: dict, file_chinh, file_phu, file_tbxn=None):
    error = validate_payload(payload)
    if error:
        return None, (jsonify({"error": error}), 400)

    if not file_chinh or not file_chinh.filename:
        label = "Đơn đăng ký" if payload.get("che_do") != "Đã có GCN" else "Giấy chứng nhận"
        return None, (jsonify({"error": f"Vui lòng chọn file PDF {label}."}), 400)

    for storage, label in (
        (file_chinh, "File chính"),
        (file_phu, "Giấy tờ"),
        (file_tbxn, "Thông báo xác nhận"),
    ):
        pdf_error = _validate_pdf(storage, label)
        if pdf_error:
            return None, (jsonify({"error": pdf_error}), 400)

    ma_xa = payload["ma_xa"]
    parcels = payload.get("thua_list") or []

    # 1) Chuẩn hóa số tờ/số thửa + tạo khóa madvhc_soto_sothua cho từng
    #    thửa. Chặn trùng ngay trong danh sách nhập.
    seen_in_payload: set[str] = set()
    parcel_keys: list[tuple[int, int, str]] = []
    for parcel in parcels:
        thua = parcel.get("thua") or {}
        so_to = _to_int(thua.get("so_to"))
        so_thua = _to_int(thua.get("so_thua"))
        if so_to is None or so_thua is None:
            return None, (
                jsonify(
                    {"error": f"Số tờ/số thửa không hợp lệ: {thua.get('so_to')}/{thua.get('so_thua')}"}
                ),
                400,
            )
        key = _make_key(ma_xa, so_to, so_thua)
        if key in seen_in_payload:
            return None, (
                jsonify({"error": f"Danh sách thửa nhập bị trùng: thửa {so_thua}, tờ {so_to}"}),
                400,
            )
        seen_in_payload.add(key)
        parcel_keys.append((so_to, so_thua, key))

    # 2-4) public.du_lieu_gcn là NGUỒN DUY NHẤT xác định thửa đã có dữ liệu
    #      GCN. EXISTS 1 bản ghi cùng khóa madvhc_soto_sothua => thửa đã có
    #      dữ liệu (dù thửa đó có nhiều dòng do nhiều chủ) => không cho nộp.
    #      KHÔNG dùng bảng khóa phụ (nhom4_thua_da_nop đã bỏ) để quyết định.
    def _reject_existing():
        existing, err = nhom4_repository.filter_existing_keys(list(seen_in_payload))
        if err:
            return err
        for _so_to, _so_thua, _key in parcel_keys:
            if _key in existing:
                return (
                    jsonify(
                        {
                            "error": (
                                f"Thửa {_so_thua}, tờ {_so_to} đã có dữ liệu GCN "
                                "và không được nộp lại."
                            )
                        }
                    ),
                    409,
                )
        return None

    error_response = _reject_existing()
    if error_response:
        return None, error_response

    # Chỉ nhận thửa CÓ THẬT trong public.thua_dat (đã nhập GML) — chặn nộp
    # nhầm số tờ/số thửa không tồn tại trên bản đồ. dong_bo_du_lieu/
    # du_lieu_gcn không tự phát hiện được lỗi này vì 2 bảng đó không bắt
    # buộc khớp với thua_dat (xem nhom4_repository.exists_in_thua_dat).
    so_to_dang_nop = [so_to for so_to, _so_thua, _key in parcel_keys]
    thua_dat_keys_by_xa, error_response = nhom4_repository.list_thua_dat_keys_by_xa(
        ma_xa, so_to_dang_nop
    )
    if error_response:
        return None, error_response

    for so_to, so_thua, _key in parcel_keys:
        if (so_to, so_thua) not in thua_dat_keys_by_xa:
            return None, (
                jsonify(
                    {
                        "error": (
                            f"Thửa {so_thua}, tờ {so_to} không tồn tại trong dữ liệu thửa đất "
                            "(thua_dat) — kiểm tra lại số tờ/số thửa."
                        )
                    }
                ),
                404,
            )

    phan_loai_by_xa, error_response = nhom4_repository.list_phan_loai_by_xa(
        ma_xa, so_to_dang_nop
    )
    if error_response:
        return None, error_response

    for parcel in parcels:
        thua = parcel.get("thua") or {}
        so_to = _to_int(thua.get("so_to"))
        so_thua = _to_int(thua.get("so_thua"))
        phan_loai = phan_loai_by_xa.get((so_to, so_thua))
        if _is_nhom_1_2(phan_loai):
            return None, (
                jsonify(
                    {
                        "error": (
                            f"Thửa {so_to}_{so_thua} đã thuộc {phan_loai} — "
                            "coi như đã có dữ liệu từ trước, không cần nhập biểu Nhóm 4 nữa."
                        )
                    }
                ),
                409,
            )

    first_thua = (parcels[0].get("thua") or {}) if parcels else {}
    che_do = payload.get("che_do") or ""
    da_co_gcn = che_do == "Đã có GCN"
    # Tên file quét trên Drive khớp quy ước bieumau/Validate.js
    # (makeTenFileHsq_):
    #   - Đã có GCN    -> base = số phát hành GCN thật  -> "<sph>-GCN.pdf"
    #   - Chưa có giấy -> base = CHUACOGIAY_<mã xã>_<số tờ>_<số thửa>
    #     (đúng bằng _default_so_phat_hanh, tức là trùng luôn với giá trị
    #     cột sophathanhgcn ghi vào du_lieu_gcn cho thửa đầu) ->
    #     "CHUACOGIAY_..-DDK.pdf".
    if da_co_gcn:
        base_name = _sanitize_filename(
            str((payload.get("gcn") or {}).get("so_phat_hanh") or "").strip()
        )
    else:
        base_name = _sanitize_filename(
            _default_so_phat_hanh(
                ma_xa, _to_int(first_thua.get("so_to")), _to_int(first_thua.get("so_thua"))
            )
        )
    chinh_suffix = "GCN" if da_co_gcn else "DDK"

    # Đọc nội dung file NGAY (trong request), vì FileStorage của Flask
    # không dùng được nữa sau khi request kết thúc — bytes đọc ra thì
    # thread nền phía dưới dùng lại được bình thường.
    chinh_bytes = file_chinh.read()
    phu_bytes = file_phu.read() if (file_phu and file_phu.filename) else None
    # Thông báo xác nhận (-TBXN) chỉ dùng ở chế độ "Chưa được cấp GCN" và
    # luôn là tùy chọn — không có thì bỏ qua, không chặn nộp.
    tbxn_bytes = (
        file_tbxn.read()
        if (file_tbxn and file_tbxn.filename and che_do != "Đã có GCN")
        else None
    )

    submission_id = str(uuid.uuid4())
    # file_info để trống lúc ghi — không chờ Drive để trả lời người nộp
    # ngay (upload PDF lên Drive là bước chậm nhất, ~vài giây tới cả phút
    # tùy dung lượng/mạng). Cột file_*/tenfilequet được cập nhật SAU bởi
    # _upload_files_background() khi upload xong.
    rows = _build_rows(payload, submission_id, {})

    # Kiểm tra lại public.du_lieu_gcn NGAY TRƯỚC KHI INSERT — thu hẹp khe
    # race khi 2 request nộp gần đồng thời cùng 1 thửa (frontend đã khóa
    # nút Nộp, đây là lớp chặn cuối phía backend).
    error_response = _reject_existing()
    if error_response:
        return None, error_response

    _, error_response = nhom4_repository.insert_rows(rows)
    if error_response:
        return None, error_response

    # current_app là proxy theo request/app context hiện tại — phải lấy
    # object app THẬT ở đây (còn trong request) để thread nền tự mở lại
    # app context riêng (xem _upload_files_background), vì current_app sẽ
    # không dùng được nữa sau khi request này kết thúc.
    app = current_app._get_current_object()
    threading.Thread(
        target=_upload_files_background,
        args=(
            app, ma_xa, payload.get("ten_xa"), base_name, chinh_suffix,
            chinh_bytes, phu_bytes, tbxn_bytes, submission_id,
        ),
        daemon=True,
    ).start()

    return {
        "ok": True,
        "message": f"Đã lưu {len(parcels)} thửa, tổng {len(rows)} dòng. File quét đang tải lên Drive ở nền.",
        "so_thua": len(parcels),
        "so_dong": len(rows),
    }, None


def _upload_files_background(
    app, ma_xa: str, ten_xa, base_name: str, chinh_suffix: str,
    chinh_bytes: bytes, phu_bytes: bytes | None, tbxn_bytes: bytes | None,
    submission_id: str,
) -> None:
    with app.app_context():
        file_info: dict = {}
        try:
            folder_id = google_drive_client.resolve_xa_folder(ma_xa, ten_xa)
            uploaded_chinh = google_drive_client.upload_pdf(
                folder_id, f"{base_name}-{chinh_suffix}.pdf", chinh_bytes
            )
            file_info["chinh_id"] = uploaded_chinh["id"]
            file_info["chinh_name"] = uploaded_chinh["name"]

            if phu_bytes:
                uploaded_phu = google_drive_client.upload_pdf(folder_id, f"{base_name}-GT.pdf", phu_bytes)
                file_info["phu_id"] = uploaded_phu["id"]
                file_info["phu_name"] = uploaded_phu["name"]

            if tbxn_bytes:
                uploaded_tbxn = google_drive_client.upload_pdf(folder_id, f"{base_name}-TBXN.pdf", tbxn_bytes)
                file_info["tbxn_id"] = uploaded_tbxn["id"]
                file_info["tbxn_name"] = uploaded_tbxn["name"]
        except Exception:
            current_app.logger.exception(
                "Upload Drive nền cho submission %s thất bại — dòng đã lưu nhưng thiếu file quét.",
                submission_id,
            )
            return

        _, error_response = nhom4_repository.update_file_info_by_submission(submission_id, file_info)
        if error_response:
            current_app.logger.error(
                "Cập nhật file_info nền cho submission %s thất bại: %s", submission_id, error_response
            )
