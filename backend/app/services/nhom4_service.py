from __future__ import annotations

import re
import uuid

from flask import jsonify

from ..repositories import google_drive_client, nhom4_repository
from ..repositories.nhom4_repository import NHOM4_MA_NGUON, NHOM4_TEN_NGUON
from ..utils.nhom4_validation import normalize_thoi_han_su_dung, validate_payload

MAX_PDF_BYTES = 20 * 1024 * 1024


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
        return {"trung": False}, None

    trung, error_response = nhom4_repository.exists_key(_make_key(ma_xa, so_to_int, so_thua_int))
    if error_response:
        return None, error_response

    return {"trung": trung}, None


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
    parcels = payload.get("thua_list") or []
    da_co_gcn = che_do == "Đã có GCN"
    la_to_chuc = doi_tuong == "Tổ chức"

    ten_file_quet = ", ".join(
        name for name in (file_info.get("chinh_name"), file_info.get("phu_name")) if name
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
                    "tenfilequet": ten_file_quet or None,
                    "file_chinh_drive_id": file_info.get("chinh_id"),
                    "file_chinh_ten_file": file_info.get("chinh_name"),
                    "file_phu_drive_id": file_info.get("phu_id"),
                    "file_phu_ten_file": file_info.get("phu_name"),
                }
            )

    return rows


def submit_ho_so(payload: dict, file_chinh, file_phu):
    error = validate_payload(payload)
    if error:
        return None, (jsonify({"error": error}), 400)

    if not file_chinh or not file_chinh.filename:
        label = "Đơn đăng ký" if payload.get("che_do") != "Đã có GCN" else "Giấy chứng nhận"
        return None, (jsonify({"error": f"Vui lòng chọn file PDF {label}."}), 400)

    for storage, label in ((file_chinh, "File chính"), (file_phu, "Giấy tờ")):
        pdf_error = _validate_pdf(storage, label)
        if pdf_error:
            return None, (jsonify({"error": pdf_error}), 400)

    ma_xa = payload["ma_xa"]
    parcels = payload.get("thua_list") or []

    seen_in_payload: set[str] = set()
    for parcel in parcels:
        thua = parcel.get("thua") or {}
        key = _make_key(ma_xa, _to_int(thua.get("so_to")), _to_int(thua.get("so_thua")))
        if key in seen_in_payload:
            return None, (
                jsonify({"error": f"Danh sách thửa nhập bị trùng: {thua.get('so_to')}_{thua.get('so_thua')}"}),
                400,
            )
        seen_in_payload.add(key)

    existing_keys, error_response = nhom4_repository.list_existing_keys(ma_xa)
    if error_response:
        return None, error_response

    for key in seen_in_payload:
        if key in existing_keys:
            return None, (jsonify({"error": f"Thửa này đã có dữ liệu GCN rồi: {key}"}), 409)

    try:
        folder_id = google_drive_client.resolve_xa_folder(ma_xa)
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)

    first_thua = (parcels[0].get("thua") or {}) if parcels else {}
    base_name = _sanitize_filename(f"{ma_xa}_{first_thua.get('so_to')}_{first_thua.get('so_thua')}")
    che_do = payload.get("che_do") or ""
    chinh_suffix = "GCN" if che_do == "Đã có GCN" else "DDK"

    file_info: dict = {}
    try:
        uploaded_chinh = google_drive_client.upload_pdf(
            folder_id, f"{base_name}-{chinh_suffix}.pdf", file_chinh.read()
        )
        file_info["chinh_id"] = uploaded_chinh["id"]
        file_info["chinh_name"] = uploaded_chinh["name"]

        if file_phu and file_phu.filename:
            uploaded_phu = google_drive_client.upload_pdf(
                folder_id, f"{base_name}-GT.pdf", file_phu.read()
            )
            file_info["phu_id"] = uploaded_phu["id"]
            file_info["phu_name"] = uploaded_phu["name"]
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 502)

    submission_id = str(uuid.uuid4())
    rows = _build_rows(payload, submission_id, file_info)

    _, error_response = nhom4_repository.insert_rows(rows)
    if error_response:
        return None, error_response

    return {
        "ok": True,
        "message": f"Đã lưu {len(parcels)} thửa, tổng {len(rows)} dòng.",
        "so_thua": len(parcels),
        "so_dong": len(rows),
    }, None
