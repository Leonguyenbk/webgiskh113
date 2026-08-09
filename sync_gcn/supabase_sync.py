from __future__ import annotations

from typing import Any

from supabase import Client, create_client

from config import BATCH_SIZE, SUPABASE_SERVICE_KEY, SUPABASE_URL, TABLE_NAME

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def replace_source(ma_nguon: str, rows: list[dict[str, Any]]) -> int:
    """Xóa dữ liệu cũ của một nguồn rồi insert dữ liệu mới theo batch.

    CHỈ gọi hàm này sau khi đã đọc + chuẩn hóa xong toàn bộ Google Sheet
    của nguồn đó — không được xóa trước khi chắc chắn đọc thành công.

    Đây không phải một transaction thật sự: nếu insert lỗi giữa chừng
    (ví dụ mất mạng ở batch thứ 5/10), dữ liệu của nguồn này có thể chỉ
    còn một phần. Lần chạy sync kế tiếp cho nguồn đó sẽ xóa sạch và ghi
    lại từ đầu nên sẽ tự sửa, nhưng khoảng thời gian ở giữa dữ liệu có
    thể thiếu. Không ảnh hưởng các nguồn khác.
    """
    client = get_client()

    client.table(TABLE_NAME).delete().eq("ma_nguon", ma_nguon).execute()

    inserted = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        client.table(TABLE_NAME).insert(batch).execute()
        inserted += len(batch)

    return inserted
