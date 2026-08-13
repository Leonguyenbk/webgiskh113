import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import L from "leaflet";

import {
  Circle,
  GeoJSON,
  LayersControl,
  MapContainer,
  Marker,
  Pane,
  Popup,
  TileLayer,
  ZoomControl,
  useMap,
} from "react-leaflet";

// CircleMarker (canvas) đè cả bản đồ ở pane của nó, chặn click vào thửa đất
// bên dưới. L.Marker chỉ chiếm đúng vùng icon nhỏ nên không có vấn đề đó.
const CURRENT_LOCATION_ICON = L.divIcon({
  className: "myLocationMarker",
  html: '<span class="myLocationDot"></span>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

const OSM_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const GOOGLE_SUBDOMAINS = ["mt0", "mt1", "mt2", "mt3"];
const GOOGLE_HYBRID_URL = "https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}";
const GOOGLE_SATELLITE_URL = "https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}";

// Esri: chính chủ, miễn phí cho ứng dụng phi thương mại.
const ESRI_IMAGERY_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/" +
  "World_Imagery/MapServer/tile/{z}/{y}/{x}";

// Số thửa mỗi lô. Giữ dưới MAX_PAGE_SIZE của backend (3000),
// vượt qua thì backend tự kẹp lại và vòng lặp hiểu nhầm là đã hết dữ liệu.
const PAGE_SIZE = 1000;

// Chốt an toàn cho vòng lặp phân trang. Không phải giới hạn hiển thị:
// chỉ để phòng trường hợp server phân trang sai và lặp vô tận.
const MAX_FEATURES = 50000;

// Nới khung quanh phạm vi dữ liệu để không sót thửa nằm sát mép, đơn vị độ.
const EXTENT_PADDING = 0.01;

// "Quanh vị trí của tôi": dò dần bán kính (mét) tới khi đủ khoảng
// NEAR_ME_TARGET thửa hoặc hết mức thử, thay vì đoán cứng một khung cố định
// (mật độ thửa đất khác nhau rất nhiều giữa khu đô thị và vùng thưa dân).
const NEAR_ME_RADII_METERS = [500, 1000, 2000, 4000, 8000, 16000];
const NEAR_ME_TARGET = 1000;
const NEAR_ME_ZOOM = 17;

// Nút "Tìm thửa quanh đây": người dùng tự bấm sau khi zoom/kéo tới khu vực
// muốn xem, thay vì tự động tải theo từng lần di chuyển bản đồ (gây lag khi
// zoom/pan liên tục). Kết quả THAY THẾ dữ liệu đang có, không gộp thêm.
const VIEWPORT_SEARCH_TARGET = 2000;

function metersToDegrees(meters, latDeg) {
  const dLat = meters / 111320;
  const dLng = meters / (111320 * Math.max(Math.cos((latDeg * Math.PI) / 180), 0.1));
  return { dLat, dLng };
}

function boundsForRadius(lat, lng, meters) {
  const { dLat, dLng } = metersToDegrees(meters, lat);
  return { west: lng - dLng, east: lng + dLng, south: lat - dLat, north: lat + dLat };
}

const GROUP_COLORS = {
  "NHÓM 1": "#22c55e",
  "NHÓM 2": "#ef4444",
  DEFAULT: "#94a3b8",
};

const GROUP_LABELS = {
  "NHÓM 1": "Nhóm 1",
  "NHÓM 2": "Nhóm 2",
  DEFAULT: "Chưa phân loại",
};

// Thửa đã có dữ liệu GCN (properties.co_gcn, xem get_parcels_in_view/
// search_parcels trong supabase/schema.sql) được tô xanh dương — nhưng
// chỉ khi thửa CHƯA thuộc Nhóm 1/Nhóm 2, vì màu nhóm quan trọng hơn và
// không được ghi đè.
const GCN_COLOR = "#2563eb";
const GCN_LABEL = "Thửa đất đã nhập biểu";

// Thửa "chưa phân loại" nhưng người thu thập đã đối chiếu thủ công và xác
// nhận thửa này thực ra đã có trên MPLIS (chỉ khác tờ thửa) — xem
// properties.ung_thua (get_parcels_in_view/search_parcels trong
// supabase/schema.sql). Ưu tiên hơn màu "đã nhập biểu" vì là xác nhận
// chắc chắn hơn, nhưng vẫn nhường màu Nhóm 1/Nhóm 2 nếu có.
const UNG_THUA_COLOR = "#eab308";
const UNG_THUA_LABEL = "Đã ứng thửa MPLIS";

function getGroupKey(phanLoai = "") {
  const normalized = phanLoai.trim().toUpperCase();
  return GROUP_COLORS[normalized] ? normalized : "DEFAULT";
}

function getGroupColor(phanLoai = "") {
  return GROUP_COLORS[getGroupKey(phanLoai)];
}

function getParcelFillColor(properties = {}) {
  const groupKey = getGroupKey(properties.dong_bo?.phan_loai_ke_hoach_2959);
  if (groupKey === "DEFAULT") {
    if (properties.ung_thua) return UNG_THUA_COLOR;
    if (properties.co_gcn) return GCN_COLOR;
  }
  return GROUP_COLORS[groupKey];
}

const MISSING_INFO_RULES = [
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

function getMissingInfo(dongBo) {
  if (!dongBo) return ["Chưa có dữ liệu đồng bộ cho thửa này"];
  return MISSING_INFO_RULES.filter((rule) => dongBo[rule.field]).map(
    (rule) => rule.label,
  );
}

function featureKey(feature) {
  if (feature.id !== null && feature.id !== undefined) {
    return `id:${String(feature.id)}`;
  }

  const p = feature.properties || {};
  return ["parcel", p.ma_xa, p.so_to, p.so_thua].join(":");
}

function googleMapsDirectionsUrl(feature) {
  const center = L.geoJSON(feature).getBounds().getCenter();
  return `https://www.google.com/maps/dir/?api=1&destination=${center.lat},${center.lng}`;
}

function FitBounds({ focusFeature, focusTick }) {
  const map = useMap();

  useEffect(() => {
    if (!focusFeature || focusTick === 0) return;

    map.fitBounds(L.geoJSON(focusFeature).getBounds(), {
      padding: [30, 30],
      maxZoom: 18,
    });

    // Chỉ chạy khi người dùng bấm chọn/phóng đến thửa.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusTick, map]);

  return null;
}

// Bắt lấy instance bản đồ Leaflet để các nút ở header (ngoài MapContainer)
// vẫn điều khiển được bản đồ.
function MapInstanceCapture({ onReady }) {
  const map = useMap();

  useEffect(() => {
    onReady(map);
  }, [map, onReady]);

  return null;
}

// =========================================================
// TRA CỨU THEO BỘ LỌC
//
// Không còn tự tải toàn tỉnh khi mở trang. Người dùng chọn mã xã
// (bắt buộc), nhóm, số tờ, số thửa rồi bấm "Tra cứu" mới gọi API.
// Component này chỉ chạy lại khi `filters` đổi tham chiếu (mỗi lần
// bấm Tra cứu tạo object filters mới, kể cả giữ nguyên giá trị).
// =========================================================

function SearchParcelsLoader({ filters, onData, onLoading, onError, onMeta }) {
  const map = useMap();

  useEffect(() => {
    if (!filters) return;

    const controller = new AbortController();

    const run = async () => {
      onLoading(true);
      onError("");
      onData(null);

      const baseParams = { ma_xa: filters.maXa };
      if (filters.nhom?.length) baseParams.nhom = filters.nhom.join(",");
      if (filters.soTo) baseParams.so_to = filters.soTo;
      if (filters.soThua) baseParams.so_thua = filters.soThua;

      const collected = [];
      const seen = new Set();

      try {
        for (
          let offset = 0;
          offset < MAX_FEATURES && !controller.signal.aborted;
          offset += PAGE_SIZE
        ) {
          const params = new URLSearchParams({
            ...baseParams,
            limit: String(PAGE_SIZE),
            offset: String(offset),
          });

          const response = await fetch(
            `${API_URL}/api/parcels/search?${params.toString()}`,
            { signal: controller.signal },
          );

          const result = await response.json();

          if (!response.ok) {
            throw new Error(result.error || "Không tải được dữ liệu thửa đất");
          }

          const features = result?.features || [];
          let added = 0;

          features.forEach((feature) => {
            const key = featureKey(feature);
            if (seen.has(key)) return;
            seen.add(key);
            collected.push(feature);
            added += 1;
          });

          onData({ type: "FeatureCollection", features: collected.slice() });
          onMeta({ loaded: collected.length });

          if (features.length < PAGE_SIZE) break;

          if (added === 0) {
            throw new Error(
              "Server trả về cùng một lô dữ liệu. Kiểm tra p_offset " +
                "trong hàm search_parcels.",
            );
          }

          await new Promise((resolve) => window.setTimeout(resolve, 60));
        }

        // Khớp bản đồ vào chính kết quả vừa tra cứu.
        if (collected.length > 0 && !controller.signal.aborted) {
          const bounds = L.geoJSON({
            type: "FeatureCollection",
            features: collected,
          }).getBounds();

          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [20, 20], maxZoom: 17 });
          }
        }
      } catch (error) {
        if (error.name !== "AbortError") onError(error.message);
      } finally {
        if (!controller.signal.aborted) onLoading(false);
      }
    };

    run();

    return () => controller.abort();
  }, [filters, map, onData, onLoading, onError, onMeta]);

  return null;
}

// =========================================================
// "QUANH VỊ TRÍ CỦA TÔI"
//
// Không biết trước mã xã, nên không dùng được /api/parcels/search.
// Dò dần bán kính quanh vị trí GPS bằng /api/parcels/count (chỉ đụng
// index GIST, rất nhẹ) tới khi đủ ~NEAR_ME_TARGET thửa, rồi mới gọi
// /api/parcels (bbox) một lần để lấy hình học.
// =========================================================

function NearMeLoader({ request, onData, onLoading, onError, onMeta }) {
  const map = useMap();

  useEffect(() => {
    if (!request) return;

    const controller = new AbortController();

    const run = async () => {
      onLoading(true);
      onError("");
      onData(null);
      onMeta({ loaded: 0 });

      const { lat, lng, nhom } = request;
      const nhomParam = nhom?.length ? nhom.join(",") : "";

      try {
        let chosenBounds = boundsForRadius(
          lat,
          lng,
          NEAR_ME_RADII_METERS[NEAR_ME_RADII_METERS.length - 1],
        );

        for (const radius of NEAR_ME_RADII_METERS) {
          if (controller.signal.aborted) return;

          const bounds = boundsForRadius(lat, lng, radius);
          chosenBounds = bounds;

          const countParams = new URLSearchParams({
            west: String(bounds.west),
            south: String(bounds.south),
            east: String(bounds.east),
            north: String(bounds.north),
            center_lng: String(lng),
            center_lat: String(lat),
          });
          if (nhomParam) countParams.set("nhom", nhomParam);

          const countResponse = await fetch(
            `${API_URL}/api/parcels/count?${countParams.toString()}`,
            { signal: controller.signal },
          );
          const countResult = await countResponse.json();

          if (!countResponse.ok) {
            throw new Error(
              countResult.error || "Không đếm được số thửa quanh vị trí",
            );
          }

          if ((countResult.total || 0) >= NEAR_ME_TARGET) break;
        }

        if (controller.signal.aborted) return;

        const params = new URLSearchParams({
          west: String(chosenBounds.west),
          south: String(chosenBounds.south),
          east: String(chosenBounds.east),
          north: String(chosenBounds.north),
          center_lng: String(lng),
          center_lat: String(lat),
          limit: String(NEAR_ME_TARGET),
          offset: "0",
          zoom: String(NEAR_ME_ZOOM),
        });
        if (nhomParam) params.set("nhom", nhomParam);

        const response = await fetch(
          `${API_URL}/api/parcels?${params.toString()}`,
          { signal: controller.signal },
        );
        const result = await response.json();

        if (!response.ok) {
          throw new Error(
            result.error || "Không tải được thửa đất quanh vị trí",
          );
        }

        const features = result?.features || [];
        onData({ type: "FeatureCollection", features });
        onMeta({ loaded: features.length });

        if (features.length > 0) {
          const bounds = L.geoJSON({
            type: "FeatureCollection",
            features,
          }).getBounds();

          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [20, 20], maxZoom: 18 });
          }
        }
      } catch (error) {
        if (error.name !== "AbortError") onError(error.message);
      } finally {
        if (!controller.signal.aborted) onLoading(false);
      }
    };

    run();

    return () => controller.abort();
  }, [request, map, onData, onLoading, onError, onMeta]);

  return null;
}

