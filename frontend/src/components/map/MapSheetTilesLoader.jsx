import { useEffect, useRef } from "react";

import { useMap, useMapEvents } from "react-leaflet";

import { getBanDoNenInView } from "../../services/mapSheetService";

const DEBOUNCE_MS = 400;

// Phải khớp CHÍNH XÁC name="..." của LayersControl.Overlay bọc lớp này
// trong App.jsx — Leaflet phát sự kiện overlayadd/overlayremove kèm đúng
// chuỗi name đó khi người dùng bật/tắt checkbox.
const OVERLAY_NAME = "Bản đồ địa chính";

// Tải danh sách tờ bản đồ nền (metadata: tile_url/bbox/trạng thái) giao
// khung nhìn hiện tại, tải lại khi pan/zoom (debounce 400ms) — khác các
// loader khác trong file này (đều chỉ tải khi người dùng bấm nút), vì lớp
// raster/ranh tờ phải tự động hiện đúng khu vực đang xem, không cần bấm
// "Tra cứu". Không tải ảnh tile ở đây — chỉ tải metadata nhẹ (JSON), ảnh
// tile do <TileLayer> tự yêu cầu khi lớp "Bản đồ địa chính" đang bật.
//
// CHỈ chạy khi overlay đang BẬT (theo dõi qua sự kiện overlayadd/
// overlayremove) — trước đây chạy vô điều kiện ngay từ lúc mở trang, kể
// cả với người chưa từng bật lớp này, tạo request bbox thừa trên mọi lần
// pan/zoom cho MỌI khách xem bản đồ (đã thấy thực tế qua log truy cập từ
// điện thoại) — không cần thiết và tốn tài nguyên Supabase vô ích.
export default function MapSheetTilesLoader({ onData }) {
  const map = useMap();
  const timerRef = useRef(null);
  const abortRef = useRef(null);
  const enabledRef = useRef(false);

  const load = () => {
    if (!enabledRef.current) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const bounds = map.getBounds();
    getBanDoNenInView(
      {
        west: bounds.getWest(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        north: bounds.getNorth(),
      },
      { signal: controller.signal },
    )
      .then((result) => onData(result?.features || []))
      .catch((error) => {
        if (error.name !== "AbortError") onData([]);
      });
  };

  const scheduleLoad = () => {
    if (!enabledRef.current) return;
    window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(load, DEBOUNCE_MS);
  };

  useMapEvents({
    moveend: scheduleLoad,
    zoomend: scheduleLoad,
    overlayadd: (event) => {
      if (event.name !== OVERLAY_NAME) return;
      enabledRef.current = true;
      load();
    },
    overlayremove: (event) => {
      if (event.name !== OVERLAY_NAME) return;
      enabledRef.current = false;
      window.clearTimeout(timerRef.current);
      abortRef.current?.abort();
      onData([]);
    },
  });

  useEffect(() => {
    // Pane riêng cho raster bản đồ nền — Leaflet mặc định dồn MỌI
    // <TileLayer> (cả lớp nền OSM/vệ tinh lẫn lớp này) vào chung
    // "tilePane", thứ tự chồng lớp giữa chúng khi đó phụ thuộc thứ tự
    // add/remove (đổi lớp nền, bật/tắt lớp này...) chứ không ổn định —
    // thực tế đã thấy lớp này bị lớp nền đè lên. Tạo pane riêng với
    // z-index cố định giữa tilePane (200) và overlayPane (400, nơi
    // polygon thửa đất nằm) đảm bảo LUÔN nằm trên mọi lớp nền, LUÔN dưới
    // thửa đất, bất kể thứ tự bật/tắt.
    if (!map.getPane("banDoNenPane")) {
      map.createPane("banDoNenPane").style.zIndex = 250;
    }

    return () => {
      window.clearTimeout(timerRef.current);
      abortRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
