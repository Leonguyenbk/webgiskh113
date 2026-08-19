from __future__ import annotations

from flask import current_app, jsonify, request

SPATIAL_ARGS = (
    "west",
    "south",
    "east",
    "north",
    "center_lng",
    "center_lat",
)


def check_import_token() -> bool:
    import_token = current_app.config.get("IMPORT_TOKEN", "")
    return not import_token or request.headers.get("X-Import-Token", "") == import_token


def read_bbox():
    """
    Đọc và kiểm tra khung bản đồ từ query string.

    Trả về (values, None) khi hợp lệ, hoặc (None, response_loi) khi không.
    """
    missing = [name for name in SPATIAL_ARGS if request.args.get(name) in (None, "")]

    if missing:
        return None, (
            jsonify({"error": "Thiếu tham số khung bản đồ: " + ", ".join(missing)}),
            400,
        )

    try:
        values = {name: float(request.args[name]) for name in SPATIAL_ARGS}
    except (TypeError, ValueError):
        return None, (jsonify({"error": "Tọa độ khung bản đồ không phải số"}), 400)

    # Leaflet trả kinh độ ngoài [-180, 180] khi người dùng kéo bản đồ vòng
    # qua đường đổi ngày. Kẹp lại thay vì báo lỗi để bản đồ không đứng hình.
    for name in ("west", "east", "center_lng"):
        values[name] = max(-180.0, min(180.0, values[name]))

    for name in ("south", "north", "center_lat"):
        values[name] = max(-90.0, min(90.0, values[name]))

    if values["west"] >= values["east"] or values["south"] >= values["north"]:
        return None, (jsonify({"error": "Khung bản đồ không hợp lệ"}), 400)

    return values, None


def read_nhom_list() -> list[str]:
    # Trả về danh sách nhóm cần lọc (rỗng nghĩa là không lọc). "DEFAULT" là
    # giá trị đặc biệt cho "chưa phân loại", còn lại là nguyên văn giá trị
    # phan_loai_ke_hoach_2959 — không giới hạn trước danh sách nhóm hợp lệ,
    # để sau này thêm nhóm mới (Nhóm 3, 4...) không cần sửa code backend.
    raw = request.args.get("nhom", "").strip()
    if not raw:
        return []
    values = [item.strip().upper() for item in raw.split(",")]
    return [value for value in values if value]


def read_optional_int(name: str):
    """Đọc tham số int tùy chọn. Trả về (giá_trị, None) hoặc (None, response_loi)."""
    raw = request.args.get(name, "").strip()
    if not raw:
        return None, None
    try:
        return int(raw), None
    except ValueError:
        return None, (jsonify({"error": f"{name} phải là số nguyên"}), 400)
