import { useEffect, useMemo, useState } from "react";

import { API_URL } from "./config/env";
import { getXaList } from "./services/parcelService";

// Trang Công cụ -> "Xuất Excel theo mẫu TANAN". Chọn đơn vị hành chính
// (xã/phường), tải file .xlsx đúng bố cục mẫu TANAN.xlsx gồm toàn bộ dữ
// liệu du_lieu_gcn của đơn vị đó, hoặc chỉ các thửa Nhóm 3 (chưa thuộc
// Nhóm 1/Nhóm 2 KH 2959) — backend /api/gcn-export-mau-tanan dựng file.
export default function ExportGcnMauTanAnPage({ onNavigateHome }) {
  const [xaList, setXaList] = useState([]);
  const [selectedMaXa, setSelectedMaXa] = useState("");
  const [xaQuery, setXaQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [phamVi, setPhamVi] = useState("toanbo"); // "toanbo" | "nhom3"
  const [token, setToken] = useState("");

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
        `${API_URL}/api/gcn-export-mau-tanan?ma_xa=${encodeURIComponent(selectedMaXa)}&chi_nhom3=${phamVi === "nhom3" ? "1" : "0"}`,
        { headers: token ? { "X-Import-Token": token } : {} },
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
      link.download = `mau_TANAN_${selectedMaXa}_${phamVi}.xlsx`;
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
          <h1>Xuất Excel theo mẫu TANAN</h1>
          <p>
            Tải Excel dữ liệu GCN đúng bố cục file mẫu TANAN.xlsx, theo đơn
            vị hành chính — lấy hết hoặc chỉ thửa Nhóm 3 (chưa thuộc Nhóm
            1/Nhóm 2)
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
          <label htmlFor="exportMauMaXa">Chọn đơn vị hành chính (xã/phường)</label>
          <div className="comboBox">
            <input
              id="exportMauMaXa"
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

          <label style={{ marginTop: 14, display: "block" }}>Phạm vi dữ liệu</label>
          <div style={{ display: "flex", gap: 16, marginTop: 6 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 400 }}>
              <input
                type="radio"
                name="phamVi"
                value="toanbo"
                checked={phamVi === "toanbo"}
                onChange={() => setPhamVi("toanbo")}
              />
              Tải hết
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 400 }}>
              <input
                type="radio"
                name="phamVi"
                value="nhom3"
                checked={phamVi === "nhom3"}
                onChange={() => setPhamVi("nhom3")}
              />
              Chỉ Nhóm 3 (không thuộc Nhóm 1/Nhóm 2)
            </label>
          </div>

          <label htmlFor="exportMauToken" style={{ marginTop: 14, display: "block" }}>
            Mã xác thực
          </label>
          <input
            id="exportMauToken"
            type="password"
            className="filterInput"
            autoComplete="off"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Nhập mã do quản trị viên cấp (nếu có)"
          />

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
            File giữ nguyên bố cục và tiêu đề cột của mẫu TANAN.xlsx. Mỗi
            chủ sử dụng 1 dòng, đánh lại số thứ tự từ 1.
          </p>
        </div>
      </section>
    </main>
  );
}
