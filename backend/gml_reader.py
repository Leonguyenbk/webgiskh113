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
    # "geometryProperty": file xuất qua OGR/GDAL (ogr:ThuaDat trong
    # ogr:featureMember, VD THUADAT/KHU VUC DONG HOA/.../XA HOA XUAN).
    geometry = _child(parcel, "Geometry", "geometryProperty")
    if geometry is None:
        return None

    polygon = _child(geometry, "Polygon")
    if polygon is not None:
        return _rings_from_polygon(polygon, transformer)

    # OGR luôn bọc thành MultiSurface kể cả thửa chỉ 1 polygon — lấy được
    # khi có đúng 1 surfaceMember, nhiều phần rời thì bỏ như MultiPolygon.
    multi = _child(geometry, "MultiSurface")
    if multi is not None:
        members = [m for m in multi if _local_name(m.tag) == "surfaceMember"]
        polygon = _child(members[0], "Polygon") if len(members) == 1 else None
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

    # File OGR/shapefile cắt tên trường còn 10 ký tự (soHieuToBa, soThuTuThu).
    so_to = int(_text(parcel, "soHieuToBanDo") or _text(parcel, "soHieuToBa") or "0")
    so_thua = int(_text(parcel, "soThuTuThua") or _text(parcel, "soThuTuThu") or "0")
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
            # Tên chủ đăng ký theo sổ mục kê cũ — đa số file chưa có thẻ này,
            # để trống thì upsert_thua_dat_diff giữ nguyên giá trị đã có.
            "ten_chu_dk": _text(parcel, "tenChuDK") or _text(parcel, "tenChuDangKy"),
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
        if event != "end" or _local_name(elem.tag) not in ("member", "featureMember"):
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


# --- Ranh giới thôn (GML) -----------------------------------------------
# Chưa có file mẫu GML ranh thôn thật để soi đúng tên thẻ (khác ThuaDat.gml
# — đây là lớp ranh giới thôn/buôn, không phải thửa đất) nên đọc theo kiểu
# "khoan dò" thay vì khớp cứng 1 tên:
#   - Tên phần tử bọc 1 thôn trong <member> KHÔNG đoán tên — GML wfs:member
#     luôn bọc ĐÚNG 1 feature, nên lấy thẳng con trực tiếp duy nhất của
#     <member>, bất kể tên thẻ là gì.
#   - Tên thôn/mã xã: thử lần lượt vài tên thường gặp (giống cách
#     mucDichSuDung/maLoaiDat ở trên đã làm với thửa đất).
#   - Hình học: ranh thôn thường rời nhiều phần (MultiPolygon, cột geom
#     trong ranh_gioi_thon cũng khai kiểu MultiPolygon, khác Polygon đơn của
#     thua_dat) — gom TẤT CẢ thẻ "Polygon" nằm trong "Geometry" (dù lồng
#     trực tiếp hay qua 1 lớp bọc MultiPolygon/polygonMember nào đó), không
#     khớp cứng theo tên thẻ bọc multi-part.
# Nếu sai tên thẻ thực tế thì sẽa lại _TEN_THON_TAGS/_MA_XA_TAGS theo lỗi
# "thiếu tên thôn/mã xã" khi người dùng thử nhập file thật.
_TEN_THON_TAGS = ("tenThon", "tenThonBuon", "tenBuonThon", "tenDonVi", "ten")
_MA_XA_TAGS = ("maXa", "maDVHC", "ma_xa")


def _first_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for name in names:
        value = _text(node, name)
        if value:
            return value
    return ""


def _only_child(node: ET.Element) -> ET.Element | None:
    for child in node:
        return child
    return None


def _multipolygon_rings_from_geometry(
    geometry: ET.Element, transformer: Transformer
) -> list[list[list[float]]] | None:
    parts = []
    for elem in geometry.iter():
        if elem is geometry or _local_name(elem.tag) != "Polygon":
            continue
        rings = _rings_from_polygon(elem, transformer)
        if rings is not None:
            parts.append(rings)
    return parts or None


def _feature_ranh_thon_from_member(member: ET.Element, transformer: Transformer) -> dict | None:
    thon = _only_child(member)
    if thon is None:
        return None

    geometry = _child(thon, "Geometry")
    if geometry is None:
        return None

    parts = _multipolygon_rings_from_geometry(geometry, transformer)
    if parts is None:
        return None

    ma_xa = _first_text(thon, _MA_XA_TAGS)
    ten_thon = _first_text(thon, _TEN_THON_TAGS)
    if not ma_xa or not ten_thon:
        return None

    return {
        "ma_xa": ma_xa,
        "ten_thon": ten_thon,
        "geom": {"type": "MultiPolygon", "coordinates": parts},
    }


def iter_rows_ranh_thon(source: BinaryIO) -> Iterator[dict]:
    """Đọc GML ranh giới thôn theo kiểu streaming (giống iter_rows ở trên),
    trả generator dict {"ma_xa", "ten_thon", "geom"} sẵn sàng ghi vào
    public.ranh_gioi_thon (geom kiểu MultiPolygon)."""
    transformer = Transformer.from_crs("EPSG:9218", "EPSG:4326", always_xy=True)
    context = ET.iterparse(source, events=("start", "end"))
    _, root = next(context)
    for event, elem in context:
        if event != "end" or _local_name(elem.tag) != "member":
            continue
        feature = _feature_ranh_thon_from_member(elem, transformer)
        if feature is not None:
            yield feature
        elem.clear()
        root.clear()


def write_geojson(data: dict, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
