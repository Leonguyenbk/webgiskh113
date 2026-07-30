from __future__ import annotations

import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import BinaryIO, Iterator

from pyproj import Transformer


NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "app": "http://www.vietbando.com/gml/vlis",
}

MEMBER_TAG = f"{{{NS['wfs']}}}member"


def _text(node: ET.Element, path: str, default: str = "") -> str:
    item = node.find(path, NS)
    return (item.text or "").strip() if item is not None else default


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


def _feature_from_member(member: ET.Element, transformer: Transformer, index: int) -> dict | None:
    parcel = member.find("app:Thua_Dat", NS)
    if parcel is None:
        return None

    exterior = parcel.find(
        "app:Geometry/gml:Polygon/gml:exterior/gml:LinearRing/gml:posList", NS
    )
    if exterior is None or not (exterior.text or "").strip():
        return None

    rings = [_ring(exterior.text or "", transformer)]
    for interior in parcel.findall(
        "app:Geometry/gml:Polygon/gml:interior/gml:LinearRing/gml:posList", NS
    ):
        rings.append(_ring(interior.text or "", transformer))

    so_to = int(_text(parcel, "app:soHieuToBanDo", "0"))
    so_thua = int(_text(parcel, "app:soThuTuThua", "0"))
    dien_tich_raw = _text(parcel, "app:dienTich", "0")

    return {
        "type": "Feature",
        "id": index,
        "geometry": {"type": "Polygon", "coordinates": rings},
        "properties": {
            "so_to": so_to,
            "so_thua": so_thua,
            "ma_xa": _text(parcel, "app:maXa"),
            "muc_dich_su_dung": _text(parcel, "app:mucDichSuDung"),
            "dien_tich": float(dien_tich_raw or 0),
            "ten_chu": _text(parcel, "app:tenChu"),
            "dia_chi": _text(parcel, "app:diaChi"),
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
        if event != "end" or elem.tag != MEMBER_TAG:
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

