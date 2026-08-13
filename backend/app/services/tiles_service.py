from __future__ import annotations

import requests
from flask import current_app


class TileFetchError(Exception):
    """Lỗi khi lấy tile từ Vietbando — payload/status sẵn sàng để route
    trả thẳng ra jsonify(payload), status."""

    def __init__(self, payload: dict, status: int):
        super().__init__(payload.get("error"))
        self.payload = payload
        self.status = status


def fetch_tile(z: int, x: int, y: int) -> tuple[bytes, str]:
    tile_url = current_app.config["VIETBANDO_TILE_URL"].format(z=z, x=x, y=y)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*,*/*;q=0.8",
    }

    referer = current_app.config.get("VIETBANDO_REFERER", "")
    if referer:
        headers["Referer"] = referer

    try:
        current_app.logger.info("Đang gọi Vietbando: %s", tile_url)

        upstream = requests.get(
            tile_url,
            headers=headers,
            timeout=(10, 30),
            allow_redirects=True,
        )
    except requests.Timeout as exc:
        current_app.logger.exception("Vietbando timeout: %s", tile_url)
        raise TileFetchError({"error": "Máy chủ Vietbando phản hồi quá lâu"}, 504) from exc
    except requests.RequestException as exc:
        current_app.logger.exception("Không kết nối được Vietbando: %s", exc)
        raise TileFetchError(
            {"error": "Không kết nối được máy chủ Vietbando", "detail": str(exc)}, 502
        ) from exc

    content_type = upstream.headers.get("Content-Type", "")

    current_app.logger.info(
        "Vietbando status=%s, content-type=%s, bytes=%s, final-url=%s",
        upstream.status_code,
        content_type,
        len(upstream.content),
        upstream.url,
    )

    if upstream.status_code != 200:
        body_preview = "" if content_type.lower().startswith("image/") else upstream.text[:500]

        current_app.logger.error(
            "Vietbando trả lỗi: status=%s, body=%s", upstream.status_code, body_preview
        )

        raise TileFetchError(
            {
                "error": "Vietbando trả về mã lỗi",
                "upstream_status": upstream.status_code,
                "content_type": content_type,
                "final_url": upstream.url,
                "body": body_preview,
            },
            502,
        )

    if not content_type.lower().startswith("image/"):
        body_preview = upstream.text[:500]

        current_app.logger.error(
            "Vietbando không trả ảnh: content-type=%s, body=%s", content_type, body_preview
        )

        raise TileFetchError(
            {
                "error": "Vietbando không trả dữ liệu ảnh",
                "content_type": content_type,
                "body": body_preview,
            },
            502,
        )

    return upstream.content, content_type
