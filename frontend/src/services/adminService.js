import { request } from "./api";

// =========================================================
// NHẬP DỮ LIỆU (GML / CSV-Excel đồng bộ) — cần mã xác thực nếu backend có
// cấu hình IMPORT_TOKEN.
// =========================================================

export function importGml(file, token) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/api/import-gml", {
    method: "POST",
    body: formData,
    isFormData: true,
    token,
    errorFallback: "Nhập dữ liệu thất bại",
  });
}

export function importDongBo(file, token) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/api/import-dong-bo", {
    method: "POST",
    body: formData,
    isFormData: true,
    token,
    errorFallback: "Nhập dữ liệu thất bại",
  });
}

export function importRanhThon(file, token) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/api/import-ranh-thon", {
    method: "POST",
    body: formData,
    isFormData: true,
    token,
    errorFallback: "Nhập ranh giới thôn thất bại",
  });
}

// =========================================================
// NGUỒN GOOGLE SHEET CHO ĐỒNG BỘ GCN (public.nguon_gcn)
// =========================================================

export function listNguonGcn() {
  return request("/api/nguon-gcn");
}

export function createNguonGcn(payload, token) {
  return request("/api/nguon-gcn", {
    method: "POST",
    body: payload,
    token,
    errorFallback: "Thêm nguồn thất bại",
  });
}

export function updateNguonGcn(maNguon, updates, token) {
  return request(`/api/nguon-gcn/${encodeURIComponent(maNguon)}`, {
    method: "PATCH",
    body: updates,
    token,
    errorFallback: "Cập nhật thất bại",
  });
}

export function deleteNguonGcn(maNguon, token) {
  return request(`/api/nguon-gcn/${encodeURIComponent(maNguon)}`, {
    method: "DELETE",
    token,
    errorFallback: "Xóa nguồn thất bại",
  });
}

export function syncNguonGcn(maNguon, token) {
  return request(`/api/nguon-gcn/${encodeURIComponent(maNguon)}/sync`, {
    method: "POST",
    token,
    errorFallback: "Đồng bộ thất bại",
  });
}
