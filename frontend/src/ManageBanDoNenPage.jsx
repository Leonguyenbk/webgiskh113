import { useCallback, useEffect, useMemo, useState } from "react";

import {
  deleteBanDoNen,
  listBanDoNen,
  toggleBanDoNen,
  updateBanDoNen,
} from "./services/mapSheetService";
import { getXaList } from "./services/parcelService";

const TRANG_THAI_LABELS = {
  ready: "Sẵn sàng",
  error: "Lỗi",
};

export default function ManageBanDoNenPage({ onNavigateHome }) {
  const [items, setItems] = useState([]);
  const [listError, setListError] = useState("");
  const [loadingList, setLoadingList] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const [token, setToken] = useState("");

  const [filterMaXa, setFilterMaXa] = useState("");
  const [filterSoTo, setFilterSoTo] = useState("");
  const [filterTrangThai, setFilterTrangThai] = useState("");
  // "" = Bản đồ địa chính, "dang_ky" = Bản đồ đăng ký (xem ban_do_nen.loai).
  const [filterLoai, setFilterLoai] = useState("");

  const [xaList, setXaList] = useState([]);
  const [xaQuery, setXaQuery] = useState("");
  const [xaDropdownOpen, setXaDropdownOpen] = useState(false);

  const [busyId, setBusyId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [description, setDescription] = useState("");

  // Danh sách xã/phường để gõ-tìm (combobox) — nhẹ (chỉ mã + tên), khác
  // danh sách tờ bản đồ (9973 dòng) nên tải 1 lần khi mở trang vẫn ổn.
  useEffect(() => {
    getXaList()
      .then((result) => setXaList(result?.items || []))
      .catch(() => {});
  }, []);

  const filteredXaOptions = useMemo(() => {
    const keyword = xaQuery.trim().toLocaleLowerCase("vi");
    if (!keyword) return xaList;
    return xaList.filter(({ ma_xa, ten_xa }) =>
      `${ten_xa} ${ma_xa}`.toLocaleLowerCase("vi").includes(keyword),
    );
  }, [xaList, xaQuery]);

  const handleSelectXa = (maXa, tenXa) => {
    setFilterMaXa(maXa);
    setXaQuery(tenXa || maXa);
    setXaDropdownOpen(false);
  };

  // Trang này có thể có RẤT NHIỀU tờ bản đồ — KHÔNG tải cả danh sách khi
  // mở trang. Chỉ truy vấn khi người dùng bấm "Tìm", và phải có ít nhất
  // mã xã hoặc số tờ (khớp theo CHỨA CHUỖI, không cần đúng tuyệt đối) —
  // khớp đúng yêu cầu backend ở ban_do_nen_service.list_sheets().
  const loadList = useCallback(() => {
    const maXa = filterMaXa.trim();
    const soTo = filterSoTo.trim();
    if (!maXa && !soTo) {
      setListError("Chọn xã/phường hoặc nhập số tờ để tìm trước khi truy vấn.");
      setItems([]);
      setHasSearched(false);
      return undefined;
    }

    setLoadingList(true);
    setListError("");
    setHasSearched(true);

    const params = {};
    if (maXa) params.ma_xa = maXa;
    if (soTo) params.so_to = soTo;
    if (filterTrangThai) params.trang_thai = filterTrangThai;
    if (filterLoai) params.loai = filterLoai;

    return listBanDoNen(params)
      .then((result) => setItems(result?.items || []))
      .catch((err) => setListError(err.message))
      .finally(() => setLoadingList(false));
  }, [filterMaXa, filterSoTo, filterTrangThai, filterLoai]);

  const handleFilterKeyDown = (event) => {
    if (event.key === "Enter") loadList();
  };

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

  const startEditingDescription = (item) => {
    setEditingId(item.id);
    setDescription(item.ghi_chu || "");
    setListError("");
  };

  const handleSaveDescription = async (item) => {
    setBusyId(item.id);
    try {
      await updateBanDoNen(item.id, { ghi_chu: description }, token);
      setEditingId(null);
      setDescription("");
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
          <p>Tờ bản đồ raster (mã xã + số tờ) — xem, ghi mô tả, bật-tắt hoặc xóa metadata</p>
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
            xuất từ DGN → georeference → EPSG:3857 → sinh tile XYZ → upload thẳng lên máy chủ
            lưu trữ → tự đăng ký với WebGIS khi upload xong 100%). Trang này không upload gì cả,
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

          <p className="importHint">
            Danh sách tờ bản đồ có thể rất nhiều — chọn xã/phường và/hoặc nhập số tờ rồi bấm{" "}
            <strong>Tìm</strong> (Enter cũng được), trang sẽ không tự tải toàn bộ.
          </p>

          <div className="filterRow">
            <div className="comboBox">
              <input
                type="text"
                className="filterInput"
                autoComplete="off"
                value={xaQuery}
                placeholder="Gõ tên hoặc mã xã/phường để tìm…"
                onChange={(event) => {
                  setXaQuery(event.target.value);
                  setFilterMaXa("");
                  setXaDropdownOpen(true);
                }}
                onFocus={() => setXaDropdownOpen(true)}
                onBlur={() => setXaDropdownOpen(false)}
                onKeyDown={handleFilterKeyDown}
              />

              {xaDropdownOpen && (
                <div className="comboBoxList">
                  {filteredXaOptions.length === 0 ? (
                    <div className="comboBoxEmpty">Không tìm thấy xã/phường</div>
                  ) : (
                    filteredXaOptions.map(({ ma_xa, ten_xa }) => (
                      <div
                        key={ma_xa}
                        className={`comboBoxItem${ma_xa === filterMaXa ? " active" : ""}`}
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
            <div>
              <input
                className="filterInput"
                value={filterSoTo}
                onChange={(event) => setFilterSoTo(event.target.value)}
                onKeyDown={handleFilterKeyDown}
                placeholder="Số tờ / tên tờ (chứa chuỗi)"
              />
            </div>
          </div>
          <select
            className="filterInput"
            value={filterLoai}
            onChange={(event) => setFilterLoai(event.target.value)}
          >
            <option value="">Bản đồ địa chính</option>
            <option value="dang_ky">Bản đồ đăng ký</option>
          </select>
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
          <button
            type="button"
            className="searchButton"
            disabled={loadingList}
            onClick={() => loadList()}
          >
            {loadingList ? "Đang tìm…" : "🔍 Tìm"}
          </button>

          {!hasSearched && !listError && (
            <div className="notice">Chọn xã/phường hoặc nhập số tờ bên trên rồi bấm Tìm để xem danh sách.</div>
          )}

          {listError && (
            <div className="notice error">
              <strong>Không tìm được</strong>
              <span>{listError}</span>
            </div>
          )}

          {hasSearched && !loadingList && !listError && items.length === 0 && (
            <div className="notice">Không tìm thấy tờ bản đồ nào khớp bộ lọc.</div>
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

                    {editingId === item.id ? (
                      <div className="mapSheetDescriptionEditor">
                        <label htmlFor={`banDoNenGhiChu-${item.id}`}>Mô tả hiển thị trên bản đồ</label>
                        <textarea
                          id={`banDoNenGhiChu-${item.id}`}
                          rows={2}
                          value={description}
                          onChange={(event) => setDescription(event.target.value)}
                          placeholder="Ví dụ: Bản đồ địa chính đo đạc năm 2024"
                        />
                        <span className="importHint">
                          Mô tả này là nhãn chung của cả tờ; nội dung chữ chi tiết phải có trong
                          ảnh tile hoặc dữ liệu nhãn từ Tool Windows.
                        </span>
                      </div>
                    ) : (
                      <span className="gcnLinkUrl">
                        Mô tả: {item.ghi_chu || "Chưa có"}
                      </span>
                    )}

                    <div className="gcnLinkActions">
                      {editingId === item.id ? (
                        <>
                          <button
                            type="button"
                            className="searchButton"
                            disabled={isBusy}
                            onClick={() => handleSaveDescription(item)}
                          >
                            {isBusy ? "Đang lưu…" : "Lưu mô tả"}
                          </button>
                          <button
                            type="button"
                            className="resetButton"
                            disabled={isBusy}
                            onClick={() => {
                              setEditingId(null);
                              setDescription("");
                            }}
                          >
                            Hủy
                          </button>
                        </>
                      ) : (
                        <button
                          type="button"
                          className="searchButton"
                          disabled={isBusy}
                          onClick={() => startEditingDescription(item)}
                        >
                          Sửa mô tả
                        </button>
                      )}
                      <button
                        type="button"
                        className="searchButton"
                        disabled={isBusy || editingId === item.id}
                        onClick={() => handleToggle(item)}
                      >
                        {item.kich_hoat ? "Tắt" : "Bật"}
                      </button>
                      <button
                        type="button"
                        className="resetButton"
                        disabled={isBusy || editingId === item.id}
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
