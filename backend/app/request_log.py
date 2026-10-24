from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

from flask import Flask, g, request

# Log từng lượt nộp biểu Nhóm 4 (thời gian xử lý, dung lượng, xã, lý do
# lỗi 4xx) — trước đây access log không có thời gian nên không phân biệt
# được "nộp chậm" do máy chủ hay do đường truyền. Thời gian ĐẦU-CUỐI (gồm
# cả lúc tải file lên) đo ở proxy vite preview, xem frontend/vite.config.js.
SUBMIT_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "nhom4_submit.log"
SUBMIT_PATH = "/api/nhom4/ho-so"

_access_logger = logging.getLogger("webgis.access")
_submit_logger = logging.getLogger("webgis.nhom4_submit")


def _client_ip() -> str:
    # Mọi request tới qua Cloudflare Tunnel trên cùng máy — IP thật nằm
    # trong CF-Connecting-IP (giống RealIpRequestHandler ở run.py).
    return request.headers.get("CF-Connecting-IP") or request.remote_addr or "-"


def _setup_loggers(access_log: bool) -> None:
    if access_log and not _access_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(message)s"))
        _access_logger.addHandler(handler)
        _access_logger.setLevel(logging.INFO)
        _access_logger.propagate = False

    if not _submit_logger.handlers:
        SUBMIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(SUBMIT_LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        _submit_logger.addHandler(handler)
        _submit_logger.setLevel(logging.INFO)
        _submit_logger.propagate = False


def _submit_info(response) -> dict:
    info = {
        "luc": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ip": _client_ip(),
        "status": response.status_code,
        "xu_ly_ms": round((time.perf_counter() - g.request_started) * 1000),
        "bytes": request.content_length,
    }
    try:
        payload = json.loads(request.form.get("payload") or "{}")
        info["ma_xa"] = payload.get("ma_xa")
        info["so_thua"] = len(payload.get("thua_list") or [])
        info["dung_chung"] = bool(payload.get("dung_chung_ho_so_quet"))
    except (ValueError, AttributeError):
        pass
    if response.status_code >= 400:
        try:
            info["loi"] = (response.get_json(silent=True) or {}).get("error")
        except Exception:
            pass
    return info


def init_request_log(app: Flask, access_log: bool = False) -> None:
    """access_log=True khi chạy bằng waitress (không tự ghi access log như
    Werkzeug) — ghi đúng định dạng dòng log Werkzeug cũ, thêm thời gian xử
    lý ở cuối, để các phép thống kê log cũ vẫn dùng được."""
    _setup_loggers(access_log)

    @app.before_request
    def _start_timer():
        g.request_started = time.perf_counter()

    @app.after_request
    def _log_request(response):
        started = g.get("request_started")
        if started is None:
            return response
        if access_log:
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            path = request.full_path if request.query_string else request.path
            _access_logger.info(
                '%s - - [%s] "%s %s %s" %s - %sms',
                _client_ip(),
                time.strftime("%d/%b/%Y %H:%M:%S"),
                request.method,
                path,
                request.environ.get("SERVER_PROTOCOL", "HTTP/1.1"),
                response.status_code,
                elapsed_ms,
            )
        if request.method == "POST" and request.path == SUBMIT_PATH:
            try:
                _submit_logger.info(json.dumps(_submit_info(response), ensure_ascii=False))
            except Exception:
                app.logger.exception("Ghi log nộp Nhóm 4 thất bại")
        return response
