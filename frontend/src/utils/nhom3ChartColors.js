// 8 màu phân loại đã kiểm chứng an toàn cho người mù màu (CVD Delta E >= 8,
// normal-vision Delta E >= 15 giữa các cặp liền kề) — xem skill dataviz,
// references/palette.md. Dùng chung cho mọi biểu đồ Nhóm 3 (trend, tỉ lệ,
// tốc độ) để 1 xã luôn cùng 1 màu trên mọi biểu đồ.
export const NHOM3_PALETTE = [
  "#2a78d6", // blue
  "#eb6834", // orange
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#e87ba4", // magenta
  "#008300", // green
  "#6250d6", // violet
  "#e34948", // red
];

// Gán màu theo HASH của mã xã (không theo thứ tự sắp xếp trong tập dữ liệu
// hiện có) — để màu của 1 xã KHÔNG đổi khi có thêm/bớt xã khác trong tập
// dữ liệu (vd nạp thêm xã mới có mã sắp xếp trước). "Color follows the
// entity, never its rank."
export function colorForMaXa(maXa) {
  let hash = 0;
  const s = String(maXa || "");
  for (let i = 0; i < s.length; i++) {
    hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
  }
  return NHOM3_PALETTE[hash % NHOM3_PALETTE.length];
}
