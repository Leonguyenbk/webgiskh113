import { useMapEvents } from "react-leaflet";

// Phải khớp CHÍNH XÁC name="..." của LayersControl.Overlay bọc lớp "Ranh
// giới thôn" trong App.jsx — cùng cơ chế OVERLAY_NAME đã dùng ở
// MapSheetTilesLoader.jsx cho lớp "Bản đồ địa chính".
const OVERLAY_NAME = "Ranh giới thôn";

// Chỉ báo cho App.jsx biết "người dùng vừa bật lớp Ranh giới thôn" — không
// tự tải dữ liệu ở đây (App.jsx giữ state ranhThonData, gọi onNeed() để
// tải qua getRanhGioiThonAllCached(), có cache module-level nên gọi lại
// nhiều lần không tốn thêm request thật). Trước đây App.jsx tải ranh giới
// thôn ngay khi mở trang bất kể có dùng tới hay không (lớp này mặc định
// TẮT, phần lớn người dùng không bao giờ bật) — lãng phí, góp phần vào sự
// cố CPU Supabase cao (xem chú thích ranh_gioi_thon_cache trong
// supabase/schema.sql). onNeed cũng được App.jsx gọi khi người dùng chọn 1
// xã ở bộ lọc (cần danh sách thôn cho dropdown "Thôn"), không chỉ khi bật
// lớp bản đồ.
export default function RanhThonOverlayLoader({ onNeed }) {
  useMapEvents({
    overlayadd: (event) => {
      if (event.name === OVERLAY_NAME) onNeed();
    },
  });
  return null;
}
