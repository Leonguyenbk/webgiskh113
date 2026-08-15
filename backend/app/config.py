from __future__ import annotations

import os

from dotenv import load_dotenv

# Phải gọi TRƯỚC khi đọc os.getenv() bên dưới — bản gốc app.py gọi
# load_dotenv() ngay đầu file vì lý do tương tự. Không có dòng này, các
# biến trong backend/.env (SUPABASE_URL...) sẽ không được nạp khi chạy
# local (`python run.py`); trên Render biến môi trường đã có sẵn nên
# load_dotenv() không tìm thấy file .env và không làm gì (an toàn).
load_dotenv()


class Config:
    """Đọc toàn bộ biến môi trường dùng trong backend — tập trung một chỗ
    thay vì os.getenv() rải rác khắp routes/services. Không ép buộc giá trị
    phải có sẵn ở đây: các endpoint cần Supabase/Google vẫn tự báo lỗi rõ
    ràng lúc gọi (giữ đúng hành vi cũ của app.py), để backend khởi động
    được kể cả khi thiếu vài biến chưa cần dùng trong lần chạy đó.
    """

    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    FRONTEND_URL = os.getenv("FRONTEND_URL", "*")
    IMPORT_TOKEN = os.getenv("IMPORT_TOKEN", "")

    GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    GOOGLE_DRIVE_ROOT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "")

    PORT = int(os.getenv("PORT", "5000"))
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    RENDER_ENV = os.getenv("RENDER", "local")

    @property
    def allowed_origins(self):
        if self.FRONTEND_URL == "*":
            return "*"
        return [origin.strip() for origin in self.FRONTEND_URL.split(",") if origin.strip()]
