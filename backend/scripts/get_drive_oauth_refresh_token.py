"""Chạy MỘT LẦN cục bộ để lấy Refresh Token OAuth (ủy quyền bằng chính tài
khoản Gmail cá nhân của bạn) cho việc upload PDF Nhóm 4 lên Google Drive.

TẠI SAO cần bước này: Service Account (dùng trước đây) KHÔNG có dung lượng
lưu trữ riêng trên Drive — mọi lần upload đều lỗi "storageQuotaExceeded"
dù đã share đúng folder + quyền Editor (giới hạn kiến trúc của Google,
không sửa được bằng cách share/xin thêm quyền). Giải pháp: ủy quyền OAuth
bằng CHÍNH tài khoản Gmail của bạn — Drive API sau đó ghi file THAY MẶT
bạn, tính vào dung lượng Drive thật của tài khoản đó (mua thêm qua Google
One nếu cần, rẻ hơn nhiều so với các phương án khác).

Chuẩn bị trước khi chạy (làm 1 lần trên Google Cloud Console, cùng project
đang dùng cho Service Account cũ):

  1. APIs & Services → OAuth consent screen:
     - User Type: External
     - Điền tên app / email hỗ trợ / email dev (email của bạn)
     - Scope: thêm https://www.googleapis.com/auth/drive
     - Test users: thêm chính email Gmail của bạn
     - QUAN TRỌNG: bấm "PUBLISH APP" để chuyển trạng thái sang "In
       production" — nếu để "Testing", refresh token hết hạn sau 7 ngày
       và phải làm lại bước này mỗi tuần. Khi đăng nhập sẽ thấy cảnh báo
       "Google chưa xác minh ứng dụng này" — bấm "Advanced" (Nâng cao) →
       "Đi tới <tên app> (không an toàn)" — vẫn dùng bình thường, cảnh báo
       này chỉ vì app chưa qua review chính thức của Google (không cần
       thiết cho ứng dụng nội bộ 1 người dùng).

  2. APIs & Services → Credentials → Create Credentials → OAuth client ID
     → Application type: **Desktop app** → Create → copy Client ID +
     Client secret.

  3. Dán 2 giá trị đó vào backend/.env:
       GOOGLE_OAUTH_CLIENT_ID=...
       GOOGLE_OAUTH_CLIENT_SECRET=...

Cách chạy:
    cd backend
    python scripts/get_drive_oauth_refresh_token.py

Script tự mở trình duyệt để bạn đăng nhập + đồng ý cấp quyền, sau đó in ra
GOOGLE_OAUTH_REFRESH_TOKEN — dán nốt giá trị đó vào backend/.env (local) và
biến môi trường trên Render (production). GOOGLE_DRIVE_ROOT_FOLDER_ID có
thể giữ nguyên nếu đang dùng, hoặc tạo folder mới bình thường trên Drive
của chính bạn (giờ chạy dưới quyền tài khoản thật, không cần share cho ai).
"""

from __future__ import annotations

import os
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

SCOPE = "https://www.googleapis.com/auth/drive"
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
PORT = 8765
REDIRECT_URI = f"http://localhost:{PORT}/"

_received_code: dict[str, str] = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - tên do http.server quy định
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        error = params.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if code:
            _received_code["code"] = code
            self.wfile.write("<h2>Đã nhận quyền — đóng tab này và quay lại terminal.</h2>".encode("utf-8"))
        else:
            self.wfile.write(f"<h2>Lỗi: {error}</h2>".encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - im lặng log HTTP mặc định
        pass


def main() -> None:
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("Thiếu GOOGLE_OAUTH_CLIENT_ID/GOOGLE_OAUTH_CLIENT_SECRET trong backend/.env — xem hướng dẫn ở đầu file.")
        return

    auth_url = AUTH_ENDPOINT + "?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    })

    server = HTTPServer(("localhost", PORT), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print("Đang mở trình duyệt để đăng nhập + cấp quyền Google Drive...")
    print(f"Nếu không tự mở, dán URL này vào trình duyệt:\n{auth_url}\n")
    webbrowser.open(auth_url)

    thread.join(timeout=300)
    code = _received_code.get("code")
    if not code:
        print("Không nhận được mã ủy quyền (hết thời gian chờ hoặc bạn từ chối cấp quyền).")
        return

    response = requests.post(
        TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    response.raise_for_status()
    tokens = response.json()

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print(
            "Không nhận được refresh_token — Google chỉ cấp refresh_token lần ĐẦU cấp "
            "quyền cho 1 app. Vào https://myaccount.google.com/permissions, gỡ quyền "
            "app này, rồi chạy lại script."
        )
        print(f"Phản hồi đầy đủ: {tokens}")
        return

    print("\nThành công — dán dòng sau vào backend/.env (local) và biến môi trường Render (production):")
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN={refresh_token}")


if __name__ == "__main__":
    main()
