import sys

from werkzeug.serving import WSGIRequestHandler

from app import create_app
from app.config import Config
from app.request_log import init_request_log

app = create_app()

# Mặc định chạy bằng waitress (server WSGI dùng thật trên Windows): nhận
# trọn body request (file PDF Nhóm 4) TRƯỚC khi giao cho thread xử lý, nên
# lượt nộp tải lên chậm không giữ chỗ thread, không làm nghẽn người khác
# như dev server Werkzeug. `python run.py --werkzeug` để quay về dev
# server cũ (dự phòng khi waitress lỗi).
USE_WERKZEUG = "--werkzeug" in sys.argv or Config.FLASK_DEBUG


def _arg_int(name: str, default: int) -> int:
    """Đọc `--port 5001` / `--threads 12` từ dòng lệnh — để chạy thêm 1
    tiến trình RIÊNG cho nhập biểu Nhóm 4 (service WebGIS-Backend-Nhom4,
    port 5001) cùng code, không tranh luồng với bản đồ ở port 5000."""
    if name in sys.argv:
        try:
            return int(sys.argv[sys.argv.index(name) + 1])
        except (IndexError, ValueError):
            pass
    return default


PORT = _arg_int("--port", Config.PORT)
THREADS = _arg_int("--threads", 24)


class RealIpRequestHandler(WSGIRequestHandler):
    """Ghi IP thật của người dùng vào access log thay vì 127.0.0.1. Mọi
    request tới server này đều đi qua Cloudflare Tunnel chạy trên cùng
    máy (cloudflared nối vào localhost), nên socket TCP luôn thấy
    127.0.0.1 — IP thật nằm trong header CF-Connecting-IP mà Cloudflare
    tự gắn ở edge (client không tự đặt/giả mạo được header này)."""

    def address_string(self) -> str:
        return self.headers.get("CF-Connecting-IP") or super().address_string()


if __name__ == "__main__":
    init_request_log(app, access_log=not USE_WERKZEUG)
    if USE_WERKZEUG:
        app.run(
            host="0.0.0.0",
            port=PORT,
            debug=Config.FLASK_DEBUG,
            request_handler=RealIpRequestHandler,
        )
    else:
        from waitress import serve

        print(f"waitress: http://0.0.0.0:{PORT} threads={THREADS}", file=sys.stderr, flush=True)
        serve(
            app,
            host="0.0.0.0",
            port=PORT,
            threads=THREADS,
            connection_limit=500,
            channel_timeout=300,
            asyncore_use_poll=True,
            ident="webgis",
        )
