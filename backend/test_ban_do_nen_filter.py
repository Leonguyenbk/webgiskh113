"""Test trực tiếp (không mock) cho route GET /api/ban-do-nen sau khi sửa:
1. Không có filter -> trả items=[] (KHÔNG tải toàn bộ danh sách, trước đây
   bug gửi "eq.eq.X" khiến lọc không khớp gì + không bắt buộc filter nên
   luôn tải hết — bảng ban_do_nen thật có 9973 dòng).
2. Có ma_xa/so_to -> khớp CHỨA CHUỖI (ILIKE), không cần đúng tuyệt đối.
3. Kết hợp ma_xa + so_to + trang_thai cùng lúc.

Chạy trực tiếp bằng python, dùng Flask test_client() + DATABASE_URL thật
trong backend/.env (không mock DB)."""

from __future__ import annotations

import sys

from app import create_app

_FAILS: list[str] = []


def _check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}  {detail}")
        _FAILS.append(name)


def main() -> int:
    app = create_app()
    client = app.test_client()

    # --- 1. Không filter -> items rỗng, KHÔNG tải hết 9973 dòng ---
    resp = client.get("/api/ban-do-nen")
    _check("không filter -> status 200", resp.status_code == 200, str(resp.status_code))
    data = resp.get_json()
    _check("không filter -> items rỗng (không tải toàn bộ danh sách)", data.get("items") == [], str(data))

    # --- 2. Lọc ma_xa chứa chuỗi (không cần đúng tuyệt đối) ---
    resp = client.get("/api/ban-do-nen", query_string={"ma_xa": "2201"})
    data = resp.get_json()
    items = data.get("items") or []
    _check("lọc ma_xa='2201' (chuỗi con) -> có kết quả", len(items) > 0, str(len(items)))
    _check(
        "mọi dòng trả về đều có ma_xa chứa '2201'",
        all("2201" in it["ma_xa"] for it in items),
        str({it["ma_xa"] for it in items}),
    )

    # --- 3. Lọc so_to chứa chuỗi '1001' trong mã xã 22015 (biết có nhiều
    #     so_to như 1001, 10010, 10011...100015 đều chứa '1001') ---
    resp = client.get("/api/ban-do-nen", query_string={"ma_xa": "22015", "so_to": "1001"})
    data = resp.get_json()
    items = data.get("items") or []
    _check("lọc ma_xa='22015' + so_to='1001' -> có nhiều kết quả (chuỗi con)", len(items) >= 5, str(len(items)))
    _check(
        "mọi dòng đều có so_to chứa '1001'",
        all("1001" in it["so_to"] for it in items),
        str({it["so_to"] for it in items}),
    )
    _check(
        "khớp đúng các so_to mong đợi (1001, 10010..10015)",
        {it["so_to"] for it in items} >= {"1001", "10010", "10011", "10012", "10013", "10014", "10015"},
        str({it["so_to"] for it in items}),
    )

    # --- 4. Lọc exact không tồn tại -> rỗng, không lỗi ---
    resp = client.get("/api/ban-do-nen", query_string={"ma_xa": "khong-ton-tai-xxxx"})
    data = resp.get_json()
    _check("lọc ma_xa không khớp gì -> items rỗng, không lỗi", data.get("items") == [], str(data))

    # --- 5. Kết hợp thêm trang_thai (exact match) ---
    resp = client.get("/api/ban-do-nen", query_string={"ma_xa": "22015", "trang_thai": "ready"})
    data = resp.get_json()
    items = data.get("items") or []
    _check("kết hợp ma_xa + trang_thai=ready -> có kết quả, đúng trạng thái", len(items) > 0 and all(it["trang_thai"] == "ready" for it in items), str(len(items)))

    resp = client.get("/api/ban-do-nen", query_string={"ma_xa": "22015", "trang_thai": "error"})
    data = resp.get_json()
    items = data.get("items") or []
    _check("kết hợp ma_xa + trang_thai=error -> không có dòng nào trạng thái khác 'error'", all(it["trang_thai"] == "error" for it in items), str(items))

    print()
    if _FAILS:
        print(f"{len(_FAILS)} CA FAIL: {_FAILS}")
        return 1
    print("TẤT CẢ PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
