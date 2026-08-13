import { useCallback, useEffect, useState } from "react";

import L from "leaflet";
import { Circle, Marker, Pane, Popup, useMap } from "react-leaflet";

// CircleMarker (canvas) đè cả bản đồ ở pane của nó, chặn click vào thửa đất
// bên dưới. L.Marker chỉ chiếm đúng vùng icon nhỏ nên không có vấn đề đó.
const CURRENT_LOCATION_ICON = L.divIcon({
  className: "myLocationMarker",
  html: '<span class="myLocationDot"></span>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

export default function CurrentLocation({ onLocated, onPosition }) {
  const map = useMap();
  const [position, setPosition] = useState(null);
  const [accuracy, setAccuracy] = useState(0);
  const [locationError, setLocationError] = useState("");

  const locateMe = useCallback(
    (isAuto = false) => {
      setLocationError("");

      if (!window.isSecureContext) {
        if (!isAuto) setLocationError("Định vị cần HTTPS hoặc localhost.");
        return;
      }

      if (!navigator.geolocation) {
        if (!isAuto) setLocationError("Thiết bị không hỗ trợ định vị.");
        return;
      }

      navigator.geolocation.getCurrentPosition(
        ({ coords }) => {
          const currentPosition = [coords.latitude, coords.longitude];
          setPosition(currentPosition);
          setAccuracy(coords.accuracy || 0);
          map.flyTo(currentPosition, 18, { animate: true, duration: 1.2 });
          onLocated?.();
          onPosition?.({ lat: coords.latitude, lng: coords.longitude });
        },
        (geoError) => {
          // Lúc mới mở trang, im lặng bỏ qua lỗi (ví dụ chưa cấp quyền) thay
          // vì dọa người dùng ngay khi họ chưa bấm gì.
          if (isAuto) return;

          const messages = {
            1: "Chưa cho phép truy cập vị trí.",
            2: "Thiết bị không xác định được vị trí.",
            3: "Quá thời gian chờ GPS.",
          };
          setLocationError(
            messages[geoError.code] || "Không lấy được vị trí hiện tại.",
          );
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 },
      );
    },
    [map, onLocated, onPosition],
  );

  // Không tự tải toàn tỉnh khi mở trang (chờ người dùng chọn bộ lọc), nên
  // tự định vị ngay lúc mở để bản đồ khớp vào vị trí người dùng trước
  // tiên, thay vì đợi bấm nút "Vị trí của tôi".
  useEffect(() => {
    locateMe(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <button
        type="button"
        className="locateButton"
        onClick={() => locateMe(false)}
        title="Hiển thị vị trí hiện tại"
      >
        ◎ <span>Vị trí của tôi</span>
      </button>

      {locationError && <div className="locationError">{locationError}</div>}

      {position && (
        <>
          <Pane name="myAccuracyPane" style={{ zIndex: 450, pointerEvents: "none" }}>
            <Circle
              center={position}
              radius={Math.min(accuracy, 10)}
              pathOptions={{
                color: "#2563eb",
                fillColor: "#60a5fa",
                fillOpacity: 0.12,
                weight: 1,
              }}
            />
          </Pane>

          <Marker position={position} icon={CURRENT_LOCATION_ICON}>
            <Popup>
              <strong>Vị trí hiện tại</strong>
              <br />
              Sai số khoảng {Math.round(accuracy)} m
            </Popup>
          </Marker>
        </>
      )}
    </>
  );
}
