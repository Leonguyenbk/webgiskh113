"""Tô màu ranh thôn theo xã bằng 4 màu (định lý 4 màu).

Mỗi xã có ranh thôn nhận 1 chỉ số màu 0..3 sao cho 2 xã giáp nhau (xem
public.ranh_xa_ke_nhau trong supabase/schema.sql) không trùng màu. Mã màu
thật nằm ở frontend (RANH_XA_COLORS, utils/constants.js).

Ưu tiên GIỮ màu cũ của từng xã: cán bộ xã đã quen "xã mình màu cam" thì
nhập thêm ranh xã bên cạnh không làm đổi màu xã mình, trừ khi bắt buộc.
"""
from __future__ import annotations

SO_MAU = 4


def to_mau(ke: dict[str, set[str]], mau_cu: dict[str, int | None]) -> dict[str, int]:
    """Backtracking kiểu DSatur, thử màu cũ trước rồi màu ít dùng nhất.

    Đồ thị kề của các xã là đồ thị phẳng nên luôn tô được bằng 4 màu; nếu
    dữ liệu ranh lệch khiến đồ thị không phẳng (hiếm) mà không tô nổi thì
    hạ dần ràng buộc: cho phép trùng màu ở cặp ít cạnh nhất (vẫn trả kết quả).
    """
    nodes = sorted(ke)
    for n in nodes:
        ke[n] = {m for m in ke[n] if m in ke and m != n}
    for n in nodes:  # đối xứng hoá
        for m in ke[n]:
            ke[m].add(n)

    gan: dict[str, int] = {}
    so_nut = len(nodes)

    def chon_nut():
        best, best_key = None, None
        for n in nodes:
            if n in gan:
                continue
            bao_hoa = len({gan[m] for m in ke[n] if m in gan})
            key = (bao_hoa, len(ke[n]), n)
            if best_key is None or key > best_key:
                best, best_key = n, key
        return best

    def thu_tu_mau(n):
        dem = [0] * SO_MAU
        for v in gan.values():
            dem[v] += 1
        ds = sorted(range(SO_MAU), key=lambda c: (dem[c], c))
        cu = mau_cu.get(n)
        if cu is not None and 0 <= cu < SO_MAU:
            ds.remove(cu)
            ds.insert(0, cu)
        return ds

    buoc = [0]

    def giai() -> bool:
        if len(gan) == so_nut:
            return True
        buoc[0] += 1
        if buoc[0] > 200_000:
            return False
        n = chon_nut()
        dung = {gan[m] for m in ke[n] if m in gan}
        for c in thu_tu_mau(n):
            if c in dung:
                continue
            gan[n] = c
            if giai():
                return True
            del gan[n]
        return False

    if giai():
        return dict(gan)

    # Dự phòng: tham lam, chọn màu trùng ít xã kề nhất.
    gan.clear()
    for n in sorted(nodes, key=lambda x: -len(ke[x])):
        dem = [sum(1 for m in ke[n] if gan.get(m) == c) for c in range(SO_MAU)]
        gan[n] = min(range(SO_MAU), key=lambda c: (dem[c], c != mau_cu.get(n), c))
    return gan


def cap_nhat_mau_ranh_xa(call_rpc) -> tuple[set[str], str | None]:
    """Tính lại màu cho mọi xã đang có ranh thôn, lưu vào ranh_xa_mau.

    Trả về (tập xã đổi màu — cần làm mới cache hiển thị, thông báo lỗi|None).
    """
    rows, err = call_rpc("ranh_xa_ke_nhau", {}, timeout=120)
    if err:
        return set(), "Không tính được xã giáp nhau để tô màu ranh thôn."
    ke = {r["ma_xa"]: set(r.get("ke") or []) for r in rows}
    mau_cu = {r["ma_xa"]: r.get("mau") for r in rows}
    moi = to_mau(ke, mau_cu)
    _, err = call_rpc("luu_ranh_xa_mau", {"p_mau": moi}, timeout=30)
    if err:
        return set(), "Không lưu được màu ranh thôn theo xã."
    doi = {x for x, c in moi.items() if mau_cu.get(x) != c}
    return doi, None
