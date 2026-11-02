"""Danh mục trong kho: tách dòng file danh mục hồ sơ gốc (mỗi dòng 1 hồ sơ, ô
có thể chứa nhiều tên/thửa/seri ngăn bởi xuống dòng, ";", ",") thành biểu
tách dòng CSDL (mỗi dòng 1 người x 1 thửa) — làm giống tool tách dòng (khớp
~99% hồ sơ khi so với BIEU_TACH_DONG_CSDL.xlsx) — rồi upsert vào bảng
danh_muc_trong_kho. Dùng cho đồng bộ định kỳ từ Google Sheet danh mục gốc
và cho trang /danh-muc-trong-kho khi người dùng gửi file gốc."""

from __future__ import annotations

import datetime
import io
import re
import unicodedata

import requests
from flask import current_app, jsonify
from openpyxl import load_workbook

from ..config import Config
from ..repositories import supabase_client

_SEP = re.compile(r"[;,\n]+|(?<=\d)\.(?=\d)")
_SEP_TEN = re.compile(r"[;\n,]+|\s+[vV]à\s+")
_SEP_DONG = re.compile(r"[;\n]+")
_GOOGLE_ID = re.compile(r"/d/([A-Za-z0-9_-]+)")


def khong_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return " ".join("".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower().split())


def _txt(v):
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, datetime.time):
        return None
    s = " ".join(str(v).split())
    return s or None


def _ds(v, sep=_SEP) -> list[str]:
    if v is None:
        return []
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, (datetime.datetime, datetime.date)):
        v = v.strftime("%d/%m/%Y")
    return [" ".join(p.split()) for p in sep.split(str(v)) if p.strip()]


def _ngay(v):
    if isinstance(v, (int, float)):
        if 1900 <= v <= 2100:
            return str(int(v))
        if 20000 < v < 80000:
            return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(v))).strftime("%d/%m/%Y")
    return _txt(v)


def _ten(t: str) -> str:
    t = " ".join(re.sub(r"\([^)]*\)?", " ", t).split())
    t = re.sub(r"^(ông|bà|Ông|Bà)\s+", "", t)
    return t.title() if t.isupper() else t


def _seri(x: str) -> str:
    m = re.fullmatch(r"([A-Za-zĐđ]+)\s*(\d+)", x)
    return f"{m.group(1).upper()} {m.group(2)}" if m else x.upper()


def tach_ho_so(rec: dict) -> list[dict]:
    """1 dòng hồ sơ gốc -> các dòng tách (tên x thửa). Danh sách thửa/tờ cũ-mới
    ghép theo vị trí, danh sách 1 phần tử dùng chung cho mọi thửa; nhiều seri mà
    số seri khác số thửa thì không ghép được -> mỗi seri 1 dòng, bỏ trống thửa."""
    tens = [t for t in (_ten(t) for t in _ds(rec["ten"], _SEP_TEN)) if t] or [None]
    tm, gm, tc, gc = _ds(rec["thua_moi"]), _ds(rec["to_moi"]), _ds(rec["thua_cu"]), _ds(rec["to_cu"])
    seri = [_seri(x) for x in _ds(rec["seri"])]
    n = max(len(tm), len(tc), 1)

    def lay(lst, k):
        if not lst:
            return None
        if len(lst) == 1:
            return lst[0]
        return lst[k] if k < len(lst) else None

    if len(seri) > 1 and len(seri) != n:
        cap_thua = [(None, None, None, None, s) for s in seri]
    else:
        cap_thua = []
        for k in range(n):
            s = seri[0] if len(seri) == 1 else (seri[k] if seri else None)
            cap_thua.append((lay(tc, k), lay(gc, k), lay(tm, k), lay(gm, k), s))
    thu_hoi = "; ".join(_ds(rec["thu_hoi"], _SEP_DONG)) or None
    xa_cu = (str(rec["xa_cu"]).strip() or None) if rec["xa_cu"] is not None else None
    out = []
    for thua_cu, to_cu, thua_moi, to_moi, s in cap_thua:
        for t in tens:
            out.append({
                "ma_xa": rec["ma_xa"], "ten_xa": rec["ten_xa"], "nam": rec["nam"], "cap": rec["cap"],
                "stt_ho_so": rec["stt"], "ten_nguoi_su_dung": t, "thua_cu": thua_cu, "to_cu": to_cu,
                "thua_moi": thua_moi, "to_moi": to_moi, "dia_chi": _txt(rec["dia_chi"]), "so_seri_gcn": s,
                "loai_ho_so": _txt(rec["loai"]), "ngay_bien_dong": _ngay(rec["ngay"]),
                "gcn_thu_hoi": thu_hoi, "xa_cu": xa_cu,
            })
    return out


