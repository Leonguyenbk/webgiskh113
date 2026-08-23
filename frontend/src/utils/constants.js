// Số thửa mỗi lô. Giữ dưới MAX_PAGE_SIZE của backend (3000), vượt qua thì
// backend tự kẹp lại và vòng lặp phân trang hiểu nhầm là đã hết dữ liệu.
export const PAGE_SIZE = 1000;

// Chốt an toàn cho vòng lặp phân trang. Không phải giới hạn hiển thị: chỉ
// để phòng trường hợp server phân trang sai và lặp vô tận.
export const MAX_FEATURES = 50000;

// "Quanh vị trí của tôi": dò dần bán kính (mét) tới khi đủ khoảng
// NEAR_ME_TARGET thửa hoặc hết mức thử, thay vì đoán cứng một khung cố
// định (mật độ thửa đất khác nhau rất nhiều giữa khu đô thị và vùng thưa
// dân).
export const NEAR_ME_RADII_METERS = [500, 1000, 2000, 4000, 8000, 16000];
export const NEAR_ME_TARGET = 1000;
export const NEAR_ME_ZOOM = 17;

// Nút "Tìm thửa quanh đây": người dùng tự bấm sau khi zoom/kéo tới khu vực
// muốn xem, thay vì tự động tải theo từng lần di chuyển bản đồ (gây lag
// khi zoom/pan liên tục). Kết quả THAY THẾ dữ liệu đang có, không gộp thêm.
export const VIEWPORT_SEARCH_TARGET = 2000;

// Màu/nhãn phân loại thửa đất — dùng chung giữa bản đồ chính (App.jsx),
// dashboard thống kê GCN và bất kỳ trang nào cần hiển thị cùng ngôn ngữ
// màu này, để không bị lệch màu giữa các trang khi cần đổi 1 chỗ.

export const GROUP_COLORS = {
  "NHÓM 1": "#22c55e",
  "NHÓM 2": "#ef4444",
  DEFAULT: "#94a3b8",
};

export const GROUP_LABELS = {
  "NHÓM 1": "Nhóm 1",
  "NHÓM 2": "Nhóm 2",
  DEFAULT: "Chưa phân loại",
};

// Thửa đã có dữ liệu GCN (properties.co_gcn, xem get_parcels_in_view/
// search_parcels trong supabase/schema.sql) được tô xanh dương — nhưng
// chỉ khi thửa CHƯA thuộc Nhóm 1/Nhóm 2, vì màu nhóm quan trọng hơn và
// không được ghi đè.
export const GCN_COLOR = "#2563eb";
export const GCN_LABEL = "Thửa đất đã nhập biểu";

export function getGroupKey(phanLoai = "") {
  const normalized = phanLoai.trim().toUpperCase();
  return GROUP_COLORS[normalized] ? normalized : "DEFAULT";
}

// Thửa đã thuộc Nhóm 1/Nhóm 2 (KH 2959) coi như đã có dữ liệu từ trước —
// không cần hiện trạng thái "chưa nhập biểu GCN" hay nút nhập biểu Nhóm 4
// nữa (xem ParcelInfoPanel.jsx).
export function isNhom12(phanLoai = "") {
  return getGroupKey(phanLoai) !== "DEFAULT";
}

export function getGroupColor(phanLoai = "") {
  return GROUP_COLORS[getGroupKey(phanLoai)];
}

export function getParcelFillColor(properties = {}) {
  const groupKey = getGroupKey(properties.dong_bo?.phan_loai_ke_hoach_2959);
  if (groupKey === "DEFAULT") {
    if (properties.co_gcn) return GCN_COLOR;
  }
  return GROUP_COLORS[groupKey];
}

export const MISSING_INFO_RULES = [
  {
    field: "chua_xuat_so_dia_chinh_dien_tu",
    label: "Chưa được xuất số địa chính điện tử",
  },
  {
    field: "khong_dong_bo_3_khoi",
    label: "Không đồng bộ 3 khối thông tin (không gian, thuộc tính, phi cấu trúc)",
  },
  {
    field: "chi_co_du_lieu_thuoc_tinh",
    label: "Chỉ có dữ liệu thuộc tính (thiếu dữ liệu không gian)",
  },
  {
    field: "chua_khop_csdlqg_dan_cu",
    label: "Thông tin người sử dụng đất chưa khớp với CSDLQG về dân cư",
  },
  {
    field: "khong_xac_dinh_csdlqg_dan_cu",
    label: "Không xác định được người sử dụng đất trong CSDLQG về dân cư",
  },
  { field: "khong_van_hanh_24_7", label: "Dữ liệu không được vận hành 24/7" },
];

export function getMissingInfo(dongBo) {
  if (!dongBo) return ["Chưa có dữ liệu đồng bộ cho thửa này"];
  return MISSING_INFO_RULES.filter((rule) => dongBo[rule.field]).map(
    (rule) => rule.label,
  );
}
