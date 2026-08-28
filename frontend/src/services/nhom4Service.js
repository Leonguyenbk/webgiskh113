import { request } from "./api";

export function checkTrungThua({ maXa, soTo, soThua }, { signal } = {}) {
  return request("/api/nhom4/kiem-tra-trung-thua", {
    params: { ma_xa: maXa, so_to: soTo, so_thua: soThua },
    signal,
    errorFallback: "Không kiểm tra được trùng thửa",
  });
}

export function submitHoSo(payload, fileChinh, filePhu, fileTbxn) {
  const formData = new FormData();
  formData.append("payload", JSON.stringify(payload));
  formData.append("file_chinh", fileChinh);
  if (filePhu) formData.append("file_phu", filePhu);
  if (fileTbxn) formData.append("file_tbxn", fileTbxn);

  return request("/api/nhom4/ho-so", {
    method: "POST",
    body: formData,
    isFormData: true,
    errorFallback: "Lưu hồ sơ thất bại",
  });
}
