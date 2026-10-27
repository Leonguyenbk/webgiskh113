import { useEffect, useMemo, useState } from "react";

import { API_URL } from "./config/env";
import { getNhom3TongHop } from "./services/parcelService";

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

// "2026-10-24T17:25:08+07:00" -> "17:25 24/10/2026" (giờ máy người xem).
function formatCapNhatLuc(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())} ${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`;
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
// group: để gộp tiêu đề nhóm ở hàng trên (yêu cầu người dùng) — "loai4" =
// phần hệ thống tự theo dõi (tổng gửi xã nội bộ), "ke_hoach" = phần cộng
// thêm Loại 1 đã làm (VPĐK gửi song song, xem nhom3_tong_hop.tong_ke_hoach).
// Không có group (ten_xa) = cột rowSpan 2, đứng ngoài 2 nhóm.
const SORT_COLUMNS = [
  { key: "ten_xa", label: "Xã / phường", type: "text", defaultDir: "asc" },
  { key: "tong", label: "Tổng gửi xã (đã trừ Chi nhánh KV)", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "da_nhom_1_2_da_nhap", label: "Nhóm 1 đã nhập biểu (Xã làm)", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "da_nhom_1_2_chua_nhap", label: "Nhóm 1 chưa nhập biểu (Chi nhánh KV làm)", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "da_thu_thap", label: "Đã nhập đủ dữ liệu", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "da_lam", label: "Đã làm (Nhóm 1 đã nhập + đã nhập biểu)", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "percent", label: "%", type: "number", defaultDir: "asc", group: "loai4" },
  { key: "con_thieu", label: "Còn thiếu", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "chua_lien_ket_khong_gian", label: "Chưa liên kết không gian", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "tong_tru_kg", label: "Tổng gửi xã (đã trừ Chi nhánh KV + chưa liên kết KG)", type: "number", defaultDir: "desc", group: "loai4" },
  { key: "percent_tru_kg", label: "% (trừ cả chưa liên kết KG)", type: "number", defaultDir: "asc", group: "loai4" },
  { key: "tong_ke_hoach", label: "Tổng danh sách theo kế hoạch (đã gồm Loại 1 đã làm)", type: "number", defaultDir: "desc", group: "ke_hoach" },
  { key: "da_lam_ke_hoach", label: "Đã thực hiện theo kế hoạch (gồm Loại 1+2+3 đã làm)", type: "number", defaultDir: "desc", group: "ke_hoach" },
  { key: "percent_ke_hoach", label: "Tỷ lệ theo kế hoạch", type: "number", defaultDir: "asc", group: "ke_hoach" },
];

const GROUP_LABELS = {
  loai4: "Tiến độ thực hiện Loại 4",
  ke_hoach: "Tiến độ thực hiện kế hoạch",
};

// Tô nền nhạt + viền trái đậm để tách bạch 2 nhóm cột trong bảng (yêu
// cầu người dùng: dễ phân biệt số liệu "Loại 4" và số liệu "theo kế
// hoạch" khi nhìn lướt bảng).
const KE_HOACH_BG = "#eef7f0";
const KE_HOACH_BORDER = "2px solid #2e7d32";

export default function Nhom3ConThieuPage({
  onNavigateHome,
  onNavigateNhom3Dashboard,
  onNavigateNhom3ChiTiet,
}) {
  const [tongHop, setTongHop] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloadingXa, setDownloadingXa] = useState("");
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
      // Đã làm theo kế hoạch = Đã làm (Loại 4) + Loại 1 + Loại 2 + Loại 3
      // đã làm (VPĐK gửi song song, như file KhoiLuongXa-KH113 — yêu cầu
      // người dùng). Tổng kế hoạch vẫn chỉ cộng Loại 1.
      const daLamKeHoach = daLam + (row.loai_123_da_lam || 0);
      return {
        ...row,
        ten_xa: row.ten_xa || row.ma_xa,
        da_lam: daLam,
        percent: formatPercent(daLam, row.tong),
        percent_tru_kg: formatPercent(daLam, row.tong_tru_kg),
        da_lam_ke_hoach: daLamKeHoach,
        percent_ke_hoach: formatPercent(daLamKeHoach, row.tong_ke_hoach),
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
  const tyLeDaLamTruKg = formatPercent(daLam, tongHop?.tong_tru_kg || 0);
  const daLamKeHoach = daLam + (tongHop?.loai_123_da_lam || 0);
  const tyLeKeHoach = formatPercent(daLamKeHoach, tongHop?.tong_ke_hoach || 0);

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>
            Nhóm 3 — thống kê còn thiếu dữ liệu
            {tongHop?.cap_nhat_luc && (
              <span
                title="Số liệu tự làm mới mỗi 2 giờ"
                style={{ marginLeft: 10, fontSize: "0.6em", fontWeight: 500, opacity: 0.75, whiteSpace: "nowrap" }}
              >
                🕒 cập nhật lúc {formatCapNhatLuc(tongHop.cap_nhat_luc)}
              </span>
            )}
          </h1>
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
                <span>Tổng gửi xã (đã trừ Chi nhánh KV)</span>
                <strong>{formatSo(tongHop.tong)}</strong>
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
                <span>Chưa liên kết không gian</span>
                <strong style={{ color: "#6a817e" }}>{formatSo(tongHop.chua_lien_ket_khong_gian)}</strong>
              </div>
              <div className="statTile">
                <span>Tổng gửi xã (đã trừ Chi nhánh KV + chưa liên kết KG)</span>
                <strong>{formatSo(tongHop.tong_tru_kg)}</strong>
              </div>
              <div className="statTile">
                <span>Tỷ lệ đã làm (trừ cả chưa liên kết KG)</span>
                <strong style={{ color: "#2e7d32" }}>
                  {formatSo(daLam)} <span style={{ fontWeight: 400, fontSize: 14 }}>({tyLeDaLamTruKg}%)</span>
                </strong>
              </div>
              <div className="statTile">
                <span>Trong đó: Loại 1 + 2 + 3 đã làm (VPĐK gửi song song)</span>
                <strong style={{ color: "#6a817e" }}>{formatSo(tongHop.loai_123_da_lam)}</strong>
              </div>
              <div className="statTile">
                <span>Tổng danh sách theo kế hoạch (đã gồm Loại 1 đã làm)</span>
                <strong>{formatSo(tongHop.tong_ke_hoach)}</strong>
              </div>
              <div className="statTile">
                <span>Tỷ lệ theo kế hoạch</span>
                <strong style={{ color: "#2e7d32" }}>
                  {formatSo(daLamKeHoach)} <span style={{ fontWeight: 400, fontSize: 14 }}>({tyLeKeHoach}%)</span>
                </strong>
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
                <table className="statsTable nhom3TongHopTable">
                  <thead>
                    <tr>
                      <th rowSpan={2} style={{ verticalAlign: "middle" }}>
                        {SORT_COLUMNS.filter((c) => !c.group).map((column) => (
                          <span
                            key={column.key}
                            onClick={() => handleSort(column.key)}
                            style={{ cursor: "pointer", userSelect: "none" }}
                            title="Bấm để sắp xếp"
                          >
                            {column.label}
                            <span style={{ marginLeft: 4, opacity: sort.key === column.key ? 1 : 0.25 }}>
                              {sort.key === column.key ? (sort.dir === "asc" ? "▲" : "▼") : "↕"}
                            </span>
                          </span>
                        ))}
                      </th>
                      {["loai4", "ke_hoach"].map((groupKey) => (
                        <th
                          key={groupKey}
                          colSpan={SORT_COLUMNS.filter((c) => c.group === groupKey).length}
                          style={{
                            textAlign: "center",
                            ...(groupKey === "ke_hoach"
                              ? { background: KE_HOACH_BG, borderLeft: KE_HOACH_BORDER }
                              : {}),
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
                            <td>{formatSo(row.tong)}</td>
                            <td>{formatSo(row.da_nhom_1_2_da_nhap)}</td>
                            <td>{formatSo(row.da_nhom_1_2_chua_nhap)}</td>
                            <td>{formatSo(row.da_thu_thap)}</td>
                            <td>{formatSo(row.da_lam)}</td>
                            <td>{row.percent}%</td>
                            <td>{formatSo(row.con_thieu)}</td>
                            <td>{formatSo(row.chua_lien_ket_khong_gian)}</td>
                            <td>{formatSo(row.tong_tru_kg)}</td>
                            <td>{row.percent_tru_kg}%</td>
                            <td style={{ background: KE_HOACH_BG, borderLeft: KE_HOACH_BORDER }}>
                              {formatSo(row.tong_ke_hoach)}
                            </td>
                            <td style={{ background: KE_HOACH_BG }}>{formatSo(row.da_lam_ke_hoach)}</td>
                            <td style={{ background: KE_HOACH_BG }}>{row.percent_ke_hoach}%</td>
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
