import { useEffect, useMemo, useState } from "react";

import { getGcnStats, getXaList } from "./services/parcelService";
import { GCN_COLOR } from "./utils/constants";

// Cùng 1 màu "đã nhập biểu" với bản đồ chính (utils/constants.js
// GCN_COLOR). CHUA_NHAP_COLOR khác màu "chưa phân loại" của bản đồ chính
// (GROUP_COLORS.DEFAULT = #94a3b8) — giữ nguyên giá trị riêng #cbd5e1
// đang hiển thị trên dashboard này, không đổi để tránh lệch màu so với
// trước khi refactor.
const DA_NHAP_COLOR = GCN_COLOR;
const CHUA_NHAP_COLOR = "#cbd5e1";

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

function formatThoiDiem(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

function formatPercent(daNhap, tong) {
  if (!tong) return 0;
  return Math.round((daNhap / tong) * 100);
}

// Cấu hình cột cho phép bấm tiêu đề để sắp xếp bảng "Tất cả xã/phường".
// defaultDir: hướng áp dụng khi bấm lần đầu vào 1 cột khác.
const SORT_COLUMNS = [
  { key: "ten_xa", label: "Xã / phường", type: "text", defaultDir: "asc" },
  { key: "tong_so_thua", label: "Chưa tạo lập DL", type: "number", defaultDir: "desc" },
  { key: "da_nhap_bieu", label: "Đã nhập biểu", type: "number", defaultDir: "desc" },
  { key: "percent", label: "Tỉ lệ", type: "number", defaultDir: "asc" },
];

// Vành khuyên (donut) 2 phần dùng stroke-dasharray trên <circle> — đơn
// giản hơn vẽ path arc tay, và dễ có bo tròn đầu nét (round cap) theo
// đúng tinh thần "4px rounded data-end" của mark spec.
function DonutChart({ daNhap, tong }) {
  const percent = formatPercent(daNhap, tong);
  const size = 200;
  const stroke = 26;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const daNhapLength = tong ? (daNhap / tong) * circumference : 0;

  return (
    <div className="donutWrap">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`${percent}% thửa đất đã nhập biểu`}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={CHUA_NHAP_COLOR}
          strokeWidth={stroke}
        >
          <title>{`Chưa nhập biểu: ${formatSo(tong - daNhap)} thửa`}</title>
        </circle>

        {daNhap > 0 && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={DA_NHAP_COLOR}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${daNhapLength} ${circumference - daNhapLength}`}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          >
            <title>{`Đã nhập biểu: ${formatSo(daNhap)} thửa`}</title>
          </circle>
        )}

        <text
          x="50%"
          y="47%"
          textAnchor="middle"
          fontSize="34"
          fontWeight="700"
          fill="#0b0b0b"
        >
          {percent}%
        </text>
        <text
          x="50%"
          y="63%"
          textAnchor="middle"
          fontSize="12"
          fill="#52514e"
        >
          đã nhập biểu
        </text>
      </svg>
    </div>
  );
}

export default function GcnDashboardPage({ onNavigateHome }) {
  const [xaList, setXaList] = useState([]);
  const [stats, setStats] = useState([]);
  const [asOf, setAsOf] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [selectedMaXa, setSelectedMaXa] = useState("");
  const [xaQuery, setXaQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const [sort, setSort] = useState({ key: "percent", dir: "asc" });
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

    Promise.all([getXaList(), getGcnStats()])
      .then(([xaResult, statsResult]) => {
        setXaList(xaResult?.items || []);
        setStats(statsResult?.items || []);
        setAsOf(statsResult?.as_of || null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const xaNameByCode = useMemo(() => {
    const map = {};
    xaList.forEach(({ ma_xa, ten_xa }) => {
      map[ma_xa] = ten_xa;
    });
    return map;
  }, [xaList]);

  // Mặc định sắp theo % hoàn thành tăng dần — xã còn thu thập dở dang
  // nhất lên đầu bảng, vì mục tiêu chính của dự án là thu thập cho xong.
  // Bấm tiêu đề cột (SORT_COLUMNS/handleSort) để đổi cách sắp.
  const rows = useMemo(() => {
    const column = SORT_COLUMNS.find((c) => c.key === sort.key);
    const mapped = stats.map((row) => ({
      ...row,
      ten_xa: xaNameByCode[row.ma_xa] || row.ma_xa,
      percent: formatPercent(row.da_nhap_bieu, row.tong_so_thua),
    }));
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
  }, [stats, xaNameByCode, sort]);

  // Ô lọc riêng cho bảng "Tất cả xã/phường" (khác ô combobox chọn 1 xã để
  // xem donut chart ở trên) — lọc theo tên hoặc mã xã.
  const filteredRows = useMemo(() => {
    const keyword = tableFilter.trim().toLocaleLowerCase("vi");
    if (!keyword) return rows;
    return rows.filter(({ ma_xa, ten_xa }) =>
      `${ten_xa} ${ma_xa}`.toLocaleLowerCase("vi").includes(keyword),
    );
  }, [rows, tableFilter]);

  const filteredXaOptions = useMemo(() => {
    const keyword = xaQuery.trim().toLocaleLowerCase("vi");
    const options = rows.map(({ ma_xa, ten_xa }) => ({ ma_xa, ten_xa }));
    if (!keyword) return options;
    return options.filter(({ ma_xa, ten_xa }) =>
      `${ten_xa} ${ma_xa}`.toLocaleLowerCase("vi").includes(keyword),
    );
  }, [rows, xaQuery]);

  const totals = useMemo(() => {
    return rows.reduce(
      (acc, row) => {
        acc.tong += row.tong_so_thua;
        acc.daNhap += row.da_nhap_bieu;
        return acc;
      },
      { tong: 0, daNhap: 0 },
    );
  }, [rows]);

  const selected = rows.find((row) => row.ma_xa === selectedMaXa) || null;

  const handleSelectXa = (maXa, tenXa) => {
    setSelectedMaXa(maXa);
    setXaQuery(tenXa || maXa);
    setDropdownOpen(false);
  };

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Thống kê thu thập dữ liệu</h1>
          <p>
            Tỉ lệ đã nhập biểu GCN trong nhóm thửa chưa tạo lập dữ liệu
            (ngoài Nhóm 1, Nhóm 2), theo từng xã/phường
          </p>
          {asOf && (
            <p className="dashboardAsOf">
              Số liệu tính lúc {formatThoiDiem(asOf)}
            </p>
          )}
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
                <span>Thửa chưa tạo lập dữ liệu (ngoài Nhóm 1/2)</span>
                <strong>{formatSo(totals.tong)}</strong>
              </div>
              <div className="statTile">
                <span>Đã nhập biểu</span>
                <strong style={{ color: DA_NHAP_COLOR }}>
                  {formatSo(totals.daNhap)}
                </strong>
              </div>
              <div className="statTile">
                <span>Tỉ lệ hoàn thành chung</span>
                <strong>{formatPercent(totals.daNhap, totals.tong)}%</strong>
              </div>
            </div>

            <div className="dashboardGrid">
              <div className="importCard">
                <label htmlFor="dashboardMaXa">Chọn xã / phường</label>
                <div className="comboBox">
                  <input
                    id="dashboardMaXa"
                    type="text"
                    className="filterInput"
                    autoComplete="off"
                    value={xaQuery}
                    placeholder="Nhập tên xã/phường để tìm…"
                    onChange={(event) => {
                      setXaQuery(event.target.value);
                      setSelectedMaXa("");
                      setDropdownOpen(true);
                    }}
                    onFocus={() => setDropdownOpen(true)}
                    onBlur={() => setDropdownOpen(false)}
                  />

                  {dropdownOpen && (
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
                              ma_xa === selectedMaXa ? " active" : ""
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

                {!selected ? (
                  <div className="emptyState">
                    <div>📊</div>
                    <strong>Chưa chọn xã/phường</strong>
                    <span>Chọn 1 xã/phường ở ô trên để xem biểu đồ.</span>
                  </div>
                ) : (
                  <>
                    <DonutChart
                      daNhap={selected.da_nhap_bieu}
                      tong={selected.tong_so_thua}
                    />

                    <div className="donutLegend">
                      <div>
                        <span style={{ backgroundColor: DA_NHAP_COLOR }} />
                        <label>Đã nhập biểu</label>
                        <strong>{formatSo(selected.da_nhap_bieu)}</strong>
                      </div>
                      <div>
                        <span style={{ backgroundColor: CHUA_NHAP_COLOR }} />
                        <label>Chưa nhập biểu</label>
                        <strong>{formatSo(selected.chua_nhap_bieu)}</strong>
                      </div>
                    </div>

                    <div className="notice">
                      <strong>{selected.ten_xa}</strong>
                      <span>
                        {formatSo(selected.tong_so_thua)} thửa chưa thuộc
                        Nhóm 1/Nhóm 2 (chưa tạo lập dữ liệu) — tỉ lệ trên là
                        số thửa trong nhóm này đã được nhập biểu GCN.
                      </span>
                    </div>
                  </>
                )}
              </div>

              <div className="importCard statsTableCard">
                <label>
                  Tất cả xã/phường ({formatSo(filteredRows.length)}/{formatSo(rows.length)})
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
                          <tr
                            key={row.ma_xa}
                            className={
                              row.ma_xa === selectedMaXa ? "active" : ""
                            }
                            onClick={() => handleSelectXa(row.ma_xa, row.ten_xa)}
                          >
                            <td>{row.ten_xa}</td>
                            <td>{formatSo(row.tong_so_thua)}</td>
                            <td>{formatSo(row.da_nhap_bieu)}</td>
                            <td>
                              <div className="statsTableBar">
                                <div className="statsTableBarTrack">
                                  <div
                                    className="statsTableBarFill"
                                    style={{ width: `${row.percent}%` }}
                                  />
                                </div>
                                <span>{row.percent}%</span>
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