// =========================================================
// NÚT "TÌM THỬA QUANH ĐÂY"
//
// Zoom/kéo bản đồ tới khu vực muốn xem rồi bấm nút này: tải tối đa
// VIEWPORT_SEARCH_TARGET thửa quanh khung nhìn hiện tại, THAY THẾ toàn bộ
// dữ liệu đang hiển thị (các thửa ngoài khung nhìn mới bị bỏ đi). Đặt ở
// header nên nhận `map` qua prop thay vì useMap() — không còn là con của
// MapContainer.
// =========================================================

function FindHereButton({ map, nhom, onBeforeSearch, onData, onLoading, onError, onMeta }) {
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

    const params = new URLSearchParams({
      west: String(bounds.getWest()),
      south: String(bounds.getSouth()),
      east: String(bounds.getEast()),
      north: String(bounds.getNorth()),
      center_lng: String(center.lng),
      center_lat: String(center.lat),
      limit: String(VIEWPORT_SEARCH_TARGET),
      offset: "0",
      zoom: String(map.getZoom()),
    });
    if (nhomParam) params.set("nhom", nhomParam);

    try {
      const response = await fetch(`${API_URL}/api/parcels?${params.toString()}`);
      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.error || "Không tải được thửa đất quanh khu vực bản đồ",
        );
      }

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

