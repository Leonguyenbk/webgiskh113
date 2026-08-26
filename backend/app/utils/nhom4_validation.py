from __future__ import annotations

import re

# Port từ bieumau/Utils.js (validateSoPhatHanhGCN_) và bieumau/Validate.js
# (parseNumberVN_, validatePayload_) — tách riêng khỏi utils/validators.py
# vì file đó chỉ parse Flask request, không chứa validation nghiệp vụ.

_SO_PHAT_HANH_10_SO = re.compile(r"^\d{10}$")
_SO_PHAT_HANH_CHU_SO = re.compile(r"^[A-ZĐ]{1,2} \d+$")
_NGAY_DDMMYYYY = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_NAM_ONLY = re.compile(r"^\d{4}$")

CCCD_PATTERN = re.compile(r"^\d{12}$")

# ONT/ODT (đất ở) mặc định thời hạn "Lâu dài"; loại đất khác bắt buộc nhập
# ngày hết hạn dd/mm/yyyy (hoặc chỉ 1 năm, hiểu là 31/12 năm đó — xem
# normalize_thoi_han_su_dung) — khớp đúng logic ở frontend
# (nhom4Constants/Nhom4FormPage.jsx, hằng số LOAI_DAT_LAU_DAI).
LOAI_DAT_LAU_DAI = {"ONT", "ODT"}


def validate_thoi_han_su_dung(loai_dat: str, thoi_han: str) -> bool:
    if str(loai_dat or "").strip().upper() in LOAI_DAT_LAU_DAI:
        return True
    s = str(thoi_han or "").strip()
    return bool(_NGAY_DDMMYYYY.match(s) or _NAM_ONLY.match(s))


def normalize_thoi_han_su_dung(loai_dat: str, thoi_han: str) -> str:
    """Chuẩn hoá trước khi lưu: chỉ nhập năm (VD "2050") thì coi là hết hạn
    31/12 năm đó — phòng trường hợp frontend chưa kịp tự chuẩn hoá lúc blur."""
    s = str(thoi_han or "").strip()
    if str(loai_dat or "").strip().upper() in LOAI_DAT_LAU_DAI:
        return s
    if _NAM_ONLY.match(s):
        return f"31/12/{s}"
    return s


def validate_so_phat_hanh_gcn(value: str) -> bool:
    """Số phát hành GCN: đúng 10 chữ số, hoặc 1-2 chữ cái + 1 dấu cách +
    8/9 số (1 chữ cái) hay 9/11 số (2 chữ cái)."""
    s = str(value or "").strip().upper()
    if not s:
        return False

    if _SO_PHAT_HANH_10_SO.match(s):
        return True

    if not _SO_PHAT_HANH_CHU_SO.match(s):
        return False

    letters = s.split(" ", 1)[0]
    if len(letters) == 1:
        return len(s) in (8, 9)
    if len(letters) == 2:
        return len(s) in (9, 11)
    return False


def parse_number_vn(value) -> float | None:
    """Chấp nhận số kiểu VN (dấu , là thập phân, dấu . là nghìn) lẫn kiểu
    chuẩn — trả None nếu không parse được."""
    s = str(value if value is not None else "").strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _thieu(*labels: str) -> str:
    return "Vui lòng nhập đủ thông tin: " + ", ".join(labels) + "."


