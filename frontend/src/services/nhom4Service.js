import { API_URL, request } from "./api";

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
// Kiểm tra trước phần KHÔNG cần file (thiếu thông tin, thửa đã có dữ
// liệu/không tồn tại/Nhóm 1-2) — gọi trước khi tải PDF lên, để người mạng
// chậm không phải chờ gửi hết file rồi mới nhận lỗi.
export function kiemTraHoSo(payload) {
  return request("/api/nhom4/kiem-tra-ho-so", {
    method: "POST",
    body: payload,
    errorFallback: "Không kiểm tra được hồ sơ",
  });
}

// Dùng XMLHttpRequest thay fetch() chỉ để có tiến trình tải lên (fetch
// không báo upload progress) — onProgress(phanTram 0-100) gọi trong lúc
// gửi file, 100 nghĩa là đã gửi xong, đang chờ máy chủ lưu.
export function submitHoSo(payload, filesByParcel, sharedFiles, { onProgress } = {}) {
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

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/nhom4/ho-so`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let body = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // Không phải JSON (VD trang lỗi của proxy) — dùng thông báo mặc định.
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else reject(new Error(body?.error || "Lưu hồ sơ thất bại"));
    };
    xhr.onerror = () =>
      reject(new Error("Mất kết nối khi gửi hồ sơ — kiểm tra mạng rồi bấm Lưu hồ sơ lại."));
    xhr.send(formData);
  });
}
