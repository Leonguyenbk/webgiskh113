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

// Toàn bộ mã loại đất thực tế trong thua_dat (backend cache 1 giờ, xem
// nhom4_service.get_loai_dat_options) — cho ô "Loại đất" autocomplete đủ
// mã đang dùng thay vì chỉ 1 danh sách cố định soạn tay.
export function getLoaiDatOptions({ signal } = {}) {
  return request("/api/nhom4/loai-dat-options", {
    signal,
    errorFallback: "Không lấy được danh sách loại đất",
  });
}

// filesByParcel: 1 phần tử cho MỖI thửa trong payload.thua_list, CÙNG THỨ
// TỰ — mỗi thửa có hồ sơ quét riêng (xem Nhom4FormPage.jsx). Field name
// đánh số khớp backend (app/routes/nhom4_routes.py): file_chinh_0,
// file_phu_0, file_tbxn_0 cho thửa đầu, file_chinh_1/... cho thửa kế
// tiếp, v.v. sharedFiles ({chinh, phu, tbxn}): khi payload.dung_chung_ho_so_quet
// = true (yêu cầu người dùng: 1 đơn nhiều thửa) — gửi ĐÚNG 1 bộ file dưới
// field cố định file_chinh_shared/file_phu_shared/file_tbxn_shared thay
// vì lặp lại cùng file cho từng thửa (payload phình to khi nhiều thửa,
// từng khiến nộp thất bại) — filesByParcel bỏ qua (truyền null) khi dùng
// sharedFiles.
export function submitHoSo(payload, filesByParcel, sharedFiles) {
  const formData = new FormData();
  formData.append("payload", JSON.stringify(payload));
  if (sharedFiles) {
    if (sharedFiles.chinh) formData.append("file_chinh_shared", sharedFiles.chinh);
    if (sharedFiles.phu) formData.append("file_phu_shared", sharedFiles.phu);
    if (sharedFiles.tbxn) formData.append("file_tbxn_shared", sharedFiles.tbxn);
  } else {
    (filesByParcel || []).forEach(({ chinh, phu, tbxn }, index) => {
      if (chinh) formData.append(`file_chinh_${index}`, chinh);
      if (phu) formData.append(`file_phu_${index}`, phu);
      if (tbxn) formData.append(`file_tbxn_${index}`, tbxn);
    });
  }

  return request("/api/nhom4/ho-so", {
    method: "POST",
    body: formData,
    isFormData: true,
    errorFallback: "Lưu hồ sơ thất bại",
  });
}
