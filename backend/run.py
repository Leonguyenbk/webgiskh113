from werkzeug.serving import WSGIRequestHandler

from app import create_app
from app.config import Config

app = create_app()


class RealIpRequestHandler(WSGIRequestHandler):
    """Ghi IP thật của người dùng vào access log thay vì 127.0.0.1. Mọi
    request tới server này đều đi qua Cloudflare Tunnel chạy trên cùng
    máy (cloudflared nối vào localhost), nên socket TCP luôn thấy
    127.0.0.1 — IP thật nằm trong header CF-Connecting-IP mà Cloudflare
    tự gắn ở edge (client không tự đặt/giả mạo được header này)."""

    def address_string(self) -> str:
        return self.headers.get("CF-Connecting-IP") or super().address_string()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=Config.PORT,
        debug=Config.FLASK_DEBUG,
        request_handler=RealIpRequestHandler,
    )
