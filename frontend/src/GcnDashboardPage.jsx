import { useEffect, useMemo, useState } from "react";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

// Cùng 1 màu "đã nhập biểu" với bản đồ chính (App.jsx GCN_COLOR) và
// cùng màu xám mặc định (App.jsx GROUP_COLORS.DEFAULT) — giữ ngôn ngữ
// màu nhất quán giữa bản đồ và dashboard.
const DA_NHAP_COLOR = "#2563eb";
const CHUA_NHAP_COLOR = "#cbd5e1";

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

function formatPercent(daNhap, tong) {
  if (!tong) return 0;
  return Math.round((daNhap / tong) * 100);
}

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [selectedMaXa, setSelectedMaXa] = useState("");
  const [xaQuery, setXaQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError("");

    Promise.all([
      fetch(`${API_URL}/api/parcels/xa-list`).then((r) => r.json()),
      fetch(`${API_URL}/api/gcn-stats`).then((r) => r.json()),
    ])
      .then(([xaResult, statsResult]) => {
        if (xaResult?.error) throw new Error(xaResult.error);
        if (statsResult?.error) throw new Error(statsResult.error);
        setXaList(xaResult?.items || []);
        setStats(statsResult?.items || []);
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

  // Sắp theo % hoàn thành tăng dần — xã còn thu thập dở dang nhất lên
  // đầu bảng, vì mục tiêu chính của dự án là thu thập cho xong.
  const rows = useMemo(() => {
    return stats
      .map((row) => ({
        ...row,
        ten_xa: xaNameByCode[row.ma_xa] || row.ma_xa,
        percent: formatPercent(row.da_nhap_bieu, row.tong_so_thua),
      }))
      .sort((a, b) => a.percent - b.percent || a.ten_xa.localeCompare(b.ten_xa, "vi"));
  }, [stats, xaNameByCode]);

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
          <p>Tỉ lệ thửa đất đã nhập biểu GCN theo từng xã/phường</p>
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
                <span>Tổng số thửa (toàn bộ)</span>
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
                        Tổng {formatSo(selected.tong_so_thua)} thửa đất — dự
                        án tập trung thu thập dữ liệu cho các thửa chưa có
                        dữ liệu, nên tỉ lệ trên phản ánh tiến độ thu thập.
                      </span>
                    </div>
                  </>
                )}
              </div>

              <div className="importCard statsTableCard">
                <label>Tất cả xã/phường (sắp theo tỉ lệ thấp → cao)</label>

                <div className="statsTableWrap">
                  <table className="statsTable">
                    <thead>
                      <tr>
                        <th>Xã / phường</th>
                        <th>Tổng số thửa</th>
                        <th>Đã nhập biểu</th>
                        <th>Tỉ lệ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
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
                      ))}
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
