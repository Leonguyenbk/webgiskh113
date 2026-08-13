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
