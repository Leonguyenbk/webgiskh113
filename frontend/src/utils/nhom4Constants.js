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
    phapNhan: "",
    vaiTroPhapNhan: "",
  };
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