def validate_parcel(parcel: dict, index: int) -> str | None:
    thua = parcel.get("thua") or {}
    dat1 = parcel.get("dat1") or {}
    dat2 = parcel.get("dat2") or {}
    stt = index + 1

    if not thua.get("so_to") or not thua.get("so_thua"):
        return f"Vui lòng nhập số tờ và số thửa cho thửa thứ {stt}."
    if not thua.get("dien_tich_thua_dat"):
        return f"Vui lòng nhập diện tích thửa đất cho thửa thứ {stt}."

    if not all(
        [
            dat1.get("loai_dat"),
            dat1.get("dien_tich"),
            dat1.get("nguon_goc_su_dung"),
            dat1.get("hinh_thuc_su_dung"),
            dat1.get("thoi_han_su_dung"),
        ]
    ):
        return f"Vui lòng nhập đủ thông tin loại đất 1 cho thửa thứ {stt}."
    if not validate_thoi_han_su_dung(dat1.get("loai_dat"), dat1.get("thoi_han_su_dung")):
        return f"Thời hạn sử dụng loại đất 1 phải nhập theo dạng dd/mm/yyyy ở thửa thứ {stt}."

    co_dat2 = any(
        [
            dat2.get("loai_dat"),
            dat2.get("dien_tich"),
            dat2.get("nguon_goc_su_dung"),
            dat2.get("hinh_thuc_su_dung"),
            dat2.get("thoi_han_su_dung"),
        ]
    )
    if co_dat2:
        if not all(
            [
                dat2.get("loai_dat"),
                dat2.get("dien_tich"),
                dat2.get("nguon_goc_su_dung"),
                dat2.get("hinh_thuc_su_dung"),
                dat2.get("thoi_han_su_dung"),
            ]
        ):
            return f"Vui lòng nhập đủ thông tin loại đất 2 cho thửa thứ {stt}."
        if not validate_thoi_han_su_dung(dat2.get("loai_dat"), dat2.get("thoi_han_su_dung")):
            return f"Thời hạn sử dụng loại đất 2 phải nhập theo dạng dd/mm/yyyy ở thửa thứ {stt}."

        tong = parse_number_vn(thua.get("dien_tich_thua_dat"))
        dt1 = parse_number_vn(dat1.get("dien_tich"))
        dt2 = parse_number_vn(dat2.get("dien_tich"))
        if tong is None or dt1 is None or dt2 is None:
            return f"Diện tích phải là số ở thửa thứ {stt}."
        if abs((dt1 + dt2) - tong) > 0.0001:
            return (
                "Diện tích loại đất 1 + loại đất 2 phải bằng diện tích "
                f"thửa đất ở thửa thứ {stt}."
            )

    return None


def validate_payload(payload: dict) -> str | None:
    """Validate toàn bộ payload trước khi lưu — trả về thông báo lỗi đầu
    tiên gặp phải, hoặc None nếu hợp lệ. Port từ validatePayload_."""
    if not payload.get("ma_xa"):
        return "Thiếu mã xã."

    che_do = payload.get("che_do") or ""
    doi_tuong = payload.get("doi_tuong") or "Hộ gia đình, cá nhân"

    parcels = payload.get("thua_list") or []
    if not parcels:
        return "Chưa có thông tin thửa đất."

    if doi_tuong == "Tổ chức":
        to_chuc = payload.get("to_chuc") or {}
        if not to_chuc.get("ten_to_chuc"):
            return "Vui lòng nhập Tên tổ chức."
        ma_dinh_danh_dai_dien = to_chuc.get("ma_dinh_danh_ca_nhan_dai_dien")
        if ma_dinh_danh_dai_dien and not CCCD_PATTERN.match(str(ma_dinh_danh_dai_dien)):
            return "Mã định danh cá nhân phải đủ 12 số."
    else:
        owners = payload.get("owners") or []
        if not owners:
            return "Chưa có thông tin chủ sử dụng."

        seen_cccd: set[str] = set()
        for i, owner in enumerate(owners):
            if not all(
                [
                    owner.get("ho_ten"),
                    owner.get("ngay_sinh"),
                    owner.get("gioi_tinh"),
                    owner.get("cccd"),
                    owner.get("dia_chi_thuong_tru"),
                    owner.get("phap_nhan"),
                    owner.get("vai_tro_phap_nhan"),
                ]
            ):
                return f"Vui lòng nhập đủ thông tin chủ sử dụng thứ {i + 1}."
            cccd = str(owner.get("cccd") or "")
            if not CCCD_PATTERN.match(cccd):
                return f"Số CCCD người thứ {i + 1} phải đủ 12 số."
            if cccd in seen_cccd:
                return f"Số CCCD người thứ {i + 1} bị trùng trong hồ sơ."
            seen_cccd.add(cccd)

    if che_do == "Đã có GCN":
        gcn = payload.get("gcn") or {}
        if not gcn.get("so_phat_hanh") or not gcn.get("ngay_cap"):
            return "Vui lòng nhập đủ thông tin GCN."
        if not validate_so_phat_hanh_gcn(gcn.get("so_phat_hanh")):
            return "Số phát hành GCN nhập không đúng định dạng."

    for i, parcel in enumerate(parcels):
        error = validate_parcel(parcel, i)
        if error:
            return error

    return None
