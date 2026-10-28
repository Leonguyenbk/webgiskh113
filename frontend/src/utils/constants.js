// Số thửa mỗi lô. Giữ dưới MAX_PAGE_SIZE của backend (1000), vượt qua thì
// backend tự kẹp lại và vòng lặp phân trang hiểu nhầm là đã hết dữ liệu.
// Từng thử 4000 để giảm số vòng phân trang nhưng gây tốn tài nguyên
// Supabase rõ rệt — đã revert.
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

// Thửa Nhóm 3 (xám) giao >= 95% diện tích với 1 ranh dự án đã lưu
// (properties.thuoc_du_an, xem luu_ranh_du_an_va_danh_dau_nhom3 trong
// supabase/schema.sql) — không còn tính vào khối lượng Nhóm 3 cần gửi xã
// nữa, tô vàng để dễ rà soát riêng. Chỉ áp dụng khi CHƯA thuộc Nhóm 1/2
// (màu nhóm quan trọng hơn) — thửa đã có GCN (xanh dương) vẫn giữ màu đó
// vì phản ánh việc đã thu thập xong, quan trọng hơn việc nằm trong ranh.
export const DU_AN_COLOR = "#eab308";
export const DU_AN_LABEL = "Thuộc dự án";

// Thửa Nhóm 3 (chưa thuộc Nhóm 1/2) KHÔNG có trong danh sách gửi xã
// (properties.ngoai_ds_gui_xa — xã đó đã có danh sách nhom3_can_thu_thap
// mà thửa này không nằm trong, xem get_parcels_in_view/search_parcels
// trong supabase/schema.sql) — tô gần đen để người thu thập không làm
// nhầm (yêu cầu người dùng). Đè lên cả sọc "đất tổ chức"; thửa đã nhập
// biểu (xanh dương) vẫn giữ màu đó vì đã làm xong.
export const NGOAI_DS_COLOR = "#0f172a";
export const NGOAI_DS_LABEL = "Không có trong DS gửi xã (không thu thập)";

// Màu tô thửa ĐANG CHỌN trên bản đồ (chọn 1 hoặc nhiều). Tím đậm — tách
// hẳn khỏi xanh lá (Nhóm 1), đỏ (Nhóm 2), xanh dương (đã nhập biểu), vàng
// (thuộc dự án) và xám (chưa phân loại).
export const SELECTED_COLOR = "#9333ea";

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

export function isNgoaiDsGuiXa(properties = {}) {
  const groupKey = getGroupKey(properties.dong_bo?.phan_loai_ke_hoach_2959);
  return groupKey === "DEFAULT" && !properties.co_gcn && Boolean(properties.ngoai_ds_gui_xa);
}

export function getParcelFillColor(properties = {}) {
  const groupKey = getGroupKey(properties.dong_bo?.phan_loai_ke_hoach_2959);
  if (groupKey === "DEFAULT") {
    if (properties.co_gcn) return GCN_COLOR;
    if (properties.ngoai_ds_gui_xa) return NGOAI_DS_COLOR;
    if (properties.thuoc_du_an) return DU_AN_COLOR;
  }
  return GROUP_COLORS[groupKey];
}

// Nhóm "đất tổ chức" theo mục đích sử dụng đất (TMD, SKC...) — không gồm
// NTS (nuôi trồng thủy sản, vẫn có thể là đất hộ gia đình/cá nhân). Thửa
// thuộc nhóm này mà CHƯA thuộc Nhóm 1/2 cần đánh dấu riêng (xám sọc đỏ)
// để dễ rà soát, tách khỏi màu xám "chưa phân loại" thông thường.
export const TO_CHUC_LAND_CODES = new Set([
  "TMD", "SKC", "SKS", "TSC", "DTS", "DGD", "DYT", "DVH", "DTT", "DHT",
  "DNL", "DCT", "TON", "TIN", "CQP", "CAN", "RPH", "RSD", "RST",
  "NTD", "SON", "MNC",
]);

export const TO_CHUC_STRIPE_LABEL = "Đất tổ chức chưa phân loại";

// Dải màu CSS cho các ô vuông chú giải/danh sách (background CSS thường,
// KHÔNG phải canvas của Leaflet — canvas cần CanvasPattern riêng, xem
// getToChucStripePattern bên dưới). Chu kỳ 5px (nhỏ hơn hình vẽ trên bản
// đồ) để chấm tròn 10px trong danh sách kết quả vẫn thấy rõ cả 2 màu.
export const TO_CHUC_STRIPE_CSS =
  "repeating-linear-gradient(45deg, #94a3b8 0px, #94a3b8 3px, #ef4444 3px, #ef4444 5px)";

// Thửa thuộc nhóm đất tổ chức (muc_dich_su_dung có thể ghi dạng
// "TMD+CLN", tách theo dấu "+") nhưng CHƯA thuộc Nhóm 1/2 — ưu tiên màu
// xanh dương (GCN_COLOR, đã có dữ liệu GCN) cao hơn cờ này, nên bỏ qua
// nếu properties.co_gcn đã true.
export function isToChucChuaPhanLoai(properties = {}) {
  const groupKey = getGroupKey(properties.dong_bo?.phan_loai_ke_hoach_2959);
  if (groupKey !== "DEFAULT" || properties.co_gcn) return false;
  const raw = String(properties.muc_dich_su_dung || "");
  return raw
    .split("+")
    .map((code) => code.trim().toUpperCase())
    .some((code) => TO_CHUC_LAND_CODES.has(code));
}

// CanvasPattern xám-sọc-đỏ dùng làm fillColor cho layer Leaflet. Renderer
// bản đồ chính dùng canvas (preferCanvas trong App.jsx) — Canvas 2D
// fillStyle chấp nhận cả CanvasPattern lẫn chuỗi màu, Leaflet chỉ gán
// thẳng options.fillColor vào ctx.fillStyle nên truyền CanvasPattern qua
// đây vẫn chạy đúng dù type khai báo là string. Tạo 1 lần rồi cache lại —
// style() của GeoJSON chạy lại cho MỌI thửa mỗi khi parcelOpacity/
// selectedIds đổi, không được tạo canvas mới mỗi lần.
let _toChucStripePattern = null;
export function getToChucStripePattern() {
  if (_toChucStripePattern) return _toChucStripePattern;
  if (typeof document === "undefined") return null;

  const size = 12;
  const tile = document.createElement("canvas");
  tile.width = size;
  tile.height = size;
  const ctx = tile.getContext("2d");

  ctx.fillStyle = GROUP_COLORS.DEFAULT;
  ctx.fillRect(0, 0, size, size);

  ctx.strokeStyle = "#ef4444";
  ctx.lineWidth = 3;
  ctx.beginPath();
  // 3 đường chéo để sọc nối liền mạch giữa các tile cạnh nhau.
  for (const offset of [-size, 0, size]) {
    ctx.moveTo(offset, size);
    ctx.lineTo(offset + size, 0);
  }
  ctx.stroke();

  _toChucStripePattern = ctx.createPattern(tile, "repeat");
  return _toChucStripePattern;
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
