import { request } from "./api";

// =========================================================
// ỨNG THỬA MPLIS (public.ung_thua_mplis) — mở cho mọi người dùng bản đồ,
// không cần token.
// =========================================================

export function getUngThuaList({ maXa, signal } = {}) {
  return request("/api/ung-thua", {
    params: maXa ? { ma_xa: maXa } : undefined,
    signal,
  });
}

export function saveUngThuaMatch(payload) {
  return request("/api/ung-thua", {
    method: "POST",
    body: payload,
    errorFallback: "Lưu thất bại",
  });
}

// =========================================================
// CẬP NHẬT TRẠNG THÁI TỪ MPLIS (public.dong_bo_du_lieu) — trang quản trị
// "Cập nhật MPLIS", cần mã xác thực (IMPORT_TOKEN, header X-Import-Token).
// =========================================================

export function capNhatPhanLoai(body, token, { errorFallback } = {}) {
  return request("/api/admin/cap-nhat-phan-loai", {
    method: "POST",
    body,
    token,
    errorFallback: errorFallback || "Cập nhật thất bại",
  });
}

export function getCapNhatPhanLoaiJob(jobId, token) {
  return request(`/api/admin/cap-nhat-phan-loai/${encodeURIComponent(jobId)}`, {
    token,
    errorFallback: "Không lấy được tiến độ job",
  });
}
