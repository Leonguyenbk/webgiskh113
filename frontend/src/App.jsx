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
  CircleMarker,
  GeoJSON,
  LayersControl,
  MapContainer,
  Popup,
  TileLayer,
  ZoomControl,
  useMap,
} from "react-leaflet";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

const OSM_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

// Số thửa mỗi lô. Giữ dưới MAX_PAGE_SIZE của backend (3000),
// vượt qua thì backend tự kẹp lại và vòng lặp hiểu nhầm là đã hết dữ liệu.
const PAGE_SIZE = 1000;

// Chốt an toàn cho vòng lặp phân trang. Không phải giới hạn hiển thị:
// chỉ để phòng trường hợp server phân trang sai và lặp vô tận.
const MAX_FEATURES = 50000;

// Nới khung quanh phạm vi dữ liệu để không sót thửa nằm sát mép, đơn vị độ.
const EXTENT_PADDING = 0.01;

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

// =========================================================
// TẢI TOÀN BỘ THỬA MỘT LƯỢT
//
// Với quy mô vài nghìn thửa, tải theo khung bản đồ là thừa và
// gây ra chuyện bản đồ trắng trơn khi người dùng đứng ở vùng
// chưa có dữ liệu. Component này hỏi phạm vi dữ liệu trước,
// nhảy bản đồ tới đó, rồi tải hết trong một lượt.
// Không nghe sự kiện moveend, kéo bản đồ không gọi lại API.
// =========================================================

function AllParcelsLoader({ onData, onLoading, onError, onMeta }) {
  const map = useMap();

  useEffect(() => {
    const controller = new AbortController();

    const run = async () => {
      onLoading(true);
      onError("");

      try {
        // Bước 1: hỏi dữ liệu nằm ở đâu.
        const extentResponse = await fetch(`${API_URL}/api/parcels/extent`, {
          signal: controller.signal,
        });

        if (!extentResponse.ok) {
          throw new Error(
            "Không xác định được phạm vi dữ liệu. Kiểm tra hàm " +
              "get_parcels_extent trên Supabase.",
          );
        }

        const extent = await extentResponse.json();

        if (
          !extent ||
          typeof extent.west !== "number" ||
          typeof extent.south !== "number"
        ) {
          throw new Error("Bảng thửa đất chưa có dữ liệu");
        }

        // Bước 2: nhảy bản đồ tới vùng có thửa.
        map.fitBounds(
          [
            [extent.south, extent.west],
            [extent.north, extent.east],
          ],
          { padding: [20, 20], maxZoom: 17 },
        );

        // Bước 3: tải hết thửa trong phạm vi đó.
        const baseParams = {
          west: String(extent.west - EXTENT_PADDING),
          south: String(extent.south - EXTENT_PADDING),
          east: String(extent.east + EXTENT_PADDING),
          north: String(extent.north + EXTENT_PADDING),
          center_lng: String((extent.west + extent.east) / 2),
          center_lat: String((extent.south + extent.north) / 2),

          // Zoom cao nhất: giữ nguyên hình học, không giản lược.
          zoom: "18",
        };

        const collected = [];
        const seen = new Set();

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
            `${API_URL}/api/parcels?${params.toString()}`,
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

          // Vẽ dần từng lô để người dùng thấy tiến độ.
          onData({ type: "FeatureCollection", features: collected.slice() });
          onMeta({ loaded: collected.length });

          // Lô cuối: server trả về ít hơn một trang đầy.
          if (features.length < PAGE_SIZE) break;

          // Lô đầy nhưng không thửa nào mới nghĩa là server bỏ qua offset.
          if (added === 0) {
            throw new Error(
              "Server trả về cùng một lô dữ liệu. Hãy kiểm tra tham số " +
                "p_offset trong hàm get_parcels_in_view.",
            );
          }

          // Nhường luồng cho trình duyệt vẽ xong lô vừa nhận.
          await new Promise((resolve) => window.setTimeout(resolve, 60));
        }
      } catch (error) {
        if (error.name !== "AbortError") onError(error.message);
      } finally {
        if (!controller.signal.aborted) onLoading(false);
      }
    };

    run();

    return () => controller.abort();
  }, [map, onData, onLoading, onError, onMeta]);

  return null;
}

function EmptyValue({ children }) {
  return children ? children : <span className="empty">Chưa có</span>;
}

