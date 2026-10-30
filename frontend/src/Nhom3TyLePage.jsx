import { useEffect, useMemo, useState } from "react";

import { API_URL } from "./config/env";
import { getNhom3TyLeGuiXuong } from "./services/parcelService";

// Trang "/nhom-3-ty-le" — tỷ lệ đơn giản theo xã: số lượng gửi xuống (đã
// trừ thửa thuộc dự án), Nhóm 1 trong danh sách, đã nhập biểu trong danh
// sách, tổng 2 số và tỷ lệ so với số gửi xuống (yêu cầu người dùng). Không
// trừ chưa liên kết KG, không cộng Loại 1/2/3 như trang /nhom-3-con-thieu.

const TO_GIAM_SAT_OPTIONS = [
  { value: "1", label: "Tổ 1 — Buôn Đôn, Ea Súp, Tuy Hòa, Đông Hòa, Tuy An" },
  { value: "2", label: "Tổ 2 — Cư Kuin, Krông Ana, Krông Bông, Lắk, Phú Hòa, Tây Hòa" },
  { value: "3", label: "Tổ 3 — Buôn Ma Thuột, Buôn Hồ, Cư M'gar, Ea H'leo, Krông Búk, Krông Năng" },
  { value: "4", label: "Tổ 4 — Krông Pắc, Ea Kar, M'Drắk, Sơn Hòa, Sông Hinh, Đồng Xuân, Sông Cầu" },
];

const COLUMNS = [
  { key: "ten_xa", label: "Xã/phường", type: "text" },
  { key: "gui_xuong", label: "Số lượng gửi xuống (đã trừ dự án)", type: "number" },
  { key: "nhom_1", label: "Nhóm 1 trong danh sách", type: "number" },
  { key: "da_nhap_bieu", label: "Đã nhập biểu trong danh sách", type: "number" },
  { key: "tong", label: "Tổng Nhóm 1 và đã nhập biểu", type: "number" },
  { key: "con_lai", label: "Còn lại", type: "number" },
  { key: "ty_le", label: "Tỷ lệ so với số lượng gửi xuống (%)", type: "number" },
];

function formatSo(v) {
  return Number(v || 0).toLocaleString("vi-VN");
}

function tyLe(phan, tong) {
  return tong ? Math.round((phan / tong) * 1000) / 10 : 0;
}

