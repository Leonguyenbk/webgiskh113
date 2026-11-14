# Đồng bộ TUẦN TỰ mọi nguồn Google Sheet đang kích hoạt (nguon_gcn.kich_hoat)
# vào du_lieu_gcn — chạy NGAY TRÊN MÁY CHỦ (Task Scheduler, xem
# register_sync_gcn_sheets_task.ps1), thay cho lịch GitHub Actions
# (.github/workflows/sync-gcn.yml): lịch "2 giờ/lần" của GitHub thực tế bị
# giãn ra 6–9 giờ/lần nên số liệu xã nhập trong ngày không lên kịp
# (VD Cuôr Đăng 14/11/2026: sheet có thêm ~870 thửa nhưng máy chủ vẫn giữ
# bản 07h sáng).
#
# Gọi thẳng gcn_sync.sync_source (cùng hàm mà POST /api/nguon-gcn/<ma>/sync
# dùng) nên không chiếm thread của waitress. Một nguồn lỗi (sai URL, chưa
# share, sai tên trang tính...) chỉ ghi log rồi chạy tiếp nguồn sau.
#
# Chạy: cd backend && .venv\Scripts\python.exe scripts\sync_gcn_sheets.py
import os
import sys
import time
from datetime import datetime

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from app import create_app  # noqa: E402
from app.repositories.supabase_client import _CursorCtx  # noqa: E402
import gcn_sync  # noqa: E402


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def main() -> int:
    app = create_app()
    app.app_context().push()
    with _CursorCtx() as cur:
        cur.execute(
            "select ma_nguon, coalesce(ten_nguon, '') ten_nguon, url from nguon_gcn "
            "where kich_hoat and coalesce(url, '') <> '' order by ma_nguon"
        )
        sources = cur.fetchall()

    t0 = time.monotonic()
    ok, loi = 0, []
    log(f"Bắt đầu đồng bộ {len(sources)} nguồn Google Sheet")
    for s in sources:
        t = time.monotonic()
        try:
            n = gcn_sync.sync_source(s["ma_nguon"], s["ten_nguon"], s["url"])
            ok += 1
            log(f"  OK  {s['ma_nguon']} {s['ten_nguon']}: {n} dòng ({time.monotonic() - t:.1f}s)")
        except Exception as exc:  # noqa: BLE001 - lỗi 1 nguồn không được chặn các nguồn sau
            loi.append(s["ma_nguon"])
            log(f"  LỖI {s['ma_nguon']} {s['ten_nguon']}: {str(exc)[:300]}")
        # Giãn nhẹ giữa các nguồn cho khỏi chạm hạn mức đọc của Google Sheets API.
        time.sleep(1)
    log(f"Xong: {ok} OK, {len(loi)} lỗi {loi if loi else ''} — {time.monotonic() - t0:.0f}s")
    return 0 if not loi else 1


if __name__ == "__main__":
    sys.exit(main())