function CurrentLocation({ onLocated }) {
  const map = useMap();
  const [position, setPosition] = useState(null);
  const [accuracy, setAccuracy] = useState(0);
  const [locationError, setLocationError] = useState("");

  const locateMe = () => {
    setLocationError("");

    if (!window.isSecureContext) {
      setLocationError("Định vị cần HTTPS hoặc localhost.");
      return;
    }

    if (!navigator.geolocation) {
      setLocationError("Thiết bị không hỗ trợ định vị.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const currentPosition = [coords.latitude, coords.longitude];
        setPosition(currentPosition);
        setAccuracy(coords.accuracy || 0);
        map.flyTo(currentPosition, 18, { animate: true, duration: 1.2 });
        onLocated?.();
      },
      (geoError) => {
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
  };

  // Không tự định vị lúc mở trang: việc đó kéo bản đồ về chỗ người dùng
  // đang đứng và đè lên khung dữ liệu vừa khớp xong.
  // Người dùng bấm nút "Vị trí của tôi" khi cần.

  return (
    <>
      <button
        type="button"
        className="locateButton"
        onClick={locateMe}
        title="Hiển thị vị trí hiện tại"
      >
        ◎ <span>Vị trí của tôi</span>
      </button>

      {locationError && <div className="locationError">{locationError}</div>}

      {position && (
        <>
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
          <CircleMarker
            center={position}
            radius={8}
            pathOptions={{
              color: "#ffffff",
              fillColor: "#2563eb",
              fillOpacity: 1,
              weight: 3,
            }}
          >
            <Popup>
              <strong>Vị trí hiện tại</strong>
              <br />
              Sai số khoảng {Math.round(accuracy)} m
            </Popup>
          </CircleMarker>
        </>
      )}
    </>
  );
}

export default function App({ onNavigateTools, onNavigateImport, onNavigateSync }) {
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [meta, setMeta] = useState({ loaded: 0 });
  const [focusTick, setFocusTick] = useState(0);
  const layerRef = useRef(null);

  const handleData = useCallback((result) => setData(result), []);
  const handleLoading = useCallback((value) => setLoading(value), []);
  const handleError = useCallback((message) => setError(message), []);
  const handleMeta = useCallback((value) => setMeta(value), []);

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
          p.muc_dich_su_dung,
        ]
          .filter((value) => value !== null && value !== undefined)
          .some((value) =>
            String(value).toLocaleLowerCase("vi").includes(keyword),
          ),
      ),
    };
  }, [data, query]);

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

  const onEachFeature = useCallback((feature, layer) => {
    const p = feature.properties;

    layer.bindTooltip(`Tờ ${p.so_to} · Thửa ${p.so_thua}`, {
      sticky: true,
      direction: "top",
    });

    layer.on("click", () => {
      setSelected({ id: feature.id, feature, ...p });
      setFocusTick((value) => value + 1);
    });
  }, []);

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
            {isFiltering && meta.loaded > shownCount
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
      </header>

      <section className="workspace">
        <aside className="sidebar">
          <div className="filterHeader">
            <strong>Bộ lọc dữ liệu</strong>
            <span>Lọc các thửa đất đang hiển thị</span>
          </div>

          <label htmlFor="search">Tìm kiếm thửa đất</label>

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

          {loading && (
            <div className="notice">
              {meta.loaded > 0
                ? `Đang tải… ${meta.loaded.toLocaleString("vi-VN")} thửa`
                : "Đang tải dữ liệu Supabase…"}
            </div>
          )}

          {!loading && !error && shownCount === 0 && !isFiltering && (
            <div className="notice">
              <strong>Chưa có thửa nào</strong>
              <span>Hãy nhập dữ liệu GML trước khi xem bản đồ.</span>
            </div>
          )}

          {error && (
            <div className="notice error">
              <strong>Chưa kết nối được dữ liệu</strong>
              <span>{error}</span>
            </div>
          )}

          <div className="filterPlaceholder">
            <div>☷</div>
            <strong>Bộ lọc sẽ bổ sung sau</strong>
            <span>Khu vực này sẽ chứa các điều kiện lọc dữ liệu.</span>
          </div>
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
            <AllParcelsLoader
              onData={handleData}
              onLoading={handleLoading}
              onError={handleError}
              onMeta={handleMeta}
            />

            <CurrentLocation />

            <ZoomControl position="bottomright" />

            <LayersControl position="topright">
              <LayersControl.BaseLayer checked name="OpenStreetMap">
                <TileLayer
                  url={OSM_TILE_URL}
                  minZoom={0}
                  maxZoom={19}
                  attribution="&copy; OpenStreetMap contributors"
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
                    <dt>Mã xã</dt>
                    <dd>
                      <EmptyValue>{selected.ma_xa}</EmptyValue>
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