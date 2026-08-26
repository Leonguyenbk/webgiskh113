import { useCallback, useEffect, useState } from "react";

import { deleteBanDoNen, listBanDoNen, toggleBanDoNen } from "./services/mapSheetService";

const TRANG_THAI_LABELS = {
  ready: "Sẵn sàng",
  error: "Lỗi",
};

export default function ManageBanDoNenPage({ onNavigateHome }) {
  const [items, setItems] = useState([]);
  const [listError, setListError] = useState("");
  const [loadingList, setLoadingList] = useState(true);

  const [token, setToken] = useState("");

  const [filterMaXa, setFilterMaXa] = useState("");
  const [filterSoTo, setFilterSoTo] = useState("");
  const [filterTrangThai, setFilterTrangThai] = useState("");

  const [busyId, setBusyId] = useState(null);

  const loadList = useCallback(() => {
    setLoadingList(true);
    setListError("");

    const params = {};
    if (filterMaXa.trim()) params.ma_xa = `eq.${filterMaXa.trim()}`;
    if (filterSoTo.trim()) params.so_to = `eq.${filterSoTo.trim()}`;
    if (filterTrangThai) params.trang_thai = `eq.${filterTrangThai}`;

    return listBanDoNen(params)
      .then((result) => setItems(result?.items || []))
      .catch((err) => setListError(err.message))
      .finally(() => setLoadingList(false));
  }, [filterMaXa, filterSoTo, filterTrangThai]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const handleToggle = async (item) => {
    setBusyId(item.id);
    try {
      await toggleBanDoNen(item.id, !item.kich_hoat, token);
      await loadList();
    } catch (err) {
      setListError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (item) => {
    if (
      !window.confirm(
        `Xóa tờ bản đồ "${item.ma_xa} / Tờ ${item.so_to}"? Chỉ xóa metadata trên WebGIS, KHÔNG xóa tile trên Storage (dọn Storage bằng Tool nếu cần). Không thể hoàn tác.`,
      )
    ) {
      return;
    }

    setBusyId(item.id);
    try {
      await deleteBanDoNen(item.id, token);
      await loadList();
    } catch (err) {
      setListError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Quản lý bản đồ nền</h1>
          <p>Tờ bản đồ raster (mã xã + số tờ) — chỉ xem/lọc/bật-tắt/xóa metadata</p>
        </div>
        <a
          className="backLink"
          href="/"
          onClick={(event) => {
            event.preventDefault();
            onNavigateHome?.();
          }}
        >
          ← Về bản đồ
        </a>
      </header>

      <section className="importWrap">
        <div className="importCard">
          <p className="importHint">
            Tờ bản đồ được thêm bằng <strong>Tool Windows</strong> chạy riêng (đọc KMZ MicroStation
            xuất từ DGN → georeference → EPSG:3857 → sinh tile XYZ → upload thẳng lên Supabase
            Storage → tự đăng ký với WebGIS khi upload xong 100%). Trang này không upload gì cả,
            chỉ xem danh sách và bật/tắt hiển thị hoặc xóa bản ghi.
          </p>

          <label htmlFor="banDoNenToken">Mã xác thực (dùng cho Bật/Tắt, Xóa)</label>
          <input
            id="banDoNenToken"
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Nhập mã do quản trị viên cấp (nếu có)"
          />
        </div>

        <div className="importCard gcnLinksListCard">
          <label>Danh sách tờ bản đồ</label>

          <div className="filterRow">
            <div>
              <input
                className="filterInput"
                value={filterMaXa}
                onChange={(event) => setFilterMaXa(event.target.value)}
                placeholder="Lọc theo mã xã"
              />
            </div>
            <div>
              <input
                className="filterInput"
                value={filterSoTo}
                onChange={(event) => setFilterSoTo(event.target.value)}
                placeholder="Lọc theo số tờ"
              />
            </div>
          </div>
          <select
            className="filterInput"
            value={filterTrangThai}
            onChange={(event) => setFilterTrangThai(event.target.value)}
          >
            <option value="">Tất cả trạng thái</option>
            {Object.entries(TRANG_THAI_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          {loadingList && <div className="notice">Đang tải danh sách…</div>}

          {listError && (
            <div className="notice error">
              <strong>Không tải được danh sách</strong>
              <span>{listError}</span>
            </div>
          )}

          {!loadingList && !listError && items.length === 0 && (
            <div className="notice">Chưa có tờ bản đồ nào — dùng Tool Windows để thêm.</div>
          )}

          {items.length > 0 && (
            <div className="gcnLinkList">
              {items.map((item) => {
                const isBusy = busyId === item.id;

                return (
                  <div key={item.id} className="gcnLinkItem">
                    <div className="gcnLinkHeader">
                      <span
                        className="parcelListDot"
                        style={{
                          backgroundColor: item.kich_hoat ? "#22c55e" : "#94a3b8",
                          cursor: "pointer",
                        }}
                        title={item.kich_hoat ? "Đang hiện — bấm để tắt" : "Đang tắt — bấm để hiện"}
                        onClick={() => !isBusy && handleToggle(item)}
                      />
                      <strong>
                        {item.ma_xa} / Tờ {item.so_to}
                      </strong>
                      <span className="tag">{TRANG_THAI_LABELS[item.trang_thai] || item.trang_thai}</span>
                    </div>

                    <span className="gcnLinkUrl">
                      bbox: {item.bbox_min_x?.toFixed?.(6)}, {item.bbox_min_y?.toFixed?.(6)} →{" "}
                      {item.bbox_max_x?.toFixed?.(6)}, {item.bbox_max_y?.toFixed?.(6)}
                    </span>
                    <span className="gcnLinkUrl">
                      v{item.tile_version}
                      {item.min_zoom != null && item.max_zoom != null
                        ? ` · zoom ${item.min_zoom}-${item.max_zoom}`
                        : ""}
                      {" · cập nhật "}
                      {item.updated_at ? new Date(item.updated_at).toLocaleString("vi-VN") : ""}
                    </span>

                    <div className="gcnLinkActions">
                      <button
                        type="button"
                        className="searchButton"
                        disabled={isBusy}
                        onClick={() => handleToggle(item)}
                      >
                        {item.kich_hoat ? "Tắt" : "Bật"}
                      </button>
                      <button
                        type="button"
                        className="resetButton"
                        disabled={isBusy}
                        onClick={() => handleDelete(item)}
                      >
                        {isBusy ? "…" : "Xóa"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
