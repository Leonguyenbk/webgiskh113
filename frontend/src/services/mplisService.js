import { request } from "./api";

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
