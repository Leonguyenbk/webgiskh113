// Danh sách lựa chọn cho biểu Nhóm 4 — port nguyên văn từ bieumau/Index.html
// (loại đất, hình thức sử dụng) và bieumau/Scripts.html (nguồn gốc sử dụng,
// mảng NGUON_GOC).

export const LOAI_DAT_OPTIONS = [
  "ODT",
  "ONT",
  "CLN",
  "LUC",
  "LUK",
  "BHK",
  "NHK",
  "RSX",
  "RPH",
  "SKC",
  "TMD",
];

export const HINH_THUC_SU_DUNG_OPTIONS = ["Sử dụng riêng", "Sử dụng chung"];

export const NGUON_GOC_OPTIONS = [
  "Nhà nước giao đất có thu tiền sử dụng đất",
  "Nhà nước giao đất không thu tiền sử dụng đất",
  "Nhà nước cho thuê đất trả tiền hàng năm",
  "Nhà nước cho thuê đất trả tiền một lần",
  "Nhà nước công nhận quyền sử dụng đất như Nhà nước giao đất có thu tiền sử dụng đất",
  "Nhà nước công nhận quyền sử dụng đất như Nhà nước giao đất không thu tiền sử dụng đất",
  "Nhận chuyển nhượng quyền sử dụng đất",
  "Thừa kế quyền sử dụng đất",
  "Tặng cho quyền sử dụng đất",
];

export const LOAI_CHU_OPTIONS = ["Cá nhân", "Đồng sử dụng", "Vợ chồng", "Hộ gia đình"];

export const SO_NGUOI_MAC_DINH = {
  "Cá nhân": 1,
  "Vợ chồng": 2,
  "Hộ gia đình": 1,
  "Đồng sử dụng": 2,
};

export function taoChuRong() {
  return {
    hoTen: "",
    ngaySinh: "",
    gioiTinh: "",
    cccd: "",
    diaChiThuongTru: "",
  };
}

// Pháp nhân/vai trò pháp nhân trên GCN suy thẳng từ tab "loại chủ" đang chọn
// + giới tính/thứ tự nhập — không để người dùng gõ tay (dễ sai/thiếu, 2
// trường này bắt buộc). Quy ước lấy từ dữ liệu GCN thật đã đồng bộ:
// - "Cá nhân": 1 người, cả 2 cột đều là "Cá nhân".
// - "Đồng sử dụng": nhiều người, mỗi người đều là "Cá nhân" (không phân
//   biệt vai trò riêng, "đồng" nằm ở cột pháp nhân).
// - "Vợ chồng": pháp nhân "Vợ chồng", vai trò suy từ giới tính (Nam ->
//   Chồng, Nữ -> Vợ) — dự phòng theo thứ tự nhập (người 1 -> Chồng, người
//   2 -> Vợ) nếu chưa chọn giới tính.
// - "Hộ gia đình": pháp nhân "Hộ gia đình", vai trò theo thứ tự nhập:
//   người 1 = Chủ hộ, người 2 = Vợ/chồng chủ hộ, còn lại = Thành viên hộ
//   gia đình.
export function tinhPhapNhanVaiTro(loaiChu, owners, index) {
  if (loaiChu === "Cá nhân") {
    return { phapNhan: "Cá nhân", vaiTroPhapNhan: "Cá nhân" };
  }
  if (loaiChu === "Đồng sử dụng") {
    return { phapNhan: "Đồng sử dụng", vaiTroPhapNhan: "Cá nhân" };
  }
  if (loaiChu === "Vợ chồng") {
    const gioiTinh = owners[index]?.gioiTinh;
    const vaiTroPhapNhan =
      gioiTinh === "Nam" ? "Chồng" : gioiTinh === "Nữ" ? "Vợ" : index === 0 ? "Chồng" : "Vợ";
    return { phapNhan: "Vợ chồng", vaiTroPhapNhan };
  }
  if (loaiChu === "Hộ gia đình") {
    const vaiTroPhapNhan =
      index === 0 ? "Chủ hộ" : index === 1 ? "Vợ/chồng chủ hộ" : "Thành viên hộ gia đình";
    return { phapNhan: "Hộ gia đình", vaiTroPhapNhan };
  }
  return { phapNhan: "", vaiTroPhapNhan: "" };
}

export function taoThuaRong() {
  return {
    soTo: "",
    soThua: "",
    soToGCN: "",
    soThuaGCN: "",
    maDinhDanh: "",
    dienTichThuaDat: "",
    diaChiThuaDat: "",
    ghiChu: "",
  };
}

export function taoDatRong() {
  return { loaiDat: "", dienTich: "", nguonGocSuDung: "", hinhThucSuDung: "", thoiHanSuDung: "" };
}
