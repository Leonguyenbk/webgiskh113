import { request } from "./api";

export function checkTrungThua({ maXa, soTo, soThua }, { signal } = {}) {
  return request("/api/nhom4/kiem-tra-trung-thua", {
    params: { ma_xa: maXa, so_to: soTo, so_thua: soThua },
    signal,
    errorFallback: "Không kiểm tra được trùng thửa",
  });
}

export function getDiaChiThuaDat({ maXa, soTo, soThua }, { signal } = {}) {
  return request("/api/nhom4/dia-chi-thua-dat", {
    params: { ma_xa: maXa, so_to: soTo, so_thua: soThua },
    signal,
    errorFallback: "Không lấy được địa chỉ thửa đất",
  });
}

// filesByParcel: 1 phần tử cho MỖI thửa trong payload.thua_list, CÙNG THỨ
// TỰ — mỗi thửa có hồ sơ quét riêng (xem Nhom4FormPage.jsx), không còn
// dùng chung 1 bộ file cho cả lô. Field name đánh số khớp backend
// (app/routes/nhom4_routes.py): file_chinh_0, file_phu_0, file_tbxn_0 cho
// thửa đầu, file_chinh_1/... cho thửa kế tiếp, v.v.
export function submitHoSo(payload, filesByParcel) {
  const formData = new FormData();
  formData.append("payload", JSON.stringify(payload));
  filesByParcel.forEach(({ chinh, phu, tbxn }, index) => {
    formData.append(`file_chinh_${index}`, chinh);
    if (phu) formData.append(`file_phu_${index}`, phu);
    if (tbxn) formData.append(`file_tbxn_${index}`, tbxn);
  });

  return request("/api/nhom4/ho-so", {
    method: "POST",
    body: formData,
    isFormData: true,
    errorFallback: "Lưu hồ sơ thất bại",
  });
}
