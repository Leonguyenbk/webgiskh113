from __future__ import annotations

import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import BinaryIO, Iterator

from pyproj import Transformer


# Một số nguồn xuất GML (VD ThuaDat.gml) khai báo xmlns:wfs/xmlns:app cục bộ
# bằng chuỗi bất kỳ (VD xmlns:wfs="ThuaDat") thay vì URI chuẩn OGC/vietbando,
# nên không thể match cố định theo NS bên dưới cho các thẻ wfs:/app:. Chỉ có
# gml: (hình học) là luôn đúng URI chuẩn trong mọi file đã gặp.
NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "app": "http://www.vietbando.com/gml/vlis",
}

# Tên phần tử bọc 1 thửa đất — mỗi nguồn xuất GML đặt tên khác nhau
# ("Thua_Dat" hay "ThuaDat" không dấu gạch dưới).
PARCEL_LOCAL_NAMES = ("Thua_Dat", "ThuaDat")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child(node: ET.Element, *names: str) -> ET.Element | None:
    """Tìm con TRỰC TIẾP theo tên local, bỏ qua namespace."""
    for child in node:
        if _local_name(child.tag) in names:
            return child
    return None


def _text(node: ET.Element, name: str, default: str = "") -> str:
    child = _child(node, name)
    return (child.text or "").strip() if child is not None else default


def _ring(pos_list: str, transformer: Transformer) -> list[list[float]]:
    values = [float(value) for value in pos_list.split()]
    if len(values) % 2:
        raise ValueError("Danh sách tọa độ GML không có đủ cặp X/Y")
    result = []
    for index in range(0, len(values), 2):
        longitude, latitude = transformer.transform(values[index], values[index + 1])
        result.append([round(longitude, 8), round(latitude, 8)])
    if result and result[0] != result[-1]:
        result.append(result[0])
    return result


def _ring_from_linear_ring_parent(parent: ET.Element, transformer: Transformer) -> list[list[float]] | None:
    ring = _child(parent, "LinearRing")
    pos_list = _child(ring, "posList") if ring is not None else None
    if pos_list is None or not (pos_list.text or "").strip():
        return None
    return _ring(pos_list.text or "", transformer)


def _rings_from_polygon(polygon: ET.Element, transformer: Transformer) -> list[list[list[float]]] | None:
    exterior = _child(polygon, "exterior")
    ext_ring = _ring_from_linear_ring_parent(exterior, transformer) if exterior is not None else None
    if ext_ring is None:
        return None

    rings = [ext_ring]
    for child in polygon:
        if _local_name(child.tag) != "interior":
            continue
        int_ring = _ring_from_linear_ring_parent(child, transformer)
        if int_ring is not None:
            rings.append(int_ring)
    return rings


def _geometry_rings(parcel: ET.Element, transformer: Transformer) -> list[list[list[float]]] | None:
    geometry = _child(parcel, "Geometry")
    if geometry is None:
        return None

    polygon = _child(geometry, "Polygon")
    if polygon is not None:
        return _rings_from_polygon(polygon, transformer)

    # MultiPolygon (thửa có nhiều phần rời nhau) — cột geom trong Supabase
    # đang khai báo kiểu Polygon đơn, chưa hỗ trợ lưu MultiPolygon nên bỏ
    # qua thửa này thay vì chỉ lấy 1 phần (sẽ sai hình dạng thật). Số lượng
    # thực tế rất ít (~15/55.654 thửa trong ThuaDat.gml).
    return None


def _feature_from_member(member: ET.Element, transformer: Transformer, index: int) -> dict | None:
    parcel = _child(member, *PARCEL_LOCAL_NAMES)
    if parcel is None:
        return None

    rings = _geometry_rings(parcel, transformer)
    if rings is None:
        return None

    so_to = int(_text(parcel, "soHieuToBanDo", "0") or "0")
    so_thua = int(_text(parcel, "soThuTuThua", "0") or "0")
    dien_tich_raw = _text(parcel, "dienTich", "0")

    return {
        "type": "Feature",
        "id": index,
        "geometry": {"type": "Polygon", "coordinates": rings},
        "properties": {
            "so_to": so_to,
            "so_thua": so_thua,
            "ma_xa": _text(parcel, "maXa"),
            "ma_thua_dat": _text(parcel, "maThuaDat"),
            # Một số nguồn xuất GML đặt tên khác cho mục đích sử dụng đất
            # (VD maLoaiDat thay vì mucDichSuDung) — thử lần lượt, không để
            # trống nếu file dùng tên khác. Quan trọng từ khi import_gml
            # chuyển sang upsert merge-duplicates: đọc sai/để trống ở đây sẽ
            # ghi đè xóa mất muc_dich_su_dung đúng đã có sẵn trong Supabase.
            "muc_dich_su_dung": _text(parcel, "mucDichSuDung") or _text(parcel, "maLoaiDat"),
            "dien_tich": float(dien_tich_raw or 0),
            "ten_chu": _text(parcel, "tenChu"),
            "dia_chi": _text(parcel, "diaChi"),
        },
    }


def iter_features(source: BinaryIO) -> Iterator[dict]:
    # File GML thực tế có thể nặng vài chục MB. Parse toàn bộ bằng
    # ET.parse/fromstring giữ cả cây DOM trong RAM (thường phình to gấp
    # 5-10 lần dung lượng file), dễ làm worker Render hết bộ nhớ và bị
    # kill giữa chừng (client thấy "Failed to fetch"). Dùng iterparse và
    # giải phóng từng <wfs:member> ngay sau khi xử lý để bộ nhớ đỉnh chỉ
    # còn cỡ một thửa đất thay vì cả file.
    transformer = Transformer.from_crs("EPSG:9218", "EPSG:4326", always_xy=True)
    context = ET.iterparse(source, events=("start", "end"))
    _, root = next(context)
    index = 0
    for event, elem in context:
        if event != "end" or _local_name(elem.tag) != "member":
            continue
        index += 1
        feature = _feature_from_member(elem, transformer, index)
        if feature is not None:
            yield feature
        elem.clear()
        root.clear()


def _collection(features: Iterator[dict]) -> dict:
    return {
        "type": "FeatureCollection",
        "name": "Thua_Dat",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": list(features),
    }


def read_gml(path: str | Path) -> dict:
    with open(Path(path), "rb") as stream:
        return _collection(iter_features(stream))


def parse_gml_bytes(data: bytes) -> dict:
    return _collection(iter_features(io.BytesIO(data)))


def rows_from_geojson(data: dict) -> list[dict]:
    rows = []
    for feature in data["features"]:
        props = feature["properties"]
        rows.append({**props, "geom": feature["geometry"]})
    return rows


def iter_rows(source: BinaryIO) -> Iterator[dict]:
    # Dùng trực tiếp khi nhập GML từ request upload: đọc/parse theo luồng
    # (không qua parse_gml_bytes + rows_from_geojson) để không phải giữ
    # thêm một bản sao toàn bộ nội dung file lẫn danh sách feature trong
    # bộ nhớ cùng lúc.
    for feature in iter_features(source):
        yield {**feature["properties"], "geom": feature["geometry"]}


def write_geojson(data: dict, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