function EmptyValue({ children }) {
  return children ? children : <span className="empty">Chưa có</span>;
}

function CurrentLocation({ onLocated, onPosition }) {
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

  // Không còn tự tải toàn tỉnh khi mở trang (giờ chờ người dùng chọn bộ
  // lọc), nên tự định vị ngay lúc mở để bản đồ khớp vào vị trí người dùng
  // trước tiên, thay vì đợi bấm nút "Vị trí của tôi".
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

export default function App({ onNavigateTools }) {
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [meta, setMeta] = useState({ loaded: 0 });
  const [focusTick, setFocusTick] = useState(0);
  const layerRef = useRef(null);

  // Instance bản đồ Leaflet, để các nút ở header (ngoài MapContainer) vẫn
  // gọi được map.getBounds()/fitBounds()...
  const [mapInstance, setMapInstance] = useState(null);

  // Ẩn header + sidebar trên điện thoại để xem trọn bản đồ (chỉ có tác
  // dụng ở màn hình hẹp, xem styles.css @media max-width: 760px).
  const [uiHidden, setUiHidden] = useState(false);

  // Độ mờ (fillOpacity) lớp phủ thửa đất — kéo slider 0-100%, mặc định 70%.
  const [parcelOpacity, setParcelOpacity] = useState(0.7);

  // Leaflet cache kích thước container, không tự phát hiện đổi kích thước
  // do CSS (ẩn header/sidebar) — phải tự gọi invalidateSize() sau khi
  // layout ổn định, nếu không nửa bản đồ mới lộ ra sẽ trống trơn.
  useEffect(() => {
    if (!mapInstance) return;
    const frame = window.requestAnimationFrame(() => mapInstance.invalidateSize());
    return () => window.cancelAnimationFrame(frame);
  }, [uiHidden, mapInstance]);

  // "Quanh vị trí của tôi": biết vị trí GPS ngay khi có (kể cả tự động lúc
  // mở trang), nhưng chỉ thật sự tải thửa đất khi người dùng bấm nút.
  const [myPosition, setMyPosition] = useState(null);
  const [nearMeRequest, setNearMeRequest] = useState(null);

  // Bộ lọc tra cứu: mã xã (bắt buộc), nhóm, số tờ, số thửa.
  const [xaOptions, setXaOptions] = useState([]);
  const [xaError, setXaError] = useState("");
  const [maXa, setMaXa] = useState("");
  const [xaQuery, setXaQuery] = useState("");
  const [xaDropdownOpen, setXaDropdownOpen] = useState(false);
  const [nhom, setNhom] = useState([]);
  const [soTo, setSoTo] = useState("");
  const [soThua, setSoThua] = useState("");
  const [submittedFilters, setSubmittedFilters] = useState(null);
  const [filtersOpen, setFiltersOpen] = useState(true);

  // Đánh dấu lần tìm gần nhất là bấm nút "Tìm thửa quanh đây" (theo khung
  // nhìn bản đồ), để phân biệt với tra cứu theo mã xã / định vị GPS.
  const [viewportSearchActive, setViewportSearchActive] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${API_URL}/api/parcels/xa-list`, { signal: controller.signal })
      .then((response) => response.json())
      .then((result) => {
        if (result?.error) throw new Error(result.error);
        setXaOptions(result?.items || []);
      })
      .catch((fetchError) => {
        if (fetchError.name !== "AbortError") setXaError(fetchError.message);
      });

    return () => controller.abort();
  }, []);

  const xaNameByCode = useMemo(() => {
    const map = {};
    xaOptions.forEach(({ ma_xa, ten_xa }) => {
      if (ma_xa) map[ma_xa] = ten_xa || ma_xa;
    });
    return map;
  }, [xaOptions]);

  const filteredXaOptions = useMemo(() => {
    const keyword = xaQuery.trim().toLocaleLowerCase("vi");
    if (!keyword) return xaOptions;

    return xaOptions.filter(
      ({ ma_xa, ten_xa }) =>
        (ten_xa || "").toLocaleLowerCase("vi").includes(keyword) ||
        (ma_xa || "").toLocaleLowerCase("vi").includes(keyword),
    );
  }, [xaOptions, xaQuery]);

  const handleSelectXa = useCallback((code, name) => {
    setMaXa(code);
    setXaQuery(name || code);
    setXaDropdownOpen(false);
  }, []);

  const handleToggleNhom = useCallback((code) => {
    setNhom((current) =>
      current.includes(code)
        ? current.filter((value) => value !== code)
        : [...current, code],
    );
  }, []);

  const handleData = useCallback((result) => setData(result), []);
  const handleLoading = useCallback((value) => setLoading(value), []);
  const handleError = useCallback((message) => setError(message), []);
  const handleMeta = useCallback((value) => setMeta(value), []);

  const handleSearch = useCallback(() => {
    if (!maXa) return;

    setSelected(null);
    setQuery("");
    setNearMeRequest(null);
    setViewportSearchActive(false);
    setSubmittedFilters({
      maXa,
      nhom,
      soTo: soTo.trim(),
      soThua: soThua.trim(),
    });
    setFiltersOpen(false);
  }, [maXa, nhom, soTo, soThua]);

  const handleNearMe = useCallback(() => {
    if (!myPosition) return;

    setSelected(null);
    setQuery("");
    setSubmittedFilters(null);
    setViewportSearchActive(false);
    setFiltersOpen(false);
    setNearMeRequest({ ...myPosition, nhom, tick: Date.now() });
  }, [myPosition, nhom]);

  // Gọi trước khi FindHereButton bắt đầu tải, để dọn các trạng thái tra cứu
  // khác (mã xã / định vị GPS) và đánh dấu chế độ hiện tại là "quanh đây".
  const handleFindHereStart = useCallback(() => {
    setSelected(null);
    setQuery("");
    setSubmittedFilters(null);
    setNearMeRequest(null);
    setViewportSearchActive(true);
    setFiltersOpen(false);
  }, []);

  const handleResetFilters = useCallback(() => {
    setMaXa("");
    setXaQuery("");
    setXaDropdownOpen(false);
    setNhom([]);
    setSoTo("");
    setSoThua("");
    setSubmittedFilters(null);
    setNearMeRequest(null);
    setViewportSearchActive(false);
    setFiltersOpen(true);
    setSelected(null);
    setQuery("");
    setData(null);
    setError("");
    setMeta({ loaded: 0 });
  }, []);

  const handleSelectParcel = useCallback((feature) => {
    setSelected({ id: feature.id, feature, ...feature.properties });
    setFocusTick((value) => value + 1);
  }, []);

  // Form "Ứng thửa MPLIS" trong khung thông tin thửa đất — nạp lại mỗi khi
  // đổi thửa đang chọn (kể cả bỏ chọn), để không lẫn dữ liệu giữa các thửa.
  const [ungThuaForm, setUngThuaForm] = useState({
    to_thua_mplis: "",
    so_giay_chung_nhan: "",
    ma_don_mplis: "",
  });
  const [ungThuaSaving, setUngThuaSaving] = useState(false);
  const [ungThuaError, setUngThuaError] = useState("");

  useEffect(() => {
    setUngThuaForm({
      to_thua_mplis: selected?.ung_thua?.to_thua_mplis || "",
      so_giay_chung_nhan: selected?.ung_thua?.so_giay_chung_nhan || "",
      ma_don_mplis: selected?.ung_thua?.ma_don_mplis || "",
    });
    setUngThuaError("");
  }, [selected?.id]);

  const handleSaveUngThua = useCallback(async () => {
    if (!selected || !ungThuaForm.to_thua_mplis.trim()) return;

    setUngThuaSaving(true);
    setUngThuaError("");

    try {
      const response = await fetch(`${API_URL}/api/ung-thua`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ma_xa: selected.ma_xa,
          so_to: selected.so_to,
          so_thua: selected.so_thua,
          to_thua_mplis: ungThuaForm.to_thua_mplis.trim(),
          so_giay_chung_nhan: ungThuaForm.so_giay_chung_nhan.trim(),
          ma_don_mplis: ungThuaForm.ma_don_mplis.trim(),
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Lưu thất bại");

      const savedUngThua = {
        to_thua_mplis: body.item?.to_thua_mplis ?? ungThuaForm.to_thua_mplis.trim(),
        so_giay_chung_nhan:
          body.item?.so_giay_chung_nhan ?? (ungThuaForm.so_giay_chung_nhan.trim() || null),
        ma_don_mplis: body.item?.ma_don_mplis ?? (ungThuaForm.ma_don_mplis.trim() || null),
      };

      // Cập nhật ngay dữ liệu đang có (data/selected) để bản đồ đổi màu
      // vàng tức thì, không phải tải lại toàn bộ thửa từ server.
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          features: prev.features.map((f) =>
            f.id === selected.id
              ? { ...f, properties: { ...f.properties, ung_thua: savedUngThua } }
              : f,
          ),
        };
      });
      setSelected((prev) => (prev ? { ...prev, ung_thua: savedUngThua } : prev));
    } catch (err) {
      setUngThuaError(err.message);
    } finally {
      setUngThuaSaving(false);
    }
  }, [selected, ungThuaForm]);

  const filtered = useMemo(() => {
    if (!data) return null;

    const keyword = query.trim().toLocaleLowerCase("vi");
    if (!keyword) return data;

    return {
      ...data,
      features: data.features.filter(({ properties: p }) =>
        [
          p.so_to,
          p.so_thua,
          `${p.so_to}/${p.so_thua}`,
          p.ma_xa,
          xaNameByCode[p.ma_xa],
          p.muc_dich_su_dung,
        ]
          .filter((value) => value !== null && value !== undefined)
          .some((value) =>
            String(value).toLocaleLowerCase("vi").includes(keyword),
          ),
      ),
    };
  }, [data, query, xaNameByCode]);

  const selectedFeature = selected?.feature || null;

  const style = useCallback(
    (feature) => {
      const isSelected = feature.id === selected?.id;

      return {
        color: isSelected ? "#ffffff" : "#334155",
        weight: isSelected ? 4 : 1.5,
        fillColor: isSelected
          ? "#2563eb"
          : getParcelFillColor(feature.properties),
        // Slider "Độ mờ thửa đất" điều khiển lớp chưa chọn; thửa đang
        // chọn luôn đậm hơn một chút (+0.2) để vẫn nổi bật, tối đa 1.
        fillOpacity: isSelected
          ? Math.min(1, parcelOpacity + 0.2)
          : parcelOpacity,
      };
    },
    [selected, parcelOpacity],
  );

  const onEachFeature = useCallback(
    (feature, layer) => {
      const p = feature.properties;

      layer.bindTooltip(`Tờ ${p.so_to} · Thửa ${p.so_thua}`, {
        sticky: true,
        direction: "top",
      });

      layer.on("click", () => handleSelectParcel(feature));
    },
    [handleSelectParcel],
  );

  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;

    layer.clearLayers();

    if (filtered) {
      layer.addData(filtered);
      layer.setStyle(style);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ tạo lại
    // layer khi đổi dữ liệu; đổi style một mình (kéo slider độ mờ, chọn
    // thửa) đã có effect setStyle() riêng bên dưới, không cần clear+addData
    // lại toàn bộ (tốn, giật khi kéo slider).
  }, [filtered]);

  // Áp style riêng (không clear+addData) mỗi khi style đổi — mượt hơn khi
  // kéo slider độ mờ hoặc đổi thửa đang chọn.
  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;
    layer.setStyle(style);
  }, [style]);

  const shownCount = filtered?.features?.length ?? 0;
  const isFiltering = query.trim().length > 0;
  const hasActiveQuery = Boolean(
    submittedFilters || nearMeRequest || viewportSearchActive,
  );

  return (
    <main className={`shell${uiHidden ? " uiHidden" : ""}`}>
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div className="topbarTitle">
          <h1>Bản đồ phân loại thửa đất</h1>
          <p>VN-2000 Đắk Lắk · Dữ liệu Supabase</p>
        </div>
        <div className="count">
          <strong>{shownCount.toLocaleString("vi-VN")}</strong>
          <span>
            {!hasActiveQuery
              ? "chưa tra cứu"
              : isFiltering && meta.loaded > shownCount
                ? `/ ${meta.loaded.toLocaleString("vi-VN")} thửa`
                : "thửa hiển thị"}
          </span>
        </div>

        <FindHereButton
          map={mapInstance}
          nhom={nhom}
          onBeforeSearch={handleFindHereStart}
          onData={handleData}
          onLoading={handleLoading}
          onError={handleError}
          onMeta={handleMeta}
        />

        <a
          className="backLink"
          href="/tools"
          onClick={(event) => {
            event.preventDefault();
            onNavigateTools?.();
          }}
        >
          ⚙ Công cụ
        </a>
      </header>

      <section className="workspace">
        <aside className="sidebar">
          <div className="filterHeader">
            <div>
              <strong>Bộ lọc dữ liệu</strong>
              <span>Chọn điều kiện rồi bấm Tra cứu</span>
            </div>

            {hasActiveQuery && (
              <button
                type="button"
                className="filterToggle"
                onClick={() => setFiltersOpen((value) => !value)}
              >
                {filtersOpen ? "Ẩn bộ lọc" : "Đổi bộ lọc"}
              </button>
            )}
          </div>

          {!filtersOpen && submittedFilters && (
            <div className="filterSummary">
              <span className="tag">
                {xaNameByCode[submittedFilters.maXa] || submittedFilters.maXa}
              </span>
              {submittedFilters.nhom?.map((code) => (
                <span key={code} className="tag">
                  {GROUP_LABELS[code] || code}
                </span>
              ))}
              {submittedFilters.soTo && (
                <span className="tag">Tờ {submittedFilters.soTo}</span>
              )}
              {submittedFilters.soThua && (
                <span className="tag">Thửa {submittedFilters.soThua}</span>
              )}
            </div>
          )}

          {!filtersOpen && nearMeRequest && (
            <div className="filterSummary">
              <span className="tag">📍 Quanh vị trí của bạn</span>
              {nearMeRequest.nhom?.map((code) => (
                <span key={code} className="tag">
                  {GROUP_LABELS[code] || code}
                </span>
              ))}
            </div>
          )}

          {!filtersOpen && viewportSearchActive && (
            <div className="filterSummary">
              <span className="tag">🔍 Quanh khu vực bản đồ</span>
              {nhom.map((code) => (
                <span key={code} className="tag">
                  {GROUP_LABELS[code] || code}
                </span>
              ))}
            </div>
          )}

          {filtersOpen && (
            <>
              <label>Nhóm (áp dụng cho cả 2 cách tìm bên dưới, có thể chọn nhiều)</label>
              <div className="nhomCheckboxes">
                {Object.keys(GROUP_LABELS).map((code) => (
                  <label key={code} className="nhomCheckbox">
                    <input
                      type="checkbox"
                      checked={nhom.includes(code)}
                      onChange={() => handleToggleNhom(code)}
                    />
                    {GROUP_LABELS[code]}
                  </label>
                ))}
              </div>

              <button
                type="button"
                className="nearMeButton"
                onClick={handleNearMe}
                disabled={!myPosition || loading}
              >
                📍 Xem ~{NEAR_ME_TARGET.toLocaleString("vi-VN")} thửa quanh vị trí của tôi
              </button>

              {!myPosition && (
                <div className="nearMeHint">Đang chờ định vị GPS…</div>
              )}

              <div className="filterDivider">
                <span>hoặc lọc theo mã xã</span>
              </div>

              <label htmlFor="filterMaXa">Xã / phường</label>
              <div className="comboBox">
                <input
                  id="filterMaXa"
                  type="text"
                  className="filterInput"
                  autoComplete="off"
                  value={xaQuery}
                  placeholder="Nhập tên xã/phường để tìm…"
                  onChange={(event) => {
                    setXaQuery(event.target.value);
                    setMaXa("");
                    setXaDropdownOpen(true);
                  }}
                  onFocus={() => setXaDropdownOpen(true)}
                  onBlur={() => setXaDropdownOpen(false)}
                />

                {xaDropdownOpen && (
                  <div className="comboBoxList">
                    {filteredXaOptions.length === 0 ? (
                      <div className="comboBoxEmpty">
                        Không tìm thấy xã/phường
                      </div>
                    ) : (
                      filteredXaOptions.map(({ ma_xa, ten_xa }) => (
                        <div
                          key={ma_xa}
                          className={`comboBoxItem${
                            ma_xa === maXa ? " active" : ""
                          }`}
                          onMouseDown={(event) => {
                            event.preventDefault();
                            handleSelectXa(ma_xa, ten_xa);
                          }}
                        >
                          {ten_xa || ma_xa}
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>

              <div className="filterRow">
                <div>
                  <label htmlFor="filterSoTo">Số tờ</label>
                  <input
                    id="filterSoTo"
                    className="filterInput"
                    inputMode="numeric"
                    value={soTo}
                    onChange={(event) => setSoTo(event.target.value)}
                    placeholder="VD: 12"
                  />
                </div>

                <div>
                  <label htmlFor="filterSoThua">Số thửa</label>
                  <input
                    id="filterSoThua"
                    className="filterInput"
                    inputMode="numeric"
                    value={soThua}
                    onChange={(event) => setSoThua(event.target.value)}
                    placeholder="VD: 34"
                  />
                </div>
              </div>

              <div className="filterActions">
                <button
                  type="button"
                  className="searchButton"
                  onClick={handleSearch}
                  disabled={!maXa || loading}
                >
                  Tra cứu
                </button>

                {hasActiveQuery && (
                  <button
                    type="button"
                    className="resetButton"
                    onClick={handleResetFilters}
                  >
                    Xóa lọc
                  </button>
                )}
              </div>
            </>
          )}

          {xaError && (
            <div className="notice error">
              <strong>Không tải được danh sách mã xã</strong>
              <span>{xaError}</span>
            </div>
          )}

          {loading && (
            <div className="notice">
              {meta.loaded > 0
                ? `Đang tải… ${meta.loaded.toLocaleString("vi-VN")} thửa`
                : "Đang tra cứu Supabase…"}
            </div>
          )}

          {!loading && !error && !hasActiveQuery && (
            <div className="filterPlaceholder">
              <div>☷</div>
              <strong>Chưa tra cứu</strong>
              <span>
                Bấm "Xem thửa quanh vị trí của tôi", hoặc chọn mã xã (và nhóm,
                số tờ, số thửa nếu cần) rồi bấm Tra cứu để xem thửa đất.
              </span>
            </div>
          )}

          {!loading &&
            !error &&
            hasActiveQuery &&
            shownCount === 0 &&
            !isFiltering && (
              <div className="notice">
                <strong>Không tìm thấy thửa nào</strong>
                <span>
                  {submittedFilters
                    ? "Hãy đổi mã xã, nhóm, số tờ hoặc số thửa rồi tra cứu lại."
                    : viewportSearchActive
                      ? "Không có thửa đất nào quanh khu vực bản đồ đang xem."
                      : "Không có thửa đất nào quanh vị trí của bạn."}
                </span>
              </div>
            )}

          {error && (
            <div className="notice error">
              <strong>Chưa kết nối được dữ liệu</strong>
              <span>{error}</span>
            </div>
          )}

          {data && (
            <>
              <label htmlFor="search">Lọc nhanh trong kết quả</label>

              <div className="searchBox">
                <span>⌕</span>

                <input
                  id="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Số tờ, số thửa, mã xã, loại đất…"
                />

                {query && (
                  <button type="button" onClick={() => setQuery("")}>
                    ×
                  </button>
                )}
              </div>

              <div className="parcelListHeader">
                Danh sách thửa ({shownCount.toLocaleString("vi-VN")})
              </div>

              <div className="parcelList">
                {filtered.features.length === 0 ? (
                  <div className="parcelListEmpty">
                    Không có thửa nào khớp bộ lọc nhanh.
                  </div>
                ) : (
                  filtered.features.map((feature) => {
                    const p = feature.properties;
                    const isActive = feature.id === selected?.id;

                    return (
                      <button
                        key={featureKey(feature)}
                        type="button"
                        className={`parcelListItem${isActive ? " active" : ""}`}
                        onClick={() => handleSelectParcel(feature)}
                      >
                        <span
                          className="parcelListDot"
                          style={{ backgroundColor: getParcelFillColor(p) }}
                        />
                        <span className="parcelListLabel">
                          Tờ {p.so_to} · Thửa {p.so_thua}
                        </span>
                        <span className="parcelListXa">
                          {xaNameByCode[p.ma_xa] || p.ma_xa}
                        </span>
                      </button>
                    );
                  })
                )}
              </div>
            </>
          )}
        </aside>

        <div className="mapWrap">
          <button
            type="button"
            className="uiToggleButton"
            onClick={() => setUiHidden((value) => !value)}
            title={uiHidden ? "Hiện thanh công cụ" : "Ẩn thanh công cụ"}
          >
            {uiHidden ? "☰" : "✕"}
          </button>

          <MapContainer
            center={[12.67, 108.05]}
            zoom={15}
            zoomControl={false}
            className="map"
            // Canvas thay cho SVG: vẽ hàng nghìn polygon vẫn mượt.
            preferCanvas
          >
            <SearchParcelsLoader
              filters={submittedFilters}
              onData={handleData}
              onLoading={handleLoading}
              onError={handleError}
              onMeta={handleMeta}
            />

            <NearMeLoader
              request={nearMeRequest}
              onData={handleData}
              onLoading={handleLoading}
              onError={handleError}
              onMeta={handleMeta}
            />

            <MapInstanceCapture onReady={setMapInstance} />

            <CurrentLocation onPosition={setMyPosition} />

            <ZoomControl position="bottomright" />

            <LayersControl position="topright">
              <LayersControl.BaseLayer name="OpenStreetMap">
                <TileLayer
                  url={OSM_TILE_URL}
                  minZoom={0}
                  maxZoom={19}
                  attribution="&copy; OpenStreetMap contributors"
                />
              </LayersControl.BaseLayer>

              <LayersControl.BaseLayer checked name="Vệ tinh (Google)">
                <TileLayer
                  url={GOOGLE_HYBRID_URL}
                  subdomains={GOOGLE_SUBDOMAINS}
                  minZoom={0}
                  maxZoom={21}
                  maxNativeZoom={20}
                  attribution="&copy; Google"
                />
              </LayersControl.BaseLayer>

              <LayersControl.BaseLayer name="Vệ tinh trần (Google)">
                <TileLayer
                  url={GOOGLE_SATELLITE_URL}
                  subdomains={GOOGLE_SUBDOMAINS}
                  minZoom={0}
                  maxZoom={21}
                  maxNativeZoom={20}
                  attribution="&copy; Google"
                />
              </LayersControl.BaseLayer>

              <LayersControl.BaseLayer name="Vệ tinh (Esri)">
                <TileLayer
                  url={ESRI_IMAGERY_URL}
                  minZoom={0}
                  maxZoom={19}
                  attribution="&copy; Esri, Maxar, Earthstar Geographics"
                />
              </LayersControl.BaseLayer>

              <LayersControl.BaseLayer name="Vietbando">
                <TileLayer
                  url={`${API_URL}/api/tiles/{z}/{x}/{y}`}
                  minZoom={0}
                  maxZoom={18}
                  attribution="&copy; Vietbando"
                />
              </LayersControl.BaseLayer>

              <LayersControl.Overlay checked name="Thửa đất">
                <GeoJSON
                  ref={layerRef}
                  data={{ type: "FeatureCollection", features: [] }}
                  style={style}
                  onEachFeature={onEachFeature}
                />
              </LayersControl.Overlay>
            </LayersControl>

            <FitBounds focusFeature={selectedFeature} focusTick={focusTick} />
          </MapContainer>

          <div className="mapHint">Bấm vào ranh thửa để xem thông tin</div>

          <div className="landLegend">
            <strong>Ghi chú</strong>

            {["NHÓM 1", "NHÓM 2"].map((code) => (
              <div key={code}>
                <span style={{ backgroundColor: GROUP_COLORS[code] }} />
                <label>{GROUP_LABELS[code]}</label>
              </div>
            ))}

            <div>
              <span style={{ backgroundColor: GCN_COLOR }} />
              <label>{GCN_LABEL}</label>
            </div>

            <div>
              <span style={{ backgroundColor: UNG_THUA_COLOR }} />
              <label>{UNG_THUA_LABEL}</label>
            </div>

            <div>
              <span style={{ backgroundColor: GROUP_COLORS.DEFAULT }} />
              <label>{GROUP_LABELS.DEFAULT}</label>
            </div>

            <div className="opacitySlider">
              <label htmlFor="parcelOpacity">
                Độ mờ thửa đất
                <span>{Math.round(parcelOpacity * 100)}%</span>
              </label>
              <input
                id="parcelOpacity"
                type="range"
                min="0"
                max="100"
                value={Math.round(parcelOpacity * 100)}
                onChange={(event) =>
                  setParcelOpacity(Number(event.target.value) / 100)
                }
              />
            </div>
          </div>

          {selected && (
            <aside className="parcelDrawer">
              <div className="drawerHeader">
                <div>
                  <strong>Thông tin thửa đất</strong>
                  <span>Chi tiết thửa đang chọn</span>
                </div>

                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  aria-label="Đóng thông tin thửa đất"
                >
                  ×
                </button>
              </div>

              <div className="parcelCard">
                <div className="parcelId">
                  <div>
                    <small>Số tờ</small>
                    <strong>{selected.so_to}</strong>
                  </div>

                  <span>/</span>

                  <div>
                    <small>Số thửa</small>
                    <strong>{selected.so_thua}</strong>
                  </div>
                </div>

                <dl>
                  <div>
                    <dt>Xã / phường</dt>
                    <dd>
                      <EmptyValue>
                        {xaNameByCode[selected.ma_xa] || selected.ma_xa}
                      </EmptyValue>
                    </dd>
                  </div>

                  <div>
                    <dt>Mục đích</dt>
                    <dd>
                      <span className="tag">{selected.muc_dich_su_dung}</span>
                    </dd>
                  </div>

                  <div>
                    <dt>Diện tích</dt>
                    <dd>
                      {Number(selected.dien_tich).toLocaleString("vi-VN")} m²
                    </dd>
                  </div>

                  <div>
                    <dt>Phân loại KH 2959</dt>
                    <dd>
                      <span
                        className="tag"
                        style={{
                          color: "white",
                          backgroundColor: getGroupColor(
                            selected.dong_bo?.phan_loai_ke_hoach_2959,
                          ),
                        }}
                      >
                        {selected.dong_bo?.phan_loai_ke_hoach_2959 ||
                          GROUP_LABELS[
                            getGroupKey(
                              selected.dong_bo?.phan_loai_ke_hoach_2959,
                            )
                          ]}
                      </span>
                    </dd>
                  </div>

                  <div>
                    <dt>Dữ liệu GCN</dt>
                    <dd>
                      <span
                        className="tag"
                        style={{
                          color: selected.co_gcn ? "white" : "#334155",
                          backgroundColor: selected.co_gcn
                            ? GCN_COLOR
                            : "#e2e8f0",
                        }}
                      >
                        {selected.co_gcn ? GCN_LABEL : "Thửa đất chưa nhập biểu"}
                      </span>
                    </dd>
                  </div>
                </dl>

                <div className="ungThuaBox">
                  <strong>Ứng thửa MPLIS</strong>

                  {selected.ung_thua ? (
                    <span
                      className="tag"
                      style={{ color: "#713f12", backgroundColor: UNG_THUA_COLOR }}
                    >
                      {UNG_THUA_LABEL}
                    </span>
                  ) : (
                    <span className="empty">
                      Thửa chưa được đối chiếu với MPLIS
                    </span>
                  )}

                  <label htmlFor="ungThuaToThua">Tờ thửa trên MPLIS</label>
                  <input
                    id="ungThuaToThua"
                    className="filterInput"
                    value={ungThuaForm.to_thua_mplis}
                    placeholder="VD: Tờ 12 - Thửa 34"
                    onChange={(event) =>
                      setUngThuaForm((prev) => ({
                        ...prev,
                        to_thua_mplis: event.target.value,
                      }))
                    }
                  />

                  <label htmlFor="ungThuaSoGcn">Số giấy chứng nhận</label>
                  <input
                    id="ungThuaSoGcn"
                    className="filterInput"
                    value={ungThuaForm.so_giay_chung_nhan}
                    onChange={(event) =>
                      setUngThuaForm((prev) => ({
                        ...prev,
                        so_giay_chung_nhan: event.target.value,
                      }))
                    }
                  />

                  <label htmlFor="ungThuaMaDon">Mã đơn trên MPLIS (nếu có)</label>
                  <input
                    id="ungThuaMaDon"
                    className="filterInput"
                    value={ungThuaForm.ma_don_mplis}
                    onChange={(event) =>
                      setUngThuaForm((prev) => ({
                        ...prev,
                        ma_don_mplis: event.target.value,
                      }))
                    }
                  />

                  {ungThuaError && <span className="empty">{ungThuaError}</span>}

                  <button
                    type="button"
                    className="searchButton"
                    disabled={!ungThuaForm.to_thua_mplis.trim() || ungThuaSaving}
                    onClick={handleSaveUngThua}
                  >
                    {ungThuaSaving
                      ? "Đang lưu…"
                      : selected.ung_thua
                        ? "Cập nhật"
                        : "Lưu"}
                  </button>
                </div>

                <div className="missingInfo">
                  <strong>Thông tin còn thiếu</strong>

                  {getMissingInfo(selected.dong_bo).length ? (
                    <ul>
                      {getMissingInfo(selected.dong_bo).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="missingInfoOk">Đầy đủ thông tin đồng bộ</span>
                  )}
                </div>

                <button
                  type="button"
                  className="zoomButton"
                  onClick={() => setFocusTick((value) => value + 1)}
                >
                  Phóng đến thửa
                </button>

                {selectedFeature && (
                  <a
                    className="directionsButton"
                    href={googleMapsDirectionsUrl(selectedFeature)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    🧭 Chỉ đường Google Maps
                  </a>
                )}
              </div>
            </aside>
          )}
        </div>
      </section>
    </main>
  );
}