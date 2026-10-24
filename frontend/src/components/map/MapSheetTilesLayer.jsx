import L from "leaflet";
import { TileLayer } from "react-leaflet";

// Leaflet mặc định maxZoom=18 cho MỌI TileLayer nếu không set — vượt quá
// là layer tự coi "ngoài phạm vi" và ẩn hẳn (khác maxNativeZoom, chỉ điều
// khiển việc phóng to tile cũ chứ không phải ẩn/hiện). Phải set bằng đúng
// zoom cao nhất map cho phép (khớp lớp nền "Vệ tinh (Google)" maxZoom=21
// trong App.jsx) để không bao giờ tự ẩn khi zoom sâu — Leaflet tự phóng
// to tile ở maxNativeZoom (độ phân giải thật của từng tờ) cho các mức
// zoom cao hơn, không tải tile mới.
const MAP_MAX_ZOOM = 21;

// Giới hạn mỗi TileLayer trong khung bao ranh tờ (nới thêm SHEET_BOUNDS_PAD
// để không cắt phần ảnh quét lấn ra ngoài ranh) — không có bounds, Leaflet
// xin tile cho CẢ khung nhìn ở MỌI tờ đang mount, đa số trả 404 (ngoài
// vùng tờ), N tờ = N lần số request, từng làm nghẽn cả server.
const SHEET_BOUNDS_PAD = 0.1;

function sheetBounds(feature) {
  try {
    const bounds = L.geoJSON(feature).getBounds();
    return bounds.isValid() ? bounds.pad(SHEET_BOUNDS_PAD) : undefined;
  } catch {
    return undefined;
  }
}

// 1 <TileLayer> raster mỗi tờ bản đồ đang trong khung nhìn (thay vì gộp
// thành 1 lớp lớn) — tờ nào ra khỏi khung nhìn thì MapSheetTilesLoader
// không còn trả về nữa, React tự unmount TileLayer tương ứng, ngừng yêu
// cầu tile của tờ đó. `key` gồm cả id lẫn tile_version để tự làm mới khi
// admin tải lại tile cho cùng 1 tờ (tile_version tăng => URL đổi).
// pane="banDoNenPane": pane riêng do MapSheetTilesLoader tạo (z-index 250,
// giữa tilePane=200 và overlayPane=400) — không dùng "tilePane" mặc định
// vì lớp nền (OSM/vệ tinh) cũng nằm đó, thứ tự chồng lớp giữa 2 bên không
// ổn định (đã thấy thực tế bị lớp nền đè lên).
export default function MapSheetTilesLayer({ sheets, opacity, pane = "banDoNenPane" }) {
  return sheets
    .filter((feature) => feature.properties?.tile_url)
    .map((feature) => {
      const {
        id,
        tile_url: tileUrl,
        tile_version: tileVersion,
        min_zoom: minZoom,
        max_zoom: maxZoom,
      } = feature.properties;
      return (
        <TileLayer
          key={`${id}-${tileVersion}`}
          url={tileUrl}
          opacity={opacity}
          pane={pane}
          bounds={sheetBounds(feature)}
          minZoom={minZoom ?? undefined}
          maxNativeZoom={maxZoom ?? undefined}
          maxZoom={MAP_MAX_ZOOM}
        />
      );
    });
}
