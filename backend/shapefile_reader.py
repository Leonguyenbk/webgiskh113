from __future__ import annotations

import os
import re
import tempfile
import zipfile
from typing import BinaryIO, Iterator

import pyproj
import shapefile

# Nguồn xuất Shapefile mặc định nếu không có .prj — cùng khu vực Đắk Lắk
# như mọi dữ liệu GML khác trong dự án (xem gml_reader.py).
DEFAULT_CRS = "EPSG:9218"

MA_XA_CANDIDATES = ("maxa", "ma_xa", "madvhc")
TEN_THON_CANDIDATES = ("tenthon", "ten_thon", "thon")


def _normalize_field_name(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[àáạảãâầấậẩẫăằắặẳẵ]", "a", s)
    s = re.sub(r"[èéẹẻẽêềếệểễ]", "e", s)
    s = re.sub(r"[ìíịỉĩ]", "i", s)
    s = re.sub(r"[òóọỏõôồốộổỗơờớợởỡ]", "o", s)
    s = re.sub(r"[ùúụủũưừứựửữ]", "u", s)
    s = re.sub(r"[ỳýỵỷỹ]", "y", s)
    s = s.replace("đ", "d")
    return re.sub(r"[^a-z0-9]", "", s)


def _find_field(field_names: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {name: _normalize_field_name(name) for name in field_names}
    for candidate in candidates:
        for name, norm in normalized.items():
            if norm == candidate:
                return name
    return None


def _read_prj_wkt(zip_path: str) -> str | None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.namelist():
            if member.lower().endswith(".prj"):
                return archive.read(member).decode("utf-8", errors="replace")
    return None


def _build_transformer(zip_path: str) -> pyproj.Transformer:
    prj_wkt = _read_prj_wkt(zip_path)
    try:
        source_crs = pyproj.CRS.from_wkt(prj_wkt) if prj_wkt else pyproj.CRS.from_user_input(DEFAULT_CRS)
    except pyproj.exceptions.CRSError:
        source_crs = pyproj.CRS.from_user_input(DEFAULT_CRS)
    return pyproj.Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)


def _transform_coords(coords, transformer: pyproj.Transformer):
    # coords là list lồng nhau tùy độ sâu (ring toạ độ, hoặc list ring, hoặc
    # list part) — đệ quy tới khi gặp 1 cặp toạ độ (tuple/list 2 số).
    if len(coords) == 2 and all(isinstance(v, (int, float)) for v in coords):
        x, y = transformer.transform(coords[0], coords[1])
        return [round(x, 8), round(y, 8)]
    return [_transform_coords(item, transformer) for item in coords]


def _to_multipolygon(geo_interface: dict) -> list | None:
    geom_type = geo_interface.get("type")
    coordinates = geo_interface.get("coordinates")
    if not coordinates:
        return None
    if geom_type == "Polygon":
        return [coordinates]
    if geom_type == "MultiPolygon":
        return coordinates
    return None


def _open_reader(zip_path: str, encoding: str) -> shapefile.Reader:
    return shapefile.Reader(zip_path, encoding=encoding)


def iter_rows(file_stream: BinaryIO, encoding: str = "utf-8") -> Iterator[dict]:
    """Đọc 1 file .zip Shapefile (upload) chứa .shp/.shx/.dbf (+ .prj tùy
    chọn) — trả generator dict {"ma_xa", "ten_thon", "geom"} sẵn sàng ghi
    vào bảng public.ranh_gioi_thon.

    pyshp chỉ hỗ trợ đọc thẳng từ zip khi truyền ĐƯỜNG DẪN FILE (không phải
    file-like object), nên phải ghi tạm ra đĩa trước khi đọc.
    """
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(file_stream.read())
        zip_path = tmp.name

    try:
        reader = _open_reader(zip_path, encoding)
        field_names = [f[0] for f in reader.fields if f[0] != "DeletionFlag"]
        ma_xa_field = _find_field(field_names, MA_XA_CANDIDATES)
        ten_thon_field = _find_field(field_names, TEN_THON_CANDIDATES)
        if not ma_xa_field or not ten_thon_field:
            raise ValueError(
                "Không nhận diện được cột mã xã/tên thôn trong file .dbf. "
                f"Các cột hiện có: {', '.join(field_names)}"
            )

        transformer = _build_transformer(zip_path)

        for shape_record in reader.shapeRecords():
            record = shape_record.record.as_dict()
            ma_xa = str(record.get(ma_xa_field) or "").strip()
            ten_thon = str(record.get(ten_thon_field) or "").strip()
            if not ma_xa or not ten_thon:
                continue

            geo = shape_record.shape.__geo_interface__
            multipolygon_coords = _to_multipolygon(geo)
            if multipolygon_coords is None:
                continue

            yield {
                "ma_xa": ma_xa,
                "ten_thon": ten_thon,
                "geom": {
                    "type": "MultiPolygon",
                    "coordinates": _transform_coords(multipolygon_coords, transformer),
                },
            }
    finally:
        try:
            os.remove(zip_path)
        except OSError:
            pass
