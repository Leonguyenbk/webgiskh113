from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import google_sheets
import supabase_sync

# Nguồn "biểu Nhóm 4" (backend ghi thẳng, madvhc từ form đã kiểm) không
# đi qua đây. Mọi nguồn Sheet: ma_nguon = mã xã chuẩn (bảng nguon_gcn).
FORM_MA_NGUON = "NHOM4_FORM"


@dataclass
class SheetSource:
    ma_nguon: str
    ten_nguon: str
    url: str


def load_sources() -> list[SheetSource]:
    """Đọc danh sách nguồn đang kích hoạt từ bảng public.nguon_gcn.

    Nguồn được quản lý qua trang "Nhập đường link" trên WebGIS (không
    còn đọc từ file Excel local). ma_nguon là primary key của bảng nên
    Postgres tự đảm bảo duy nhất — không cần kiểm tra trùng ở đây.
    """
    rows = supabase_sync.list_active_sources()
    return [
        SheetSource(
            ma_nguon=str(row["ma_nguon"]),
            ten_nguon=str(row.get("ten_nguon") or ""),
            url=str(row.get("url") or ""),
        )
        for row in rows
        if row.get("url")
    ]


def sync_source(source: SheetSource) -> int:
    # 1) Đọc toàn bộ Google Sheet trước — nếu lỗi ở đây thì dừng lại
    #    ngay, chưa hề đụng tới Supabase.
    records = google_sheets.read_sheet_rows(source.url)

    # 2) Chuẩn hóa thành records hoàn chỉnh.
    synced_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for record in records:
        row = dict(record)
        dong_sheet = row.pop("_dong_sheet")
        row["ma_nguon"] = source.ma_nguon
        row["ten_nguon"] = source.ten_nguon
        row["sheet_url"] = source.url
        row["dong_sheet"] = dong_sheet
        row["synced_at"] = synced_at
        # madvhc (cột B của Sheet) hay bị gõ sai -> khóa generated
        # madvhc_soto_sothua lệch. Ép madvhc = ma_nguon (mã xã chuẩn).
        if source.ma_nguon != FORM_MA_NGUON:
            row["madvhc"] = source.ma_nguon
        rows.append(row)

    # 3) Chỉ xóa + ghi Supabase sau khi (1) và (2) đã xong an toàn.
    return supabase_sync.replace_source(source.ma_nguon, rows)


def main() -> None:
    sources = load_sources()
    if not sources:
        print("Không có nguồn nào kích hoạt trong bảng nguon_gcn (xem trang \"Nhập đường link\")")
        return

    results: list[tuple[SheetSource, bool, int, str]] = []

    for source in sources:
        try:
            count = sync_source(source)
        except Exception as exc:  # noqa: BLE001 - lỗi 1 nguồn không được chặn các nguồn khác
            message = f"{type(exc).__name__}: {exc}"
            results.append((source, False, 0, message))
            print(f"[{source.ma_nguon}] {source.ten_nguon}: ERROR - {message}")
        else:
            results.append((source, True, count, ""))
            print(f"[{source.ma_nguon}] {source.ten_nguon}: OK - {count:,} dòng".replace(",", "."))

    ok = [r for r in results if r[1]]
    errors = [r for r in results if not r[1]]
    total_rows = sum(r[2] for r in ok)

    print()
    print("===== Tổng kết =====")
    print(f"Tổng nguồn  : {len(results)}")
    print(f"Thành công  : {len(ok)}")
    print(f"Lỗi         : {len(errors)}")
    print(f"Tổng bản ghi: {total_rows:,}".replace(",", "."))
    if errors:
        print("Nguồn lỗi:")
        for source, _, _, message in errors:
            print(f"  - [{source.ma_nguon}] {source.ten_nguon}: {message}")


if __name__ == "__main__":
    main()
