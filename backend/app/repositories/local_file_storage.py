from __future__ import annotations

import re
from pathlib import Path

# Hồ sơ quét PDF biểu Nhóm 4 — trước đây upload lên Google Drive (OAuth cá
# nhân, hay hết hạn token/tốn quota), giờ lưu thẳng trên đĩa máy chủ. Giữ
# đúng chữ ký resolve_xa_folder()/upload_pdf() như google_drive_client.py cũ
# để nhom4_service.py chỉ đổi tên module import, không đổi logic gọi.
SCANS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "nhom4_scans"

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_. \-]+")


def _safe_name(name: str) -> str:
    return _SAFE_NAME_RE.sub("_", name).strip("_") or "file"


def resolve_xa_folder(ma_xa: str, ten_xa: str | None = None) -> str:  # noqa: ARG001 - giữ chữ ký cũ
    """Thư mục lưu file của 1 xã — dùng thẳng mã xã (đã kiểm tra hợp lệ ở
    validate_payload), không cần "tìm hoặc tạo" như Drive."""
    return _safe_name(ma_xa)


def upload_pdf(folder_id: str, filename: str, content: bytes) -> dict:
    """Lưu 1 file PDF vào đĩa, trả {"id": "<ma_xa>/<tên file lưu>", "name": tên gốc}
    — "id" dùng làm giá trị cột file_*_drive_id (giờ là đường dẫn tương đối,
    không phải Drive ID thật) để backend/route serve lại đúng file."""
    safe_filename = _safe_name(filename)
    target_dir = SCANS_DIR / folder_id
    target_dir.mkdir(parents=True, exist_ok=True)

    path = target_dir / safe_filename
    if path.exists():
        stem, dot, ext = safe_filename.rpartition(".")
        for i in range(2, 1000):
            candidate = f"{stem}_{i}.{ext}" if dot else f"{safe_filename}_{i}"
            path = target_dir / candidate
            if not path.exists():
                safe_filename = candidate
                break

    path.write_bytes(content)
    return {"id": f"{folder_id}/{safe_filename}", "name": filename}
