import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  GeoJSON,
  LayersControl,
  MapContainer,
  TileLayer,
  ZoomControl,
} from "react-leaflet";

import CurrentLocation from "./components/map/CurrentLocation";
import { FindHereButton } from "./components/map/MapControls";
import {
  FitBounds,
  MapInstanceCapture,
  NearMeLoader,
  SearchParcelsLoader,
} from "./components/map/MapDataLoaders";
import ParcelInfoPanel from "./components/parcel/ParcelInfoPanel";
import { getXaList } from "./services/parcelService";
import { getRanhGioiThon } from "./services/ranhThonService";
import {
  GCN_COLOR,
  GCN_LABEL,
  GROUP_COLORS,
  GROUP_LABELS,
  NEAR_ME_TARGET,
  UNG_THUA_COLOR,
  UNG_THUA_LABEL,
  VIEWPORT_SEARCH_TARGET,
  getParcelFillColor,
} from "./utils/constants";
import { featureKey } from "./utils/geometry";

const OSM_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const GOOGLE_SUBDOMAINS = ["mt0", "mt1", "mt2", "mt3"];
const GOOGLE_HYBRID_URL = "https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}";
const GOOGLE_SATELLITE_URL = "https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}";

// Esri: chính chủ, miễn phí cho ứng dụng phi thương mại.
const ESRI_IMAGERY_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/" +
  "World_Imagery/MapServer/tile/{z}/{y}/{x}";

// Nới khung quanh phạm vi dữ liệu để không sót thửa nằm sát mép, đơn vị độ.
const EXTENT_PADDING = 0.01;

export default function App({ onNavigateTools, onNavigateNhom4 }) {
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

  // Ranh giới thôn: tải hết 1 lần khi mở trang (dataset nhỏ, không cần
  // theo khung bản đồ/xã) — hễ zoom/kéo tới đâu có ranh là hiện ngay,
  // không cần bấm Tra cứu trước. Xã nào chưa có dữ liệu ranh thì đơn giản
  // là không có feature nào rơi vào khu vực đó.
  const [ranhThonData, setRanhThonData] = useState({ type: "FeatureCollection", features: [] });

  useEffect(() => {
    const controller = new AbortController();
    getRanhGioiThon({}, { signal: controller.signal })
      .then((result) => setRanhThonData(result || { type: "FeatureCollection", features: [] }))
      .catch((fetchError) => {
        if (fetchError.name !== "AbortError") setRanhThonData({ type: "FeatureCollection", features: [] });
      });

    return () => controller.abort();
  }, []);

  // Danh sách thôn của xã đang chọn trong bộ lọc (không phải xã đã tra
  // cứu) — suy ra thẳng từ ranhThonData đã tải sẵn, không gọi thêm API.
  // Rỗng thì không hiện bộ lọc thôn (xã đó chưa có dữ liệu ranh).
  const thonOptionsForXa = useMemo(() => {
    if (!maXa) return [];
    const names = ranhThonData.features
      .filter((f) => f.properties?.ma_xa === maXa)
      .map((f) => f.properties.ten_thon);
    return [...new Set(names)].sort((a, b) => a.localeCompare(b, "vi"));
  }, [ranhThonData, maXa]);

  const [tenThon, setTenThon] = useState("");

  useEffect(() => {
    setTenThon("");
  }, [maXa]);

  // Đánh dấu lần tìm gần nhất là bấm nút "Tìm thửa quanh đây" (theo khung
  // nhìn bản đồ), để phân biệt với tra cứu theo mã xã / định vị GPS.
  const [viewportSearchActive, setViewportSearchActive] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    getXaList({ signal: controller.signal })
      .then((result) => setXaOptions(result?.items || []))
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
      tenThon: tenThon || "",
    });
    setFiltersOpen(false);
  }, [maXa, nhom, soTo, soThua, tenThon]);

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

  // Sau khi MplisMatchForm lưu thành công: cập nhật ngay dữ liệu đang có
  // (data/selected) để bản đồ đổi màu vàng tức thì, không phải tải lại
  // toàn bộ thửa từ server.
  const handleMplisSaved = useCallback(
    (savedUngThua) => {
      setData((prev) => {
        if (!prev || !selected) return prev;
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
    },
    [selected],
  );

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

              {thonOptionsForXa.length > 0 && (
                <div>
                  <label htmlFor="filterTenThon">Thôn</label>
                  <select
                    id="filterTenThon"
                    className="filterInput"
                    value={tenThon}
                    onChange={(event) => setTenThon(event.target.value)}
                  >
                    <option value="">-- Tất cả thôn --</option>
                    {thonOptionsForXa.map((ten) => (
                      <option key={ten} value={ten}>
                        {ten}
                      </option>
                    ))}
                  </select>
                </div>
              )}

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

              <LayersControl.Overlay checked name="Thửa đất">
                <GeoJSON
                  ref={layerRef}
                  data={{ type: "FeatureCollection", features: [] }}
                  style={style}
                  onEachFeature={onEachFeature}
                />
              </LayersControl.Overlay>

              <LayersControl.Overlay name="Ranh giới thôn">
                <GeoJSON
                  key={JSON.stringify(ranhThonData.features.map((f) => f.id))}
                  data={ranhThonData}
                  style={{
                    color: "#dc2626",
                    weight: 2,
                    opacity: 1,
                    dashArray: "6 4",
                    fillOpacity: 0,
                  }}
                  onEachFeature={(feature, layer) => {
                    if (feature.properties?.ten_thon) {
                      layer.bindTooltip(feature.properties.ten_thon, { sticky: true });
                    }
                  }}
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

          <ParcelInfoPanel
            parcel={selected}
            feature={selectedFeature}
            xaNameByCode={xaNameByCode}
            onClose={() => setSelected(null)}
            onZoom={() => setFocusTick((value) => value + 1)}
            onMplisSaved={handleMplisSaved}
            onNhapNhom4={onNavigateNhom4}
          />
        </div>
      </section>
    </main>
  );
}