function formatTyLe(v) {
  return Number(v || 0).toLocaleString("vi-VN", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function formatCapNhatLuc(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())} ${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`;
}

export default function Nhom3TyLePage({ onNavigateHome }) {
  const [toGiamSat, setToGiamSat] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState({ key: "ty_le", dir: "desc" });

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    getNhom3TyLeGuiXuong(toGiamSat ? { to_giam_sat: toGiamSat } : undefined, { signal: controller.signal })
      .then((body) => setData(body))
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [toGiamSat]);

  const rows = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const list = (data?.theo_xa || [])
      .map((r) => {
        const tong = (r.nhom_1 || 0) + (r.da_nhap_bieu || 0);
        return { ...r, tong, con_lai: (r.gui_xuong || 0) - tong, ty_le: tyLe(tong, r.gui_xuong) };
      })
      .filter((r) => !q || `${r.ten_xa || ""} ${r.ma_xa} ${r.khu_vuc || ""}`.toLowerCase().includes(q));
    const col = COLUMNS.find((c) => c.key === sort.key);
    const dir = sort.dir === "asc" ? 1 : -1;
    list.sort((a, b) =>
      col?.type === "text"
        ? dir * String(a[sort.key] || "").localeCompare(String(b[sort.key] || ""), "vi")
        : dir * ((a[sort.key] || 0) - (b[sort.key] || 0)),
    );
    return list;
  }, [data, filter, sort]);

  const tongCong = useMemo(() => {
    const gui = rows.reduce((s, r) => s + (r.gui_xuong || 0), 0);
    const n1 = rows.reduce((s, r) => s + (r.nhom_1 || 0), 0);
    const nhap = rows.reduce((s, r) => s + (r.da_nhap_bieu || 0), 0);
    return { gui, n1, nhap, tong: n1 + nhap, conLai: gui - n1 - nhap, tyLe: tyLe(n1 + nhap, gui) };
  }, [rows]);

  // Tải .xlsx danh sách còn lại của 1 xã (gồm cả thửa chưa có trên bản đồ,
  // kèm thôn) — 1 xã/lần, mỗi lượt ~1-3s.
  const [downloadingXa, setDownloadingXa] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const handleExportConLai = async (maXa) => {
    if (downloadingXa) return;
    setDownloadingXa(maXa);
    setDownloadError("");
    try {
      const res = await fetch(`${API_URL}/api/nhom3-ty-le-gui-xuong/export-con-lai?ma_xa=${encodeURIComponent(maXa)}`);
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
      link.download = `nhom3_con_lai_${maXa}.xlsx`;
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

  const handleSort = (key) =>
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: COLUMNS.find((c) => c.key === key)?.type === "text" ? "asc" : "desc" },
    );

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>
            Nhóm 3 — tỷ lệ so với số lượng gửi xuống
            {data?.cap_nhat_luc && (
              <span
                title="Số liệu tự làm mới mỗi 2 giờ"
                style={{ marginLeft: 10, fontSize: "0.6em", fontWeight: 500, opacity: 0.75, whiteSpace: "nowrap" }}
              >
                🕒 cập nhật lúc {formatCapNhatLuc(data.cap_nhat_luc)}
              </span>
            )}
          </h1>
          <p>
            Số lượng gửi xuống đã trừ thửa thuộc dự án; tỷ lệ = (Nhóm 1 + đã nhập biểu trong danh sách) / số lượng gửi
            xuống.
          </p>
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
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
          <label htmlFor="nhom3TyLeTo" style={{ fontWeight: 600 }}>
            Tổ kiểm tra, giám sát:
          </label>
          <select
            id="nhom3TyLeTo"
            className="filterInput"
            style={{ maxWidth: 440 }}
            value={toGiamSat}
            onChange={(event) => setToGiamSat(event.target.value)}
          >
            <option value="">— Tất cả —</option>
            {TO_GIAM_SAT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            type="text"
            className="filterInput"
            autoComplete="off"
            value={filter}
            placeholder="Lọc theo tên hoặc mã xã/phường…"
            style={{ maxWidth: 320 }}
            onChange={(event) => setFilter(event.target.value)}
          />
        </div>

        {loading && <div className="notice">Đang tải số liệu…</div>}
        {error && (
          <div className="notice error">
            <strong>Không tải được số liệu</strong>
            <span>{error}</span>
          </div>
        )}

        {downloadError && (
          <div className="notice error" style={{ marginBottom: 10 }}>
            <strong>Không tải được file</strong>
            <span>{downloadError}</span>
          </div>
        )}

        {!loading && !error && (
          <div className="statsTableWrap">
            <table className="statsTable">
              <thead>
                <tr>
                  <th>STT</th>
                  {COLUMNS.map((column) => (
                    <th
                      key={column.key}
                      onClick={() => handleSort(column.key)}
                      style={{ cursor: "pointer", userSelect: "none", whiteSpace: "normal", maxWidth: 140 }}
                      title="Bấm để sắp xếp"
                    >
                      {column.label}
                      <span style={{ marginLeft: 4, opacity: sort.key === column.key ? 1 : 0.25 }}>
                        {sort.key === column.key ? (sort.dir === "asc" ? "▲" : "▼") : "↕"}
                      </span>
                    </th>
                  ))}
                  <th style={{ whiteSpace: "normal", maxWidth: 110 }}>Xuất DS còn lại</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.ma_xa}>
                    <td>{i + 1}</td>
                    <td>{r.ten_xa || r.ma_xa}</td>
                    <td>{formatSo(r.gui_xuong)}</td>
                    <td>{formatSo(r.nhom_1)}</td>
                    <td>{formatSo(r.da_nhap_bieu)}</td>
                    <td>{formatSo(r.tong)}</td>
                    <td>{formatSo(r.con_lai)}</td>
                    <td>
                      <strong>{formatTyLe(r.ty_le)}%</strong>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <button
                        type="button"
                        className="downloadButton"
                        disabled={!!downloadingXa || !r.con_lai}
                        onClick={() => handleExportConLai(r.ma_xa)}
                        title={`Tải Excel ${formatSo(r.con_lai)} thửa còn lại`}
                      >
                        {downloadingXa === r.ma_xa ? "Đang tải…" : "⬇ Excel"}
                      </button>
                    </td>
                  </tr>
                ))}
                {!rows.length && (
                  <tr>
                    <td colSpan={COLUMNS.length + 2}>Không có xã/phường nào.</td>
                  </tr>
                )}
              </tbody>
              {rows.length > 0 && (
                <tfoot>
                  <tr style={{ fontWeight: 700 }}>
                    <td colSpan={2}>Tổng cộng ({rows.length} xã/phường)</td>
                    <td>{formatSo(tongCong.gui)}</td>
                    <td>{formatSo(tongCong.n1)}</td>
                    <td>{formatSo(tongCong.nhap)}</td>
                    <td>{formatSo(tongCong.tong)}</td>
                    <td>{formatSo(tongCong.conLai)}</td>
                    <td>{formatTyLe(tongCong.tyLe)}%</td>
                    <td />
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
