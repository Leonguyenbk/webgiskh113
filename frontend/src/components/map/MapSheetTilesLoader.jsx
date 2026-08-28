import { useEffect, useRef } from "react";

import L from "leaflet";
import { useMap, useMapEvents } from "react-leaflet";

import { getBanDoNenInView } from "../../services/mapSheetService";

const DEBOUNCE_MS = 400;

// Nới khung nhìn 25% khi lọc tờ ghim theo xã — tờ nằm sát mép vẫn được
// mount trước để kéo bản đồ 1 chút là thấy ngay, không giật.
const VIEWPORT_PAD = 0.25;

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
//
// Chế độ lọc theo xã (filterMaXa khác rỗng): KHÔNG gọi API theo khung
// nhìn nữa. App đưa TRỌN danh sách tờ của xã qua pinnedSheets; loader chỉ
// lọc lại các tờ giao khung nhìn hiện tại (rẻ, tính client) rồi trả về
// onData — tránh mount hàng chục <TileLayer> cùng lúc khi xã có nhiều tờ.
export default function MapSheetTilesLoader({
  onData,
  filterMaXa = "",
  pinnedSheets = [],
  onEnabledChange,
}) {
  const map = useMap();
  const timerRef = useRef(null);
  const abortRef = useRef(null);
  const enabledRef = useRef(false);
  // filterMaXa / pinnedSheets qua ref để các handler đăng ký 1 lần trong
  // useMapEvents luôn đọc được giá trị mới nhất.
  const filterRef = useRef(filterMaXa);
  filterRef.current = filterMaXa;
  const pinnedRef = useRef(pinnedSheets);
  pinnedRef.current = pinnedSheets;

  // Lọc danh sách tờ ghim còn các tờ giao khung nhìn (đã nới 25%).
  const emitViewportCull = () => {
    if (!enabledRef.current || !filterRef.current) return;
    const view = map.getBounds().pad(VIEWPORT_PAD);
    const visible = pinnedRef.current.filter((feature) => {
      try {
        return L.geoJSON(feature).getBounds().intersects(view);
      } catch {
        return true;
      }
    });
    onData(visible);
  };

  const load = () => {
    if (!enabledRef.current) return;
    // Đang lọc theo xã: danh sách tờ do App ghim, lọc theo khung nhìn ở
    // emitViewportCull — không gọi API viewport.
    if (filterRef.current) return;
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
    if (filterRef.current) {
      emitViewportCull();
      return;
    }
    window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(load, DEBOUNCE_MS);
  };

  useMapEvents({
    moveend: scheduleLoad,
    zoomend: scheduleLoad,
    overlayadd: (event) => {
      if (event.name !== OVERLAY_NAME) return;
      enabledRef.current = true;
      onEnabledChange?.(true);
      if (filterRef.current) emitViewportCull();
      else load();
    },
    overlayremove: (event) => {
      if (event.name !== OVERLAY_NAME) return;
      enabledRef.current = false;
      onEnabledChange?.(false);
      window.clearTimeout(timerRef.current);
      abortRef.current?.abort();
      // Đang lọc theo xã thì giữ nguyên danh sách của App để bật lại thấy ngay.
      if (!filterRef.current) onData([]);
    },
  });

  // Vào/ra chế độ lọc, hoặc danh sách tờ ghim đổi: huỷ request viewport
  // đang chờ; lọc lại theo khung nhìn (chế độ lọc) hoặc nạp lại theo khung
  // nhìn (đã bỏ lọc) khi lớp đang bật.
  useEffect(() => {
    window.clearTimeout(timerRef.current);
    abortRef.current?.abort();
    if (!enabledRef.current) return;
    if (filterMaXa) emitViewportCull();
    else load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterMaXa, pinnedSheets]);

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
