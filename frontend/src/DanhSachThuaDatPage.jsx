import { useEffect, useMemo, useState } from "react";

import { getGcnDanhSach, getXaList } from "./services/parcelService";

const PAGE_SIZE = 100;

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

function formatNgay(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("vi-VN");
}

export default function DanhSachThuaDatPage({ onNavigateHome }) {
  const [xaList, setXaList] = useState([]);
  const [xaLoading, setXaLoading] = useState(true);
  const [xaError, setXaError] = useState("");

  const [maXa, setMaXa] = useState("");
  const [xaQuery, setXaQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [soToFilter, setSoToFilter] = useState("");
  const [soThuaFilter, setSoThuaFilter] = useState("");
  // Backend chỉ chấp nhận 'asc'/'desc' theo ngày nhập (created_at) —
  // hàm list_du_lieu_gcn_da_nhap trong supabase/schema.sql chỉ có chỉ mục
  // cho cột này, không sắp theo cột khác để tránh phải filesort cả xã.
  const [sortDesc, setSortDesc] = useState(true);
  const [offset, setOffset] = useState(0);

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setXaLoading(true);
    setXaError("");
    getXaList()
      .then((result) => setXaList(result?.items || []))
      .catch((err) => setXaError(err.message))
      .finally(() => setXaLoading(false));
  }, []);

  useEffect(() => {
    if (!maXa) {
      setItems([]);
      setTotal(0);
      return undefined;
    }

    const controller = new AbortController();
    setLoading(true);
    setError("");

    getGcnDanhSach(
      {
        ma_xa: maXa,
        sort: sortDesc ? "desc" : "asc",
        limit: PAGE_SIZE,
        offset,
        so_to: soToFilter.trim() || undefined,
        so_thua: soThuaFilter.trim() || undefined,
      },
      { signal: controller.signal },
    )
      .then((result) => {
        setItems(result?.items || []);
        setTotal(Number(result?.total) || 0);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [maXa, sortDesc, offset, soToFilter, soThuaFilter]);

  const filteredXaOptions = useMemo(() => {
    const keyword = xaQuery.trim().toLocaleLowerCase("vi");
    if (!keyword) return xaList;
    return xaList.filter(({ ma_xa, ten_xa }) =>
      `${ten_xa} ${ma_xa}`.toLocaleLowerCase("vi").includes(keyword),
    );
  }, [xaList, xaQuery]);

  const handleSelectXa = (ma_xa, ten_xa) => {
    setMaXa(ma_xa);
    setXaQuery(ten_xa || ma_xa);
    setDropdownOpen(false);
    setOffset(0);
  };

  const handleChangeSoTo = (value) => {
    setSoToFilter(value);
    setOffset(0);
  };

  const handleChangeSoThua = (value) => {
    setSoThuaFilter(value);
    setOffset(0);
  };

  const handleToggleSort = () => {
    setSortDesc((prev) => !prev);
    setOffset(0);
  };

  const rangeFrom = total === 0 ? 0 : offset + 1;
  const rangeTo = Math.min(offset + PAGE_SIZE, total);
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Danh sách thửa đã nhập</h1>
          <p>Tra cứu các thửa đã có dữ liệu GCN (du_lieu_gcn) theo xã/phường — mỗi thửa 1 dòng dù có nhiều chủ sử dụng</p>
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

      <section className="dashboardWrap">
        {xaError && (
          <div className="notice error">
            <strong>Không tải được danh sách xã/phường</strong>
            <span>{xaError}</span>
          </div>
        )}

        <div
          className="importCard statsTableCard"
          style={{ width: "80%", maxWidth: "80%", margin: "0 auto" }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-end",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: 12 }}>
              <div style={{ width: 280, maxWidth: "100%" }}>
                <label htmlFor="daNhapXa">Xã / phường</label>
                <div className="comboBox" style={{ marginBottom: 0 }}>
                  <input
                    id="daNhapXa"
                    type="text"
                    className="filterInput"
                    autoComplete="off"
                    disabled={xaLoading}
                    value={xaQuery}
                    placeholder="Nhập tên xã/phường để tìm…"
                    style={{ width: "100%" }}
                    onChange={(event) => {
                      setXaQuery(event.target.value);
                      setMaXa("");
                      setDropdownOpen(true);
                    }}
                    onFocus={() => setDropdownOpen(true)}
                    onBlur={() => setDropdownOpen(false)}
                  />

                  {dropdownOpen && (
                    <div className="comboBoxList">
                      {filteredXaOptions.length === 0 ? (
                        <div className="comboBoxEmpty">Không tìm thấy xã/phường</div>
                      ) : (
                        filteredXaOptions.map(({ ma_xa, ten_xa }) => (
                          <div
                            key={ma_xa}
                            className={`comboBoxItem${ma_xa === maXa ? " active" : ""}`}
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
              </div>

              <div style={{ width: 100 }}>
                <label htmlFor="daNhapSoTo">Số tờ</label>
                <input
                  id="daNhapSoTo"
                  type="text"
                  inputMode="numeric"
                  className="filterInput"
                  autoComplete="off"
                  value={soToFilter}
                  placeholder="Tất cả"
                  style={{ width: "100%", marginBottom: 0 }}
                  onChange={(event) => handleChangeSoTo(event.target.value)}
                />
              </div>

              <div style={{ width: 100 }}>
                <label htmlFor="daNhapSoThua">Số thửa</label>
                <input
                  id="daNhapSoThua"
                  type="text"
                  inputMode="numeric"
                  className="filterInput"
                  autoComplete="off"
                  value={soThuaFilter}
                  placeholder="Tất cả"
                  style={{ width: "100%", marginBottom: 0 }}
                  onChange={(event) => handleChangeSoThua(event.target.value)}
                />
              </div>
            </div>

            {maXa && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <label style={{ margin: 0 }}>
                  {loading
                    ? "Đang tải…"
                    : `${formatSo(rangeFrom)}–${formatSo(rangeTo)} / ${formatSo(total)} thửa`}
                </label>
                <button
                  type="button"
                  className="downloadButton"
                  disabled={!canPrev || loading}
                  style={{ opacity: !canPrev || loading ? 0.5 : 1 }}
                  onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
                >
                  ← Trang trước
                </button>
                <button
                  type="button"
                  className="downloadButton"
                  disabled={!canNext || loading}
                  style={{ opacity: !canNext || loading ? 0.5 : 1 }}
                  onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
                >
                  Trang sau →
                </button>
              </div>
            )}
          </div>

          {!maXa ? (
            <div className="emptyState" style={{ marginTop: 10 }}>
              <div>📋</div>
              <strong>Chưa chọn xã/phường</strong>
              <span>Chọn 1 xã/phường ở trên để xem danh sách đã nhập.</span>
            </div>
          ) : (
            <>
              {error && (
                <div className="notice error" style={{ marginTop: 10 }}>
                  <strong>Không tải được dữ liệu</strong>
                  <span>{error}</span>
                </div>
              )}

              <div className="statsTableWrap" style={{ marginTop: 10 }}>
                <table className="statsTable">
                  <thead>
                    <tr>
                      <th>Xã / phường</th>
                      <th>Số tờ</th>
                      <th>Số thửa</th>
                      <th>Mã định danh</th>
                      <th
                        onClick={handleToggleSort}
                        style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
                        title="Bấm để đổi chiều sắp xếp"
                      >
                        Ngày nhập
                        <span style={{ marginLeft: 4 }}>{sortDesc ? "▼" : "▲"}</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {!loading && items.length === 0 ? (
                      <tr>
                        <td colSpan={5}>Xã/phường này chưa có dữ liệu trong du_lieu_gcn</td>
                      </tr>
                    ) : (
                      items.map((row, index) => (
                        <tr key={`${row.ma_xa}_${row.so_to}_${row.so_thua}_${index}`}>
                          <td>{row.ten_xa || row.ma_xa}</td>
                          <td>{row.so_to}</td>
                          <td>{row.so_thua}</td>
                          <td>{row.ma_dinh_danh || ""}</td>
                          <td>{formatNgay(row.ngay_nhap)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
