import { API_URL, request } from "./api";

// =========================================================
// DANH MỤC HỒ SƠ LƯU TRỮ (public.danhmuchoso) — trang "/danh-muc-ho-so".
// =========================================================

export function getDanhMucHoSo(params, { signal } = {}) {
  return request("/api/danhmuchoso", {
    params,
    signal,
    errorFallback: "Không tải được danh mục hồ sơ",
  });
}

export function kiemTraGcnDanhMuc(soSeriGcn, excludeId, { signal } = {}) {
  return request("/api/danhmuchoso/kiem-tra-gcn", {
    params: { so_seri_gcn: soSeriGcn, exclude_id: excludeId },
    signal,
    errorFallback: "Không kiểm tra được GCN",
  });
}

export function themDanhMucHoSo(payload) {
  return request("/api/danhmuchoso", {
    method: "POST",
    body: payload,
    errorFallback: "Nhập hồ sơ thất bại",
  });
}

export function capNhatDanhMucHoSo(id, payload) {
  return request(`/api/danhmuchoso/${id}`, {
    method: "PATCH",
    body: payload,
    errorFallback: "Cập nhật hồ sơ thất bại",
  });
}

// Trả file .xlsx (blob) — không qua request() vì đó trả JSON.
export async function exportDanhMucHoSo(params) {
  const query = new URLSearchParams(
    Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  ).toString();
  const res = await fetch(`${API_URL}/api/danhmuchoso/export${query ? `?${query}` : ""}`);
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

// File mẫu trống (MAUFILE.xlsx) để điền tay rồi nhập lại.
export async function taiMauDanhMucHoSo() {
  const res = await fetch(`${API_URL}/api/danhmuchoso/mau`);
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

const IMPORT_POLL_MS = 2000;

// Nhập hàng loạt từ file .xlsx đúng mẫu — multipart/form-data, không qua
// request() (đó gửi JSON). Backend ghi chạy nền (file vài nghìn dòng mất
// nhiều phút, quá giới hạn 100 giây/request của Cloudflare): POST trả
// {job_id}, rồi hỏi tiến độ mỗi 2 giây tới khi xong — onProgress nhận
// {da_xu_ly, tong_dong, thanh_cong, so_dong_loi}. Trả báo cáo kết quả
// (thanh_cong/so_dong_loi/loi…). Backend cũ (trả thẳng kết quả, không có
// job_id) vẫn chạy được.
export async function importDanhMucHoSo({ file, nam, chiNhanh, onProgress }) {
  const started = await batDauImport({ file, nam, chiNhanh });
  if (!started?.job_id) return started;
  onProgress?.({ da_xu_ly: 0, tong_dong: started.tong_dong, thanh_cong: 0, so_dong_loi: 0 });
  for (;;) {
    await new Promise((resolve) => window.setTimeout(resolve, IMPORT_POLL_MS));
    let job;
    try {
      job = await request(`/api/danhmuchoso/import/${started.job_id}`, {
        errorFallback: "Không lấy được tiến độ nhập",
      });
    } catch (err) {
      // Mất mạng thoáng qua thì hỏi lại; job vẫn chạy trên server.
      if (err instanceof TypeError) continue;
      throw err;
    }
    onProgress?.(job);
    if (job.trang_thai === "xong") return job.ket_qua;
    if (job.trang_thai === "loi") throw new Error(job.loi_he_thong || "Nhập thất bại");
  }
}

async function batDauImport({ file, nam, chiNhanh }) {
  const form = new FormData();
  form.append("file", file);
  form.append("nam", nam);
  if (chiNhanh) form.append("chi_nhanh", chiNhanh);
  const res = await fetch(`${API_URL}/api/danhmuchoso/import`, { method: "POST", body: form });
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* body không phải JSON */
  }
  if (!res.ok) {
    throw new Error(data?.error || `Nhập thất bại (HTTP ${res.status})`);
  }
  return data;
}
