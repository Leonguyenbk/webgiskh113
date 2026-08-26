import { request } from "./api";

// =========================================================
// BẢN ĐỒ NỀN (tờ bản đồ raster, public.ban_do_nen) — WebGIS chỉ nhận đăng
// ký metadata (Tool Windows KMZ→XYZ→Storage tự gọi /register sau khi
// upload xong), không nhận KMZ/tile qua đây.
// =========================================================

export function listBanDoNen(params = {}, { signal } = {}) {
  return request("/api/ban-do-nen", {
    params,
    signal,
    errorFallback: "Không tải được danh sách bản đồ nền",
  });
}

export function getBanDoNen(id, { signal } = {}) {
  return request(`/api/ban-do-nen/${id}`, {
    signal,
    errorFallback: "Không tải được tờ bản đồ",
  });
}

export function deleteBanDoNen(id, token) {
  return request(`/api/ban-do-nen/${id}`, {
    method: "DELETE",
    token,
    errorFallback: "Xóa tờ bản đồ thất bại",
  });
}

export function toggleBanDoNen(id, kichHoat, token) {
  return request(`/api/ban-do-nen/${id}`, {
    method: "PATCH",
    body: { kich_hoat: kichHoat },
    token,
    errorFallback: "Cập nhật thất bại",
  });
}

export function getBanDoNenInView({ west, south, east, north }, { signal } = {}) {
  return request("/api/ban-do-nen/in-view", {
    params: { west, south, east, north },
    signal,
    errorFallback: "Không tải được bản đồ nền trong khung nhìn",
  });
}

export function searchBanDoNen({ maXa, soTo } = {}, { signal } = {}) {
  return request("/api/ban-do-nen/search", {
    params: { ma_xa: maXa, so_to: soTo },
    signal,
    errorFallback: "Không tìm thấy tờ bản đồ",
  });
}
