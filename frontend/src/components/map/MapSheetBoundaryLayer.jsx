import { useEffect, useRef, useState } from "react";

import { GeoJSON, useMap, useMapEvents } from "react-leaflet";

// Từ zoom này trở lên mới hiện nhãn "Tờ {so_to}" thường trực — zoom thấp
// hơn thì quá nhiều tờ chồng nhãn lên nhau, chỉ giữ lại viền mảnh.
const MIN_LABEL_ZOOM = 14;

const BOUNDARY_STYLE = {
  color: "#0ea5e9",
  weight: 1.5,
  opacity: 1,
  dashArray: "4 3",
  fillOpacity: 0,
};

// Viền + nhãn số tờ bản đồ nền — tách khỏi lớp raster (MapSheetTilesLayer)
// vì đây là vector nhẹ, luôn hữu ích để biết đang đứng ở tờ nào kể cả khi
// chưa có tile thật (trạng thái draft/uploaded/processing).
export default function MapSheetBoundaryLayer({ sheets }) {
  const map = useMap();
  const groupRef = useRef(null);
  const [zoom, setZoom] = useState(() => map.getZoom());

  useMapEvents({
    zoomend: () => setZoom(map.getZoom()),
  });

  useEffect(() => {
    const showLabels = zoom >= MIN_LABEL_ZOOM;
    groupRef.current?.eachLayer((layer) => {
      if (showLabels) layer.openTooltip();
      else layer.closeTooltip();
    });
  }, [zoom, sheets]);

  const collection = { type: "FeatureCollection", features: sheets };

  return (
    <GeoJSON
      ref={groupRef}
      key={sheets.map((feature) => feature.properties?.id).join(",")}
      data={collection}
      style={BOUNDARY_STYLE}
      onEachFeature={(feature, layer) => {
        const p = feature.properties || {};
        layer.bindTooltip(`Tờ ${p.so_to}`, {
          permanent: true,
          direction: "center",
          className: "mapSheetLabel",
        });
        layer.bindPopup(
          `<strong>Bản đồ địa chính</strong><br/>Mã xã: ${p.ma_xa}<br/>Tờ bản đồ: ${p.so_to}`,
        );
        layer.on("add", () => {
          if (zoom >= MIN_LABEL_ZOOM) layer.openTooltip();
          else layer.closeTooltip();
        });
      }}
    />
  );
}
