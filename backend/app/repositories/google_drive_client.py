from __future__ import annotations

import json
import os

import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials

# Upload PDF hồ sơ quét lên Google Drive bằng Service Account — dùng lại
# GOOGLE_SERVICE_ACCOUNT_JSON đã có (xem backend/gcn_sync.py), nhưng với
# scope drive.file riêng (không dùng chung Credentials với gcn_sync vì
# khác scope).
#
# Folder gốc (GOOGLE_DRIVE_ROOT_FOLDER_ID) có 2 cách hợp lệ để chuẩn bị:
# 1) Tự tạo bằng scripts/create_drive_root_folder.py (service account là
#    chủ sở hữu), HOẶC
# 2) Dùng folder có sẵn của người dùng (VD "HSQ 2959" đã tạo tay), miễn
#    là SHARE folder đó cho email service account (lấy từ trường
#    "client_email" trong GOOGLE_SERVICE_ACCOUNT_JSON) với quyền Editor —
#    scope drive.file vẫn thấy/ghi được các file share trực tiếp cho nó,
#    không chỉ file tự tạo. Không cần đổi sang scope "drive" rộng hơn.
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"

_session: AuthorizedSession | None = None
_folder_cache: dict[str, str] = {}


def _get_session() -> AuthorizedSession:
    global _session
    if _session is None:
        raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not raw:
            raise RuntimeError(
                "Thiếu GOOGLE_SERVICE_ACCOUNT_JSON trong backend/.env (nội dung "
                "file service_account.json, dán nguyên văn thành 1 dòng)"
            )
        try:
            info = json.loads(raw)
        except ValueError as exc:
            raise RuntimeError(
                f"GOOGLE_SERVICE_ACCOUNT_JSON không phải JSON hợp lệ: {exc}"
            ) from exc

        creds = Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)
        _session = AuthorizedSession(creds)
    return _session


def _get_root_folder_id() -> str:
    root_id = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "").strip()
    if not root_id:
        raise RuntimeError(
            "Thiếu GOOGLE_DRIVE_ROOT_FOLDER_ID trong backend/.env — chạy "
            "backend/scripts/create_drive_root_folder.py một lần để tạo "
            "folder gốc rồi dán ID vào biến này."
        )
    return root_id


def _find_folder_by_ma_xa(session: AuthorizedSession, parent_id: str, ma_xa: str) -> str | None:
    # Dùng "contains" (không phải "=") vì folder có sẵn của người dùng đặt
    # tên kiểu "Xã Yang Mao - 24484" (tên xã + mã xã), không phải chỉ mã xã
    # trần — khớp theo mã xã là đủ, không cần biết đúng tên xã ghi trước đó.
    escaped_ma_xa = ma_xa.replace("'", "\\'")
    query = (
        f"'{parent_id}' in parents and name contains '{escaped_ma_xa}' "
        "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    try:
        response = session.get(
            f"{DRIVE_API_BASE}/files",
            params={"q": query, "fields": "files(id,name)", "pageSize": 5},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Tìm thư mục Google Drive theo mã xã thất bại: {exc}") from exc
    files = response.json().get("files") or []
    return files[0]["id"] if files else None


def _create_folder(session: AuthorizedSession, parent_id: str, name: str) -> str:
    try:
        response = session.post(
            f"{DRIVE_API_BASE}/files",
            params={"fields": "id"},
            json={
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Tạo thư mục Google Drive thất bại: {exc}") from exc
    return response.json()["id"]


def resolve_xa_folder(ma_xa: str, ten_xa: str | None = None) -> str:
    """Tìm (hoặc tạo mới) subfolder theo mã xã dưới folder gốc. Cache
    trong tiến trình để đỡ gọi Drive API lặp lại — chấp nhận mất cache khi
    Render restart, không ảnh hưởng tính đúng vì vẫn tìm-hoặc-tạo lại.

    ten_xa (tùy chọn): chỉ dùng để đặt tên khi phải TẠO MỚI folder (xã
    chưa có sẵn) — khớp đúng quy ước đặt tên "Xã <tên xã> - <mã xã>" đã
    dùng cho các folder có sẵn, để không tạo folder trùng mục đích nhưng
    khác cách đặt tên."""
    if ma_xa in _folder_cache:
        return _folder_cache[ma_xa]

    session = _get_session()
    root_id = _get_root_folder_id()

    folder_id = _find_folder_by_ma_xa(session, root_id, ma_xa)
    if not folder_id:
        folder_name = f"{ten_xa} - {ma_xa}" if ten_xa else ma_xa
        folder_id = _create_folder(session, root_id, folder_name)

    _folder_cache[ma_xa] = folder_id
    return folder_id


def upload_pdf(folder_id: str, filename: str, content: bytes) -> dict:
    """Upload 1 file PDF lên Drive, trả {"id": ..., "name": ...}."""
    session = _get_session()

    metadata = {"name": filename, "parents": [folder_id]}
    boundary = "nhom4-upload-boundary"
    body = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        "Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--".encode("utf-8")

    try:
        response = session.post(
            f"{DRIVE_UPLOAD_BASE}/files",
            params={"uploadType": "multipart", "fields": "id,name"},
            headers={"Content-Type": f"multipart/related; boundary={boundary}"},
            data=body,
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Upload file lên Google Drive thất bại: {exc}") from exc

    return response.json()
