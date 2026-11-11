from __future__ import annotations

import psycopg2
from flask import Blueprint, current_app, jsonify, request

from ..repositories import ranh_gml_repository
from ..utils.validators import check_import_token


def _check_token() -> bool:
    """Nhận RANH_GML_TOKEN (mã riêng phát cho tool) hoặc IMPORT_TOKEN."""
    rieng = current_app.config.get("RANH_GML_TOKEN", "")
    if rieng and request.headers.get("X-Import-Token", "") == rieng:
        return True
    return check_import_token()

ranh_gml_bp = Blueprint("ranh_gml", __name__)

# Ranh_GML_Tool (tool desktop, D:\QUANGTUAN\ranhgmltool) gửi ranh lên đây vì
# máy người dùng không kết nối thẳng CSDL được. Trả cả tên chủ/địa chỉ nên
# bắt buộc mã xác thực: RANH_GML_TOKEN (mã riêng, chỉ mở
# /api/ranh-gml/*) hoặc IMPORT_TOKEN.
GIOI_HAN_THUA = 60000
GIOI_HAN_VUNG = 50000  # tool cũ (chưa chia đợt) gửi cả ranh 1 lần — vd 7.067 vùng trồng


@ranh_gml_bp.get("/api/ranh-gml/kiem-tra")
def kiem_tra():
    if not _check_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401
    return jsonify({"ok": True, "gioi_han_thua": GIOI_HAN_THUA})


@ranh_gml_bp.post("/api/ranh-gml/thua-giao-ranh")
def thua_giao_ranh():
    if not _check_token():
        return jsonify({"error": "Mã xác thực không đúng"}), 401
    body = request.get_json(silent=True) or {}
    vung = body.get("vung")
    if not isinstance(vung, list) or not vung:
        return jsonify({"error": "Thiếu danh sách vùng ranh (vung)"}), 400
    if len(vung) > GIOI_HAN_VUNG:
        return jsonify({"error": f"Ranh quá nhiều vùng (tối đa {GIOI_HAN_VUNG})"}), 400
    sach = []
    for i, v in enumerate(vung, 1):
        g = v.get("g") if isinstance(v, dict) else None
        if not isinstance(g, dict) or g.get("type") not in ("Polygon", "MultiPolygon"):
            return jsonify({"error": f"Vùng {i} không phải Polygon/MultiPolygon GeoJSON"}), 400
        sach.append({"stt": int(v.get("stt") or i), "g": g})
    try:
        rows = ranh_gml_repository.thua_giao_ranh(sach, GIOI_HAN_THUA + 1)
    except psycopg2.errors.QueryCanceled:
        return jsonify({"error": "Ranh quá lớn, truy vấn quá thời gian — chia nhỏ ranh rồi xuất từng phần"}), 504
    except psycopg2.Error as exc:
        current_app.logger.warning("ranh-gml loi: %s", exc)
        msg = (getattr(exc, "pgerror", None) or str(exc)).strip().splitlines()
        return jsonify({"error": "Truy vấn lỗi: " + (msg[0] if msg else "không rõ")}), 400
    if len(rows) > GIOI_HAN_THUA:
        return jsonify({"error": f"Ranh giao hơn {GIOI_HAN_THUA:,} thửa — chia nhỏ ranh rồi xuất từng phần"}), 400
    return jsonify({"tong": len(rows), "items": rows})
