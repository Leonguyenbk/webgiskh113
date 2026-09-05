import { useEffect, useMemo, useState } from "react";

import { API_URL } from "./config/env";
import { getBieuThongKe, getXaList } from "./services/parcelService";
import { GCN_COLOR } from "./utils/constants";

const DA_NHAP_COLOR = GCN_COLOR;

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

function formatThoiDiem(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

// Cấu hình cột cho phép bấm tiêu đề để sắp xếp. defaultDir: hướng áp
// dụng khi bấm lần đầu vào 1 cột khác — số thì mặc định giảm dần (xã
// nhiều lên đầu), chữ thì mặc định tăng dần (A→Z).
//
// Mẫu số duy nhất hiển thị là "Chưa tạo lập dữ liệu" (Nhóm 3/loại 4 —
// ngoài Nhóm 1/2 KH 2959), giống cách tính ở GcnDashboardPage
// (/thong-ke-gcn) — KHÔNG hiển thị tổng số thửa toàn xã (mọi nhóm) và
// KHÔNG hiển thị thanh tỉ lệ, vì "Từ form"/"Từ nguồn khác"/"Tổng đã nhập
// biểu" vẫn đếm trên TẤT CẢ bản ghi (không lọc nhóm) nên % so với riêng
// nhóm 3 sẽ gây hiểu nhầm.
const SORT_COLUMNS = [
  { key: "ten_xa", label: "Xã / phường", type: "text", defaultDir: "asc" },
  {
    key: "so_thua_can_thu_thap",
    label: "Chưa tạo lập dữ liệu (Nhóm 3)",
    type: "number",
    defaultDir: "desc",
  },
  { key: "da_nhap_form", label: "Từ form", type: "number", defaultDir: "desc" },
  { key: "da_nhap_nguon_khac", label: "Từ nguồn khác", type: "number", defaultDir: "desc" },
  { key: "da_nhap_bieu", label: "Tổng đã nhập biểu", type: "number", defaultDir: "desc" },
];

// Trang "Thống kê nhập biểu" — khác GcnDashboardPage (chỉ tính nhóm thửa
// "chưa tạo lập dữ liệu", ngoài Nhóm 1/2): trang này tách riêng số thửa
// có dữ liệu nhập từ biểu Nhóm 4 (form) với số thửa có dữ liệu từ nguồn
// khác (đồng bộ Google Sheet) — đếm trên TẤT CẢ bản ghi, không phân biệt
// nhóm KH 2959. 1 thửa có thể có cả 2 nên "Từ form" + "Từ nguồn khác" có
// thể lớn hơn "Tổng đã nhập biểu" (số thửa duy nhất).
export default function BieuThongKePage({ onNavigateHome }) {
  const [xaList, setXaList] = useState([]);
  const [stats, setStats] = useState([]);
  const [asOf, setAsOf] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [exportNotice, setExportNotice] = useState("");

  const [sort, setSort] = useState({ key: "ten_xa", dir: "asc" });
  const [xaFilter, setXaFilter] = useState("");

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

    Promise.all([getXaList(), getBieuThongKe()])
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

  const rows = useMemo(() => {
    const column = SORT_COLUMNS.find((c) => c.key === sort.key);
    const mapped = stats.map((row) => ({
      ...row,
      ten_xa: xaNameByCode[row.ma_xa] || row.ma_xa,
    }));
    mapped.sort((a, b) => {
      let cmp;
      if (column?.type === "text") {
        cmp = a[sort.key].localeCompare(b[sort.key], "vi");
      } else {
        cmp = a[sort.key] - b[sort.key];
      }
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return mapped;
  }, [stats, xaNameByCode, sort]);

  const filteredRows = useMemo(() => {
    const keyword = xaFilter.trim().toLocaleLowerCase("vi");
    if (!keyword) return rows;
    return rows.filter(({ ma_xa, ten_xa }) =>
      `${ten_xa} ${ma_xa}`.toLocaleLowerCase("vi").includes(keyword),
    );
  }, [rows, xaFilter]);

  const totals = useMemo(() => {
    return filteredRows.reduce(
      (acc, row) => {
        acc.canThuThap += row.so_thua_can_thu_thap;
        acc.tuForm += row.da_nhap_form;
        acc.tuNguonKhac += row.da_nhap_nguon_khac;
        acc.daNhap += row.da_nhap_bieu;
        return acc;
      },
      { canThuThap: 0, tuForm: 0, tuNguonKhac: 0, daNhap: 0 },
    );
  }, [filteredRows]);

  const handleExport = async () => {
    if (exporting) return;
    setExporting(true);
    setExportError("");
    setExportNotice("");
    try {
      const res = await fetch(`${API_URL}/api/bieu-thong-ke/export`);
      if (!res.ok) {
        let message = `Tải thất bại (HTTP ${res.status})`;
        try {
          message = (await res.json())?.error || message;
        } catch {
          /* body không phải JSON */
        }
        throw new Error(message);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "thong_ke_nhap_bieu_theo_xa.xlsx";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setExportNotice("Đã tải file thống kê.");
    } catch (err) {
      setExportError(err.message);
    } finally {
      setExporting(false);
    }
  };

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Thống kê nhập biểu</h1>
          <p>
            Số thửa đất đã nhập biểu theo từng xã/phường — tách form (Nhóm
            4) và nguồn khác, lấy tất cả bản ghi không phân biệt nhóm
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
                <span>Chưa tạo lập dữ liệu (Nhóm 3)</span>
                <strong>{formatSo(totals.canThuThap)}</strong>
              </div>
              <div className="statTile">
                <span>Từ form (Nhóm 4)</span>
                <strong style={{ color: DA_NHAP_COLOR }}>
                  {formatSo(totals.tuForm)}
                </strong>
              </div>
              <div className="statTile">
                <span>Từ nguồn khác</span>
                <strong>{formatSo(totals.tuNguonKhac)}</strong>
              </div>
              <div className="statTile">
                <span>Tổng đã nhập biểu (duy nhất)</span>
                <strong>{formatSo(totals.daNhap)}</strong>
              </div>
            </div>

            <div
              className="importCard statsTableCard"
              style={{ width: "80%", maxWidth: "80%", margin: "0 auto" }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <label style={{ margin: 0 }}>
                  Tất cả xã/phường ({formatSo(filteredRows.length)}/{formatSo(rows.length)})
                </label>
                <button
                  type="button"
                  className="downloadButton"
                  style={{ opacity: exporting ? 0.5 : 1 }}
                  disabled={exporting}
                  onClick={handleExport}
                >
                  {exporting ? "Đang tạo file…" : "⬇ Xuất Excel (toàn bộ)"}
                </button>
              </div>

              <input
                type="text"
                className="filterInput"
                autoComplete="off"
                value={xaFilter}
                placeholder="Lọc theo tên hoặc mã xã/phường…"
                style={{ marginTop: 12 }}
                onChange={(event) => setXaFilter(event.target.value)}
              />

              {exportNotice && (
                <div className="notice" style={{ marginTop: 12 }}>
                  <span>{exportNotice}</span>
                </div>
              )}
              {exportError && (
                <div className="notice error" style={{ marginTop: 12 }}>
                  <strong>Lỗi</strong>
                  <span>{exportError}</span>
                </div>
              )}

              <div className="statsTableWrap" style={{ marginTop: 14 }}>
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
                          <td>{row.ten_xa}</td>
                          <td>{formatSo(row.so_thua_can_thu_thap)}</td>
                          <td>{formatSo(row.da_nhap_form)}</td>
                          <td>{formatSo(row.da_nhap_nguon_khac)}</td>
                          <td>{formatSo(row.da_nhap_bieu)}</td>
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
