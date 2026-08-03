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
  DEFAULT: "Chưa phân loại / chưa có dữ liệu đồng bộ",
};

function getGroupKey(phanLoai = "") {
  const normalized = phanLoai.trim().toUpperCase();
  return GROUP_COLORS[normalized] ? normalized : "DEFAULT";
}

function getGroupColor(phanLoai = "") {
  return GROUP_COLORS[getGroupKey(phanLoai)];
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

// Nút đưa bản đồ tới phạm vi lớp phủ địa chính (MBTiles), lấy từ
// /api/tiles/diachinh/metadata. Không hiện nếu chưa có bounds (ví dụ chưa
// có file .mbtiles trong backend/data).
function DiaChinhFitButton({ bounds }) {
  const map = useMap();

  if (!bounds) return null;

  return (
    <button
      type="button"
      className="diaChinhButton"
      onClick={() => map.fitBounds(bounds, { padding: [40, 40] })}
      title="Đưa bản đồ tới phạm vi lớp địa chính"
    >
      🗺️ Vùng địa chính
    </button>
  );
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

export default function App({
  onNavigateTools,
  onNavigateImport,
  onNavigateSync,
  onNavigateMbtiles,
}) {
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [meta, setMeta] = useState({ loaded: 0 });
  const [focusTick, setFocusTick] = useState(0);
  const layerRef = useRef(null);

  // "Quanh vị trí của tôi": biết vị trí GPS ngay khi có (kể cả tự động lúc
  // mở trang), nhưng chỉ thật sự tải thửa đất khi người dùng bấm nút.
  const [myPosition, setMyPosition] = useState(null);
  const [nearMeRequest, setNearMeRequest] = useState(null);

  // Lớp phủ địa chính (MBTiles) — chỉ lấy bounds để có nút "đến vùng địa
  // chính"; không báo lỗi nếu thiếu, đây là lớp bổ sung tùy chọn.
  const [diaChinhBounds, setDiaChinhBounds] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${API_URL}/api/tiles/diachinh/metadata`, {
      signal: controller.signal,
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((result) => {
        if (!result?.bounds) return;

        const parts = result.bounds.split(",").map(Number);
        if (parts.length !== 4 || parts.some(Number.isNaN)) return;

        const [west, south, east, north] = parts;
        setDiaChinhBounds([
          [south, west],
          [north, east],
        ]);
      })
      .catch(() => {});

    return () => controller.abort();
  }, []);

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
    setFiltersOpen(false);
    setNearMeRequest({ ...myPosition, nhom, tick: Date.now() });
  }, [myPosition, nhom]);

  const handleResetFilters = useCallback(() => {
    setMaXa("");
    setXaQuery("");
    setXaDropdownOpen(false);
    setNhom([]);
    setSoTo("");
    setSoThua("");
    setSubmittedFilters(null);
    setNearMeRequest(null);
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
          : getGroupColor(feature.properties?.dong_bo?.phan_loai_ke_hoach_2959),
        fillOpacity: isSelected ? 0.75 : 0.55,
      };
    },
    [selected],
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
  }, [filtered, style]);

  const shownCount = filtered?.features?.length ?? 0;
  const isFiltering = query.trim().length > 0;
  const hasActiveQuery = Boolean(submittedFilters || nearMeRequest);

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Bản đồ thửa đất</h1>
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
        <a
          className="backLink"
          href="/tools"
          onClick={(event) => {
            event.preventDefault();
            onNavigateTools?.();
          }}
        >
          ⬇ Tải công cụ
        </a>
        <a
          className="backLink"
          href="/import-gml"
          onClick={(event) => {
            event.preventDefault();
            onNavigateImport?.();
          }}
        >
          ⇪ Nhập GML
        </a>
        <a
          className="backLink"
          href="/import-dong-bo"
          onClick={(event) => {
            event.preventDefault();
            onNavigateSync?.();
          }}
        >
          ⇪ Nhập đồng bộ
        </a>
        <a
          className="backLink"
          href="/mbtiles"
          onClick={(event) => {
            event.preventDefault();
            onNavigateMbtiles?.();
          }}
        >
          ⇪ Quản lý MBTiles
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
                          style={{
                            backgroundColor: getGroupColor(
                              p.dong_bo?.phan_loai_ke_hoach_2959,
                            ),
                          }}
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

              <LayersControl.Overlay name="Địa chính (MBTiles)">
                <TileLayer
                  url={`${API_URL}/api/tiles/diachinh/{z}/{x}/{y}.png`}
                  opacity={0.8}
                  zIndex={5}
                  attribution="Địa chính"
                />
              </LayersControl.Overlay>

              <LayersControl.Overlay checked name="Thửa đất">
                <GeoJSON
                  ref={layerRef}
                  data={{ type: "FeatureCollection", features: [] }}
                  style={style}
                  onEachFeature={onEachFeature}
                />
              </LayersControl.Overlay>
            </LayersControl>

            <DiaChinhFitButton bounds={diaChinhBounds} />

            <FitBounds focusFeature={selectedFeature} focusTick={focusTick} />
          </MapContainer>

          <div className="mapHint">Bấm vào ranh thửa để xem thông tin</div>

          <div className="landLegend">
            <strong>Phân loại KH 2959/KH-BNNMT-BCA</strong>

            {Object.entries(GROUP_LABELS).map(([code, label]) => (
              <div key={code}>
                <span style={{ backgroundColor: GROUP_COLORS[code] }} />
                <label>{label}</label>
              </div>
            ))}
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
                </dl>

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