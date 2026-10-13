import { useEffect, useMemo, useState } from "react";

import { getNhom3TongHop } from "./services/parcelService";

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

function formatPercent(phan, tong) {
  if (!tong) return 0;
  return Math.round((phan / tong) * 1000) / 10;
}

// Cấu hình cột cho phép bấm tiêu đề để sắp xếp bảng "Chi tiết theo
// xã/phường" — cùng pattern với GcnDashboardPage.jsx (SORT_COLUMNS/handleSort).
// defaultDir: hướng áp dụng khi bấm lần đầu vào 1 cột khác.
const SORT_COLUMNS = [
  { key: "ten_xa", label: "Xã / phường", type: "text", defaultDir: "asc" },
  { key: "tong", label: "Tổng Nhóm 3", type: "number", defaultDir: "desc" },
  { key: "da_nhom_1_2", label: "Đã Nhóm 1/2", type: "number", defaultDir: "desc" },
  { key: "da_thu_thap", label: "Đã nhập đủ dữ liệu", type: "number", defaultDir: "desc" },
  { key: "da_lam", label: "Đã làm", type: "number", defaultDir: "desc" },
  { key: "percent", label: "%", type: "number", defaultDir: "asc" },
  { key: "con_thieu", label: "Còn thiếu", type: "number", defaultDir: "desc" },
];

export default function Nhom3ConThieuPage({ onNavigateHome, onNavigateNhom3Dashboard }) {
  const [tongHop, setTongHop] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Mặc định sắp theo "Còn thiếu" giảm dần — xã còn nhiều việc nhất lên
  // đầu bảng, đúng mục đích chính của trang. Bấm tiêu đề cột để đổi.
  const [sort, setSort] = useState({ key: "con_thieu", dir: "desc" });
  const [tableFilter, setTableFilter] = useState("");

  const handleSort = (key) => {
    setSort((prev) => {
      if (prev.key === key) {
        return { key, dir: prev.dir === "asc" ? "desc" : "asc" };
      }
      const column = SORT_COLUMNS.find((c) => c.key === key);
      return { key, dir: column?.defaultDir || "asc" };
    });
  };

  useEffect(() => {
    setLoading(true);
    setError("");
    getNhom3TongHop()
      .then((result) => setTongHop(result))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const theoXaRows = useMemo(() => {
    return (tongHop?.theo_xa || []).map((row) => {
      const daLam = (row.da_nhom_1_2 || 0) + (row.da_thu_thap || 0);
      return {
        ...row,
        ten_xa: row.ten_xa || row.ma_xa,
        da_lam: daLam,
        percent: formatPercent(daLam, row.tong),
      };
    });
  }, [tongHop]);

  const sortedRows = useMemo(() => {
    const column = SORT_COLUMNS.find((c) => c.key === sort.key);
    const mapped = [...theoXaRows];
    mapped.sort((a, b) => {
      let cmp;
      if (column?.type === "text") {
        cmp = a[sort.key].localeCompare(b[sort.key], "vi");
      } else {
        cmp = a[sort.key] - b[sort.key];
      }
      if (cmp === 0) cmp = a.ten_xa.localeCompare(b.ten_xa, "vi");
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return mapped;
  }, [theoXaRows, sort]);

  // Lọc theo tên hoặc mã xã — client-side, dữ liệu theo_xa đã tải hết sẵn
  // (không phải phân trang từ server).
  const filteredRows = useMemo(() => {
    const keyword = tableFilter.trim().toLocaleLowerCase("vi");
    if (!keyword) return sortedRows;
    return sortedRows.filter(({ ma_xa, ten_xa }) =>
      `${ten_xa} ${ma_xa}`.toLocaleLowerCase("vi").includes(keyword),
    );
  }, [sortedRows, tableFilter]);

  const daLam = (tongHop?.da_nhom_1_2 || 0) + (tongHop?.da_thu_thap || 0);
  const tyLeDaLam = formatPercent(daLam, tongHop?.tong || 0);

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Nhóm 3 — thống kê còn thiếu dữ liệu</h1>
          <p>
            Đối chiếu danh sách thửa cần thu thập (Nhóm 3) với thửa đã thuộc Nhóm 1/2 và thửa đã thu thập — chỉ còn lại là thửa thật sự cần nhập biểu.
          </p>
        </div>
        <a
          className="backLink"
          href="/nhom-3-dashboard"
          onClick={(event) => {
            event.preventDefault();
            onNavigateNhom3Dashboard?.();
          }}
        >
          📊 Dashboard tỉ lệ &amp; tốc độ →
        </a>
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
        {loading && <div className="notice">Đang tải số liệu thống kê…</div>}
        {error && (
          <div className="notice error">
            <strong>Không tải được số liệu</strong>
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && tongHop && (
          <>
            <div className="statTiles">
              <div className="statTile">
                <span>Tổng thửa Nhóm 3 có trên bản đồ</span>
                <strong>{formatSo(tongHop.tong)}</strong>
              </div>
              <div className="statTile">
                <span>Đã lên Nhóm 1/2 (không cần nhập biểu)</span>
                <strong>{formatSo(tongHop.da_nhom_1_2)}</strong>
              </div>
              <div className="statTile">
                <span>Đã nhập đủ dữ liệu bắt buộc (như form Nhóm 4)</span>
                <strong>{formatSo(tongHop.da_thu_thap)}</strong>
              </div>
              <div className="statTile">
                <span>Số thửa đã làm (Nhóm 1/2 + đã nhập biểu)</span>
                <strong style={{ color: "#2e7d32" }}>
                  {formatSo(daLam)} <span style={{ fontWeight: 400, fontSize: 14 }}>({tyLeDaLam}%)</span>
                </strong>
              </div>
              <div className="statTile">
                <span>Còn thiếu dữ liệu</span>
                <strong style={{ color: "#c0392b" }}>{formatSo(tongHop.con_thieu)}</strong>
              </div>
            </div>

            <div
              className="importCard statsTableCard"
              style={{ width: "80%", maxWidth: "80%", margin: "16px auto 0" }}
            >
              <label>
                Chi tiết theo xã/phường ({formatSo(filteredRows.length)}/{formatSo(theoXaRows.length)})
              </label>

              <input
                type="text"
                className="filterInput"
                autoComplete="off"
                value={tableFilter}
                placeholder="Lọc theo tên hoặc mã xã/phường…"
                style={{ marginTop: 10, marginBottom: 10 }}
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
                        <td colSpan={SORT_COLUMNS.length}>
                          {theoXaRows.length === 0 ? "Chưa có dữ liệu" : "Không tìm thấy xã/phường phù hợp"}
                        </td>
                      </tr>
                    ) : (
                      filteredRows.map((row) => (
                        <tr key={row.ma_xa}>
                          <td>{row.ten_xa}</td>
                          <td>{formatSo(row.tong)}</td>
                          <td>{formatSo(row.da_nhom_1_2)}</td>
                          <td>{formatSo(row.da_thu_thap)}</td>
                          <td>{formatSo(row.da_lam)}</td>
                          <td>{row.percent}%</td>
                          <td>{formatSo(row.con_thieu)}</td>
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
