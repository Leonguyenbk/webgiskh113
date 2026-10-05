import { useEffect, useMemo, useState } from "react";

import { getThongKeNguonNhap } from "./services/parcelService";

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

function formatPercent(phan, tong) {
  if (!tong) return 0;
  return Math.round((phan / tong) * 100);
}

// Cấu hình cột cho bảng "Tất cả xã/phường" — cùng kiểu bấm-để-sắp-xếp như
// GcnDashboardPage (SORT_COLUMNS).
const SORT_COLUMNS = [
  { key: "ten_xa", label: "Xã / phường", type: "text", defaultDir: "asc" },
  { key: "tong", label: "Tổng đã nhập", type: "number", defaultDir: "desc" },
  { key: "tong_form", label: "Từ biểu Nhóm 4", type: "number", defaultDir: "desc" },
  { key: "tong_khac", label: "Từ nguồn khác", type: "number", defaultDir: "desc" },
];

export default function ThongKeNguonNhapPage({ onNavigateHome }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sort, setSort] = useState({ key: "tong", dir: "desc" });
  const [tableFilter, setTableFilter] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    getThongKeNguonNhap({ signal: controller.signal })
      .then((result) => setStats(result))
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const total = stats?.total || 0;
  const totalForm = stats?.total_form || 0;
  const totalKhac = stats?.total_khac || 0;
  const percentForm = formatPercent(totalForm, total);
  const percentKhac = formatPercent(totalKhac, total);
  const theoXa = stats?.theo_xa || [];

  const handleSort = (key) => {
    setSort((prev) => {
      if (prev.key === key) return { key, dir: prev.dir === "asc" ? "desc" : "asc" };
      const column = SORT_COLUMNS.find((c) => c.key === key);
      return { key, dir: column?.defaultDir || "asc" };
    });
  };

  const rows = useMemo(() => {
    const column = SORT_COLUMNS.find((c) => c.key === sort.key);
    const sorted = [...theoXa];
    sorted.sort((a, b) => {
      let cmp;
      if (column?.type === "text") {
        cmp = (a.ten_xa || a.ma_xa).localeCompare(b.ten_xa || b.ma_xa, "vi");
      } else {
        cmp = (a[sort.key] || 0) - (b[sort.key] || 0);
      }
      if (cmp === 0) cmp = (a.ten_xa || a.ma_xa).localeCompare(b.ten_xa || b.ma_xa, "vi");
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return sorted;
  }, [theoXa, sort]);

  const filteredRows = useMemo(() => {
    const keyword = tableFilter.trim().toLocaleLowerCase("vi");
    if (!keyword) return rows;
    return rows.filter(({ ma_xa, ten_xa }) =>
      `${ten_xa || ""} ${ma_xa}`.toLocaleLowerCase("vi").includes(keyword),
    );
  }, [rows, tableFilter]);

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Tổng số thửa đã nhập theo nguồn</h1>
          <p>Toàn dự án — tách số thửa nhập từ biểu Nhóm 4 (form) và số thửa nhập từ nguồn khác (đồng bộ Google Sheet)</p>
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
        {loading && <div className="notice">Đang tải dữ liệu thống kê…</div>}

        {error && (
          <div className="notice error">
            <strong>Không tải được dữ liệu</strong>
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && (
          <>
            <div className="statTiles">
              <div className="statTile">
                <span>Tổng số thửa đã nhập</span>
                <strong>{formatSo(total)}</strong>
              </div>
              <div className="statTile">
                <span>Nhập từ biểu Nhóm 4 (form)</span>
                <strong>
                  {formatSo(totalForm)} <span style={{ fontWeight: 400, fontSize: 14 }}>({percentForm}%)</span>
                </strong>
              </div>
              <div className="statTile">
                <span>Nhập từ nguồn khác (đồng bộ Sheet)</span>
                <strong>
                  {formatSo(totalKhac)} <span style={{ fontWeight: 400, fontSize: 14 }}>({percentKhac}%)</span>
                </strong>
              </div>
            </div>

            <div
              className="importCard statsTableCard"
              style={{ width: "80%", maxWidth: "80%", margin: "16px auto 0" }}
            >
              <label>
                Chi tiết từng xã/phường ({formatSo(filteredRows.length)}/{formatSo(rows.length)})
              </label>

              <input
                type="text"
                className="filterInput"
                autoComplete="off"
                value={tableFilter}
                placeholder="Lọc theo tên hoặc mã xã/phường…"
                style={{ marginBottom: 10 }}
                onChange={(event) => setTableFilter(event.target.value)}
              />

              <div className="statsTableWrap">
                <table className="statsTable">
                  <thead>
                    <tr>
                      {SORT_COLUMNS.map((column) => (
                        <th
                          key={column.key}
                          onClick={() => handleSort(column.key)}
                          style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
                          title="Bấm để sắp xếp"
                        >
                          {column.label}
                          <span style={{ marginLeft: 4, opacity: sort.key === column.key ? 1 : 0.25 }}>
                            {sort.key === column.key ? (sort.dir === "asc" ? "▲" : "▼") : "↕"}
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.length === 0 ? (
                      <tr>
                        <td colSpan={SORT_COLUMNS.length}>Không tìm thấy xã/phường phù hợp</td>
                      </tr>
                    ) : (
                      filteredRows.map((row) => (
                        <tr key={row.ma_xa}>
                          <td>{row.ten_xa || row.ma_xa}</td>
                          <td>{formatSo(row.tong)}</td>
                          <td>{formatSo(row.tong_form)}</td>
                          <td>{formatSo(row.tong_khac)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
