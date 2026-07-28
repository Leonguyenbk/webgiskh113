from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from pyproj import Transformer


NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "app": "http://www.vietbando.com/gml/vlis",
}


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


def _parse_root(root: ET.Element) -> dict:
    transformer = Transformer.from_crs("EPSG:9218", "EPSG:4326", always_xy=True)
    features = []

    for index, member in enumerate(root.findall("wfs:member", NS), start=1):
        parcel = member.find("app:Thua_Dat", NS)
        if parcel is None:
            continue

        exterior = parcel.find(
            "app:Geometry/gml:Polygon/gml:exterior/gml:LinearRing/gml:posList", NS
        )
        if exterior is None or not (exterior.text or "").strip():
            continue

        rings = [_ring(exterior.text or "", transformer)]
        for interior in parcel.findall(
            "app:Geometry/gml:Polygon/gml:interior/gml:LinearRing/gml:posList", NS
        ):
            rings.append(_ring(interior.text or "", transformer))

        so_to = int(_text(parcel, "app:soHieuToBanDo", "0"))
        so_thua = int(_text(parcel, "app:soThuTuThua", "0"))
        dien_tich_raw = _text(parcel, "app:dienTich", "0")

        features.append(
            {
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
        )

    return {
        "type": "FeatureCollection",
        "name": "Thua_Dat",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": features,
    }


def read_gml(path: str | Path) -> dict:
    root = ET.parse(Path(path)).getroot()
    return _parse_root(root)


def parse_gml_bytes(data: bytes) -> dict:
    root = ET.fromstring(data)
    return _parse_root(root)


def rows_from_geojson(data: dict) -> list[dict]:
    rows = []
    for feature in data["features"]:
        props = feature["properties"]
        rows.append({**props, "geom": feature["geometry"]})
    return rows


def write_geojson(data: dict, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

