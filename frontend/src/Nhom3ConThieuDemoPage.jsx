import { useEffect, useMemo, useState } from "react";

import { API_URL } from "./config/env";
import { getNhom3TongHopCoDinh } from "./services/parcelService";

// Trang DEMO "/nhom-3-con-thieu-demo" — bản sao /nhom-3-con-thieu nhưng số
// lượng gửi xuống CỨNG theo xã (chốt 1 lần vào nhom3_gui_xuong_co_dinh, về
// sau không đổi) và đã làm kẹp tối đa bằng số chốt nên tỷ lệ không bao giờ
// vượt 100% (yêu cầu người dùng). Mọi phép tính nằm ở
// public.nhom3_tong_hop_co_dinh, trang chỉ hiển thị.

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

function formatThoiGian(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())} ${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`;
}

function formatPercent(phan, tong) {
  if (!tong) return 0;
  return Math.min(100, Math.round((phan / tong) * 1000) / 10);
}

const TO_GIAM_SAT_OPTIONS = [
  { value: "1", label: "Tổ 1 — Buôn Đôn, Ea Súp, Tuy Hòa, Đông Hòa, Tuy An" },
  { value: "2", label: "Tổ 2 — Cư Kuin, Krông Ana, Krông Bông, Lắk, Phú Hòa, Tây Hòa" },
  { value: "3", label: "Tổ 3 — Buôn Ma Thuột, Buôn Hồ, Cư M'gar, Ea H'leo, Krông Búk, Krông Năng" },
  { value: "4", label: "Tổ 4 — Krông Pắc, Ea Kar, M'Drắk, Sơn Hòa, Sông Hinh, Đồng Xuân, Sông Cầu" },
];

const SORT_COLUMNS = [
  { key: "ten_xa", label: "Xã / phường", type: "text", defaultDir: "asc" },
  { key: "gui_xuong", label: "Số lượng gửi xuống (cố định)", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "da_nhom_1_2_da_nhap", label: "Nhóm 1 đã nhập biểu (Xã làm)", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "da_thu_thap", label: "Đã nhập đủ dữ liệu", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "da_lam", label: "Đã làm", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "percent", label: "%", type: "number", defaultDir: "asc", group: "loai4" },
  { key: "con_lai", label: "Còn lại", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "ke_hoach", label: "Tổng theo kế hoạch (cố định)", type: "number", defaultDir: "desc", group: "ke_hoach" },
  { key: "da_lam_ke_hoach", label: "Đã thực hiện theo kế hoạch (gồm Loại 1+2+3)", type: "number", defaultDir: "desc", group: "ke_hoach" },
  { key: "percent_ke_hoach", label: "Tỷ lệ theo kế hoạch", type: "number", defaultDir: "asc", group: "ke_hoach" },
];

const GROUP_LABELS = {
  loai4: "Tiến độ thực hiện Loại 4",
  ke_hoach: "Tiến độ thực hiện kế hoạch",
};

const KE_HOACH_BG = "#eef7f0";
const KE_HOACH_BORDER = "2px solid #2e7d32";

export default function Nhom3ConThieuDemoPage({ onNavigateHome, onNavigateNhom3ConThieu, onNavigateNhom3ChiTiet }) {
  const [tongHop, setTongHop] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloadingXa, setDownloadingXa] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const [toGiamSat, setToGiamSat] = useState("");
  const [sort, setSort] = useState({ key: "con_lai", dir: "desc" });
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
      const res = await fetch(`${API_URL}/api/nhom3-con-thieu/export?ma_xa=${encodeURIComponent(maXa)}`);
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
      link.download = `nhom3_tong_gui_xa_${maXa}.xlsx`;
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

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    getNhom3TongHopCoDinh(toGiamSat ? { to_giam_sat: toGiamSat } : undefined, { signal: controller.signal })
      .then((result) => setTongHop(result))
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [toGiamSat]);

  const theoXaRows = useMemo(
    () =>
      (tongHop?.theo_xa || []).map((row) => ({
        ...row,
        ten_xa: row.ten_xa || row.ma_xa,
        percent: formatPercent(row.da_lam, row.gui_xuong),
        percent_ke_hoach: formatPercent(row.da_lam_ke_hoach, row.ke_hoach),
      })),
    [tongHop],
  );

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

  const filteredRows = useMemo(() => {
    const keyword = tableFilter.trim().toLocaleLowerCase("vi");
    if (!keyword) return sortedRows;
    return sortedRows.filter(({ ma_xa, ten_xa }) => `${ten_xa} ${ma_xa}`.toLocaleLowerCase("vi").includes(keyword));
  }, [sortedRows, tableFilter]);

  const tyLeDaLam = formatPercent(tongHop?.da_lam, tongHop?.gui_xuong);
  const tyLeKeHoach = formatPercent(tongHop?.da_lam_ke_hoach, tongHop?.ke_hoach);

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>
            Nhóm 3 — thống kê còn thiếu{" "}
            <span style={{ fontSize: "0.55em", background: "#c0392b", color: "#fff", padding: "2px 8px", borderRadius: 6 }}>
              DEMO
            </span>
            {tongHop?.cap_nhat_luc && (
              <span
                title="Số liệu đã làm tự làm mới mỗi 2 giờ"
                style={{ marginLeft: 10, fontSize: "0.6em", fontWeight: 500, opacity: 0.75, whiteSpace: "nowrap" }}
              >
                🕒 cập nhật lúc {formatThoiGian(tongHop.cap_nhat_luc)}
              </span>
            )}
          </h1>
          <p>
            Số lượng gửi xuống cố định theo xã
            {tongHop?.chot_luc ? ` (chốt lúc ${formatThoiGian(tongHop.chot_luc)})` : ""} — không đổi theo danh sách,
            dự án hay chưa liên kết KG; tỷ lệ tối đa 100%.
          </p>
        </div>
        <a
          className="backLink"
          href="/nhom-3-con-thieu"
          onClick={(event) => {
            event.preventDefault();
            onNavigateNhom3ConThieu?.();
          }}
        >
          Trang gốc →
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
          <label htmlFor="nhom3DemoToGiamSat" style={{ fontWeight: 600 }}>
            Tổ kiểm tra, giám sát:
          </label>
          <select
            id="nhom3DemoToGiamSat"
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
                <span>Số lượng gửi xuống (cố định)</span>
                <strong>{formatSo(tongHop.gui_xuong)}</strong>
              </div>
              <div className="statTile">
                <span>Trong đó: Nhóm 1 đã nhập biểu (Xã làm)</span>
                <strong style={{ color: "#2e7d32" }}>{formatSo(tongHop.da_nhom_1_2_da_nhap)}</strong>
              </div>
              <div className="statTile">
                <span>Đã nhập đủ dữ liệu bắt buộc (như form Nhóm 4)</span>
                <strong>{formatSo(tongHop.da_thu_thap)}</strong>
              </div>
              <div className="statTile">
                <span>Số thửa đã làm (tối đa bằng số gửi xuống từng xã)</span>
                <strong style={{ color: "#2e7d32" }}>
                  {formatSo(tongHop.da_lam)} <span style={{ fontWeight: 400, fontSize: 14 }}>({tyLeDaLam}%)</span>
                </strong>
              </div>
              <div className="statTile">
                <span>Còn lại</span>
                <strong style={{ color: "#c0392b" }}>{formatSo(tongHop.con_lai)}</strong>
              </div>
              <div className="statTile">
                <span>Trong đó: Loại 1 + 2 + 3 đã làm (VPĐK gửi song song)</span>
                <strong style={{ color: "#6a817e" }}>{formatSo(tongHop.loai_123_da_lam)}</strong>
              </div>
              <div className="statTile">
                <span>Tổng theo kế hoạch (cố định)</span>
                <strong>{formatSo(tongHop.ke_hoach)}</strong>
              </div>
              <div className="statTile">
                <span>Tỷ lệ theo kế hoạch</span>
                <strong style={{ color: "#2e7d32" }}>
                  {formatSo(tongHop.da_lam_ke_hoach)}{" "}
                  <span style={{ fontWeight: 400, fontSize: 14 }}>({tyLeKeHoach}%)</span>
                </strong>
              </div>
            </div>

            <div className="importCard statsTableCard" style={{ width: "80%", maxWidth: "80%", margin: "16px auto 0" }}>
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
                <table className="statsTable nhom3TongHopTable">
                  <thead>
                    <tr>
                      <th rowSpan={2} style={{ verticalAlign: "middle" }}>
                        <span
                          onClick={() => handleSort("ten_xa")}
                          style={{ cursor: "pointer", userSelect: "none" }}
                          title="Bấm để sắp xếp"
                        >
                          Xã / phường
                          <span style={{ marginLeft: 4, opacity: sort.key === "ten_xa" ? 1 : 0.25 }}>
                            {sort.key === "ten_xa" ? (sort.dir === "asc" ? "▲" : "▼") : "↕"}
                          </span>
                        </span>
                      </th>
                      {["loai4", "ke_hoach"].map((groupKey) => (
                        <th
                          key={groupKey}
                          colSpan={SORT_COLUMNS.filter((c) => c.group === groupKey).length}
                          style={{
                            textAlign: "center",
                            ...(groupKey === "ke_hoach" ? { background: KE_HOACH_BG, borderLeft: KE_HOACH_BORDER } : {}),
                          }}
                        >
                          {GROUP_LABELS[groupKey]}
                        </th>
                      ))}
                      <th rowSpan={2} style={{ whiteSpace: "normal", maxWidth: 90, verticalAlign: "middle" }}>
                        Danh sách
                      </th>
                      <th rowSpan={2} style={{ whiteSpace: "normal", maxWidth: 90, verticalAlign: "middle" }}>
                        Excel
                      </th>
                    </tr>
                    <tr>
                      {SORT_COLUMNS.filter((c) => c.group).map((column, index, arr) => (
                        <th
                          key={column.key}
                          onClick={() => handleSort(column.key)}
                          style={{
                            cursor: "pointer",
                            userSelect: "none",
                            whiteSpace: "normal",
                            maxWidth: 110,
                            ...(column.group === "ke_hoach" ? { background: KE_HOACH_BG } : {}),
                            ...(column.group === "ke_hoach" && arr[index - 1]?.group !== "ke_hoach"
                              ? { borderLeft: KE_HOACH_BORDER }
                              : {}),
                          }}
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
                        <td colSpan={SORT_COLUMNS.length + 2}>
                          {theoXaRows.length === 0 ? "Chưa có dữ liệu" : "Không tìm thấy xã/phường phù hợp"}
                        </td>
                      </tr>
                    ) : (
                      filteredRows.map((row) =>
                        row.ghi_chu ? (
                          <tr key={row.ma_xa} style={{ color: "#6b7280", fontStyle: "italic" }}>
                            <td style={{ textAlign: "left" }}>{row.ten_xa}</td>
                            <td colSpan={SORT_COLUMNS.length - 1 + 2} style={{ textAlign: "left" }}>
                              {row.ghi_chu}
                            </td>
                          </tr>
                        ) : (
                          <tr key={row.ma_xa}>
                            <td>{row.ten_xa}</td>
                            <td>{formatSo(row.gui_xuong)}</td>
                            <td>{formatSo(row.da_nhom_1_2_da_nhap)}</td>
                            <td>{formatSo(row.da_thu_thap)}</td>
                            <td>{formatSo(row.da_lam)}</td>
                            <td>{row.percent}%</td>
                            <td>{formatSo(row.con_lai)}</td>
                            <td style={{ background: KE_HOACH_BG, borderLeft: KE_HOACH_BORDER }}>
                              {formatSo(row.ke_hoach)}
                            </td>
                            <td style={{ background: KE_HOACH_BG }}>{formatSo(row.da_lam_ke_hoach)}</td>
                            <td style={{ background: KE_HOACH_BG }}>{row.percent_ke_hoach}%</td>
                            <td style={{ textAlign: "center" }}>
                              <button
                                type="button"
                                title={`Xem danh sách thửa còn thiếu của ${row.ten_xa}`}
                                onClick={() => onNavigateNhom3ChiTiet?.(row.ma_xa, row.ten_xa)}
                                style={{ border: "none", background: "transparent", cursor: "pointer", fontSize: 18, lineHeight: 1 }}
                              >
                                📋
                              </button>
                            </td>
                            <td style={{ textAlign: "center" }}>
                              <button
                                type="button"
                                title={`Tải Excel danh sách tổng gửi xã (kèm ghi chú trạng thái) của ${row.ten_xa}`}
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
