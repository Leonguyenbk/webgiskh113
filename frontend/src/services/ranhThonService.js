import { request } from "./api";

export function getRanhGioiThon({ maXa } = {}, { signal } = {}) {
  return request("/api/ranh-thon", {
    params: { ma_xa: maXa },
    signal,
    errorFallback: "Không tải được ranh giới thôn",
  });
}

// Cache module-level (sống hết vòng đời tab, không phải state component) cho
// biến thể "lấy TOÀN BỘ ranh giới thôn" (không lọc theo xã) — App.jsx dùng
// biến thể này để vẽ lớp "Ranh giới thôn" bất kể đang xem xã nào.
//
// Vì sao cần cache riêng ở đây dù backend cũng đã cache (xem
// backend/app/repositories/ranh_thon_repository.py): main.jsx điều hướng
// bằng path tự chế (không phải React Router có cache) nên <App> bị
// UNMOUNT/MOUNT LẠI mỗi khi người dùng rời trang bản đồ rồi quay lại (bấm
// "Công cụ" rồi "Về bản đồ", nộp xong biểu Nhóm 4 rồi quay lại...) — effect
// tải ranh giới thôn chạy lại mỗi lần đó. Cache ở module-level (ngoài
// component) sống sót qua các lần mount lại trong cùng phiên trình duyệt,
// nên phần lớn các lần quay lại trang không cần gọi mạng nữa.
const ALL_CACHE_TTL_MS = 5 * 60 * 1000; // khớp TTL cache RAM ở backend
let allCache = null; // { data, fetchedAt }
let allInflight = null; // Promise đang chờ — 2 lần mount gần nhau (StrictMode ở
// dev, hoặc điều hướng nhanh) dùng chung 1 request thay vì gọi trùng.

export function getRanhGioiThonAllCached() {
  if (allCache && Date.now() - allCache.fetchedAt < ALL_CACHE_TTL_MS) {
    return Promise.resolve(allCache.data);
  }

  if (!allInflight) {
    // Không cache lỗi: allInflight bị xoá trong finally kể cả khi request
    // lỗi, nên lần gọi kế tiếp thử lại ngay thay vì kẹt với promise đã reject.
    allInflight = getRanhGioiThon()
      .then((data) => {
        allCache = { data, fetchedAt: Date.now() };
        return data;
      })
      .finally(() => {
        allInflight = null;
      });
  }

  return allInflight;
}
