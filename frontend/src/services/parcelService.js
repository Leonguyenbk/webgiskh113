import { request } from "./api";

export function getXaList({ signal } = {}) {
  return request("/api/parcels/xa-list", { signal });
}

export function getParcelsCount(params, { signal, errorFallback } = {}) {
  return request("/api/parcels/count", {
    params,
    signal,
    errorFallback: errorFallback || "Không đếm được số thửa",
  });
}

export function getParcelsByBounds(params, { signal, errorFallback } = {}) {
  return request("/api/parcels", {
    params,
    signal,
    errorFallback: errorFallback || "Không tải được thửa đất",
  });
}

export function searchParcels(params, { signal, errorFallback } = {}) {
  return request("/api/parcels/search", {
    params,
    signal,
    errorFallback: errorFallback || "Không tải được dữ liệu thửa đất",
  });
}

export function getGcnStats({ signal } = {}) {
  return request("/api/gcn-stats", { signal });
}

export function getGcnDanhSach(params, { signal, errorFallback } = {}) {
  return request("/api/gcn-danh-sach", {
    params,
    signal,
    errorFallback: errorFallback || "Không tải được danh sách dữ liệu GCN",
  });
}

// Nút "Xem/Sửa" ở trang "Danh sách thửa đã nhập" — lộ dữ liệu cá nhân
// (CCCD, ngày sinh, địa chỉ...) nên backend bắt buộc mã xác thực
// IMPORT_TOKEN (header X-Import-Token, giống ImportGmlPage/MplisSyncPage).
export function getGcnChiTiet(params, { signal, token, errorFallback } = {}) {
  return request("/api/gcn-danh-sach/chi-tiet", {
    params,
    signal,
    token,
    errorFallback: errorFallback || "Không tải được thông tin đã nhập",
  });
}

export function updateGcnChiTiet(rowId, params, body, { token, errorFallback } = {}) {
  return request(`/api/gcn-danh-sach/chi-tiet/${rowId}`, {
    method: "PATCH",
    params,
    body,
    token,
    errorFallback: errorFallback || "Không lưu được thay đổi",
  });
}

export function getThongKeNguonNhap({ signal } = {}) {
  return request("/api/thong-ke-nguon-nhap", {
    signal,
    errorFallback: "Không tải được thống kê nguồn nhập",
  });
}

export function getNhom3TongHop(params, { signal } = {}) {
  return request("/api/nhom3-con-thieu/tong-hop", {
    params,
    signal,
    errorFallback: "Không tải được tổng hợp Nhóm 3",
  });
}

export function getNhom3DanhSachConThieu(params, { signal, errorFallback } = {}) {
  return request("/api/nhom3-con-thieu/danh-sach", {
    params,
    signal,
    errorFallback: errorFallback || "Không tải được danh sách Nhóm 3 còn thiếu",
  });
}

// params có thể gồm { ma_xa, tu, den } — tu/den là chuỗi ISO datetime
// (ranh giới khoảng hiển thị trend, xem backend get_nhom3_tien_do_trend).
export function getNhom3Trend(params, { signal } = {}) {
  return request("/api/nhom3-con-thieu/trend", {
    params,
    signal,
    errorFallback: "Không tải được trend tiến độ Nhóm 3",
  });
}
