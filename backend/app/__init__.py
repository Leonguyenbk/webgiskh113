from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import cors


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    cors.init_app(app, resources={r"/api/*": {"origins": Config().allowed_origins}})

    _register_blueprints(app)
    _register_error_handlers(app)

    return app


def _register_blueprints(app: Flask) -> None:
    from .routes.admin_routes import admin_bp
    from .routes.ban_do_nen_routes import ban_do_nen_bp
    from .routes.gcn_routes import gcn_bp
    from .routes.health_routes import health_bp
    from .routes.mplis_routes import mplis_bp
    from .routes.nhom4_routes import nhom4_bp
    from .routes.parcel_routes import parcel_bp
    from .routes.ranh_thon_routes import ranh_thon_bp

    for blueprint in (
        health_bp, parcel_bp, gcn_bp, admin_bp, mplis_bp, nhom4_bp, ranh_thon_bp, ban_do_nen_bp,
    ):
        app.register_blueprint(blueprint)


def _register_error_handlers(app: Flask) -> None:
    # Lưới an toàn cho lỗi KHÔNG được route/service nào tự bắt và trả JSON
    # gọn (mọi trường hợp đã lường trước — thiếu tham số, Supabase lỗi...
    # vẫn tự trả (jsonify(...), status) như trước, không đi qua đây). Bỏ
    # qua HTTPException (404 route lạ, 405 sai method...) để giữ đúng hành
    # vi mặc định của Flask cho các lỗi đó — chỉ nuốt exception Python
    # thường (bug/lỗi chưa lường trước), tránh lộ stack trace ra frontend.
    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        if isinstance(exc, HTTPException):
            return exc
        app.logger.exception("Lỗi không xác định: %s", exc)
        return jsonify({"error": "Có lỗi không xác định ở server."}), 500
