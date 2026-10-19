import { useEffect, useMemo, useState } from "react";

import { API_URL } from "./config/env";
import { getNhom3TongHop } from "./services/parcelService";

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

function formatPercent(phan, tong) {
  if (!tong) return 0;
  return Math.round((phan / tong) * 1000) / 10;
}

// 4 Tổ kiểm tra, giám sát KH113 (Quyết định 867/QĐ-VPĐKĐĐ ngày
// 01/10/2026) — khu vực liệt kê theo đúng Danh sách kèm theo quyết định,
// chỉ để hiển thị gợi nhớ trong dropdown; việc lọc thật nằm ở bảng
// nhom3_to_giam_sat phía backend (xem supabase/schema.sql).
const TO_GIAM_SAT_OPTIONS = [
  { value: "1", label: "Tổ 1 — Buôn Đôn, Ea Súp, Tuy Hòa, Đông Hòa, Tuy An" },
  { value: "2", label: "Tổ 2 — Cư Kuin, Krông Ana, Krông Bông, Lắk, Phú Hòa, Tây Hòa" },
  { value: "3", label: "Tổ 3 — Buôn Ma Thuột, Buôn Hồ, Cư M'gar, Ea H'leo, Krông Búk, Krông Năng" },
  { value: "4", label: "Tổ 4 — Krông Pắc, Ea Kar, M'Drắk, Sơn Hòa, Sông Hinh, Đồng Xuân, Sông Cầu" },
];

// Cấu hình cột cho phép bấm tiêu đề để sắp xếp bảng "Chi tiết theo
// xã/phường" — cùng pattern với GcnDashboardPage.jsx (SORT_COLUMNS/handleSort).
// defaultDir: hướng áp dụng khi bấm lần đầu vào 1 cột khác.
const SORT_COLUMNS = [
  { key: "ten_xa", label: "Xã / phường", type: "text", defaultDir: "asc" },
  { key: "tong", label: "Tổng xã phải làm (đã trừ Chi nhánh KV + chưa liên kết KG)", type: "number", defaultDir: "desc" },
  { key: "da_nhom_1_2", label: "Đã Nhóm 1", type: "number", defaultDir: "desc" },
  { key: "da_nhom_1_2_da_nhap", label: "Nhóm 1 đã nhập biểu (Xã làm)", type: "number", defaultDir: "desc" },
  { key: "da_nhom_1_2_chua_nhap", label: "Nhóm 1 chưa nhập biểu (Chi nhánh KV làm)", type: "number", defaultDir: "desc" },
  { key: "da_thu_thap", label: "Đã nhập đủ dữ liệu", type: "number", defaultDir: "desc" },
  { key: "da_lam", label: "Đã làm (Nhóm 1 đã nhập + đã nhập biểu)", type: "number", defaultDir: "desc" },
  { key: "percent", label: "%", type: "number", defaultDir: "asc" },
  { key: "con_thieu", label: "Còn thiếu", type: "number", defaultDir: "desc" },
  { key: "chua_lien_ket_khong_gian", label: "Chưa liên kết không gian", type: "number", defaultDir: "desc" },
];