def _ds_xa() -> list[tuple[str, str, str]]:
    rows, error_response = supabase_client.call_rpc("danh_muc_kho_ds_xa", {})
    if error_response:
        raise RuntimeError("Không đọc được danh sách xã/phường")
    # Tên dài trước để tên ngắn không khớp nhầm vào 1 phần tên dài hơn.
    xs = [
        (r["ma_xa"], r["ten_xa"], khong_dau(re.sub(r"^(Phường|Xã|Thị trấn)\s+", "", r["ten_xa"] or "", flags=re.I)))
        for r in rows
    ]
    return sorted(xs, key=lambda x: -len(x[2]))


def _tim_xa(text: str, ds_xa):
    t = khong_dau(text or "")
    for ma, ten, khoa in ds_xa:
        if khoa and khoa in t:
            return ma, ten
    return None


def doc_danh_muc_goc(data: bytes) -> tuple[list[dict], list[str]]:
    """Đọc workbook danh mục gốc: mọi trang có dòng tiêu đề "STT hồ sơ" ở cột D.
    Xã lấy theo cột Địa chỉ thửa đất, không được thì theo tên trang tính."""
    ds_xa = _ds_xa()
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    rows, canh_bao = [], []
    co_trang = False
    for ws in wb.worksheets:
        xa_trang = _tim_xa(ws.title, ds_xa)
        co_tieu_de = False
        for i, r in enumerate(ws.iter_rows(values_only=True), 1):
            r = list(r) + [None] * 16
            if not co_tieu_de:
                co_tieu_de = khong_dau(str(r[3] or "")) == "stt ho so"
                co_trang = co_trang or co_tieu_de
                continue
            stt = _txt(r[3])
            if not stt:
                continue
            xa = _tim_xa(_txt(r[9]) or "", ds_xa) or xa_trang
            try:
                nam = int(float(r[1])) if r[1] is not None else None
            except (TypeError, ValueError):
                nam = None
            cap = _txt(r[2])
            if not xa or not nam or not cap:
                canh_bao.append(f"{ws.title} dòng {i}: thiếu xã/năm/cặp")
                continue
            rows += tach_ho_so({
                "ma_xa": xa[0], "ten_xa": xa[1], "nam": nam, "cap": cap, "stt": stt, "ten": r[4],
                "thua_moi": r[5], "to_moi": r[6], "thua_cu": r[7], "to_cu": r[8], "dia_chi": r[9],
                "seri": r[10], "loai": r[11], "ngay": r[13], "thu_hoi": r[14], "xa_cu": r[15],
            })
    if not co_trang:
        raise ValueError("Không tìm thấy trang tính danh mục (dòng tiêu đề có 'STT hồ sơ' ở cột D)")
    return rows, canh_bao


def ghi_kho(rows: list[dict], nguon: str):
    return supabase_client.call_rpc(
        "upsert_danh_muc_trong_kho", {"p_data": {"rows": rows}, "p_nguon_file": nguon}, timeout=300
    )


def dong_bo_google_sheet(url: str | None = None):
    url = url or Config.DANH_MUC_KHO_SHEET_URL
    m = _GOOGLE_ID.search(url or "")
    if not m:
        return None, (jsonify({"error": "Chưa cấu hình link Google Sheet danh mục (DANH_MUC_KHO_SHEET_URL)"}), 400)
    try:
        resp = requests.get(f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=xlsx", timeout=120)
        resp.raise_for_status()
        if "spreadsheetml" not in resp.headers.get("Content-Type", ""):
            raise RuntimeError("Google không trả file Excel — kiểm tra quyền chia sẻ 'Bất kỳ ai có đường liên kết'")
        rows, canh_bao = doc_danh_muc_goc(resp.content)
    except Exception as exc:  # noqa: BLE001 - lỗi tải/đọc Sheet phải báo rõ cho người gọi/lịch chạy
        current_app.logger.exception("Đồng bộ danh mục trong kho lỗi")
        return None, (jsonify({"error": f"Đồng bộ thất bại: {exc}"}), 502)
    ket_qua, error_response = ghi_kho(rows, f"Google Sheet {m.group(1)}")
    if error_response:
        return None, error_response
    return {
        "ok": True, "tong_dong_tach": len(rows), "so_canh_bao": len(canh_bao), "canh_bao": canh_bao[:50],
        **(ket_qua or {}),
    }, None
