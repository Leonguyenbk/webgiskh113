import { API_URL, request } from "./api";

// =========================================================
// DANH MỤC HỒ SƠ LƯU TRỮ (public.danhmuchoso) — trang "/danh-muc-ho-so".
// Mọi endpoint đều chứa tên người sử dụng đất (thông tin cá nhân) nên
// bắt buộc mã xác thực IMPORT_TOKEN, giống /api/gcn-export-nhom3.
// =========================================================

export function getDanhMucHoSo(params, token, { signal } = {}) {
  return request("/api/danhmuchoso", {
    params,
    token,
    signal,
    errorFallback: "Không tải được danh mục hồ sơ",
  });
}

export function kiemTraGcnDanhMuc(soSeriGcn, token, { signal } = {}) {
  return request("/api/danhmuchoso/kiem-tra-gcn", {
    params: { so_seri_gcn: soSeriGcn },
    token,
    signal,
    errorFallback: "Không kiểm tra được GCN",
  });
}

export function themDanhMucHoSo(payload, token) {
  return request("/api/danhmuchoso", {
    method: "POST",
    body: payload,
    token,
    errorFallback: "Nhập hồ sơ thất bại",
  });
}

// Trả file .xlsx (blob) — không qua request() vì đó trả JSON.
export async function exportDanhMucHoSo(params, token) {
  const query = new URLSearchParams(
    Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  ).toString();
  const res = await fetch(`${API_URL}/api/danhmuchoso/export${query ? `?${query}` : ""}`, {
    headers: token ? { "X-Import-Token": token } : {},
  });
  if (!res.ok) {
    let message = `Tải thất bại (HTTP ${res.status})`;
    try {
      message = (await res.json())?.error || message;
    } catch {
      /* body không phải JSON */
    }
    throw new Error(message);
  }
  return res.blob();
}
