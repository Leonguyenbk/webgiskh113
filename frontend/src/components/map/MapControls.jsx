import { useCallback, useState } from "react";

import { getParcelsByBounds } from "../../services/parcelService";
import { VIEWPORT_SEARCH_TARGET } from "../../utils/constants";

// Nút "Tìm thửa quanh đây": người dùng tự bấm sau khi zoom/kéo tới khu vực
// muốn xem, thay vì tự động tải theo từng lần di chuyển bản đồ (gây lag khi
// zoom/pan liên tục). Kết quả THAY THẾ dữ liệu đang có, không gộp thêm. Đặt
// ở header nên nhận `map` qua prop thay vì useMap() — không còn là con của
// MapContainer.
export function FindHereButton({ map, nhom, onBeforeSearch, onData, onLoading, onError, onMeta }) {
  const [busy, setBusy] = useState(false);

  const handleClick = useCallback(async () => {
    if (!map) return;

    onBeforeSearch?.();
    setBusy(true);
    onLoading(true);
    onError("");
    onData(null);
    onMeta({ loaded: 0 });

    const bounds = map.getBounds();
    const center = map.getCenter();
    const nhomParam = nhom?.length ? nhom.join(",") : "";

    try {
      const result = await getParcelsByBounds(
        {
          west: bounds.getWest(),
          south: bounds.getSouth(),
          east: bounds.getEast(),
          north: bounds.getNorth(),
          center_lng: center.lng,
          center_lat: center.lat,
          limit: VIEWPORT_SEARCH_TARGET,
          offset: 0,
          zoom: map.getZoom(),
          nhom: nhomParam || undefined,
        },
        { errorFallback: "Không tải được thửa đất quanh khu vực bản đồ" },
      );

      const features = result?.features || [];
      onData({ type: "FeatureCollection", features });
      onMeta({ loaded: features.length });
    } catch (error) {
      onError(error.message);
    } finally {
      setBusy(false);
      onLoading(false);
    }
  }, [map, nhom, onBeforeSearch, onData, onLoading, onError, onMeta]);

  return (
    <button
      type="button"
      className="headerMapButton primary"
      onClick={handleClick}
      disabled={busy || !map}
      title={`Tìm ${VIEWPORT_SEARCH_TARGET.toLocaleString("vi-VN")} thửa quanh khu vực bản đồ đang xem`}
    >
      🔍{" "}
      <span>
        {busy
          ? "Đang tìm…"
          : `Tìm ${VIEWPORT_SEARCH_TARGET.toLocaleString("vi-VN")} thửa quanh đây`}
      </span>
    </button>
  );
}
