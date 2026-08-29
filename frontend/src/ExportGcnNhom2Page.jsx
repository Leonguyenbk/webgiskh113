import { useEffect, useMemo, useState } from "react";

import { API_URL } from "./config/env";
import { getXaList } from "./services/parcelService";

// Trang Công cụ -> "Xuất GCN đã thu thập (Nhóm 2)". Chọn xã, tải file
// .xlsx gồm các dòng du_lieu_gcn của thửa đã có dữ liệu GCN nhưng thuộc
// Nhóm 2 (KH 2959) — backend /api/gcn-export-theo-nhom dựng file.
export default function ExportGcnNhom2Page({ onNavigateHome }) {
  const [xaList, setXaList] = useState([]);
  const [selectedMaXa, setSelectedMaXa] = useState("");
  const [xaQuery, setXaQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    getXaList()
      .then((result) => setXaList(result?.items || []))
      .catch((err) => setError(err.message));
  }, []);

  const filteredXaOptions = useMemo(() => {
    const keyword = xaQuery.trim().toLocaleLowerCase("vi");
    if (!keyword) return xaList;
    return xaList.filter(({ ma_xa, ten_xa }) =>
      `${ten_xa} ${ma_xa}`.toLocaleLowerCase("vi").includes(keyword),
    );
  }, [xaList, xaQuery]);

  const selectedTen = xaList.find((x) => x.ma_xa === selectedMaXa)?.ten_xa || "";

  const handleSelectXa = (maXa, tenXa) => {
    setSelectedMaXa(maXa);
    setXaQuery(tenXa || maXa);
    setDropdownOpen(false);
    setNotice("");
    setError("");
  };

  const handleDownload = async () => {
    if (!selectedMaXa || loading) return;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const res = await fetch(
        `${API_URL}/api/gcn-export-theo-nhom?ma_xa=${encodeURIComponent(selectedMaXa)}&nhom=${encodeURIComponent("Nhóm 2")}`,
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
      link.download = `gcn_N2_${selectedMaXa}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setNotice(`Đã tải file cho ${selectedTen || selectedMaXa}.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Xuất GCN đã thu thập — Nhóm 2</h1>
          <p>
            Tải Excel các dòng dữ liệu GCN của thửa đã có dữ liệu nhưng
            đang thuộc Nhóm 2 (KH 2959), theo xã/phường
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
        <div className="importCard" style={{ maxWidth: 560 }}>
          <label htmlFor="exportMaXa">Chọn xã / phường</label>
          <div className="comboBox">
            <input
              id="exportMaXa"
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
                  <div className="comboBoxEmpty">Không tìm thấy xã/phường</div>
                ) : (
                  filteredXaOptions.map(({ ma_xa, ten_xa }) => (
                    <div
                      key={ma_xa}
                      className={`comboBoxItem${ma_xa === selectedMaXa ? " active" : ""}`}
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

          <button
            type="button"
            className="downloadButton"
            style={{ marginTop: 14, opacity: selectedMaXa && !loading ? 1 : 0.5 }}
            disabled={!selectedMaXa || loading}
            onClick={handleDownload}
          >
            {loading ? "Đang tạo file…" : "⬇ Tải Excel"}
          </button>

          {notice && (
            <div className="notice" style={{ marginTop: 14 }}>
              <span>{notice}</span>
            </div>
          )}
          {error && (
            <div className="notice error" style={{ marginTop: 14 }}>
              <strong>Lỗi</strong>
              <span>{error}</span>
            </div>
          )}

          <p style={{ marginTop: 16, fontSize: 12, color: "#52514e" }}>
            Mỗi thửa có nhiều chủ sử dụng sẽ có nhiều dòng. File chứa toàn
            bộ cột của bảng du_lieu_gcn.
          </p>
        </div>
      </section>
    </main>
  );
}
