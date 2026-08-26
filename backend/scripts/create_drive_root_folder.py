"""Chạy MỘT LẦN cục bộ để tạo folder gốc trên Google Drive cho biểu Nhóm 4.

LƯU Ý: từ khi backend chuyển sang OAuth (ủy quyền bằng tài khoản Gmail cá
nhân — xem get_drive_oauth_refresh_token.py), script này KHÔNG còn bắt
buộc — bạn có thể tự tạo 1 folder bình thường trên Drive của chính mình,
copy ID từ URL rồi dán vào GOOGLE_DRIVE_ROOT_FOLDER_ID. Script này vẫn
chạy được (tiện nếu muốn tạo bằng lệnh thay vì tay) vì cũng gọi chung
_get_session() đã dùng OAuth.

Cách dùng:
    cd backend
    python -m dotenv run python scripts/create_drive_root_folder.py
    (hoặc: chạy trực tiếp nếu backend/.env đã có GOOGLE_SERVICE_ACCOUNT_JSON,
    script tự load .env)

Script in ra folder ID — dán vào GOOGLE_DRIVE_ROOT_FOLDER_ID trong
backend/.env (local) và trên Render (production). Nếu muốn tự xem folder
này qua "Shared with me" trên Google Drive của bạn, sửa ADMIN_EMAIL bên
dưới trước khi chạy.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.repositories import google_drive_client  # noqa: E402

ROOT_FOLDER_NAME = "Biểu mẫu Nhóm 4 - Hồ sơ quét"
ADMIN_EMAIL = ""  # điền email Gmail của bạn để tự share folder gốc về xem


def main() -> None:
    session = google_drive_client._get_session()  # noqa: SLF001 - script nội bộ, chấp nhận gọi hàm private

    response = session.post(
        f"{google_drive_client.DRIVE_API_BASE}/files",
        params={"fields": "id"},
        json={"name": ROOT_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
        timeout=15,
    )
    response.raise_for_status()
    folder_id = response.json()["id"]

    print(f"Đã tạo folder gốc: {ROOT_FOLDER_NAME}")
    print(f"GOOGLE_DRIVE_ROOT_FOLDER_ID={folder_id}")

    if ADMIN_EMAIL:
        share_response = session.post(
            f"{google_drive_client.DRIVE_API_BASE}/files/{folder_id}/permissions",
            json={"type": "user", "role": "reader", "emailAddress": ADMIN_EMAIL},
            timeout=15,
        )
        share_response.raise_for_status()
        print(f"Đã share (xem) folder cho {ADMIN_EMAIL} — kiểm tra mục 'Shared with me' trên Drive.")
    else:
        print("Chưa điền ADMIN_EMAIL trong script nên chưa share folder cho ai xem.")


if __name__ == "__main__":
    main()
