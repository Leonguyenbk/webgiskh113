import { useEffect, useMemo, useRef, useState } from "react";
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

const OSM_TILE_URL =
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

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
  { field: "chua_xuat_so_dia_chinh_dien_tu", label: "Chưa được xuất số địa chính điện tử" },
  {
    field: "khong_dong_bo_3_khoi",
    label: "Không đồng bộ 3 khối thông tin (không gian, thuộc tính, phi cấu trúc)",
  },
  { field: "chi_co_du_lieu_thuoc_tinh", label: "Chỉ có dữ liệu thuộc tính (thiếu dữ liệu không gian)" },
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
  return MISSING_INFO_RULES.filter((rule) => dongBo[rule.field]).map((rule) => rule.label);
}

function googleMapsDirectionsUrl(feature) {
  const center = L.geoJSON(feature).getBounds().getCenter();
  return `https://www.google.com/maps/dir/?api=1&destination=${center.lat},${center.lng}`;
}

function FitBounds({ data, focusFeature, focusTick, hasUserLocation }) {
  const map = useMap();
  const didInitialFit = useRef(false);
  useEffect(() => {
    const target = focusFeature
      ? L.geoJSON(focusFeature)
      : data?.features?.length
        ? L.geoJSON(data)
        : null;
    if (!target) return;

    const isInitialFit = !didInitialFit.current;
    didInitialFit.current = true;
    if (isInitialFit && !focusFeature && hasUserLocation) return;

    map.fitBounds(target.getBounds(), { padding: [30, 30], maxZoom: 18 });
  }, [data, focusFeature, focusTick, map]);
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
      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 5000,
      },
    );
  };

  useEffect(() => {
    locateMe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

      {locationError && (
        <div className="locationError">{locationError}</div>
      )}

      {position && (
        <>
          <Circle
            center={position}
            radius={accuracy}
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
  const [focusTick, setFocusTick] = useState(0);
  const [hasUserLocation, setHasUserLocation] = useState(false);
  const layerRef = useRef(null);

  useEffect(() => {
    fetch(`${API_URL}/api/parcels`)
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Không tải được dữ liệu");
        return result;
      })
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
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
          p.muc_dich_su_dung,
          p.ten_chu,
          p.dia_chi,
        ]
          .filter((value) => value !== null && value !== undefined)
          .some((value) => String(value).toLocaleLowerCase("vi").includes(keyword)),
      ),
    };
  }, [data, query]);

  const selectedFeature = useMemo(
    () => data?.features?.find((feature) => feature.id === selected?.id) || null,
    [data, selected],
  );

  const style = (feature) => {
    const isSelected = feature.id === selected?.id;
    return {
      color: isSelected ? "#ffffff" : "#334155",
      weight: isSelected ? 4 : 1.5,
      fillColor: isSelected
        ? "#2563eb"
        : getGroupColor(feature.properties?.dong_bo?.phan_loai_ke_hoach_2959),
      fillOpacity: isSelected ? 0.75 : 0.55,
    };
  };

  const onEachFeature = (feature, layer) => {
    const p = feature.properties;
    layer.bindTooltip(`Tờ ${p.so_to} · Thửa ${p.so_thua}`, {
      sticky: true,
      direction: "top",
    });
    layer.on("click", () => {
      setSelected({ id: feature.id, ...p });
      setFocusTick((value) => value + 1);
    });
  };

  useEffect(() => {
    layerRef.current?.clearLayers();
    if (filtered) layerRef.current?.addData(filtered);
  }, [filtered]);

  useEffect(() => {
    layerRef.current?.setStyle(style);
  }, [selected]);

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Bản đồ thửa đất</h1>
          <p>VN-2000 Đắk Lắk · Dữ liệu Supabase</p>
        </div>
        <div className="count">
          <strong>{filtered?.features?.length ?? 0}</strong>
          <span>thửa hiển thị</span>
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
          <label htmlFor="search">Tìm kiếm thửa đất</label>
          <div className="searchBox">
            <span>⌕</span>
            <input
              id="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Số tờ/thửa, tên chủ, loại đất…"
            />
            {query && <button onClick={() => setQuery("")}>×</button>}
          </div>

          {loading && <div className="notice">Đang tải dữ liệu Supabase…</div>}
          {error && (
            <div className="notice error">
              <strong>Chưa kết nối được dữ liệu</strong>
              <span>{error}</span>
            </div>
          )}

          <div className="sectionTitle">
            <span>Thông tin thửa đất</span>
            {selected && <button onClick={() => setSelected(null)}>Đóng</button>}
          </div>

          {selected ? (
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
                <div><dt>Mã xã</dt><dd><EmptyValue>{selected.ma_xa}</EmptyValue></dd></div>
                <div><dt>Mục đích</dt><dd><span className="tag">{selected.muc_dich_su_dung}</span></dd></div>
                <div><dt>Diện tích</dt><dd>{Number(selected.dien_tich).toLocaleString("vi-VN")} m²</dd></div>
                <div><dt>Chủ sử dụng</dt><dd><EmptyValue>{selected.ten_chu}</EmptyValue></dd></div>
                <div><dt>Địa chỉ</dt><dd><EmptyValue>{selected.dia_chi}</EmptyValue></dd></div>
                <div>
                  <dt>Phân loại KH 2959</dt>
                  <dd>
                    <span
                      className="tag"
                      style={{
                        color: "white",
                        backgroundColor: getGroupColor(selected.dong_bo?.phan_loai_ke_hoach_2959),
                      }}
                    >
                      {selected.dong_bo?.phan_loai_ke_hoach_2959 ||
                        GROUP_LABELS[getGroupKey(selected.dong_bo?.phan_loai_ke_hoach_2959)]}
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
          ) : (
            <div className="emptyState">
              <div>⌁</div>
              <strong>Chọn một thửa trên bản đồ</strong>
              <span>Thông tin thuộc tính sẽ xuất hiện tại đây.</span>
            </div>
          )}
        </aside>

        <div className="mapWrap">
          <MapContainer
            center={[12.67, 108.05]}
            zoom={15}
            zoomControl={false}
            className="map"
          >
            <CurrentLocation onLocated={() => setHasUserLocation(true)} />
            <ZoomControl position="bottomright" />
            <LayersControl position="topright">
              <LayersControl.BaseLayer checked name="OpenStreetMap">
                <TileLayer
                  url={OSM_TILE_URL}
                  minZoom={0}
                  maxZoom={19}
                  attribution='&copy; OpenStreetMap contributors'
                />
              </LayersControl.BaseLayer>
              <LayersControl.Overlay checked name="Thửa đất">
                <GeoJSON
                  ref={layerRef}
                  data={filtered || { type: "FeatureCollection", features: [] }}
                  style={style}
                  onEachFeature={onEachFeature}
                />
              </LayersControl.Overlay>
            </LayersControl>
            <FitBounds
              data={filtered}
              focusFeature={selectedFeature}
              focusTick={focusTick}
              hasUserLocation={hasUserLocation}
            />
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
        </div>
      </section>
    </main>
  );
}
