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

export function getThongKeNguonNhap({ signal } = {}) {
  return request("/api/thong-ke-nguon-nhap", {
    signal,
    errorFallback: "Không tải được thống kê nguồn nhập",
  });
}

export function getNhom3TongHop({ signal } = {}) {
  return request("/api/nhom3-con-thieu/tong-hop", {
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