export default function Nhom3ConThieuPage({
  onNavigateHome,
  onNavigateNhom3Dashboard,
  onNavigateNhom3ChiTiet,
}) {
  const [tongHop, setTongHop] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloadingXa, setDownloadingXa] = useState("");
  const [downloadingNhom1ChuaXa, setDownloadingNhom1ChuaXa] = useState("");
  const [downloadingNhom1DaXa, setDownloadingNhom1DaXa] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const [toGiamSat, setToGiamSat] = useState("");
  const [downloadingTongHop, setDownloadingTongHop] = useState(false);

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

  const handleExportConThieu = async (maXa) => {
    if (downloadingXa) return;
    setDownloadingXa(maXa);
    setDownloadError("");
    try {
      const res = await fetch(
        `${API_URL}/api/nhom3-con-thieu/export?ma_xa=${encodeURIComponent(maXa)}`,
      );
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
      link.download = `nhom3_con_thieu_${maXa}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err.message);
    } finally {
      setDownloadingXa("");
    }
  };

  const handleExportNhom1ChuaNhap = async (maXa) => {
    if (downloadingNhom1ChuaXa) return;
    setDownloadingNhom1ChuaXa(maXa);
    setDownloadError("");
    try {
      const res = await fetch(
        `${API_URL}/api/nhom3-con-thieu/export-nhom1-chua-nhap?ma_xa=${encodeURIComponent(maXa)}`,
      );
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
      link.download = `nhom3_nhom1_chua_nhap_${maXa}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err.message);
    } finally {
      setDownloadingNhom1ChuaXa("");
    }
  };

  const handleExportNhom1DaNhap = async (maXa) => {
    if (downloadingNhom1DaXa) return;
    setDownloadingNhom1DaXa(maXa);
    setDownloadError("");
    try {
      const res = await fetch(
        `${API_URL}/api/nhom3-con-thieu/export-nhom1-da-nhap?ma_xa=${encodeURIComponent(maXa)}`,
      );
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
      link.download = `nhom3_nhom1_da_nhap_${maXa}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err.message);
    } finally {
      setDownloadingNhom1DaXa("");
    }
  };

  useEffect(() => {
    setLoading(true);
    setError("");
    getNhom3TongHop(toGiamSat ? { to_giam_sat: toGiamSat } : undefined)
      .then((result) => setTongHop(result))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [toGiamSat]);

  const handleExportTongHop = async () => {
    if (downloadingTongHop) return;
    setDownloadingTongHop(true);
    setDownloadError("");
    try {
      const query = toGiamSat ? `?to_giam_sat=${encodeURIComponent(toGiamSat)}` : "";
      const res = await fetch(`${API_URL}/api/nhom3-con-thieu/export-tong-hop${query}`);
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
      link.download = `nhom3_tong_hop_${toGiamSat ? `to${toGiamSat}` : "tatca"}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err.message);
    } finally {
      setDownloadingTongHop(false);
    }
  };

  const theoXaRows = useMemo(() => {
    return (tongHop?.theo_xa || []).map((row) => {
      // Chỉ tính phần xã THỰC SỰ phải làm và đã làm được — Nhóm 1 ĐÃ nhập
      // biểu (không tính phần Chi nhánh KV làm trực tiếp, chưa nhập) +
      // Nhóm 3 đã nhập biểu (yêu cầu người dùng).
      const daLam = (row.da_nhom_1_2_da_nhap || 0) + (row.da_thu_thap || 0);
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

  const daLam = (tongHop?.da_nhom_1_2_da_nhap || 0) + (tongHop?.da_thu_thap || 0);
  const tyLeDaLam = formatPercent(daLam, tongHop?.tong || 0);

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Nhóm 3 — thống kê còn thiếu dữ liệu</h1>
          <p>
            Đối chiếu danh sách thửa cần thu thập (Nhóm 3) với thửa đã thuộc Nhóm 1 và thửa đã thu thập — chỉ còn lại là thửa thật sự cần nhập biểu.
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
        <div
          style={{
            width: "80%",
            maxWidth: "80%",
            margin: "0 auto 12px",
            display: "flex",
            gap: 12,
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <label htmlFor="nhom3ToGiamSat" style={{ fontWeight: 600 }}>
            Tổ kiểm tra, giám sát:
          </label>
          <select
            id="nhom3ToGiamSat"
            className="filterInput"
            style={{ maxWidth: 440 }}
            value={toGiamSat}
            onChange={(event) => setToGiamSat(event.target.value)}
          >
            <option value="">Tất cả</option>
            {TO_GIAM_SAT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="downloadButton"
            disabled={downloadingTongHop}
            style={{ opacity: downloadingTongHop ? 0.5 : 1 }}
            onClick={handleExportTongHop}
          >
            {downloadingTongHop ? "⏳ Đang tải…" : "⬇️ Xuất Excel tổng hợp"}
          </button>
        </div>

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
                <span>Tổng xã phải làm (đã trừ Chi nhánh KV + chưa liên kết không gian)</span>
                <strong>{formatSo(tongHop.tong)}</strong>
              </div>
              <div className="statTile">
                <span>Đã lên Nhóm 1 (không cần nhập biểu)</span>
                <strong>{formatSo(tongHop.da_nhom_1_2)}</strong>
              </div>
              <div className="statTile">
                <span>Trong đó: Nhóm 1 đã nhập biểu (Xã làm)</span>
                <strong style={{ color: "#2e7d32" }}>{formatSo(tongHop.da_nhom_1_2_da_nhap)}</strong>
              </div>
              <div className="statTile">
                <span>Trong đó: Nhóm 1 chưa nhập biểu (Chi nhánh KV làm — đã trừ khỏi tổng)</span>
                <strong style={{ color: "#8e5c00" }}>{formatSo(tongHop.da_nhom_1_2_chua_nhap)}</strong>
              </div>
              <div className="statTile">
                <span>Đã nhập đủ dữ liệu bắt buộc (như form Nhóm 4)</span>
                <strong>{formatSo(tongHop.da_thu_thap)}</strong>
              </div>
              <div className="statTile">
                <span>Số thửa đã làm (Nhóm 1 đã nhập + đã nhập biểu)</span>
                <strong style={{ color: "#2e7d32" }}>
                  {formatSo(daLam)} <span style={{ fontWeight: 400, fontSize: 14 }}>({tyLeDaLam}%)</span>
                </strong>
              </div>
              <div className="statTile">
                <span>Còn thiếu dữ liệu</span>
                <strong style={{ color: "#c0392b" }}>{formatSo(tongHop.con_thieu)}</strong>
              </div>
              <div className="statTile">
                <span>Chưa liên kết không gian (đã trừ khỏi tổng)</span>
                <strong style={{ color: "#6a817e" }}>{formatSo(tongHop.chua_lien_ket_khong_gian)}</strong>
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

              {downloadError && (
                <div className="notice error" style={{ marginBottom: 10 }}>
                  <strong>Không tải được file</strong>
                  <span>{downloadError}</span>
                </div>
              )}

              <div className="statsTableWrap">
                <table className="statsTable">
                  <thead>
                    <tr>
                      {SORT_COLUMNS.map((column) => (
                        <th
                          key={column.key}
                          onClick={() => handleSort(column.key)}
                          style={{ cursor: "pointer", userSelect: "none", whiteSpace: "normal", maxWidth: 110 }}
                          title="Bấm để sắp xếp"
                        >
                          {column.label}
                          <span style={{ marginLeft: 4, opacity: sort.key === column.key ? 1 : 0.25 }}>
                            {sort.key === column.key ? (sort.dir === "asc" ? "▲" : "▼") : "↕"}
                          </span>
                        </th>
                      ))}
                      <th style={{ whiteSpace: "normal", maxWidth: 90 }}>Danh sách</th>
                      <th style={{ whiteSpace: "normal", maxWidth: 90 }}>Excel</th>
                      <th style={{ whiteSpace: "normal", maxWidth: 90 }}>Excel (Nhóm 1 đã nhập)</th>
                      <th style={{ whiteSpace: "normal", maxWidth: 90 }}>Excel (Nhóm 1 chưa nhập)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.length === 0 ? (
                      <tr>
                        <td colSpan={SORT_COLUMNS.length + 4}>
                          {theoXaRows.length === 0 ? "Chưa có dữ liệu" : "Không tìm thấy xã/phường phù hợp"}
                        </td>
                      </tr>
                    ) : (
                      filteredRows.map((row) =>
                        row.ghi_chu ? (
                          <tr key={row.ma_xa} style={{ color: "#6b7280", fontStyle: "italic" }}>
                            <td>{row.ten_xa}</td>
                            <td colSpan={SORT_COLUMNS.length - 1 + 4}>{row.ghi_chu}</td>
                          </tr>
                        ) : (
                          <tr key={row.ma_xa}>
                            <td>{row.ten_xa}</td>
                            <td>{formatSo(row.tong)}</td>
                            <td>{formatSo(row.da_nhom_1_2)}</td>
                            <td>{formatSo(row.da_nhom_1_2_da_nhap)}</td>
                            <td>{formatSo(row.da_nhom_1_2_chua_nhap)}</td>
                            <td>{formatSo(row.da_thu_thap)}</td>
                            <td>{formatSo(row.da_lam)}</td>
                            <td>{row.percent}%</td>
                            <td>{formatSo(row.con_thieu)}</td>
                            <td>{formatSo(row.chua_lien_ket_khong_gian)}</td>
                            <td style={{ textAlign: "center" }}>
                              <button
                                type="button"
                                title={`Xem danh sách thửa còn thiếu của ${row.ten_xa}`}
                                onClick={() => onNavigateNhom3ChiTiet?.(row.ma_xa, row.ten_xa)}
                                style={{
                                  border: "none",
                                  background: "transparent",
                                  cursor: "pointer",
                                  fontSize: 18,
                                  lineHeight: 1,
                                }}
                              >
                                📋
                              </button>
                            </td>
                            <td style={{ textAlign: "center" }}>
                              <button
                                type="button"
                                title={`Tải Excel danh sách thửa còn thiếu của ${row.ten_xa}`}
                                disabled={downloadingXa === row.ma_xa}
                                onClick={() => handleExportConThieu(row.ma_xa)}
                                style={{
                                  border: "none",
                                  background: "transparent",
                                  cursor: downloadingXa === row.ma_xa ? "default" : "pointer",
                                  fontSize: 18,
                                  lineHeight: 1,
                                  opacity: downloadingXa === row.ma_xa ? 0.5 : 1,
                                }}
                              >
                                {downloadingXa === row.ma_xa ? "⏳" : "⬇️"}
                              </button>
                            </td>
                            <td style={{ textAlign: "center" }}>
                              <button
                                type="button"
                                title={`Tải Excel thửa Nhóm 1 đã nhập biểu của ${row.ten_xa}`}
                                disabled={downloadingNhom1DaXa === row.ma_xa}
                                onClick={() => handleExportNhom1DaNhap(row.ma_xa)}
                                style={{
                                  border: "none",
                                  background: "transparent",
                                  cursor: downloadingNhom1DaXa === row.ma_xa ? "default" : "pointer",
                                  fontSize: 18,
                                  lineHeight: 1,
                                  opacity: downloadingNhom1DaXa === row.ma_xa ? 0.5 : 1,
                                }}
                              >
                                {downloadingNhom1DaXa === row.ma_xa ? "⏳" : "🏛️"}
                              </button>
                            </td>
                            <td style={{ textAlign: "center" }}>
                              <button
                                type="button"
                                title={`Tải Excel thửa Nhóm 1 chưa nhập biểu của ${row.ten_xa}`}
                                disabled={downloadingNhom1ChuaXa === row.ma_xa}
                                onClick={() => handleExportNhom1ChuaNhap(row.ma_xa)}
                                style={{
                                  border: "none",
                                  background: "transparent",
                                  cursor: downloadingNhom1ChuaXa === row.ma_xa ? "default" : "pointer",
                                  fontSize: 18,
                                  lineHeight: 1,
                                  opacity: downloadingNhom1ChuaXa === row.ma_xa ? 0.5 : 1,
                                }}
                              >
                                {downloadingNhom1ChuaXa === row.ma_xa ? "⏳" : "🏢"}
                              </button>
                            </td>
                          </tr>
                        ),
                      )
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
